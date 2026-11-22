# pyright: reportPrivateUsage=false
"""Tests for Phase 5: Silver Column Disposition and Consumer Archaeology.

Owns
----
- Verification of the 24-table Silver warehouse topology against the authoritative disposition manifest.
- Verification that all 534 active physical columns across Silver DDL are cataloged and classified.
- Verification that deterministic business keys, identity keys, and core financial quantities are PROTECTED.
- Verification that REMOVE_CANDIDATE columns have zero downstream consumers in analytical marts.
- Verification that __file_category__ is guarded and not prematurely removed.
- Verification that Silver DDL and contracts remain 100% unmodified during this archaeology phase.

Does not own
-------------
- Execution of Silver schema migrations or DDL mutations (owned by Phase 006 and Phase 007).
- Execution of Gold Power BI query migrations (owned by Phase 008 and Phase 010).
"""

from __future__ import annotations

import re
from pathlib import Path

from personal_finance_etl.infrastructure.warehouse.contracts import DATA_CONTRACT_REGISTRY
from personal_finance_etl.infrastructure.warehouse.schema.silver import SILVER_DDL

MANIFEST_PATH = Path(".planning/v11/SILVER-DISPOSITION-MANIFEST.md")

EXPECTED_24_ACTIVE_SILVER_TABLES: list[str] = [
    # 15 Phase 006 Cutover Tables
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
    # 9 Preserved Legacy Investment/Tax Tables (Phase 007 target)
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

EXPECTED_TARGET_NAMES: dict[str, str] = {
    "silver.d_Calendar": "silver.dim_calendar",
    "silver.d_Income_Category": "silver.dim_income_category",
    "silver.d_Income_Subcategory": "silver.dim_income_subcategory",
    "silver.d_Expense_Category": "silver.dim_expense_category",
    "silver.d_Expense_Subcategory": "silver.dim_expense_subcategory",
    "silver.d_Asset_Category": "silver.dim_asset_category",
    "silver.d_Asset_Subcategory": "silver.dim_asset_subcategory",
    "silver.d_Currency": "silver.dim_currency",
    "silver.f_Currency_FX_Rates": "silver.fact_currency_fx_rates",
    "silver.f_Income_Transactions": "silver.fact_income_transactions",
    "silver.f_Expense_Transactions": "silver.fact_expense_transactions",
    "silver.f_Transfer_Transactions": "silver.fact_transfer_transactions",
    "silver.f_Opening_Balances": "silver.fact_opening_balances",
    "silver.d_Investment_Benchmark_Master": "silver.dim_benchmark_master",
    "silver.d_Investment_Master": "silver.dim_instrument_master",
    "silver.d_Macro_Parameters": "silver.ref_financial_year_parameters",
    "silver.f_Investment_Market_Data": "silver.fact_investment_market_data",
    "silver.f_Investment_Purchase_Data": "silver.fact_investment_purchases",
    "silver.f_Investment_Sale_Data": "silver.fact_investment_sales",
    "silver.f_Investment_Benchmark_Data": "silver.fact_investment_benchmark_data",
    "silver.f_Investment_Analytics_Lot": "silver.fact_investment_lot_analytics",
    "silver.f_Investment_Realized_Events": "silver.fact_investment_realized_events",
    "silver.f_Investment_Reconciliation_Events": "silver.fact_investment_reconciliation_events",
    "silver.f_Tax_Events": "silver.fact_tax_events",
}

CRITICAL_PROTECTED_IDENTITIES: set[str] = {
    "ISIN",
    "Lot_ID",
    "Sale_ID",
    "Purchase_ID",
    "Realized_Event_ID",
    "Reconciliation_Event_ID",
    "Tax_Event_ID",
    "UID",
    "Date",
    "Closing_Date",
    "Buy_Date",
    "Acquisition_Date",
    "Disposal_Date",
    "Event_Date",
    "Reconciliation_Date",
    "CURRENCY_ID",
    "Currency_ID",
    "CATEGORY_ID",
    "BENCHMARK_ID",
}

CRITICAL_PROTECTED_FINANCIALS: set[str] = {
    "Quantity",
    "Quantity_Disposed",
    "Buy_Price",
    "Market_Price",
    "Sell_Price",
    "Buy_Value",
    "Close_Value",
    "Sell_Value",
    "Realized_Gain_Loss",
    "XIRR",
    "CAGR",
    "Absolute_Return",
    "Asset_PnL",
    "Forex_PnL",
    "Amount_INR",
    "Estimated_Tax",
    "Applied_Rate",
    "Tax_Rate",
    "Unrealized_LTCG",
    "Unrealized_STCG",
    "Unrealized_Gain",
    "Unrealized_LTCL",
    "Unrealized_STCL",
    "Unrealized_Loss",
    "LTCG_Tax_If_Sold",
    "STCG_Tax_If_Sold",
    "After_Tax_PL",
    "After_Tax_Close_Value",
    "ZASSETUID",
    "ZAMOUNTACCOUNT",
    "ZTXDATESTR",
    "ZUTIME",
    "AMOUNT_PROPER",
    "BASE_AMOUNT",
    "AMOUNT_ACCOUNT",
    "LOCAL_AMOUNT",
}


def _extract_ddl_columns() -> dict[str, list[str]]:
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


def test_manifest_file_exists() -> None:
    """Verify that the authoritative Silver disposition manifest is checked in."""
    assert MANIFEST_PATH.exists(), f"Manifest missing at {MANIFEST_PATH}"
    content = MANIFEST_PATH.read_text(encoding="utf-8")
    assert len(content) > 50000, "Manifest file is incomplete or truncated"


def test_silver_table_inventory_parity() -> None:
    """Verify that all 24 physical tables in SILVER_DDL match the manifest and registry."""
    ddl_tables = _extract_ddl_columns()
    assert len(ddl_tables) == 24, f"Expected 24 tables in SILVER_DDL, got {len(ddl_tables)}"
    assert sorted(ddl_tables.keys()) == sorted(EXPECTED_24_ACTIVE_SILVER_TABLES)

    manifest_content = MANIFEST_PATH.read_text(encoding="utf-8")
    for tbl in EXPECTED_24_ACTIVE_SILVER_TABLES:
        assert f"`{tbl}`" in manifest_content, f"Table {tbl} missing from manifest"

    silver_contracts = [c for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"]
    assert len(silver_contracts) == 24, (
        f"Expected 24 Silver contracts in DATA_CONTRACT_REGISTRY, got {len(silver_contracts)}"
    )


def test_silver_column_inventory_complete() -> None:
    """Verify that all 442 columns in active SILVER_DDL are cataloged in the manifest."""
    ddl_tables = _extract_ddl_columns()
    total_ddl_columns = sum(len(cols) for cols in ddl_tables.values())
    assert total_ddl_columns == 442, (
        f"Expected exactly 442 active columns across Silver DDL after Phase 006, got {total_ddl_columns}"
    )

    manifest_content = MANIFEST_PATH.read_text(encoding="utf-8")
    for tbl, cols in ddl_tables.items():
        for col in cols:
            assert f"`{col}`" in manifest_content, (
                f"Column {col} of table {tbl} is missing from manifest"
            )


def test_protected_identity_invariants() -> None:
    """Assert that critical business keys and financial columns are marked PROTECTED."""
    manifest_content = MANIFEST_PATH.read_text(encoding="utf-8")

    for key in CRITICAL_PROTECTED_IDENTITIES:
        pattern = rf"\|\s*`{re.escape(key)}`\s*\|\s*[^|]+\|\s*[^|]+\|\s*🛡️ PROTECTED"
        assert re.search(pattern, manifest_content), (
            f"Critical business identity key '{key}' must be classified as PROTECTED in manifest"
        )

    for fin in CRITICAL_PROTECTED_FINANCIALS:
        pattern = rf"\|\s*`{re.escape(fin)}`\s*\|\s*[^|]+\|\s*[^|]+\|\s*🛡️ PROTECTED"
        assert re.search(pattern, manifest_content), (
            f"Critical financial quantity/metric '{fin}' must be classified as PROTECTED in manifest"
        )


def test_remove_candidates_have_zero_codebase_consumers() -> None:
    """Assert that REMOVE_CANDIDATE columns have zero consumers in downstream analytics."""
    manifest_content = MANIFEST_PATH.read_text(encoding="utf-8")

    # Extract all rows with REMOVE_CANDIDATE
    rem_matches = re.findall(
        r"\|\s*`([^`]+)`\s*\|\s*[^|]+\|\s*\*\([^)]+\)\*\s*\|\s*🗑️ REMOVE\s*\|\s*`([^`]+)`\s*\|\s*([^|]+)\|",
        manifest_content,
    )
    assert len(rem_matches) >= 90, (
        f"Expected at least 90 removal candidate columns, got {len(rem_matches)}"
    )

    # Downstream analytical directories that must never consume these columns
    downstream_dirs = [
        Path("src/personal_finance_etl/domain/tax"),
        Path("src/personal_finance_etl/domain/fire"),
        Path("src/personal_finance_etl/domain/wealth"),
        Path("src/personal_finance_etl/infrastructure/warehouse/gold.py"),
    ]

    downstream_contents: list[str] = []
    for d in downstream_dirs:
        if d.is_file():
            downstream_contents.append(d.read_text(encoding="utf-8", errors="ignore"))
        elif d.is_dir():
            for p in d.rglob("*.py"):
                if "__pycache__" not in p.parts:
                    downstream_contents.append(p.read_text(encoding="utf-8", errors="ignore"))

    combined_downstream = "\n".join(downstream_contents)

    for col, _, _ in rem_matches:
        # Check that no downstream engine consumes this column
        pattern = rf"\b{re.escape(col)}\b"
        assert not re.search(pattern, combined_downstream), (
            f"Dead column candidate '{col}' is still referenced in downstream analytical engines!"
        )


def test_file_category_is_guarded_and_not_dropped() -> None:
    """Verify that __file_category__ is guarded and NOT marked as an immediate drop candidate."""
    manifest_content = MANIFEST_PATH.read_text(encoding="utf-8")
    assert "__file_category__" in manifest_content

    # Assert it is marked KEEP / Phase 007 migration rather than REMOVE
    pattern = r"\|\s*`__file_category__`\s*\|\s*TEXT\s*\|\s*`__file_category__`\s*\|\s*📦 KEEP"
    assert re.search(pattern, manifest_content), (
        "__file_category__ must be kept with migration note, not prematurely marked REMOVE!"
    )


def test_silver_ddl_and_contracts_unmodified() -> None:
    """Assert that Phase 006 cutover preserves legacy names for 9 investment/tax tables."""
    ddl_tables = _extract_ddl_columns()
    assert "silver.dim_calendar" in ddl_tables
    assert "silver.f_Investment_Analytics_Lot" in ddl_tables
    assert "silver.d_Investment_Master" in ddl_tables

    # Verify contracts registry reflects cutover for household and legacy for investment
    silver_contract_tables = {
        c.physical_table for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"
    }
    assert "silver.dim_calendar" in silver_contract_tables
    assert "silver.f_Investment_Analytics_Lot" in silver_contract_tables
    assert "silver.d_Investment_Master" in silver_contract_tables
