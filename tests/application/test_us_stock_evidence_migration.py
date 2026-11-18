# pyright: reportPrivateUsage=false
"""Verification suite for Phase 033 US Investment Evidence Migration.

Owns
----
- Vertical slice ingestion for foreign US equity trade evidence:
  (INVESTMENT_US_STOCK_TRANSACTIONS -> bronze.r_US_Stock_Transactions).
- Verification of zero artificial Bronze row UIDs (IdentityRequirement.NONE invariant).
- Pre-Bronze operational provenance tracking (__artifact_id__, __source_id__, __dataset_id__).
- Pandera schema validation enforcement (Gate 1 Source & Gate 2 Canonical Bronze) and rejection.
- Idempotent rerun verification ensuring zero redundant row appends on unchanged files.
- Downstream USStockPipeline parity and deterministic PURCHASE / SALE identity generation.
- Legacy extraction demolition verification.

Does not own
------------
- Single-slice generalized ingestion mechanics (owned by test_generalized_vertical_slice.py).
- Domestic stock evidence migration (owned by test_domestic_stock_evidence_migration.py).
- Mutual fund evidence migration (owned by test_mutual_fund_evidence_migration.py).
- Downstream FIFO and Tax calculations (owned by test_tax_domain.py).
"""

from __future__ import annotations

import io
import zipfile
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import polars as pl
import pytest
from pandera.errors import SchemaError, SchemaErrors

from personal_finance_etl.application.ingestion.admission import AdmissionService
from personal_finance_etl.application.ingestion.asset_strategies import USStockPipeline
from personal_finance_etl.application.ingestion.slice_runner import (
    DatasetIngestionService,
)
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import SourcePlanner
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.loader import (
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.validation import ValidationError
from personal_finance_etl.domain.investments.classification import (
    filter_us_market_trades,
)
from personal_finance_etl.domain.investments.transforms import (
    get_f_tf_investment_purchase_data,
    get_f_tf_investment_sale_data,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import get_global_emitter
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


def _build_minimal_xlsx(sheet_name: str, rows: list[list[object]]) -> bytes:
    """Build an in-memory .xlsx binary payload for testing fastexcel ingestion.

    Parameters
    ----------
    sheet_name : str
        Target worksheet title.
    rows : list[list[object]]
        Table rows including header row.

    Returns
    -------
    bytes
        Valid raw Excel workbook byte stream.
    """
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    wb_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    wb = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets><sheet name="{sheet_name}" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )

    ws_rows: list[str] = []
    for r_idx, row in enumerate(rows, start=1):
        cells: list[str] = []
        for c_idx, val in enumerate(row):
            col_letter = chr(65 + c_idx)
            cell_ref = f"{col_letter}{r_idx}"
            if isinstance(val, (int, float)):
                cells.append(f'<c r="{cell_ref}"><v>{val}</v></c>')
            elif isinstance(val, (datetime, date)):
                iso_str = val.isoformat()
                cells.append(f'<c r="{cell_ref}" t="d"><v>{iso_str}</v></c>')
            elif val is None:
                continue
            else:
                str_val = str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{str_val}</t></is></c>')
        row_str = f'<row r="{r_idx}">{"".join(cells)}</row>'
        ws_rows.append(row_str)

    ws = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(ws_rows)}</sheetData>"
        "</worksheet>"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/worksheets/sheet1.xml", ws)

    return buf.getvalue()


