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
from pathlib import Path

import duckdb
import polars as pl
import pytest

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts import (
    EngineStage,
    EventCode,
    ObservabilityContext,
    ObservabilityEvent,
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
