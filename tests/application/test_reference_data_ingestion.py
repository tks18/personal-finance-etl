# pyright: reportPrivateUsage=false
"""Verification suite for Reference Evidence Ingestion and Source-Agnostic Bindings.

Owns
----
- Multi-dataset vertical slice ingestion across all 5 reference evidence datasets:
  (INVESTMENT_MF_ISIN_MAPPING, INVESTMENT_BENCHMARK_MAPPING, INVESTMENT_BENCHMARK_MASTER,
  INVESTMENT_MACRO_PARAMETERS, MARKET_CURRENCY_MAPPING).
- Natural grain preservation without unwanted synthetic UID columns on reference tables.
- Pandera schema validation enforcement (Gate 1 & Gate 2) and error rejection.
- Natural key collision rejection on duplicate records.
- Idempotent rerun verification ensuring zero redundant row appends.
- Downstream transformation and provider symbol registry construction from Bronze tables.

Does not own
------------
- Single-slice generalized ingestion mechanics (owned by test_generalized_vertical_slice.py).
- Household SQLite evidence family ingestion (owned by test_household_family_migration.py).
- Downstream FIFO and Tax calculations (owned by test_tax_domain.py).
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import polars as pl
import pytest
from pandera.errors import SchemaError, SchemaErrors

from personal_finance_etl.application.ingestion.admission import AdmissionService
from personal_finance_etl.application.ingestion.identity import (
    IdentityCollisionError,
)
from personal_finance_etl.application.ingestion.slice_runner import (
    DatasetIngestionService,
)
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import (
    SourcePlanner,
)
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.loader import (
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.validation import ValidationError
from personal_finance_etl.domain.household.transforms.reference_dimensions import (
    transform_d_currency,
    transform_d_investment_benchmark_master,
    transform_d_macro_parameters,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import (
    get_global_emitter,
)
from personal_finance_etl.infrastructure.providers.market.symbol_mapping import (
    build_provider_symbol_registry,
)
from personal_finance_etl.infrastructure.validation import (
    PanderaDataFrameValidator,
)
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_bronze_contract_by_dataset_id,
    get_pre_bronze_contract_by_dataset_id,
)

REFERENCE_DATASETS: tuple[DatasetId, ...] = (
    DatasetId.INVESTMENT_MF_ISIN_MAPPING,
    DatasetId.INVESTMENT_BENCHMARK_MAPPING,
    DatasetId.INVESTMENT_BENCHMARK_MASTER,
    DatasetId.INVESTMENT_MACRO_PARAMETERS,
    DatasetId.MARKET_CURRENCY_MAPPING,
)


def _create_reference_csv_fixtures(inputs_dir: Path) -> dict[str, str]:
    """Copy canonical static test CSV files for all 5 reference evidence datasets.

    Parameters
    ----------
    inputs_dir : Path
        Directory where CSV files should be written.

    Returns
    -------
    dict[str, str]
        Mapping from sync_category to normalized file path.
    """
    inputs_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = Path(__file__).resolve().parent.parent / "fixtures" / "evidence" / "reference"

    mapping = {
        "mf_isin": "MF_ISIN_MAPPING.csv",
        "benchmark_mapping": "BENCHMARK_MAPPING.csv",
        "benchmark_master": "BENCHMARK_MASTER.csv",
        "macro_parameters": "MACRO_PARAMETERS.csv",
        "currency_mapping": "CURRENCY_MAPPING.csv",
    }
    result: dict[str, str] = {}
    for cat, filename in mapping.items():
        src = evidence_dir / filename
        dest = inputs_dir / filename
        shutil.copy2(src, dest)
        result[cat] = str(dest).replace("\\", "/")

    return result


@pytest.fixture(autouse=True)
def _auto_open_control_plane(isolated_control_plane: ControlPlane) -> Iterator[None]:
    """Ensure isolated ControlPlane connection is open and schema initialized.

    Parameters
    ----------
    isolated_control_plane : ControlPlane
        Isolated test SQLite Control Plane fixture.
    """
    isolated_control_plane.open()
    isolated_control_plane.ensure_schema()
    yield
    isolated_control_plane.close()


def test_reference_evidence_end_to_end_vertical_slice_admission(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Ingest all 5 reference evidence datasets through generalized vertical slice.

    Parameters
    ----------
    isolated_settings : Settings
        Isolated test settings.
    isolated_duckdb_manager : DuckDBManager
        Isolated test DuckDB connection manager.
    isolated_control_plane : ControlPlane
        Isolated test SQLite Control Plane facade.
    rules : FinancialRules
        Isolated financial rules fixture.
    tmp_path : Path
        Isolated temporary directory path.
    """
    csv_paths = _create_reference_csv_fixtures(tmp_path / "inputs")
    actionable = {cat: [path] for cat, path in csv_paths.items()}
    isolated_control_plane.artifacts.ingest_binaries(actionable)

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    emitter = get_global_emitter()
    validator = PanderaDataFrameValidator(emitter=emitter)
    admission = AdmissionService()
    ingestion_service = DatasetIngestionService(validator, admission, emitter)

    pre_bronze = PreBronzeLayer(isolated_duckdb_manager, emitter=emitter)
    meta = MetaLayer(isolated_duckdb_manager, isolated_settings, rules)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta, emitter=emitter)

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()

    # 1. Ingest all 5 reference datasets through generalized vertical slice
    for ds_id in REFERENCE_DATASETS:
        ds_plan = source_plan.get_dataset_plan(ds_id)
        assert ds_plan is not None
        success = ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files=actionable,
            run_id="run_ref_001",
        )
        assert success is True

    # 2. Verify all 5 Pre-Bronze tables created and link to respective artifact_id
    for ds_id in REFERENCE_DATASETS:
        pb_contract = get_pre_bronze_contract_by_dataset_id(ds_id)
        assert pb_contract is not None
        assert pre_bronze.table_exists(pb_contract)
        pb_df = isolated_duckdb_manager.conn.query(
            f"SELECT * FROM {pb_contract.physical_table}"
        ).pl()
        assert pb_df.height >= 2
        assert "artifact_id" in pb_df.columns

    # 3. Verify all 5 Bronze tables created with preserved natural grains (no unwanted synthetic UID)
    b_mf = isolated_duckdb_manager.conn.query(
        "SELECT * FROM bronze.investment_mf_isin_mapping"
    ).pl()
    assert b_mf.height == 2
    assert "INSTRUMENT_NAME" in b_mf.columns
    assert "ISIN" in b_mf.columns
    assert "UID" not in b_mf.columns
    assert set(b_mf["ISIN"]) == {"INF879O01019", "INF769K01018"}

    b_bmap = isolated_duckdb_manager.conn.query(
        "SELECT * FROM bronze.investment_benchmark_mapping"
    ).pl()
    assert b_bmap.height == 5
    assert "ISIN" in b_bmap.columns
    assert "Benchmark_ID" in b_bmap.columns
    assert "UID" not in b_bmap.columns
    assert "NIFTY50" in set(b_bmap["Benchmark_ID"])

    b_bmst = isolated_duckdb_manager.conn.query(
        "SELECT * FROM bronze.investment_benchmark_master"
    ).pl()
    assert b_bmst.height == 2
    assert "ID" in b_bmst.columns
    assert "Benchmark_Name" in b_bmst.columns
    assert "UID" not in b_bmst.columns
    assert set(b_bmst["ID"]) == {"NIFTY50", "SENSEX"}

    b_macro = isolated_duckdb_manager.conn.query(
        "SELECT * FROM bronze.investment_macro_parameters"
    ).pl()
    assert b_macro.height == 2
    assert "FY" in b_macro.columns
    assert "UID" not in b_macro.columns
    assert set(b_macro["FY"]) == {"2023-24", "2024-25"}

    b_curr = isolated_duckdb_manager.conn.query("SELECT * FROM bronze.market_currency_mapping").pl()
    assert b_curr.height == 2
    assert "UID" in b_curr.columns
    assert "Currency_Code" in b_curr.columns
    assert set(b_curr["UID"]) == {"USD_INR", "EUR_INR"}


