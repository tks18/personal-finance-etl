"""Tests for NormalizationExecutor vectorized Polars execution engine and equivalence fixtures.

Owns
----
- Unit tests verifying vectorized execution of all 8 normalization rules.
- Negative tests for MissingSourceFieldError when incoming frames lack mapped columns.
- Proof of source column order invariance (reordering input columns yields identical canonical frames).
- Proof of input format flexibility (DataFrame vs LazyFrame inputs).
- Proof of runtime provenance preservation (artifact_id, __file_name__, __folder_path__).
- Proof that execution is purely native Polars with zero Python row UDFs.
- In-memory equivalence fixtures for household SQLite, CSV, and Excel parsing.
"""

from __future__ import annotations

import datetime

import polars as pl
import pytest

from personal_finance_etl.application.normalization.compiler import (
    NormalizationCompiler,
)
from personal_finance_etl.application.normalization.errors import (
    MissingSourceFieldError,
)
from personal_finance_etl.application.normalization.executor import (
    NormalizationExecutor,
)
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.model import SourceDatasetConfig
from personal_finance_etl.config.sources.normalization import (
    CastRule,
    ConstantRule,
    DefaultRule,
    MapValuesRule,
    NormalizeCaseRule,
    NormalizeNullRule,
    ParseDateRule,
    TrimRule,
)
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    ExcelSelector,
    SqliteSelector,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId
from personal_finance_etl.domain.household.transforms.common import get_column_mapping


def test_executor_executes_all_rules_vectorized() -> None:
    """Verify NormalizationExecutor executes all 8 rule types cleanly in a single plan."""
    df_raw = pl.DataFrame(
        {
            "RAW_ID": [101, 102, 103],
            "RAW_NAME": ["  Reliance Industries  ", "tcs ltd", "   HDFC Bank   "],
            "RAW_DATE": ["2026-01-15", "2026-02-20", "2026-03-25"],
            "RAW_AMOUNT": ["1500.50", "2400.00", "950.25"],
            "RAW_STATUS": ["0", "1", "99"],
            "RAW_NOTES": ["Regular trade", "None", ""],
            "artifact_id": ["art_1", "art_1", "art_1"],
            "__file_name__": ["trades.csv", "trades.csv", "trades.csv"],
            "__folder_path__": ["inputs", "inputs", "inputs"],
        }
    )

    config = SourceDatasetConfig(
        source_id=SourceId("trade_source"),
        dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
        selector=CsvSelector(),
        mapping=[
            ColumnMapping(source_field="RAW_ID", canonical_field="UID"),
            ColumnMapping(source_field="RAW_NAME", canonical_field="CONTENT"),
            ColumnMapping(source_field="RAW_DATE", canonical_field="TRANSACTION_DATE"),
            ColumnMapping(source_field="RAW_AMOUNT", canonical_field="AMOUNT"),
            ColumnMapping(source_field="RAW_STATUS", canonical_field="TRANSACTION_TYPE"),
            ColumnMapping(source_field="RAW_NOTES", canonical_field="MEMO"),
        ],
        normalization=[
            TrimRule(field="RAW_NAME", mode="both"),
            NormalizeCaseRule(field="CONTENT", case="upper"),
            ParseDateRule(field="TRANSACTION_DATE", format="%Y-%m-%d"),
            CastRule(field="AMOUNT", target_type="float64"),
            MapValuesRule(
                field="TRANSACTION_TYPE",
                mapping={"0": "INCOME", "1": "EXPENSE"},
                default="TRANSFER",
            ),
            NormalizeNullRule(field="MEMO", null_values=["", "None"]),
            DefaultRule(field="MEMO", value="UNCATEGORIZED"),
            ConstantRule(field="ORDER_NUM", value=1),
        ],
    )

    compiler = NormalizationCompiler()
    plan = compiler.compile(config)

    executor = NormalizationExecutor()
    result_lf = executor.execute(plan, df_raw)
    result_df = result_lf.collect()

    # Assert Content is trimmed and uppercase
    assert result_df["CONTENT"].to_list() == ["RELIANCE INDUSTRIES", "TCS LTD", "HDFC BANK"]

    # Assert Date is parsed into Date dtype
    assert result_df["TRANSACTION_DATE"].to_list() == [
        datetime.date(2026, 1, 15),
        datetime.date(2026, 2, 20),
        datetime.date(2026, 3, 25),
    ]

    # Assert Amount is float64
    assert result_df["AMOUNT"].to_list() == [1500.50, 2400.00, 950.25]
    assert result_df["AMOUNT"].dtype == pl.Float64

    # Assert Mapped Values
    assert result_df["TRANSACTION_TYPE"].to_list() == ["INCOME", "EXPENSE", "TRANSFER"]

    # Assert Null normalization + default fill
    assert result_df["MEMO"].to_list() == ["Regular trade", "UNCATEGORIZED", "UNCATEGORIZED"]

    # Assert Constant injected
    assert result_df["ORDER_NUM"].to_list() == [1, 1, 1]

    # Assert Provenance preserved
    assert result_df["artifact_id"].to_list() == ["art_1", "art_1", "art_1"]
    assert "__file_name__" in result_df.columns
    assert "__folder_path__" in result_df.columns


