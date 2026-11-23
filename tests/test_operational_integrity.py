"""Operational integrity, observability forensics, database snapshots, and architectural safeguards.

Owns
----
- JSONL forensic sink emission and Polars ndjson queryability.
- Lifecycle event sequencing and Control Plane run record durability.
- Database backup snapshot creation and restore round-trip telemetry.
- Configuration and financial rules fingerprint tracking.
- Architectural boundary enforcement and zero inline/deferred import certification.
"""

from __future__ import annotations

import ast
import sqlite3
from datetime import date
from pathlib import Path

import duckdb
import polars as pl
import pytest
from pydantic import ValidationError

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.financial_rules.tax import TaxAssumptions
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts import (
    EngineStage,
    EventCode,
    ObservabilityContext,
    ObservabilityEvent,
)
from personal_finance_etl.domain.household.transforms.income_dimensions import (
    transform_d_income_subcategory,
)
from personal_finance_etl.domain.household.transforms.transactions import (
    transform_f_transfer_transactions,
)
from personal_finance_etl.domain.investments.reconciliation.engine import (
    ReconciliationEngine,
)
from personal_finance_etl.infrastructure.observability import JsonlForensicSink
from personal_finance_etl.infrastructure.observability.redaction import (
    fingerprint_config,
    fingerprint_rules,
)

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "personal_finance_etl"

FORBIDDEN_IMPORTS = {
    "contracts": [
        "personal_finance_etl.domain",
        "personal_finance_etl.application",
        "personal_finance_etl.infrastructure",
        "personal_finance_etl.presentation",
    ],
    "config": [
        "personal_finance_etl.application",
        "personal_finance_etl.infrastructure",
        "personal_finance_etl.presentation",
        "personal_finance_etl.domain",
    ],
    "domain": [
        "personal_finance_etl.application",
        "personal_finance_etl.infrastructure",
        "personal_finance_etl.presentation",
        "duckdb",
        "sqlite3",
    ],
    "presentation": [
        "personal_finance_etl.domain.investments.lots.fifo",
        "personal_finance_etl.infrastructure.warehouse.connection",
        "personal_finance_etl.infrastructure.control_plane.connection",
    ],
}


def test_jsonl_forensics_and_polars_queryability(tmp_path: Path) -> None:
    """Verify JsonlForensicSink produces valid append-only NDJSON readable by Polars."""
    log_file = tmp_path / "test_run.jsonl"
    sink = JsonlForensicSink(log_file)

    ctx = ObservabilityContext(
        run_id="run-operational-001",
        stage=EngineStage.TRANSFORMING,
        component="LedgerBuilder",
        rows=150,
        duration_ms=42.0,
    )
    ev_start = ObservabilityEvent.create(
        event_code=EventCode.RUN_START,
        message="Starting run",
        context=ctx,
    )
    ev_done = ObservabilityEvent.create(
        event_code=EventCode.RUN_COMPLETED,
        message="Finished run",
        context=ctx,
    )
    sink.emit(ev_start)
    sink.emit(ev_done)
    sink.close()

    assert log_file.exists()
    df = pl.read_ndjson(log_file)
    assert df.height == 2
    assert "event_code" in df.columns
    assert "context" in df.columns

    unnested = df.unnest("context")
    assert unnested["run_id"][0] == "run-operational-001"
    assert unnested["rows"][0] == 150


def test_snapshot_and_restore_round_trip(
    isolated_config: tuple[Settings, Path], tmp_path: Path
) -> None:
    """Verify coordinated database snapshot and restore cycle."""
    cfg, cfg_path = isolated_config
    engine = PersonalFinanceEngine()

    # Create valid database files in target_db_base_path
    base_dir = Path(cfg.database.target_db_base_path)
    base_dir.mkdir(parents=True, exist_ok=True)
    duckdb_file = base_dir / cfg.database.target_db_name
    sqlite_file = base_dir / cfg.database.raw_document_store_name

    conn_d = duckdb.connect(str(duckdb_file))
    conn_d.execute("CREATE TABLE test_table (id INT); INSERT INTO test_table VALUES (42);")
    conn_d.close()

    conn_s = sqlite3.connect(str(sqlite_file))
    conn_s.executescript("CREATE TABLE test_table (id INT); INSERT INTO test_table VALUES (42);")
    conn_s.close()

    # 1. Snapshot
    snap_res = engine.snapshot_database_detailed(str(cfg_path))
    assert snap_res.is_success is True
    assert snap_res.zip_path is not None
    assert Path(snap_res.zip_path).exists()

    # Mutate database
    conn_m = duckdb.connect(str(duckdb_file))
    conn_m.execute("DROP TABLE test_table;")
    conn_m.close()

    # 2. Restore
    restore_res = engine.restore_database_detailed(str(cfg_path), snap_res.zip_path)
    assert restore_res.is_success is True

    # Verify restoration restored original contents
    conn_v = duckdb.connect(str(duckdb_file))
    row = conn_v.execute("SELECT id FROM test_table").fetchone()
    conn_v.close()
    assert row == (42,)


