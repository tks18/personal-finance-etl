# pyright: reportPrivateUsage=false
"""Verification suite for Domestic-Stock Ingestion and Lakehouse Integration.

Owns
----
- Multi-dataset vertical slice ingestion across domestic stock evidence datasets:
  (MARKET_STOCK_HOLDINGS, INVESTMENT_STOCK_ORDERS).
- Verification of zero artificial Bronze row UIDs (IdentityRequirement.NONE invariant).
- Pre-Bronze operational provenance tracking (__artifact_id__, __source_id__, __dataset_id__).
- Pandera schema validation enforcement (Gate 1 & Gate 2) and error rejection.
- Empty statement handling (header-only statements with zero trades).
- Idempotent rerun verification ensuring zero redundant row appends on unchanged files.
- Downstream StockPipeline parity and deterministic PURCHASE / SALE identity generation.
- Legacy extraction demolition verification.

Does not own
------------
- Single-slice generalized ingestion mechanics (owned by test_generalized_vertical_slice.py).
- Mutual fund evidence migration (owned by test_mutual_fund_evidence_migration.py).
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
    StockPipeline,
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
from personal_finance_etl.domain.investments.transforms import (
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
    get_pre_bronze_contract_by_dataset_id,
)


def _create_stock_excel_fixtures(inputs_dir: Path) -> dict[str, str]:
    """Copy canonical static test Excel files for domestic stock holdings and orders.

    Parameters
    ----------
    inputs_dir : Path
        Target directory to populate with test fixtures.

    Returns
    -------
    dict[str, str]
        Mapping of logical dataset key to file path.
    """
    stock_pl_dir = inputs_dir / "Statements" / "Stock PL Statements"
    stock_orders_dir = inputs_dir / "Statements" / "Stock - Orders"
    stock_pl_dir.mkdir(parents=True, exist_ok=True)
    stock_orders_dir.mkdir(parents=True, exist_ok=True)

    evidence_dir = (
        Path(__file__).resolve().parent.parent / "fixtures" / "evidence" / "domestic_stocks"
    )

    pl_src = evidence_dir / "Stock PL Statements" / "stock_pl_31-03-2024.xlsx"
    orders_src = evidence_dir / "Stock - Orders" / "stock_orders_31-03-2024.xlsx"

    pl_dest = stock_pl_dir / "PL Statement - 31-03-2024.xlsx"
    orders_dest = stock_orders_dir / "Orders - 01-04-2023 - 31-03-2024.xlsx"

    shutil.copy2(pl_src, pl_dest)
    shutil.copy2(orders_src, orders_dest)

    return {
        "stock_pl": str(pl_dest).replace("\\", "/"),
        "stock_orders": str(orders_dest).replace("\\", "/"),
    }


@pytest.fixture(autouse=True)
def _auto_open_control_plane(isolated_control_plane: ControlPlane) -> Iterator[None]:
    """Ensure isolated ControlPlane connection is open and schema initialized."""
    isolated_control_plane.open()
    isolated_control_plane.ensure_schema()
    yield
    isolated_control_plane.close()


def test_domestic_stock_end_to_end_vertical_slice_admission(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Ingest both domestic stock Excel statements through generalized vertical slice.

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
    files_map = _create_stock_excel_fixtures(tmp_path / "inputs_stock")
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

    stock_datasets = (DatasetId.MARKET_STOCK_HOLDINGS, DatasetId.INVESTMENT_STOCK_ORDERS)

    # 1. Ingest both domestic stock datasets through generalized vertical slice
    for ds_id in stock_datasets:
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
            run_id="run_stock_001",
        )
        assert success is True

    # 2. Verify Pre-Bronze tables created with operational provenance
    for ds_id in stock_datasets:
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
        assert "artifact_id" not in pb_df.columns

    # 3. Verify Bronze tables created with NO synthetic row UIDs (IdentityRequirement.NONE)
    b_holdings = isolated_duckdb_manager.conn.query(
        "SELECT * FROM bronze.market_stock_holdings"
    ).pl()
    assert b_holdings.height == 2
    assert "artifact_id" in b_holdings.columns
    assert "Month Date" in b_holdings.columns
    assert b_holdings["Month Date"][0] == date(2024, 3, 31)
    assert b_holdings["__file_category__"][0] == "Indian Stocks"
    assert "UID" not in b_holdings.columns
    assert "ZUID" not in b_holdings.columns

    b_orders = isolated_duckdb_manager.conn.query(
        "SELECT * FROM bronze.investment_stock_orders"
    ).pl()
    assert b_orders.height == 3
    assert b_orders["Quantity"].dtype == pl.Float64
    assert b_orders["Value"].dtype == pl.Float64
    assert b_orders["Quantity"].to_list() == [10.0, 20.0, 5.0]
    assert b_orders["Value"].to_list() == [24000.0, 30000.0, 8000.0]
    assert b_orders["Type"].to_list() == ["BUY", "BUY", "SELL"]
    assert b_orders["__file_category__"][0] == "Indian Stocks"
    assert "artifact_id" in b_orders.columns
    assert "UID" not in b_orders.columns
    assert "ZUID" not in b_orders.columns

    isolated_duckdb_manager.close()


def test_empty_stock_orders_statement_handling(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify statements with headers but 0 transaction rows ingest cleanly without error."""
    inputs_dir = tmp_path / "inputs_empty_orders"
    orders_dir = inputs_dir / "Statements" / "Stock - Orders"
    orders_dir.mkdir(parents=True, exist_ok=True)

    # Header-only workbook copied from canonical empty fixture
    empty_src = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "evidence"
        / "negative"
        / "stock_orders_empty_31-03-2024.xlsx"
    )
    empty_path = orders_dir / "Orders - 04-2026.xlsx"
    shutil.copy2(empty_src, empty_path)

    norm_path = str(empty_path).replace("\\", "/")
    actionable = {"stock_orders": [norm_path]}
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.INVESTMENT_STOCK_ORDERS)
    assert ds_plan is not None

    success = ingestion_service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files=actionable,
        run_id="run_empty_orders",
    )
    assert success is True

    b_orders = isolated_duckdb_manager.conn.query(
        "SELECT * FROM bronze.investment_stock_orders"
    ).pl()
    assert b_orders.height == 0

    isolated_duckdb_manager.close()