def test_executor_missing_source_field_raises() -> None:
    """Verify NormalizationExecutor raises MissingSourceFieldError when mapped column is missing."""
    df_raw = pl.DataFrame({"COL_A": [1, 2], "COL_B": ["x", "y"]})

    config = SourceDatasetConfig(
        source_id=SourceId("src"),
        dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
        selector=SqliteSelector(table_name="ASSETGROUP"),
        mapping=[
            ColumnMapping(source_field="NON_EXISTENT_SOURCE_COL", canonical_field="UID"),
        ],
    )

    compiler = NormalizationCompiler()
    plan = compiler.compile(config)

    executor = NormalizationExecutor()
    with pytest.raises(MissingSourceFieldError) as exc_info:
        executor.execute(plan, df_raw)

    err = exc_info.value
    assert err.missing_field == "NON_EXISTENT_SOURCE_COL"
    assert "COL_A" in err.available_fields


def test_executor_source_column_order_invariance() -> None:
    """Verify that permuting source column order yields 100% identical canonical output."""
    df_order_1 = pl.DataFrame(
        {
            "Z_PK": ["1", "2"],
            "ZNAME": ["Liquid Cash", "Savings"],
            "ZORDER_NUM": [1, 2],
            "ZIS_DEL": ["0", "0"],
        }
    )

    # Permuted column order
    df_order_2 = pl.DataFrame(
        {
            "ZIS_DEL": ["0", "0"],
            "ZNAME": ["Liquid Cash", "Savings"],
            "Z_PK": ["1", "2"],
            "ZORDER_NUM": [1, 2],
        }
    )

    config = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
        selector=SqliteSelector(table_name="ASSETGROUP"),
        mapping=[
            ColumnMapping(source_field="Z_PK", canonical_field="UID"),
            ColumnMapping(source_field="ZNAME", canonical_field="ASSET_GROUP"),
            ColumnMapping(source_field="ZORDER_NUM", canonical_field="ORDER_NUM"),
            ColumnMapping(source_field="ZIS_DEL", canonical_field="IS_DEL"),
        ],
    )

    compiler = NormalizationCompiler()
    plan = compiler.compile(config)
    executor = NormalizationExecutor()

    res_1 = executor.execute(plan, df_order_1).collect()
    res_2 = executor.execute(plan, df_order_2).collect()

    assert res_1.equals(res_2)