def test_configuration_fingerprint_sensitivity(
    test_config_path: Path, test_rules_path: Path
) -> None:
    """Verify SHA-256 configuration fingerprints mutate upon field changes."""
    cfg1 = Settings.from_toml(str(test_config_path))
    hash1 = fingerprint_config(cfg1)["config_hash"]

    cfg2 = Settings.from_toml(str(test_config_path))
    cfg2.observability.retain_last_n_runs = 99
    hash2 = fingerprint_config(cfg2)["config_hash"]

    assert hash1 != hash2, "Material settings change must alter hash fingerprint"
    assert hash1.startswith("sha256_")

    rules1 = FinancialRules.from_toml(str(test_rules_path))
    r_hash1 = fingerprint_rules(rules1)["rules_hash"]

    rules2 = FinancialRules.from_toml(str(test_rules_path))
    rules2.assumptions.fire.swr_multiplier = 33.0
    r_hash2 = fingerprint_rules(rules2)["rules_hash"]

    assert r_hash1 != r_hash2, "Material financial rules change must alter hash fingerprint"
    assert r_hash1.startswith("sha256_")


def test_architectural_boundary_enforcement() -> None:
    """Assert strict architectural layer boundaries across src/personal_finance_etl."""
    violations: list[str] = []

    for layer, forbidden_prefixes in FORBIDDEN_IMPORTS.items():
        layer_dir = SRC_ROOT / layer
        if not layer_dir.is_dir():
            continue

        for py_file in layer_dir.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except Exception as e:
                pytest.fail(f"Could not parse {py_file}: {e}")

            for node in ast.walk(tree):
                mod_name: str | None = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod_name = alias.name
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mod_name = node.module

                if mod_name:
                    for forbidden in forbidden_prefixes:
                        if mod_name == forbidden or mod_name.startswith(forbidden + "."):
                            lineno = getattr(node, "lineno", 0)
                            violations.append(
                                f"{py_file.relative_to(SRC_ROOT)}:{lineno} imports '{mod_name}' "
                                f"(prohibited prefix '{forbidden}' in layer '{layer}')"
                            )

    assert not violations, "Architectural boundary violations found:\n" + "\n".join(violations)


def test_zero_inline_or_deferred_imports_across_src() -> None:
    """Assert zero inline or deferred import statements inside function/method bodies across src/."""
    violations: list[str] = []

    for py_file in SRC_ROOT.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for child in ast.walk(node):
                    if isinstance(child, (ast.Import, ast.ImportFrom)):
                        violations.append(f"{py_file.relative_to(SRC_ROOT)}:{child.lineno}")

    assert not violations, "Found inline/deferred imports inside functions:\n" + "\n".join(
        violations
    )


