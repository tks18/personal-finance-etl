# pyright: reportPrivateUsage=false
"""Verification suite for Mutual-Fund Evidence Ingestion and Lakehouse Integration.

Owns
----
- Multi-dataset vertical slice ingestion across mutual fund evidence datasets:
  (MARKET_MF_HOLDINGS, INVESTMENT_MF_ORDERS).
- Verification of zero artificial Bronze row UIDs (IdentityRequirement.NONE invariant).
- Pre-Bronze operational provenance tracking (__artifact_id__, __source_id__, __dataset_id__).
- Pandera schema validation enforcement (Gate 1 & Gate 2) and error rejection.
- Idempotent rerun verification ensuring zero redundant row appends on unchanged files.
- Downstream MutualFundStrategy parity and deterministic PURCHASE / SALE identity generation.

Does not own
------------
- Single-slice generalized ingestion mechanics (owned by test_generalized_vertical_slice.py).
- Reference evidence ingestion (owned by test_reference_evidence_migration.py).
- Downstream FIFO and Tax calculations (owned by test_tax_domain.py).
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import polars as pl
import pytest
from pandera.errors import SchemaError, SchemaErrors

from personal_finance_etl.application.ingestion.admission import AdmissionService
from personal_finance_etl.application.ingestion.asset_strategies import (
    MutualFundPipeline,
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
from personal_finance_etl.contracts.dataset_collection import DatasetCollection
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.validation import ValidationError
from personal_finance_etl.domain.investments.transforms.common import (
    get_f_tf_investment_purchase_data,
    get_f_tf_investment_sale_data,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import (
    get_global_emitter,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.validation import (
    PanderaDataFrameValidator,
)
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    PRE_BRONZE_ARTIFACT_ID,
)
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_bronze_contract_by_dataset_id,
    get_pre_bronze_contract_by_dataset_id,
)


def _create_mf_excel_fixtures(inputs_dir: Path) -> dict[str, str]:
    """Copy canonical static test Excel files for mutual fund holdings and orders.

    Parameters
    ----------
    inputs_dir : Path
        Directory where Excel statement workbooks should be written.

    Returns
    -------
    dict[str, str]
        Mapping from sync_category to normalized file path.
    """
    inputs_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir = Path(__file__).resolve().parent.parent / "fixtures" / "evidence" / "mutual_funds"

    holdings_src = evidence_dir / "Mutual Funds - Holdings" / "mf_holdings_31-03-2024.xlsx"
    orders_src = evidence_dir / "Mutual Funds - Orders" / "mf_orders_31-03-2024.xlsx"

    holdings_dest = inputs_dir / "Mutual_Funds_Holdings_31-03-2024.xlsx"
    orders_dest = inputs_dir / "Mutual_Funds_Transactions_31-03-2024.xlsx"

    shutil.copy2(holdings_src, holdings_dest)
    shutil.copy2(orders_src, orders_dest)

    return {
        "mf_holdings": str(holdings_dest).replace("\\", "/"),
        "mf_orders": str(orders_dest).replace("\\", "/"),
    }


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


def test_mutual_fund_end_to_end_vertical_slice_admission(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Ingest both mutual fund Excel statements through generalized vertical slice.

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
    files_map = _create_mf_excel_fixtures(tmp_path / "inputs_mf")
    actionable = {cat: [path] for cat, path in files_map.items()}
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

    mf_datasets = (DatasetId.MARKET_MF_HOLDINGS, DatasetId.INVESTMENT_MF_ORDERS)

    # 1. Ingest both mutual fund datasets through generalized vertical slice
    for ds_id in mf_datasets:
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
            run_id="run_mf_001",
        )
        assert success is True

    # 2. Verify Pre-Bronze tables created with operational provenance
    for ds_id in mf_datasets:
        pb_contract = get_pre_bronze_contract_by_dataset_id(ds_id)
        assert pb_contract is not None
        assert pre_bronze.table_exists(pb_contract)
        pb_df = isolated_duckdb_manager.conn.query(
            f"SELECT * FROM {pb_contract.physical_table}"
        ).pl()
        assert pb_df.height >= 2
        assert PRE_BRONZE_ARTIFACT_ID in pb_df.columns
        assert "__source_id__" in pb_df.columns
        assert "__dataset_id__" in pb_df.columns
        # Cleanliness invariant: raw Pre-Bronze does NOT carry duplicate artifact_id column
        assert "artifact_id" not in pb_df.columns

    # 3. Verify Bronze tables created with NO synthetic row UIDs (IdentityRequirement.NONE)
    b_holdings = isolated_duckdb_manager.conn.query("SELECT * FROM bronze.market_mf_holdings").pl()
    assert b_holdings.height == 2
    assert "Scheme Name" in b_holdings.columns
    assert "Units" in b_holdings.columns
    assert "Month Date" in b_holdings.columns
    assert "artifact_id" in b_holdings.columns
    assert "UID" not in b_holdings.columns  # No artificial UID!
    assert b_holdings["Month Date"][0] == date(2024, 3, 31)

    b_orders = isolated_duckdb_manager.conn.query("SELECT * FROM bronze.investment_mf_orders").pl()
    assert b_orders.height == 2
    assert "Scheme Name" in b_orders.columns
    assert "Transaction Type" in b_orders.columns
    assert "Units" in b_orders.columns
    assert "artifact_id" in b_orders.columns
    assert "UID" not in b_orders.columns  # No artificial UID!
    assert set(b_orders["Transaction Type"]) == {"PURCHASE", "REDEEM"}


def test_mutual_fund_gate1_pandera_schema_validation_rejection(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify that corrupt mutual fund orders fail Gate 1 Pandera validation and abort.

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
    inputs_dir = tmp_path / "inputs_corrupt_mf"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    # Missing mandatory Transaction Type column copied from canonical corrupt fixture
    corrupt_src = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "evidence"
        / "negative"
        / "mf_orders_corrupt.xlsx"
    )
    corrupt_path = inputs_dir / "Mutual_Funds_Transactions_31-03-2024.xlsx"
    shutil.copy2(corrupt_src, corrupt_path)

    norm_path = str(corrupt_path).replace("\\", "/")
    actionable = {"mf_orders": [norm_path]}
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.INVESTMENT_MF_ORDERS)
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
            run_id="run_corrupt_mf",
        )

    # Bronze table must not be populated
    b_contract = get_bronze_contract_by_dataset_id(DatasetId.INVESTMENT_MF_ORDERS)
    assert b_contract is not None
    row_count = isolated_duckdb_manager.conn.execute(
        f"SELECT count(*) FROM {b_contract.physical_table}"
    ).fetchone()
    assert row_count is not None
    assert row_count[0] == 0


def test_mutual_fund_idempotent_rerun(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify unchanged mutual fund workbooks yield zero redundant row appends on rerun.

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
    files_map = _create_mf_excel_fixtures(tmp_path / "inputs_idempotent_mf")
    actionable = {cat: [path] for cat, path in files_map.items()}
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

    mf_datasets = (DatasetId.MARKET_MF_HOLDINGS, DatasetId.INVESTMENT_MF_ORDERS)

    # First run
    for ds_id in mf_datasets:
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
            run_id="run_idem_mf_1",
        )

    res_h1 = isolated_duckdb_manager.conn.query(
        "SELECT COUNT(*) FROM bronze.market_mf_holdings"
    ).fetchone()
    assert res_h1 is not None
    res_o1 = isolated_duckdb_manager.conn.query(
        "SELECT COUNT(*) FROM bronze.investment_mf_orders"
    ).fetchone()
    assert res_o1 is not None
    counts_after_first: dict[str, int] = {
        "holdings": int(res_h1[0]),
        "orders": int(res_o1[0]),
    }

    # Second run with identical input files
    for ds_id in mf_datasets:
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
            run_id="run_idem_mf_2",
        )

    res_h2 = isolated_duckdb_manager.conn.query(
        "SELECT COUNT(*) FROM bronze.market_mf_holdings"
    ).fetchone()
    assert res_h2 is not None
    res_o2 = isolated_duckdb_manager.conn.query(
        "SELECT COUNT(*) FROM bronze.investment_mf_orders"
    ).fetchone()
    assert res_o2 is not None
    counts_after_second: dict[str, int] = {
        "holdings": int(res_h2[0]),
        "orders": int(res_o2[0]),
    }

    assert counts_after_second == counts_after_first


def test_mutual_fund_downstream_transformation_and_identity_parity(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify downstream MutualFundStrategy produces valid and deterministic PURCHASE/SALE IDs.

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
    files_map = _create_mf_excel_fixtures(tmp_path / "inputs_downstream_mf")
    actionable = {cat: [path] for cat, path in files_map.items()}
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

    for ds_id in (DatasetId.MARKET_MF_HOLDINGS, DatasetId.INVESTMENT_MF_ORDERS):
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
            run_id="run_downstream_mf",
        )

    # Ingest ISIN mapping into Bronze to satisfy join
    isin_df = pl.DataFrame(
        {
            "INSTRUMENT_NAME": ["Parag Parikh Flexi Cap Fund - Direct Plan - Growth"],
            "ISIN": ["INF879O01019"],
            "artifact_id": ["art_isin_001"],
        }
    )
    isolated_duckdb_manager.conn.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    isolated_duckdb_manager.conn.register("_temp_isin", isin_df)
    isolated_duckdb_manager.conn.execute(
        "CREATE OR REPLACE TABLE bronze.investment_mf_isin_mapping AS SELECT * FROM _temp_isin"
    )

    # Query Bronze frames for MutualFundStrategy
    bronze_holdings = (
        isolated_duckdb_manager.conn.query("SELECT * FROM bronze.market_mf_holdings").pl().lazy()
    )
    bronze_orders = (
        isolated_duckdb_manager.conn.query("SELECT * FROM bronze.investment_mf_orders").pl().lazy()
    )
    bronze_isin = (
        isolated_duckdb_manager.conn.query("SELECT * FROM bronze.investment_mf_isin_mapping")
        .pl()
        .lazy()
    )

    collection = DatasetCollection(
        frames={
            DatasetId.MARKET_MF_HOLDINGS: bronze_holdings,
            DatasetId.INVESTMENT_MF_ORDERS: bronze_orders,
            DatasetId.INVESTMENT_MF_ISIN_MAPPING: bronze_isin,
        }
    )

    d_asset_subcategory = pl.DataFrame(
        {
            "UID": ["ASSET_SUBCAT_MF"],
            "ASSET_NAME": ["Mutual Funds"],
        }
    ).lazy()

    pipeline = MutualFundPipeline()
    diag = get_observability_diagnostics("test_downstream_mf")
    result = pipeline.process(
        extracted=collection,
        d_asset_subcategory_lazy=d_asset_subcategory,
        rules=rules,
        diagnostics=diag,
    )

    # Assert Purchase Reference has ISIN and valid height
    purchase_df = result.purchase_ref.collect()
    assert purchase_df.height == 1
    assert "ISIN" in purchase_df.columns
    assert purchase_df["ISIN"][0] == "INF879O01019"

    # Assert Sale Reference has ISIN and valid height
    sale_df = result.sale_ref.collect()
    assert sale_df.height == 1
    assert "ISIN" in sale_df.columns

    # Verify downstream Silver fact tables compute deterministic Purchase_ID and Sale_ID
    purchase_fact = get_f_tf_investment_purchase_data(
        [result.purchase_ref], rules.DEFAULT_CURRENCY_ID
    ).collect()
    assert "Purchase_ID" in purchase_fact.columns
    assert purchase_fact["Purchase_ID"][0].startswith("PURCHASE_")

    sale_fact = get_f_tf_investment_sale_data(
        [result.sale_ref], rules.DEFAULT_CURRENCY_ID
    ).collect()
    assert "Sale_ID" in sale_fact.columns
    assert sale_fact["Sale_ID"][0].startswith("SALE_")

    # Assert Master Reference unions distinct instruments
    master_df = result.master_ref.collect()
    assert master_df.height >= 1
    assert "ISIN" in master_df.columns
    assert "INSTRUMENT_CLASS" in master_df.columns
    assert master_df["INSTRUMENT_CLASS"][0] == "Mutual Funds"