def _create_us_stock_excel_fixtures(inputs_dir: Path) -> dict[str, str]:
    """Create isolated test Excel file for foreign US stock transactions.

    Parameters
    ----------
    inputs_dir : Path
        Target directory to populate with test fixtures.

    Returns
    -------
    dict[str, str]
        Mapping of logical dataset key to file path.
    """
    reports_dir = (
        inputs_dir / "Statements" / "IND Money (US Stocks)" / "Transaction Reports" / "2025-26"
    )
    reports_dir.mkdir(parents=True, exist_ok=True)

    rows: list[list[object]] = [
        [
            "Stock Name",
            "ISIN",
            "Stock Symbol",
            "Yahoo Ticker",
            "Order Date",
            "Currency",
            "Transaction Type",
            "Order Type",
            "Quantity",
            "Price ($)",
            "Order Amount ($)",
            "Brokerage ($)",
            "Exch Rate",
            "Order Amount (INR)",
            "Brokerage (INR)",
        ],
        [
            "Apple Inc.",
            "US0378331005",
            "AAPL",
            "AAPL",
            datetime(2024, 1, 15, 14, 30, 0),
            "USD",
            "BUY",
            "MARKET",
            2.5,
            180.0,
            450.0,
            0.0,
            83.0,
            37350.0,
            0.0,
        ],
        [
            "Apple Inc.",
            "US0378331005",
            "AAPL",
            "AAPL",
            datetime(2024, 3, 20, 15, 45, 0),
            "USD",
            "SELL",
            "LIMIT",
            1.0,
            190.0,
            190.0,
            0.0,
            83.5,
            15865.0,
            0.0,
        ],
    ]
    file_bytes = _build_minimal_xlsx("02-2026", rows)
    file_path = reports_dir / "02-2026.xlsx"
    file_path.write_bytes(file_bytes)

    return {
        "us_stock_transactions": str(file_path).replace("\\", "/"),
    }


@pytest.fixture(autouse=True)
def _auto_open_control_plane(isolated_control_plane: ControlPlane) -> Iterator[None]:
    """Ensure isolated ControlPlane connection is open and schema initialized."""
    isolated_control_plane.open()
    isolated_control_plane.ensure_schema()
    yield
    isolated_control_plane.close()


def test_us_stock_end_to_end_vertical_slice_admission(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify end-to-end ingestion of foreign US stock trade evidence into Pre-Bronze and Bronze."""
    files_map = _create_us_stock_excel_fixtures(tmp_path / "inputs")
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

    ds_plan = source_plan.get_dataset_plan(DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS)
    assert ds_plan is not None
    assert ds_plan.is_enabled is True

    ingestion_service.ingest_dataset(
        dataset_plan=ds_plan,
        source_config=source_config,
        cp=isolated_control_plane,
        pre_bronze=pre_bronze,
        bronze=bronze,
        meta_layer=meta,
        actionable_files=actionable,
        run_id="run_us_stock_001",
    )

    # 1. Assert Pre-Bronze Layer schema and operational provenance
    pb_contract = get_pre_bronze_contract_by_dataset_id(DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS)
    assert pb_contract is not None
    assert pre_bronze.table_exists(pb_contract)
    pb_df = isolated_duckdb_manager.conn.query(f"SELECT * FROM {pb_contract.physical_table}").pl()
    assert pb_df.height == 2
    assert PRE_BRONZE_ARTIFACT_ID in pb_df.columns
    assert "__source_id__" in pb_df.columns
    assert "__dataset_id__" in pb_df.columns
    assert pb_df["__dataset_id__"][0] == DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS.value
    assert pb_df["__source_id__"][0] == "us_stock_transactions"

    # 2. Assert Bronze Layer persistence and zero artificial UID invariant
    bronze_df = isolated_duckdb_manager.conn.query(
        "SELECT * FROM bronze.r_US_Stock_Transactions"
    ).pl()
    assert bronze_df.height == 2
    assert "UID" not in bronze_df.columns  # IdentityRequirement.NONE invariant
    assert "artifact_id" in bronze_df.columns
    assert "__file_category__" in bronze_df.columns
    assert bronze_df["__file_category__"][0] == "US Stocks"
    assert bronze_df["Stock Name"][0] == "Apple Inc."
    assert bronze_df["Stock Symbol"][0] == "AAPL"
    assert bronze_df["Transaction Type"][0] == "BUY"
    assert bronze_df["Transaction Type"][1] == "SELL"

    isolated_duckdb_manager.close()


def test_us_stock_gate1_source_validation_rejection(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify Gate 1 rejects US stock transaction statement with missing non-nullable columns."""
    malformed_dir = (
        tmp_path
        / "inputs_malformed"
        / "Statements"
        / "IND Money (US Stocks)"
        / "Transaction Reports"
    )
    malformed_dir.mkdir(parents=True, exist_ok=True)

    # Missing non-nullable "Stock Name"
    rows: list[list[object]] = [
        [
            "ISIN",
            "Stock Symbol",
            "Yahoo Ticker",
            "Order Date",
            "Currency",
            "Transaction Type",
            "Order Type",
            "Quantity",
        ],
        [
            "US0378331005",
            "AAPL",
            "AAPL",
            datetime(2024, 1, 15, 14, 30, 0),
            "USD",
            "BUY",
            "MARKET",
            2.5,
        ],
    ]
    file_bytes = _build_minimal_xlsx("02-2026", rows)
    file_path = malformed_dir / "02-2026.xlsx"
    file_path.write_bytes(file_bytes)

    actionable = {"us_stock_transactions": [str(file_path).replace("\\", "/")]}
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS)
    assert ds_plan is not None

    with pytest.raises((SchemaError, SchemaErrors, ValidationError)):
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files=actionable,
            run_id="run_us_stock_malformed",
        )

    isolated_duckdb_manager.close()