def test_stock_evidence_gate1_rejection(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify that Gate 1 rejects stock files missing mandatory source columns."""
    inputs_dir = tmp_path / "inputs_corrupt_stock"
    pl_dir = inputs_dir / "Statements" / "Stock PL Statements"
    pl_dir.mkdir(parents=True, exist_ok=True)

    # Missing mandatory "Stock name" and "ISIN" columns copied from canonical corrupt fixture
    corrupt_src = (
        Path(__file__).resolve().parent.parent
        / "fixtures"
        / "evidence"
        / "negative"
        / "stock_pl_corrupt.xlsx"
    )
    corrupt_path = pl_dir / "PL Statement - 31-03-2024.xlsx"
    shutil.copy2(corrupt_src, corrupt_path)

    norm_path = str(corrupt_path).replace("\\", "/")
    actionable = {"stock_pl": [norm_path]}
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.MARKET_STOCK_HOLDINGS)
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
            run_id="run_corrupt_stock",
        )

    isolated_duckdb_manager.close()


def test_stock_evidence_idempotent_rerun(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify running vertical slice ingestion repeatedly on identical artifacts is idempotent."""
    files_map = _create_stock_excel_fixtures(tmp_path / "inputs_idempotent")
    actionable = {"stock_orders": [files_map["stock_orders"]]}
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.INVESTMENT_STOCK_ORDERS)
    assert ds_plan is not None

    # First run
    ingestion_service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files=actionable,
        run_id="run_idempotent_1",
    )
    res1 = isolated_duckdb_manager.conn.query(
        "SELECT COUNT(*) FROM bronze.investment_stock_orders"
    ).fetchone()
    assert res1 is not None
    count1 = res1[0]
    assert count1 == 3

    # Second run with same file
    ingestion_service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files=actionable,
        run_id="run_idempotent_2",
    )
    res2 = isolated_duckdb_manager.conn.query(
        "SELECT COUNT(*) FROM bronze.investment_stock_orders"
    ).fetchone()
    assert res2 is not None
    count2 = res2[0]
    assert count2 == count1

    isolated_duckdb_manager.close()


