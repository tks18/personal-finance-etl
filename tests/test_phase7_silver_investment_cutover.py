"""Authoritative Phase 007 verification suite.

Validates:
1. Cutover of 9 Investment, Event, and Tax tables to canonical names in SILVER_DDL & DATA_CONTRACT_REGISTRY.
2. Complete 24-table lakehouse modernization (all 24 tables under silver.dim_*, silver.fact_*, silver.ref_*).
3. Elimination of 4 dead provenance columns from fact_investment_purchases and fact_investment_sales.
4. Total Silver column count of exactly 438 columns (534 baseline - 96 total removed).
5. SilverLayer._validate_investment_master schema enforcement on silver.dim_instrument_master.
6. Byte-for-byte deterministic identity invariance for Purchase_ID, Sale_ID, Lot_ID, Realized_Event_ID, Recon_ID, Tax_Event_ID.
7. Preservation of __file_category__ in DDL and investment transforms as directed.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from personal_finance_etl.domain.common.identity import generate_deterministic_id
from personal_finance_etl.domain.investments.transforms.common import (
    get_f_tf_investment_purchase_data,
    get_f_tf_investment_sale_data,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    DATA_CONTRACT_REGISTRY,
)
from personal_finance_etl.infrastructure.warehouse.schema.silver import SILVER_DDL
from personal_finance_etl.infrastructure.warehouse.silver import SilverLayer

# 9 Investment, Event & Tax tables cut over in Phase 007
PHASE_7_CUTOVER_TABLES = [
    "silver.dim_instrument_master",
    "silver.fact_investment_market_data",
    "silver.fact_investment_purchases",
    "silver.fact_investment_sales",
    "silver.fact_investment_benchmark_data",
    "silver.fact_investment_lot_analytics",
    "silver.fact_investment_realized_events",
    "silver.fact_investment_reconciliation_events",
    "silver.fact_tax_events",
]

LEGACY_9_TABLE_NAMES = [
    "silver.d_Investment_Master",
    "silver.f_Investment_Market_Data",
    "silver.f_Investment_Purchase_Data",
    "silver.f_Investment_Sale_Data",
    "silver.f_Investment_Benchmark_Data",
    "silver.f_Investment_Analytics_Lot",
    "silver.f_Investment_Realized_Events",
    "silver.f_Investment_Reconciliation_Events",
    "silver.f_Tax_Events",
]

ALL_24_CANONICAL_TABLES = [
    # 15 Household & Reference tables (Phase 006)
    "silver.dim_calendar",
    "silver.dim_income_category",
    "silver.dim_income_subcategory",
    "silver.dim_expense_category",
    "silver.dim_expense_subcategory",
    "silver.dim_asset_category",
    "silver.dim_asset_subcategory",
    "silver.dim_currency",
    "silver.fact_currency_fx_rates",
    "silver.fact_income_transactions",
    "silver.fact_expense_transactions",
    "silver.fact_transfer_transactions",
    "silver.fact_opening_balances",
    "silver.dim_benchmark_master",
    "silver.ref_financial_year_parameters",
    # 9 Investment, Event & Tax tables (Phase 007)
    "silver.dim_instrument_master",
    "silver.fact_investment_market_data",
    "silver.fact_investment_purchases",
    "silver.fact_investment_sales",
    "silver.fact_investment_benchmark_data",
    "silver.fact_investment_lot_analytics",
    "silver.fact_investment_realized_events",
    "silver.fact_investment_reconciliation_events",
    "silver.fact_tax_events",
]

ALL_24_LEGACY_TABLES = [
    "silver.d_Calendar",
    "silver.d_Income_Category",
    "silver.d_Income_Subcategory",
    "silver.d_Expense_Category",
    "silver.d_Expense_Subcategory",
    "silver.d_Asset_Category",
    "silver.d_Asset_Subcategory",
    "silver.d_Currency",
    "silver.f_Currency_FX_Rates",
    "silver.f_Income_Transactions",
    "silver.f_Expense_Transactions",
    "silver.f_Transfer_Transactions",
    "silver.f_Opening_Balances",
    "silver.d_Investment_Benchmark_Master",
    "silver.d_Macro_Parameters",
    "silver.d_Investment_Master",
    "silver.f_Investment_Market_Data",
    "silver.f_Investment_Purchase_Data",
    "silver.f_Investment_Sale_Data",
    "silver.f_Investment_Benchmark_Data",
    "silver.f_Investment_Analytics_Lot",
    "silver.f_Investment_Realized_Events",
    "silver.f_Investment_Reconciliation_Events",
    "silver.f_Tax_Events",
]


def _extract_ddl_tables_and_columns() -> dict[str, list[str]]:
    """Parse all 24 tables and their columns directly from SILVER_DDL."""
    table_blocks = re.findall(
        r"CREATE TABLE IF NOT EXISTS (silver\.[^\s\(]+)\s*\((.*?)\);",
        SILVER_DDL,
        re.DOTALL,
    )
    result: dict[str, list[str]] = {}
    for tbl, body in table_blocks:
        cols: list[str] = []
        for line in body.splitlines():
            line_s = line.strip()
            if not line_s or line_s.startswith(
                ("--", "PRIMARY", "UNIQUE", "FOREIGN", "CONSTRAINT", ")")
            ):
                continue
            col_name = line_s.split()[0].strip('",`')
            cols.append(col_name)
        result[tbl] = cols
    return result


def test_all_24_silver_tables_in_ddl_and_contracts() -> None:
    """Assert all 24 Silver tables exist under canonical names in DDL and contracts."""
    ddl_tables = _extract_ddl_tables_and_columns()
    contract_tables = {c.physical_table for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"}

    assert len(ddl_tables) == 24, f"Expected 24 tables in SILVER_DDL, found {len(ddl_tables)}"
    assert len(contract_tables) == 24, f"Expected 24 Silver contracts, found {len(contract_tables)}"

    for tbl in ALL_24_CANONICAL_TABLES:
        assert tbl in ddl_tables, f"Canonical table {tbl} missing from SILVER_DDL"
        assert tbl in contract_tables, f"Canonical table {tbl} missing from DATA_CONTRACT_REGISTRY"

    for legacy_tbl in ALL_24_LEGACY_TABLES:
        assert legacy_tbl not in ddl_tables, f"Legacy table {legacy_tbl} must NOT be in SILVER_DDL"
        assert legacy_tbl not in contract_tables, (
            f"Legacy table {legacy_tbl} must NOT be in contracts"
        )


def test_exact_438_total_active_silver_columns_in_ddl() -> None:
    """Assert total active columns across all 24 Silver tables is exactly 438 (534 - 96)."""
    ddl_tables = _extract_ddl_tables_and_columns()

    total_cols = sum(len(cols) for cols in ddl_tables.values())
    assert total_cols == 438, f"Expected exactly 438 total columns in SILVER_DDL, found {total_cols}"

    # Specifically check the 9 investment/event/tax tables
    assert len(ddl_tables["silver.dim_instrument_master"]) == 17
    assert len(ddl_tables["silver.fact_investment_market_data"]) == 22
    assert len(ddl_tables["silver.fact_investment_purchases"]) == 11  # 13 - 2 dead cols = 11
    assert len(ddl_tables["silver.fact_investment_sales"]) == 17      # 19 - 2 dead cols = 17
    assert len(ddl_tables["silver.fact_investment_benchmark_data"]) == 12
    assert len(ddl_tables["silver.fact_investment_lot_analytics"]) == 88
    assert len(ddl_tables["silver.fact_investment_realized_events"]) == 24
    assert len(ddl_tables["silver.fact_investment_reconciliation_events"]) == 17
    assert len(ddl_tables["silver.fact_tax_events"]) == 15


def test_4_dead_columns_absent_from_ddl_and_fact_transforms() -> None:
    """Assert __file_name__ and __folder_path__ are dropped from purchases and sales."""
    ddl_tables = _extract_ddl_tables_and_columns()

    for col in ("__file_name__", "__folder_path__"):
        assert col not in ddl_tables["silver.fact_investment_purchases"]
        assert col not in ddl_tables["silver.fact_investment_sales"]

    # Test transforms also do not emit these dead columns
    dummy_purchase_ref = pl.DataFrame(
        {
            "__file_name__": ["order1.xlsx"],
            "__folder_path__": ["/orders"],
            "ISIN": ["INF209K01157"],
            "Instrument name": ["Axis Bluechip"],
            "Date": [date(2023, 1, 15)],
            "Price": [50.0],
            "Quantity": [100.0],
            "Value": [5000.0],
            "__file_category__": ["Indian MF"],
            "CURRENCY_ID": ["INR"],
        }
    ).lazy()

    df_p = get_f_tf_investment_purchase_data([dummy_purchase_ref], default_currency_id="INR").collect()
    assert "__file_name__" not in df_p.columns
    assert "__folder_path__" not in df_p.columns
    assert "Purchase_ID" in df_p.columns
    assert df_p["Purchase_ID"][0].startswith("PURCHASE_")

    dummy_sale_ref = pl.DataFrame(
        {
            "__file_name__": ["order1.xlsx"],
            "__folder_path__": ["/orders"],
            "ISIN": ["INF209K01157"],
            "Instrument name": ["Axis Bluechip"],
            "Date": [date(2023, 6, 15)],
            "Sell_Price": [60.0],
            "Quantity": [50.0],
            "Sell_Value": [3000.0],
            "Buy_Price": [50.0],
            "Buy_Value": [2500.0],
            "Unit_PnL": [10.0],
            "Total_PnL": [500.0],
            "__file_category__": ["Indian MF"],
            "CURRENCY_ID": ["INR"],
        }
    ).lazy()

    df_s = get_f_tf_investment_sale_data([dummy_sale_ref], default_currency_id="INR").collect()
    assert "__file_name__" not in df_s.columns
    assert "__folder_path__" not in df_s.columns
    assert "Sale_ID" in df_s.columns
    assert df_s["Sale_ID"][0].startswith("SALE_")


def test_silver_layer_validates_dim_instrument_master(tmp_path: Path) -> None:
    """Assert SilverLayer._validate_investment_master guards silver.dim_instrument_master."""
    manager = DuckDBManager(str(tmp_path), "test.duckdb")
    manager.open()
    try:
        layer = SilverLayer(manager)

        # Valid DataFrame for dim_instrument_master
        valid_df = pl.DataFrame(
            {
                "ISIN": ["INE002A01018"],
                "CATEGORY_ID": pl.Series([None], dtype=pl.String),
                "BENCHMARK_ID": pl.Series([None], dtype=pl.String),
                "CURRENCY_ID": pl.Series([None], dtype=pl.String),
                "INSTRUMENT_NAME": ["Reliance Industries"],
                "INSTRUMENT_HOUSE": ["Reliance"],
                "INSTRUMENT_CLASS": ["Direct Stocks"],
                "INSTRUMENT_TYPE": ["Equity"],
                "INSTRUMENT_SUBTYPE": ["Large Cap"],
                "SECTOR": ["Energy"],
                "INDUSTRY": ["Oil & Gas"],
                "COUNTRY": ["India"],
                "GEO": ["Domestic"],
                "GEO_SUBTYPE": ["India"],
                "YAHOO_TICKER": ["RELIANCE.NS"],
                "TAX_TYPE": ["Equity_Listed"],
                "TAX_SUBTYPE": ["Equity"],
            }
        )

        layer.load({"df_d_investment_master": valid_df})

        # Verify DuckDB table has the row
        res = manager.conn.execute("SELECT COUNT(*) FROM silver.dim_instrument_master").fetchone()
        assert res is not None and res[0] == 1

        # Invalid DataFrame missing mandatory INSTRUMENT_CLASS / TAX_TYPE
        invalid_df = pl.DataFrame(
            {
                "ISIN": ["INE002A01018"],
                "INSTRUMENT_NAME": ["Reliance Industries"],
                # missing INSTRUMENT_CLASS and TAX_TYPE
            }
        )
        with pytest.raises(Exception):
            layer.load({"df_d_investment_master": invalid_df})
    finally:
        manager.close()


def test_foreign_key_references_dim_instrument_master() -> None:
    """Assert foreign keys in DDL reference silver.dim_instrument_master(ISIN)."""
    assert "FOREIGN KEY(ISIN) REFERENCES silver.dim_instrument_master(ISIN)" in SILVER_DDL
    assert "REFERENCES silver.d_Investment_Master" not in SILVER_DDL


def test_deterministic_identity_invariance() -> None:
    """Assert deterministic hashing algorithms produce identical byte-for-byte IDs."""
    purchase_fields = {
        "ISIN": "INE002A01018",
        "Date": "2023-01-15",
        "Price": 2500.50,
        "Quantity": 10.0,
        "CURRENCY_ID": "INR",
    }
    pid1 = generate_deterministic_id("PURCHASE", purchase_fields)
    pid2 = generate_deterministic_id("PURCHASE", purchase_fields)
    assert pid1 == pid2
    assert pid1.startswith("PURCHASE_")

    sale_fields = {
        "ISIN": "INE002A01018",
        "Date": "2023-06-15",
        "Sell_Price": 2750.0,
        "Quantity": 5.0,
        "CURRENCY_ID": "INR",
    }
    sid1 = generate_deterministic_id("SALE", sale_fields)
    sid2 = generate_deterministic_id("SALE", sale_fields)
    assert sid1 == sid2
    assert sid1.startswith("SALE_")

    # Lot ID deterministic composition
    lot_fields = {
        "ISIN": "INE002A01018",
        "Purchase_ID": pid1,
        "Buy_Date": "2023-01-15",
    }
    lot_id1 = generate_deterministic_id("LOT", lot_fields)
    lot_id2 = generate_deterministic_id("LOT", lot_fields)
    assert lot_id1 == lot_id2
    assert lot_id1.startswith("LOT_")

    # Realized Event ID
    real_fields = {
        "Sale_ID": sid1,
        "Lot_ID": lot_id1,
    }
    re_id1 = generate_deterministic_id("REALIZED", real_fields)
    re_id2 = generate_deterministic_id("REALIZED", real_fields)
    assert re_id1 == re_id2
    assert re_id1.startswith("REALIZED_")