def test_us_stock_gate2_canonical_validation_rejection(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify Gate 2 rejects canonical Bronze DataFrame violating schema nullability constraints."""
    malformed_dir = (
        tmp_path / "inputs_gate2" / "Statements" / "IND Money (US Stocks)" / "Transaction Reports"
    )
    malformed_dir.mkdir(parents=True, exist_ok=True)

    # Null value for non-nullable ISIN
    rows: list[list[object]] = [
        [
            "Stock Name",
            "ISIN",
            "Stock Symbol",
            "Yahoo Ticker",
            "Order Date",
            "Currency",
            "Transaction Type",
            "Order Type",
            "Quantity",
            "Price ($)",
            "Order Amount ($)",
            "Brokerage ($)",
            "Exch Rate",
            "Order Amount (INR)",
            "Brokerage (INR)",
        ],
        [
            "Apple Inc.",
            None,  # ISIN is non-nullable in canonical schema
            "AAPL",
            "AAPL",
            datetime(2024, 1, 15, 14, 30, 0),
            "USD",
            "BUY",
            "MARKET",
            2.5,
            180.0,
            450.0,
            0.0,
            83.0,
            37350.0,
            0.0,
        ],
    ]
    file_bytes = _build_minimal_xlsx("02-2026", rows)
    file_path = malformed_dir / "02-2026.xlsx"
    file_path.write_bytes(file_bytes)

    actionable = {"us_stock_transactions": [str(file_path).replace("\\", "/")]}
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS)
    assert ds_plan is not None

    with pytest.raises((SchemaError, SchemaErrors, ValidationError)):
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan,
            source_config=source_config,
            cp=isolated_control_plane,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files=actionable,
            run_id="run_us_stock_gate2",
        )

    isolated_duckdb_manager.close()


def test_us_stock_idempotency_rerun(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify executing ingestion twice on unchanged statements does not duplicate Bronze rows."""
    files_map = _create_us_stock_excel_fixtures(tmp_path / "inputs_idempotent")
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
    ds_plan = source_plan.get_dataset_plan(DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS)
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
        "SELECT COUNT(*) FROM bronze.r_US_Stock_Transactions"
    ).fetchone()
    assert res1 is not None
    count1 = res1[0]
    assert count1 == 2

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
        "SELECT COUNT(*) FROM bronze.r_US_Stock_Transactions"
    ).fetchone()
    assert res2 is not None
    count2 = res2[0]
    assert count2 == count1

    isolated_duckdb_manager.close()