def test_executor_lazy_frame_input() -> None:
    """Verify NormalizationExecutor accepts LazyFrame directly without eager collection."""
    lf = pl.DataFrame({"Z_PK": ["1"], "ZNAME": ["Cash"]}).lazy()

    config = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
        selector=SqliteSelector(table_name="ASSETGROUP"),
        mapping=[
            ColumnMapping(source_field="Z_PK", canonical_field="UID"),
            ColumnMapping(source_field="ZNAME", canonical_field="ASSET_GROUP"),
        ],
    )

    compiler = NormalizationCompiler()
    plan = compiler.compile(config)
    executor = NormalizationExecutor()

    out_lf = executor.execute(plan, lf)
    assert isinstance(out_lf, pl.LazyFrame)
    out_df = out_lf.collect()
    assert out_df.columns == ["UID", "ASSET_GROUP"]


def test_executor_pure_vectorized_no_python_udf() -> None:
    """Verify that compiled execution plan produces native Polars expressions without python UDFs."""
    df_raw = pl.DataFrame({"SRC_NAME": ["  alpha  ", "  beta  "]})

    config = SourceDatasetConfig(
        source_id=SourceId("src"),
        dataset_id=DatasetId.INVESTMENT_MF_ISIN_MAPPING,
        selector=CsvSelector(),
        mapping=[ColumnMapping(source_field="SRC_NAME", canonical_field="INSTRUMENT_NAME")],
        normalization=[
            TrimRule(field="SRC_NAME", mode="both"),
            NormalizeCaseRule(field="INSTRUMENT_NAME", case="upper"),
        ],
    )

    compiler = NormalizationCompiler()
    plan = compiler.compile(config)
    executor = NormalizationExecutor()

    out_lf = executor.execute(plan, df_raw)
    plan_text = out_lf.explain()

    # Assert no python UDF / map_elements in query plan
    assert "map_elements" not in plan_text
    assert "python_udf" not in plan_text.lower()


# --- In-Memory Equivalence Fixtures ---


def test_equivalence_household_sqlite_assetgroup() -> None:
    """Verify NormalizationExecutor reproduces legacy column_master mapping for ASSETGROUP."""
    # 1. Simulate legacy column_master DataFrame
    df_column_master = pl.DataFrame(
        {
            "TABLE_NAME": ["ASSETGROUP", "ASSETGROUP", "ASSETGROUP", "ASSETGROUP"],
            "OLD_COLUMN": ["Z_PK", "ZNAME", "ZORDER_NUM", "ZIS_DEL"],
            "NEW_COLUMN": ["UID", "ASSET_GROUP", "ORDER_NUM", "IS_DEL"],
        }
    )
    legacy_mapping = get_column_mapping(df_column_master, "ASSETGROUP")

    # 2. Source-shaped SQLite raw frame
    df_sqlite_raw = pl.DataFrame(
        {
            "Z_PK": ["10", "20", "30"],
            "ZNAME": ["Bank Accounts", "Equities", "Real Estate"],
            "ZORDER_NUM": [1, 2, 3],
            "ZIS_DEL": ["0", "0", "0"],
            "artifact_id": ["art_db", "art_db", "art_db"],
            "__file_name__": ["source.sqlite", "source.sqlite", "source.sqlite"],
            "__folder_path__": ["inputs", "inputs", "inputs"],
        }
    )

    # Legacy output
    legacy_output = df_sqlite_raw.lazy().rename(legacy_mapping).collect()

    # 3. New Normalization Engine Plan
    config = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
        selector=SqliteSelector(table_name="ASSETGROUP"),
        mapping=legacy_mapping,  # type: ignore[arg-type]
    )

    compiler = NormalizationCompiler()
    plan = compiler.compile(config)
    executor = NormalizationExecutor()
    new_output = executor.execute(plan, df_sqlite_raw).collect()

    # Compare content across all columns regardless of column permutation
    cols = sorted(new_output.columns)
    assert new_output.select(cols).equals(legacy_output.select(cols))