def test_reference_evidence_gate1_pandera_schema_validation_rejection(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify that corrupt CSV evidence fails Gate 1 Pandera validation and aborts before write.

    Parameters
    ----------
    isolated_settings : Settings
        Isolated test settings.
    isolated_duckdb_manager : DuckDBManager
        Isolated test DuckDB connection manager.
    isolated_control_plane : ControlPlane
        Isolated test SQLite Control Plane facade.
    rules : FinancialRules
        Isolated financial rules fixture.
    tmp_path : Path
        Isolated temporary directory path.
    """
    inputs_dir = tmp_path / "inputs_corrupt"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    # Write a macro parameters CSV missing the required FY_End_Date column
    corrupt_macro_path = inputs_dir / "MACRO_PARAMETERS.csv"
    corrupt_macro_path.write_text(
        "FY,FY_Start_Date,Debt_MF_Cutoff_Date,Inflation_Rate\n2023-24,2023-04-01,2023-03-31,0.06\n",
        encoding="utf-8",
    )
    norm_path = str(corrupt_macro_path).replace("\\", "/")
    actionable = {"macro_parameters": [norm_path]}
    isolated_control_plane.artifacts.ingest_binaries(actionable)

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    emitter = get_global_emitter()
    validator = PanderaDataFrameValidator(emitter=emitter)
    admission = AdmissionService()
    ingestion_service = DatasetIngestionService(validator, admission, emitter)

    pre_bronze = PreBronzeLayer(isolated_duckdb_manager, emitter=emitter)
    meta = MetaLayer(isolated_duckdb_manager, isolated_settings, rules)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta, emitter=emitter)

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()
    ds_plan = source_plan.get_dataset_plan(DatasetId.INVESTMENT_MACRO_PARAMETERS)
    assert ds_plan is not None

    with pytest.raises((ValidationError, SchemaError, SchemaErrors)):
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files=actionable,
            run_id="run_corrupt_test",
        )

    # Assert bronze table was not populated
    b_contract = get_bronze_contract_by_dataset_id(DatasetId.INVESTMENT_MACRO_PARAMETERS)
    assert b_contract is not None
    row_count = isolated_duckdb_manager.conn.execute(
        f"SELECT count(*) FROM {b_contract.physical_table}"
    ).fetchone()
    assert row_count is not None
    assert row_count[0] == 0


def test_reference_evidence_natural_grain_collision_rejection(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify duplicate natural key entries trigger collision rejection and abort.

    Parameters
    ----------
    isolated_settings : Settings
        Isolated test settings.
    isolated_duckdb_manager : DuckDBManager
        Isolated test DuckDB connection manager.
    isolated_control_plane : ControlPlane
        Isolated test SQLite Control Plane facade.
    rules : FinancialRules
        Isolated financial rules fixture.
    tmp_path : Path
        Isolated temporary directory path.
    """
    inputs_dir = tmp_path / "inputs_duplicate"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    # Write an MF ISIN CSV with duplicate INSTRUMENT_NAME
    dup_mf_path = inputs_dir / "MF_ISIN_MAPPING.csv"
    dup_mf_path.write_text(
        "INSTRUMENT_NAME,ISIN\n"
        "Parag Parikh Flexi Cap Fund - Direct Plan - Growth,INF879O01019\n"
        "Parag Parikh Flexi Cap Fund - Direct Plan - Growth,INF879O01020\n",
        encoding="utf-8",
    )
    norm_path = str(dup_mf_path).replace("\\", "/")
    actionable = {"mf_isin": [norm_path]}
    isolated_control_plane.artifacts.ingest_binaries(actionable)

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    emitter = get_global_emitter()
    validator = PanderaDataFrameValidator(emitter=emitter)
    admission = AdmissionService()
    ingestion_service = DatasetIngestionService(validator, admission, emitter)

    pre_bronze = PreBronzeLayer(isolated_duckdb_manager, emitter=emitter)
    meta = MetaLayer(isolated_duckdb_manager, isolated_settings, rules)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta, emitter=emitter)

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()
    ds_plan = source_plan.get_dataset_plan(DatasetId.INVESTMENT_MF_ISIN_MAPPING)
    assert ds_plan is not None

    with pytest.raises((IdentityCollisionError, ValidationError, SchemaError, SchemaErrors)):
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files=actionable,
            run_id="run_collision_test",
        )