def test_downstream_us_stock_pipeline_parity(
    isolated_settings: Settings,
    isolated_duckdb_manager: DuckDBManager,
    isolated_control_plane: ControlPlane,
    rules: FinancialRules,
    tmp_path: Path,
) -> None:
    """Verify USStockPipeline consumes admitted Bronze data and derives deterministic IDs."""
    files_map = _create_us_stock_excel_fixtures(tmp_path / "inputs_downstream")
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

    ds_plan = source_plan.get_dataset_plan(DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS)
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
    assert DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS in collection

    # Execute downstream USStockPipeline
    pipeline = USStockPipeline()
    d_asset_subcategory_lazy = pl.LazyFrame(
        {"ASSET_NAME": ["Stocks & ETFs"], "UID": ["CAT_STOCKS_001"]}
    )
    diagnostics = get_observability_diagnostics(__name__)
    result = pipeline.process(collection, d_asset_subcategory_lazy, rules, diagnostics)

    # 1. Verify Purchase Reference
    purchase_df = result.purchase_ref.collect()
    assert purchase_df.height == 1
    assert "ISIN" in purchase_df.columns
    assert "Quantity" in purchase_df.columns
    assert "Price" in purchase_df.columns
    assert "Price_Local" in purchase_df.columns
    assert "CURRENCY_ID" in purchase_df.columns
    assert purchase_df["CURRENCY_ID"][0] == "USD"
    assert purchase_df["Quantity"][0] == 2.5

    # 2. Verify Sale Reference
    sale_df = result.sale_ref.collect()
    assert sale_df.height == 1
    assert "ISIN" in sale_df.columns
    assert "Quantity" in sale_df.columns
    assert "Sell_Price_Local" in sale_df.columns
    assert "CURRENCY_ID" in sale_df.columns
    assert sale_df["CURRENCY_ID"][0] == "USD"
    assert sale_df["Quantity"][0] == 1.0

    # 3. Verify Deterministic Purchase and Sale Identifiers via Fact Tables
    purchase_fact = get_f_tf_investment_purchase_data(
        [result.purchase_ref], rules.DEFAULT_CURRENCY_ID
    ).collect()
    assert purchase_fact.height == 1
    assert "Purchase_ID" in purchase_fact.columns
    assert str(purchase_fact["Purchase_ID"][0]).startswith("PURCHASE_")

    sale_fact = get_f_tf_investment_sale_data(
        [result.sale_ref], rules.DEFAULT_CURRENCY_ID
    ).collect()
    assert sale_fact.height == 1
    assert "Sale_ID" in sale_fact.columns
    assert str(sale_fact["Sale_ID"][0]).startswith("SALE_")

    # 4. Verify Master Reference
    master_df = result.master_ref.collect()
    assert master_df.height == 1
    assert "INSTRUMENT_NAME" in master_df.columns
    assert "INSTRUMENT_TYPE" in master_df.columns
    assert master_df["INSTRUMENT_TYPE"][0] == "Equity"
    assert master_df["CATEGORY_ID"][0] == "CAT_STOCKS_001"
    assert master_df["INSTRUMENT_SUBTYPE"][0] == "US Stocks"

    # 5. Verify US Market trade filtering for market range discovery
    us_purchases = filter_us_market_trades(purchase_fact)
    assert us_purchases.height == 1
    assert us_purchases["CURRENCY_ID"][0] == "USD"

    isolated_duckdb_manager.close()


def test_legacy_us_stock_extraction_demolished() -> None:
    """Verify legacy extraction functions are demolished from files provider and coordinator."""
    import personal_finance_etl.application.ingestion as ingestion_pkg
    import personal_finance_etl.infrastructure.providers.files as files_pkg
    import personal_finance_etl.infrastructure.providers.files.excel as excel_mod

    assert not hasattr(files_pkg, "extract_us_stock_transactions_raw")
    assert not hasattr(excel_mod, "extract_us_stock_transactions_raw")
    assert not hasattr(excel_mod, "_process_us_stock_transactions")
    assert not hasattr(ingestion_pkg, "DataExtractor")