def test_equivalence_csv_isin_mapping_cleaning() -> None:
    """Verify NormalizationExecutor reproduces CSV schema overrides and string cleanup."""
    # Source raw CSV frame with untrimmed strings and integer-like ISIN
    df_csv_raw = pl.DataFrame(
        {
            "INSTRUMENT_NAME": ["  Nippon India Growth Fund  ", "Mirae Asset Large Cap Fund  "],
            "ISIN": ["INF204K01018", "INF769K01010"],
            "artifact_id": ["art_isin", "art_isin"],
            "__file_name__": ["isin.csv", "isin.csv"],
            "__folder_path__": ["inputs", "inputs"],
        }
    )

    config = SourceDatasetConfig(
        source_id=SourceId("mf_isin_csv"),
        dataset_id=DatasetId.INVESTMENT_MF_ISIN_MAPPING,
        selector=CsvSelector(),
        mapping=[
            ColumnMapping(source_field="INSTRUMENT_NAME", canonical_field="INSTRUMENT_NAME"),
            ColumnMapping(source_field="ISIN", canonical_field="ISIN"),
        ],
        normalization=[
            TrimRule(field="INSTRUMENT_NAME", mode="both"),
            TrimRule(field="ISIN", mode="both"),
            CastRule(field="INSTRUMENT_NAME", target_type="string"),
            CastRule(field="ISIN", target_type="string"),
        ],
    )

    compiler = NormalizationCompiler()
    plan = compiler.compile(config)
    executor = NormalizationExecutor()
    result_df = executor.execute(plan, df_csv_raw).collect()

    assert result_df["INSTRUMENT_NAME"].to_list() == [
        "Nippon India Growth Fund",
        "Mirae Asset Large Cap Fund",
    ]
    assert result_df["ISIN"].to_list() == ["INF204K01018", "INF769K01010"]
    assert result_df["artifact_id"].to_list() == ["art_isin", "art_isin"]


def test_equivalence_excel_us_stock_cleaning() -> None:
    """Verify NormalizationExecutor reproduces Excel US stock transaction cleaning."""
    df_excel_raw = pl.DataFrame(
        {
            "Trade Date": ["05-02-2026", "10-02-2026"],
            "Symbol": ["aapl", "msft"],
            "Quantity": ["10", "5"],
            "Price": ["230.50", "410.20"],
            "Gross Amount": ["2305.00", "2051.00"],
            "Currency": ["USD", "USD"],
            "artifact_id": ["art_us", "art_us"],
            "__file_name__": ["us_stocks.xlsx", "us_stocks.xlsx"],
            "__folder_path__": ["inputs", "inputs"],
        }
    )

    config = SourceDatasetConfig(
        source_id=SourceId("us_stocks_excel"),
        dataset_id=DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS,
        selector=ExcelSelector(sheet_name="Transactions"),
        mapping=[
            ColumnMapping(source_field="Trade Date", canonical_field="Trade Date"),
            ColumnMapping(source_field="Symbol", canonical_field="Symbol"),
            ColumnMapping(source_field="Quantity", canonical_field="Quantity"),
            ColumnMapping(source_field="Price", canonical_field="Price"),
            ColumnMapping(source_field="Gross Amount", canonical_field="Gross Amount"),
            ColumnMapping(source_field="Currency", canonical_field="Currency"),
        ],
        normalization=[
            ParseDateRule(field="Trade Date", format="%d-%m-%Y"),
            NormalizeCaseRule(field="Symbol", case="upper"),
            CastRule(field="Quantity", target_type="float64"),
            CastRule(field="Price", target_type="float64"),
            CastRule(field="Gross Amount", target_type="float64"),
        ],
    )

    compiler = NormalizationCompiler()
    plan = compiler.compile(config)
    executor = NormalizationExecutor()
    result_df = executor.execute(plan, df_excel_raw).collect()

    assert result_df["Trade Date"].to_list() == [
        datetime.date(2026, 2, 5),
        datetime.date(2026, 2, 10),
    ]
    assert result_df["Symbol"].to_list() == ["AAPL", "MSFT"]
    assert result_df["Quantity"].to_list() == [10.0, 5.0]
    assert result_df["Price"].to_list() == [230.50, 410.20]
    assert result_df["Gross Amount"].to_list() == [2305.00, 2051.00]
    assert result_df["artifact_id"].to_list() == ["art_us", "art_us"]