def test_parameter_relocation_sensitivity(mock_rules: FinancialRules) -> None:
    """Verify that relocated domain and settings configuration parameters dynamically alter engine behavior."""
    # 1. Cost basis tolerance sensitivity
    assert not ReconciliationEngine.should_reconcile_basis(
        broker_buy_val=1000.05,
        reconstructed_avg=100.0,
        current_units=10.0,
        cost_basis_tolerance=0.01,
    )
    assert ReconciliationEngine.should_reconcile_basis(
        broker_buy_val=1000.05,
        reconstructed_avg=100.0,
        current_units=10.0,
        cost_basis_tolerance=0.001,
    )

    # 2. Dynamic allowance grouping policy sensitivity
    custom_rules = mock_rules.model_copy(deep=True)
    custom_rules.income.grouping.salary_category_name = "CustomSalary"
    custom_rules.income.grouping.allowance_name_pattern = "stipend"
    custom_rules.income.grouping.allowance_group_name = "CustomStipends"

    df_lazy_in = pl.LazyFrame(
        {
            "UID": ["U1", "U2"],
            "CATEGORY_NAME": ["Monthly Stipend", "Basic Pay"],
            "CATEGORY_ID": ["CAT1", "CAT1"],
            "IS_DEL": ["0", "0"],
            "TYPE": [0, 0],
        }
    )
    col_mapping = {
        "UID": "UID",
        "CATEGORY_NAME": "CATEGORY_NAME",
        "CATEGORY_ID": "CATEGORY_ID",
        "IS_DEL": "IS_DEL",
        "TYPE": "TYPE",
    }
    df_cat_lazy = pl.LazyFrame({"UID": ["CAT1"], "CATEGORY_NAME_SHORT": ["CustomSalary"]})

    res = transform_d_income_subcategory(
        df_lazy_in, col_mapping, df_cat_lazy, rules=custom_rules
    ).collect()
    row_stipend = res.filter(pl.col("UID") == "U1").to_dicts()[0]
    row_basic = res.filter(pl.col("UID") == "U2").to_dicts()[0]
    assert row_stipend["CATEGORY_GROUPS"] == "CustomStipends"
    assert row_basic["CATEGORY_GROUPS"] == "Basic Pay"

    # 3. Transfer analysis timing offset sensitivity
    custom_rules.assets.cashflow.investing_analysis_offset_months = -3
    trans_data: dict[str, list[object]] = {
        "UID": ["T1"],
        "DATE": ["2024-06-15"],
        "TIME": ["12:00:00"],
        "DESCRIPTION": ["Transfer to MF"],
        "PAID": ["Paid"],
        "TRANSACTION_TYPE": [3],
        "BASE_AMOUNT": [50000.0],
        "AMOUNT_ACCOUNT": [50000.0],
        "LOCAL_AMOUNT": [50000.0],
        "EXCH_RATE": [1.0],
        "ASSET_ID": ["A1"],
        "CATEGORY_ID": ["C1"],
        "TO_ASSET_ID": ["A2"],
        "TRANSFER_UID": ["TR1"],
        "CURRENCY_ID": ["INR_INR"],
    }
    base_trans_lazy = pl.LazyFrame(trans_data)
    df_asset_sub = pl.LazyFrame(
        {
            "UID": ["A1"],
            "ASSET_GROUP_ID": ["G1"],
            "cashflow_activity_type": ["INVESTING"],
        }
    )
    df_asset_cat = pl.LazyFrame({"UID": ["G1"], "ASSET_GROUP": ["Investments"]})
    res_transfer = transform_f_transfer_transactions(
        base_trans_lazy, df_asset_sub, df_asset_cat, rules=custom_rules
    ).collect()
    assert res_transfer["ADJUSTED_DATE_FOR_ANALYSIS"][0] == date(2024, 3, 15)

    # 4. TaxAssumptions ladder validation
    TaxAssumptions(
        debt_mf_cutoff_date="2023-04-01",
        harvest_wait_days_threshold=90,
        fallback_equity_ltcg_exemption=125000.0,
        ltcg_threshold_months={"default": 24},
        ltcg_maturity_ladder_days=[15, 45, 90, 180],
    )

    with pytest.raises(ValidationError):
        TaxAssumptions(
            debt_mf_cutoff_date="2023-04-01",
            harvest_wait_days_threshold=90,
            fallback_equity_ltcg_exemption=125000.0,
            ltcg_threshold_months={"default": 24},
            ltcg_maturity_ladder_days=[15, 90, 45, 180],
        )

    with pytest.raises(ValidationError):
        TaxAssumptions(
            debt_mf_cutoff_date="2023-04-01",
            harvest_wait_days_threshold=90,
            fallback_equity_ltcg_exemption=125000.0,
            ltcg_threshold_months={"default": 24},
            ltcg_maturity_ladder_days=[15, 45, 90],
        )
