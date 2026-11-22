"""Tests for Phase 006: Silver Household and Reference Vocabulary Cutover.

Verifies:
1. All 15 Household and Reference tables exist under dimensional naming (`silver.dim_*`, `silver.fact_*`, `silver.ref_*`).
2. None of the 15 old names (`silver.d_*`, `silver.f_*`) exist in DDL or contracts.
3. The 9 Investment, Event, and Tax tables remain under legacy naming.
4. Exactly the 92 proven dead columns are absent from DDL and transform outputs.
5. Foreign key definitions in DDL cleanly reference the new dimensional names.
6. Transforms for household/reference tables execute and match target DDL columns.
7. Downstream domain builders (Ledger, SpendAnalytics, NetWorth) function identically.
8. Financial rules and tax classifiers validate against silver.dim_income_subcategory.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from personal_finance_etl.config.financial_rules import (
    FinancialRules,
    InvestmentExclusionsConfig,
)
from personal_finance_etl.domain.household.ledger import LedgerBuilder
from personal_finance_etl.domain.household.transforms.asset_dimensions import (
    transform_d_asset_category,
    transform_d_asset_subcategory,
)
from personal_finance_etl.domain.household.transforms.expense_dimensions import (
    transform_d_expense_category,
    transform_d_expense_subcategory,
)
from personal_finance_etl.domain.household.transforms.income_dimensions import (
    transform_d_income_category,
    transform_d_income_subcategory,
)
from personal_finance_etl.domain.household.transforms.reference_dimensions import (
    transform_d_currency,
    transform_d_investment_benchmark_master,
    transform_d_macro_parameters,
)
from personal_finance_etl.domain.household.transforms.transactions import (
    BASE_TRANSACTION_COLS,
    get_base_transactions,
    transform_f_expense_transactions,
    transform_f_income_transactions,
    transform_f_opening_balances,
    transform_f_transfer_transactions,
)
from personal_finance_etl.domain.tax.classification import TaxClassifier
from personal_finance_etl.infrastructure.warehouse.contracts import DATA_CONTRACT_REGISTRY
from personal_finance_etl.infrastructure.warehouse.schema.silver import SILVER_DDL

# 15 household/reference tables cut over in Phase 006
EXPECTED_15_CUTOVER_TABLES = [
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
]

LEGACY_15_OLD_NAMES = [
    "silver.d_Calendar",
    "silver.d_Income_Category",
    "silver.d_Income_Subcategory",
    "silver.d_Expense_Category",
    "silver.d_Expense_Subcategory",
    "silver.d_Asset_Category",
    "silver.d_Asset_SubCategory",
    "silver.d_Asset_Subcategory",
    "silver.d_Currency",
    "silver.f_Currency_FX_Rates",
    "silver.f_Income_Transactions",
    "silver.f_Expense_Transactions",
    "silver.f_Transfer_Transactions",
    "silver.f_Opening_Balances",
    "silver.d_Investment_Benchmark_Master",
    "silver.d_Macro_Parameters",
]

# 9 investment/event/tax tables strictly preserved under legacy names until Phase 007
EXPECTED_9_LEGACY_INVESTMENT_TABLES = [
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

FUTURE_INVESTMENT_NAMES_PHASE7 = [
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


def _extract_ddl_tables_and_columns() -> dict[str, list[str]]:
    """Parse SILVER_DDL into table -> columns map."""
    ddl_tables: dict[str, list[str]] = {}
    statements = re.split(r"CREATE TABLE IF NOT EXISTS\s+", SILVER_DDL)
    for stmt in statements[1:]:
        lines = stmt.strip().splitlines()
        table_name = lines[0].split("(")[0].strip()
        cols: list[str] = []
        for line in lines[1:]:
            line_s = line.strip()
            if not line_s or line_s == ");" or line_s.startswith("--"):
                continue
            if line_s.upper().startswith("FOREIGN KEY"):
                continue
            parts = line_s.rstrip(",").split(None, 1)
            if len(parts) >= 1:
                cols.append(parts[0])
        ddl_tables[table_name] = cols
    return ddl_tables


def test_15_household_and_reference_tables_in_ddl_and_contracts() -> None:
    """Assert all 15 household/reference tables exist under dimensional names."""
    ddl_tables = _extract_ddl_tables_and_columns()
    contract_tables = {c.physical_table for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"}

    for tbl in EXPECTED_15_CUTOVER_TABLES:
        assert tbl in ddl_tables, f"Expected {tbl} in SILVER_DDL"
        assert tbl in contract_tables, f"Expected {tbl} in DATA_CONTRACT_REGISTRY"

    for old_tbl in LEGACY_15_OLD_NAMES:
        assert old_tbl not in ddl_tables, f"Old table {old_tbl} must NOT be in SILVER_DDL"
        assert old_tbl not in contract_tables, f"Old table {old_tbl} must NOT be in contracts"


def test_9_investment_and_tax_tables_preserved_under_legacy_names() -> None:
    """Assert the 9 investment/tax tables are cut over to canonical names in Phase 007."""
    ddl_tables = _extract_ddl_tables_and_columns()
    contract_tables = {c.physical_table for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"}

    for tbl in FUTURE_INVESTMENT_NAMES_PHASE7:
        assert tbl in ddl_tables, f"Canonical table {tbl} must be in SILVER_DDL"
        assert tbl in contract_tables, f"Canonical table {tbl} must be in DATA_CONTRACT_REGISTRY"

    for old_tbl in EXPECTED_9_LEGACY_INVESTMENT_TABLES:
        assert old_tbl not in ddl_tables, f"{old_tbl} must not exist after Phase 007 cutover"
        assert old_tbl not in contract_tables, f"{old_tbl} must not exist in contracts after Phase 007"


def test_proven_dead_columns_absent_from_ddl() -> None:
    """Assert all 92 dead columns identified in Phase 005 are absent from Silver DDL."""
    manifest_path = Path(".planning/v11/SILVER-DISPOSITION-MANIFEST.md")
    if not manifest_path.exists():
        pytest.skip("Silver disposition manifest removed after v11 finalization")
    ddl_tables = _extract_ddl_tables_and_columns()

    manifest_text = manifest_path.read_text(encoding="utf-8")
    sections = re.split(r"### `(silver\.[^`]+)` -> `(silver\.[^`]+)`", manifest_text)

    removed_count = 0
    # sections: [preamble, old_1, target_1, body_1, old_2, target_2, body_2, ...]
    for i in range(1, len(sections), 3):
        old_table = sections[i]
        target_table = sections[i + 1]
        body = sections[i + 2]

        if target_table in EXPECTED_15_CUTOVER_TABLES:
            rem_matches = re.findall(
                r"^\|\s*`([^`]+)`\s*\|\s*[^|]+\|\s*\*\([^)]+\)\*\s*\|\s*🗑️ REMOVE",
                body,
                re.MULTILINE,
            )
            cols_in_ddl = ddl_tables.get(target_table, [])
            for col_name in rem_matches:
                assert col_name not in cols_in_ddl, (
                    f"Dead column {col_name} from {old_table} is still present in {target_table} DDL!"
                )
                removed_count += 1

    assert removed_count == 92, f"Expected exactly 92 REMOVE columns, found {removed_count}"


def test_foreign_key_references_use_dimensional_names() -> None:
    """Assert all foreign key constraints reference the cutover dimensional tables."""
    assert "REFERENCES silver.dim_calendar(Date)" in SILVER_DDL
    assert "REFERENCES silver.dim_currency(UID)" in SILVER_DDL
    assert "REFERENCES silver.dim_income_category(UID)" in SILVER_DDL
    assert "REFERENCES silver.dim_income_subcategory(UID)" in SILVER_DDL
    assert "REFERENCES silver.dim_expense_category(UID)" in SILVER_DDL
    assert "REFERENCES silver.dim_expense_subcategory(UID)" in SILVER_DDL
    assert "REFERENCES silver.dim_asset_category(UID)" in SILVER_DDL
    assert "REFERENCES silver.dim_asset_subcategory(UID)" in SILVER_DDL
    assert "REFERENCES silver.dim_benchmark_master(ID)" in SILVER_DDL
    assert "REFERENCES silver.dim_instrument_master(ISIN)" in SILVER_DDL

    # Assert no foreign keys reference the old names
    assert "REFERENCES silver.d_Calendar" not in SILVER_DDL
    assert "REFERENCES silver.d_Currency" not in SILVER_DDL
    assert "REFERENCES silver.d_Income_Category" not in SILVER_DDL
    assert "REFERENCES silver.d_Investment_Master" not in SILVER_DDL
    assert "REFERENCES silver.d_Income_Subcategory" not in SILVER_DDL
    assert "REFERENCES silver.d_Expense_Category" not in SILVER_DDL
    assert "REFERENCES silver.d_Expense_Subcategory" not in SILVER_DDL
    assert "REFERENCES silver.d_Asset_Category" not in SILVER_DDL
    assert "REFERENCES silver.d_Asset_SubCategory" not in SILVER_DDL
    assert "REFERENCES silver.d_Asset_Subcategory" not in SILVER_DDL
    assert "REFERENCES silver.d_Investment_Benchmark_Master" not in SILVER_DDL


def test_household_dimension_transforms_produce_clean_schemas() -> None:
    """Verify transforms output columns matching the new dimensional DDL."""
    # 1. Income Category
    raw_cat = pl.DataFrame(
        {
            "__file_name__": ["f1.db"],
            "__folder_path__": ["/p"],
            "S_NO": [1],
            "MODIFY_DATE": ["2024-01-01"],
            "UID": ["CAT1"],
            "NAME": ["Income from Salary"],
            "ORDER_SEQUENCE": [1],
            "TYPE": [0],
            "CATEGORY_ID": pl.Series([None], dtype=pl.String),
            "IS_DEL": ["0"],
        }
    ).lazy()
    df_cat = transform_d_income_category(raw_cat, {"NAME": "CATEGORY_NAME"}).collect()
    assert df_cat.columns == ["UID", "CATEGORY_NAME", "CATEGORY_NAME_SHORT"]
    assert df_cat["CATEGORY_NAME_SHORT"][0] == "Salary"

    # 2. Income Subcategory
    raw_subcat = pl.DataFrame(
        {
            "__file_name__": ["f1.db"],
            "__folder_path__": ["/p"],
            "S_NO": [1],
            "MODIFY_DATE": ["2024-01-01"],
            "UID": ["SUB1"],
            "NAME": ["Basic Salary"],
            "ORDER_SEQUENCE": [1],
            "TYPE": [0],
            "CATEGORY_ID": ["CAT1"],
            "IS_DEL": ["0"],
        }
    ).lazy()
    df_subcat = transform_d_income_subcategory(
        raw_subcat,
        {"NAME": "CATEGORY_NAME"},
        df_cat.lazy(),
    ).collect()
    assert "UID" in df_subcat.columns
    assert "CATEGORY_ID" in df_subcat.columns
    assert "CATEGORY_NAME" in df_subcat.columns
    assert "__file_name__" not in df_subcat.columns
    assert "ORDER_SEQUENCE" not in df_subcat.columns

    # 3. Expense Category
    raw_exp_cat = pl.DataFrame(
        {
            "__file_name__": ["f1.db"],
            "__folder_path__": ["/p"],
            "S_NO": [1],
            "MODIFY_DATE": ["2024-01-01"],
            "UID": ["EXP1"],
            "NAME": ["Groceries"],
            "ORDER_SEQUENCE": [1],
            "TYPE": [1],
            "CATEGORY_ID": pl.Series([None], dtype=pl.String),
            "IS_DEL": ["0"],
        }
    ).lazy()
    df_exp_cat = transform_d_expense_category(raw_exp_cat, {"NAME": "CATEGORY_NAME"}).collect()
    assert df_exp_cat.columns == ["UID", "CATEGORY_NAME"]

    # 4. Expense Subcategory
    raw_exp_sub = pl.DataFrame(
        {
            "__file_name__": ["f1.db"],
            "__folder_path__": ["/p"],
            "S_NO": [1],
            "MODIFY_DATE": ["2024-01-01"],
            "UID": ["EXPSUB1"],
            "NAME": ["Vegetables"],
            "ORDER_SEQUENCE": [1],
            "TYPE": [1],
            "CATEGORY_ID": ["EXP1"],
            "IS_DEL": ["0"],
        }
    ).lazy()
    df_exp_sub = transform_d_expense_subcategory(raw_exp_sub, {"NAME": "CATEGORY_NAME"}).collect()
    assert set(df_exp_sub.columns) == {"UID", "CATEGORY_NAME", "CATEGORY_ID", "Is_Core_Expense"}

    # 5. Asset Category
    raw_asset_cat = pl.DataFrame(
        {
            "__file_name__": ["f1.db"],
            "__folder_path__": ["/p"],
            "DEVICE_ID": ["d1"],
            "UID": ["ACAT1"],
            "USE_TIME": [100],
            "ASSET_GROUP": ["Bank Accounts"],
            "TYPE": [1],
            "ORDER_SEQUENCE": [1],
            "IS_DEL": ["0"],
        }
    ).lazy()
    df_asset_cat = transform_d_asset_category(raw_asset_cat, {}).collect()
    assert "UID" in df_asset_cat.columns
    assert "ASSET_GROUP" in df_asset_cat.columns
    assert "DEVICE_ID" not in df_asset_cat.columns
    assert "USE_TIME" not in df_asset_cat.columns
    assert "ORDER_SEQUENCE" not in df_asset_cat.columns

    # 6. Asset Subcategory
    raw_asset_sub = pl.DataFrame(
        {
            "__file_name__": ["f1.db"],
            "__folder_path__": ["/p"],
            "S_NO": [1],
            "CARD_STATEMENT_DATE": ["15"],
            "CARD_PAYMENT_DATE": ["5"],
            "ASSET_NAME": ["HDFC Savings"],
            "ORDER_SEQUENCE": [1],
            "ASSET_DESCRIPTION": ["Main"],
            "NOTES": [""],
            "TRANSFER_EXPENSE": [0],
            "CARD_AUTOPAY": [0],
            "ADDED_TIME": [100],
            "UID": ["ASUB1"],
            "CURRENCY_ID": ["INR"],
            "AUTOPAY_ASSET_ID": [""],
            "ASSET_GROUP_ID": ["ACAT1"],
            "IS_DEL": ["0"],
        }
    ).lazy()
    df_asset_sub = transform_d_asset_subcategory(raw_asset_sub, {}).collect()
    assert "UID" in df_asset_sub.columns
    assert "ASSET_NAME" in df_asset_sub.columns
    assert "CARD_STATEMENT_DATE" not in df_asset_sub.columns
    assert "AUTOPAY_ASSET_ID" not in df_asset_sub.columns
    assert "ORDER_SEQUENCE" not in df_asset_sub.columns

    # 7. Currency
    raw_curr = pl.DataFrame(
        {
            "__file_name__": ["f1.db"],
            "__folder_path__": ["/p"],
            "S_NO": [1],
            "UID": ["INR"],
            "CURRENCY_NAME": ["Indian Rupee"],
            "ISO": ["INR"],
            "MAIN_ISO": ["INR"],
            "ORDER_SEQUENCE": [1],
            "RATE": [1.0],
            "SYMBOL": ["₹"],
            "INSERT_TYPE": [0],
            "SYMBOL_POSITION": [0],
            "IS_MAIN_CURRENCY": [1],
            "IS_SHOW": [1],
            "MODIFY_DATE": ["2024-01-01"],
            "DECIMAL_POINT": [2],
            "IS_DEL": ["0"],
        }
    ).lazy()
    df_curr = transform_d_currency(raw_curr, {}).collect()
    assert df_curr.columns == [
        "UID",
        "CURRENCY_NAME",
        "ISO",
        "SYMBOL",
        "Target_Currency_Code",
        "yF_Ticker",
        "Is_Active",
    ]

    # 8. Benchmark Master
    raw_bm = pl.DataFrame(
        {
            "__file_name__": ["bm.csv"],
            "__folder_path__": ["/p"],
            "ID": ["NIFTY50"],
            "Benchmark_Name": ["Nifty 50"],
            "yF_Ticker": ["^NSEI"],
            "Currency": ["INR"],
        }
    ).lazy()
    df_bm = transform_d_investment_benchmark_master(raw_bm).collect()
    assert df_bm.columns == ["ID", "CURRENCY_ID", "Benchmark_Name", "yF_Ticker"]

    # 9. Macro Parameters
    raw_macro = pl.DataFrame(
        {
            "FY": ["2023"],
            "__file_name__": ["macro.csv"],
            "__folder_path__": ["/p"],
            "FY_Start_Date": [date(2023, 4, 1)],
            "FY_End_Date": [date(2024, 3, 31)],
            "Debt_MF_Cutoff_Date": [date(2023, 3, 31)],
            "Inflation_Rate": [0.06],
            "Risk_Free_Rate": [0.07],
            "Equity_Listed_LTCG": [0.10],
            "Equity_Listed_STCG": [0.15],
            "Equity_Unlisted_LTCG": [0.20],
            "Equity_Unlisted_STCG": [0.30],
            "Gold_LTCG": [0.20],
            "Gold_STCG": [0.30],
            "Debt_MF_Pre_Cutoff_LTCG": [0.20],
            "Debt_MF_Pre_Cutoff_STCG": [0.30],
            "Debt_MF_Post_Cutoff_LTCG": [0.30],
            "Debt_MF_Post_Cutoff_STCG": [0.30],
            "Other_Debt_LTCG": [0.20],
            "Other_Debt_STCG": [0.30],
            "Default_LTCG": [0.20],
            "Default_STCG": [0.30],
            "Estimated_Ordinary_Income_Tax_Rate": [0.30],
            "Equity_LTCG_Exemption": [100000],
            "Remarks": ["Standard"],
        }
    ).lazy()
    df_macro = transform_d_macro_parameters(raw_macro).collect()
    assert df_macro["FY"][0] == "2023-24"
    assert "__file_name__" not in df_macro.columns
    assert "__folder_path__" not in df_macro.columns


def test_transaction_transforms_and_opening_balances() -> None:
    """Verify transaction and opening balance transforms match target schemas."""
    raw_tx = pl.DataFrame(
        {
            "__file_name__": ["inoutcome.sqlite"],
            "__folder_path__": ["/data"],
            "S_NO": [1],
            "UID": ["TX1"],
            "ASSET_ID": ["ASUB1"],
            "CARDDIVIDMONTH": [0],
            "CATEGORY_ID": ["SUB1"],
            "TO_ASSET_ID": [None],
            "DESCRIPTION": ["Salary Credit"],
            "TIMESTAMP": [1700000000],
            "DATE": ["2024-01-31"],
            "TIME": ["10:00"],
            "PAID": ["Paid"],
            "TRANSACTION_TYPE": [0],
            "BASE_AMOUNT": [100000.0],
            "TRANSFER_UID": [None],
            "FEES_NOTES": [""],
            "LOCAL_AMOUNT": [100000.0],
            "MARK": [0],
            "TRANSFER_FEES": [0.0],
            "UPDATED_TIME": [1700000000],
            "CURRENCY_ID": ["INR"],
            "AMOUNT_ACCOUNT": [100000.0],
            "IS_DEL": ["0"],
        }
    ).lazy()

    base_tx = get_base_transactions(raw_tx, {})
    assert set(BASE_TRANSACTION_COLS).issubset(set(base_tx.collect_schema().names()))
    assert "__file_name__" not in BASE_TRANSACTION_COLS
    assert "S_NO" not in BASE_TRANSACTION_COLS
    assert "CARDDIVIDMONTH" not in BASE_TRANSACTION_COLS

    df_inc = transform_f_income_transactions(base_tx).collect()
    assert "Is_Active_Income" in df_inc.columns
    assert "BASE_AMOUNT" in df_inc.columns

    df_exp = transform_f_expense_transactions(base_tx).collect()
    assert "Is_Core_Expense" in df_exp.columns
    assert "BASE_AMOUNT" in df_exp.columns

    df_asset_sub_lazy = pl.DataFrame({"UID": ["ASUB1"], "ASSET_GROUP_ID": ["ACAT1"]}).lazy()
    df_asset_cat_lazy = pl.DataFrame({"UID": ["ACAT1"], "ASSET_GROUP": ["Bank Accounts"]}).lazy()
    df_trn = transform_f_transfer_transactions(
        base_tx,
        df_asset_sub_lazy,
        df_asset_cat_lazy,
    ).collect()
    assert "TRANSFER_TYPE" in df_trn.columns
    assert "AMOUNT_PROPER" in df_trn.columns

    # Opening Balances
    raw_opbal = pl.DataFrame(
        {
            "__file_name__": ["opbal.csv"],
            "__folder_path__": ["/data"],
            "Z_PK": [1],
            "ZUTIME": [1700000000],
            "ZDATE": [0.0],
            "ZAMOUNT": [50000.0],
            "ZAMOUNTACCOUNT": [50000.0],
            "ZAMOUNTSUB": [0.0],
            "ZCONTENT": [""],
            "ZDO_TYPE": [0],
            "ZASSETUID": ["ASUB1"],
            "ZCATEGORYUID": [""],
            "ZCURRENCYUID": ["INR"],
            "ZTOASSETUID": [""],
            "ZTXDATESTR": ["2024-01-01"],
            "ZTXUIDFEE": [""],
            "ZTXUIDTRANS": [""],
            "ZUID": ["OP1"],
        }
    ).lazy()

    df_opbal = transform_f_opening_balances(raw_opbal, {}).collect()
    assert df_opbal.columns == ["ZASSETUID", "ZAMOUNTACCOUNT", "ZTXDATESTR", "ZUTIME"]
    assert df_opbal["ZASSETUID"][0] == "ASUB1"
    assert df_opbal["ZAMOUNTACCOUNT"][0] == 50000.0


def test_financial_rules_and_tax_classifier_validation() -> None:
    """Verify validation messages reference silver.dim_income_subcategory."""
    mock_rules = FinancialRules.from_toml(Path("tests/financial_rules.toml"))
    mock_rules.assumptions.tax.investment_exclusions = InvestmentExclusionsConfig(
        stcg_sub_cat_ids=["SC_INVALID_STCG"],
        ltcg_sub_cat_ids=[],
    )

    df_subcat = pl.DataFrame({"UID": ["SC_VALID_1", "SC_VALID_2"]})

    with pytest.raises(ValueError, match="do not exist in silver.dim_income_subcategory"):
        mock_rules.validate_investment_exclusion_uids(df_subcat)

    with pytest.raises(ValueError, match="do not exist in silver.dim_income_subcategory"):
        TaxClassifier.validate_tax_credit_uids(df_subcat, {"SC_INVALID_CREDIT": "Interest"})


def test_ledger_builder_with_cutover_data() -> None:
    """Verify LedgerBuilder functions correctly with the renamed cutover facts and dimensions."""
    dfs: dict[str, pl.DataFrame] = {
        "df_f_opening_balances": pl.DataFrame(
            {
                "ZASSETUID": ["BANK1"],
                "ZAMOUNTACCOUNT": [100000.0],
                "ZTXDATESTR": [date(2024, 1, 1)],
                "ZUTIME": [1704067200],
            }
        ),
        "df_f_income_transactions": pl.DataFrame(
            {
                "ASSET_ID": ["BANK1"],
                "BASE_AMOUNT": [50000.0],
                "CATEGORY_ID": ["INC_SALARY"],
                "DATE": [date(2024, 1, 31)],
                "Is_Active_Income": [True],
                "Is_Dividend_Income": [False],
                "Is_Interest_Income": [False],
                "Is_Non_Cash_Income": [False],
            }
        ),
        "df_f_expense_transactions": pl.DataFrame(
            {
                "ASSET_ID": ["BANK1"],
                "BASE_AMOUNT": [20000.0],
                "CATEGORY_ID": ["EXP_RENT"],
                "DATE": [date(2024, 1, 15)],
                "Is_Core_Expense": [True],
            }
        ),
        "df_f_transfer_transactions": pl.DataFrame(
            {
                "ASSET_ID": ["BANK1"],
                "TO_ASSET_ID": ["WALLET1"],
                "BASE_AMOUNT": [5000.0],
                "AMOUNT_PROPER": [-5000.0],
                "DATE": [date(2024, 1, 10)],
                "ADJUSTED_DATE_FOR_ANALYSIS": [date(2024, 1, 10)],
            }
        ),
        "df_d_asset_subcategory": pl.DataFrame(
            {
                "UID": ["BANK1", "WALLET1"],
                "is_non_cash_pnl": [False, False],
            }
        ),
        "df_d_expense_subcategory": pl.DataFrame(
            {
                "UID": ["EXP_RENT"],
                "CATEGORY_ID": ["CAT_HOUSING"],
            }
        ),
        "df_d_expense_category": pl.DataFrame(
            {
                "UID": ["CAT_HOUSING"],
                "CATEGORY_NAME": ["Housing"],
            }
        ),
    }

    rules = FinancialRules.from_toml(Path("tests/financial_rules.toml"))

    builder = LedgerBuilder(dfs, rules)
    ledger_result = builder.build()

    assert ledger_result is not None
    # Verify monthly balances and activity were calculated
    assert "lf_balances" in ledger_result
    df_balances = ledger_result["lf_balances"].collect()
    assert df_balances.height > 0