def test_downstream_stock_pipeline_parity(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify StockPipeline consumes admitted Bronze data and derives deterministic IDs."""
    files_map = _create_stock_excel_fixtures(tmp_path / "inputs_downstream")
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

    for ds_id in (DatasetId.MARKET_STOCK_HOLDINGS, DatasetId.INVESTMENT_STOCK_ORDERS):
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

    # Assemble DatasetCollection from Bronze Lakehouse
    collection = bronze.get_dataset_collection()
    assert DatasetId.MARKET_STOCK_HOLDINGS in collection
    assert DatasetId.INVESTMENT_STOCK_ORDERS in collection

    # Execute downstream StockPipeline
    pipeline = StockPipeline()
    d_asset_subcategory_lazy = pl.LazyFrame(
        {"ASSET_NAME": ["Stocks & ETFs"], "UID": ["CAT_STOCKS_001"]}
    )
    diagnostics = get_observability_diagnostics(__name__)
    result = pipeline.process(collection, d_asset_subcategory_lazy, rules, diagnostics)

    # 1. Verify Purchase Reference
    purchase_df = result.purchase_ref.collect()
    assert purchase_df.height == 2
    assert "ISIN" in purchase_df.columns
    assert "Quantity" in purchase_df.columns
    assert "Price" in purchase_df.columns
    assert "Value" in purchase_df.columns

    # 2. Verify Sale Reference
    sale_df = result.sale_ref.collect()
    assert sale_df.height == 1
    assert "ISIN" in sale_df.columns
    assert "Sell_Price" in sale_df.columns
    assert "Total_PnL" in sale_df.columns

    # 3. Verify Deterministic Purchase and Sale Identifiers via Fact Tables
    purchase_fact = get_f_tf_investment_purchase_data(
        [result.purchase_ref], rules.DEFAULT_CURRENCY_ID
    ).collect()
    assert purchase_fact.height == 2
    assert "Purchase_ID" in purchase_fact.columns
    for p_id in purchase_fact["Purchase_ID"].to_list():
        assert str(p_id).startswith("PURCHASE_")

    sale_fact = get_f_tf_investment_sale_data(
        [result.sale_ref], rules.DEFAULT_CURRENCY_ID
    ).collect()
    assert sale_fact.height == 1
    assert "Sale_ID" in sale_fact.columns
    assert str(sale_fact["Sale_ID"][0]).startswith("SALE_")

    # 4. Verify Master Reference
    master_df = result.master_ref.collect()
    assert master_df.height == 2
    assert "INSTRUMENT_NAME" in master_df.columns
    assert "INSTRUMENT_TYPE" in master_df.columns
    assert master_df["INSTRUMENT_TYPE"][0] == "Equity"
    assert master_df["CATEGORY_ID"][0] == "CAT_STOCKS_001"

    # 5. Verify Market Data Reference Aggregation
    market_ref_df = result.market_data_ref.collect()
    assert market_ref_df.height == 2
    assert "Closing_Price" in market_ref_df.columns
    assert "Buy_Price" in market_ref_df.columns
    assert "Closing_Value" in market_ref_df.columns
    assert "Buy_Value" in market_ref_df.columns
    assert "Total_PnL" in market_ref_df.columns

    isolated_duckdb_manager.close()


def test_legacy_stock_extraction_demolished() -> None:
    """Verify legacy extraction functions are demolished from files provider and coordinator."""
    import personal_finance_etl.infrastructure.providers.files as files_pkg
    import personal_finance_etl.infrastructure.providers.files.excel as excel_mod

    assert not hasattr(files_pkg, "extract_stock_market_data_raw")
    assert not hasattr(files_pkg, "extract_stock_transactions_raw")
    assert not hasattr(excel_mod, "extract_stock_market_data_raw")
    assert not hasattr(excel_mod, "extract_stock_transactions_raw")
    assert not hasattr(excel_mod, "_process_stock_closing_statement")
    assert not hasattr(excel_mod, "_process_stock_transactions")