def test_reference_evidence_idempotent_rerun(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify unchanged reference files yield zero redundant writes on consecutive runs.

    Parameters
    ----------
    isolated_settings : Settings
        Isolated test settings.
    isolated_duckdb_manager : DuckDBManager
        Isolated test DuckDB connection manager.
    isolated_control_plane : ControlPlane
        Isolated test SQLite Control Plane facade.
    rules : FinancialRules
        Isolated financial rules fixture.
    tmp_path : Path
        Isolated temporary directory path.
    """
    csv_paths = _create_reference_csv_fixtures(tmp_path / "inputs_idempotent")
    actionable = {cat: [path] for cat, path in csv_paths.items()}
    isolated_control_plane.artifacts.ingest_binaries(actionable)

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    emitter = get_global_emitter()
    validator = PanderaDataFrameValidator(emitter=emitter)
    admission = AdmissionService()
    ingestion_service = DatasetIngestionService(validator, admission, emitter)

    pre_bronze = PreBronzeLayer(isolated_duckdb_manager, emitter=emitter)
    meta = MetaLayer(isolated_duckdb_manager, isolated_settings, rules)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta, emitter=emitter)

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()

    # Initial ingestion
    for ds_id in REFERENCE_DATASETS:
        ds_plan = source_plan.get_dataset_plan(ds_id)
        assert ds_plan is not None
        success = ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files=actionable,
            run_id="run_idem_001",
        )
        assert success is True

    # Capture initial Bronze row counts
    initial_counts: dict[DatasetId, int] = {}
    for ds_id in REFERENCE_DATASETS:
        b_contract = get_bronze_contract_by_dataset_id(ds_id)
        assert b_contract is not None
        df = isolated_duckdb_manager.conn.query(f"SELECT * FROM {b_contract.physical_table}").pl()
        initial_counts[ds_id] = df.height

    # Re-ingest with identical inputs (simulating rerun)
    for ds_id in REFERENCE_DATASETS:
        ds_plan = source_plan.get_dataset_plan(ds_id)
        assert ds_plan is not None
        success = ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files=actionable,
            run_id="run_idem_002",
        )
        assert success is True

    # Assert row counts remain identical (0 duplicate/redundant appends)
    for ds_id in REFERENCE_DATASETS:
        b_contract = get_bronze_contract_by_dataset_id(ds_id)
        assert b_contract is not None
        df = isolated_duckdb_manager.conn.query(f"SELECT * FROM {b_contract.physical_table}").pl()
        assert df.height == initial_counts[ds_id]


def test_reference_evidence_downstream_transformation_parity(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify downstream transformation parity and provider symbol registry construction.

    Parameters
    ----------
    isolated_settings : Settings
        Isolated test settings.
    isolated_duckdb_manager : DuckDBManager
        Isolated test DuckDB connection manager.
    isolated_control_plane : ControlPlane
        Isolated test SQLite Control Plane facade.
    rules : FinancialRules
        Isolated financial rules fixture.
    tmp_path : Path
        Isolated temporary directory path.
    """
    csv_paths = _create_reference_csv_fixtures(tmp_path / "inputs_downstream")
    actionable = {cat: [path] for cat, path in csv_paths.items()}
    isolated_control_plane.artifacts.ingest_binaries(actionable)

    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()

    emitter = get_global_emitter()
    validator = PanderaDataFrameValidator(emitter=emitter)
    admission = AdmissionService()
    ingestion_service = DatasetIngestionService(validator, admission, emitter)

    pre_bronze = PreBronzeLayer(isolated_duckdb_manager, emitter=emitter)
    meta = MetaLayer(isolated_duckdb_manager, isolated_settings, rules)
    bronze = BronzeLayer(isolated_duckdb_manager, isolated_control_plane, meta, emitter=emitter)

    source_config = get_shan_baseline_source_configuration()
    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()

    for ds_id in REFERENCE_DATASETS:
        ds_plan = source_plan.get_dataset_plan(ds_id)
        assert ds_plan is not None
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files=actionable,
            run_id="run_downstream_001",
        )

    # 1. Build and verify ProviderSymbolRegistry
    curr_df = isolated_duckdb_manager.conn.query(
        "SELECT * FROM bronze.market_currency_mapping"
    ).pl()
    bmst_df = isolated_duckdb_manager.conn.query(
        "SELECT * FROM bronze.investment_benchmark_master"
    ).pl()
    bmap_df = isolated_duckdb_manager.conn.query(
        "SELECT * FROM bronze.investment_benchmark_mapping"
    ).pl()

    registry = build_provider_symbol_registry(
        currency_mapping=curr_df,
        benchmark_master=bmst_df,
        benchmark_mapping=bmap_df,
    )

    # Verify provider symbol lookup
    assert registry.get_symbol("USD_INR") == "USDINR=X"
    assert registry.get_symbol("NIFTY50") == "^NSEI"
    assert registry.get_symbol("INF879O01019") == "^NSEI"

    # 2. Transform Macro Parameters dimension
    macro_lf = (
        isolated_duckdb_manager.conn.query("SELECT * FROM bronze.investment_macro_parameters")
        .pl()
        .lazy()
    )
    d_macro = transform_d_macro_parameters(macro_lf).collect()
    assert d_macro.height == 2
    assert "FY" in d_macro.columns
    assert "Equity_Listed_LTCG" in d_macro.columns
    assert set(d_macro["FY"]) == {"2023-24", "2024-25"}

    # 3. Transform Benchmark Master dimension
    bmst_lf = bmst_df.lazy()
    d_bmst = transform_d_investment_benchmark_master(bmst_lf).collect()
    assert d_bmst.height == 2
    assert set(d_bmst["ID"]) == {"NIFTY50", "SENSEX"}
    assert "Benchmark_Name" in d_bmst.columns

    # 4. Transform Currency dimension with joined mapping
    mock_household_currency = pl.LazyFrame(
        {
            "ID": [1, 2],
            "uid": ["USD_INR", "EUR_INR"],
            "NAME": ["US Dollar", "Euro"],
            "ISO": ["USD", "EUR"],
            "SYMBOL": ["$", "€"],
            "IS_DEL": [0, 0],
            "artifact_id": ["art_curr", "art_curr"],
        }
    )
    col_map = {
        "uid": "UID",
        "NAME": "CURRENCY_NAME",
        "ISO": "ISO",
        "SYMBOL": "SYMBOL",
        "IS_DEL": "IS_DEL",
        "artifact_id": "artifact_id",
    }
    d_curr = transform_d_currency(
        mock_household_currency,
        column_mapping=col_map,
        mapping_lazy=curr_df.lazy(),
    ).collect()
    assert d_curr.height == 2
    assert "Target_Currency_Code" in d_curr.columns
    assert "Is_Active" in d_curr.columns
    assert set(d_curr["Target_Currency_Code"]) == {"INR"}
    assert d_curr["Is_Active"].to_list() == [True, True]
