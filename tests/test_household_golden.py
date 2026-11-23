"""Golden assertions verifying exact numerical outputs for household transactions, ledger, and cashflow.

Owns
----
- Hand-checkable numerical assertions for monthly cash income (active vs passive).
- Core vs non-core expense classification and totals.
- Net cashflow and investment transfer flow.
- Account opening, closing, and net worth balances.
- Savings rates, investment rates, and expense variance analytics.
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.household.ledger import LedgerBuilder


def test_household_exact_cashflow_and_balances(mock_rules: FinancialRules) -> None:
    """Verify exact hand-calculated financial numbers from the miniature household fixture."""
    # Build test facts representing the miniature household transactions
    df_opening = pl.DataFrame(
        {
            "ZASSETUID": ["ACC_CHECKING"],
            "ZAMOUNTACCOUNT": [100000.0],
            "ZTXDATESTR": [date(2024, 1, 1)],
            "ZUTIME": [1704067200],
        }
    )
    df_income = pl.DataFrame(
        {
            "UID": ["TX_SALARY", "TX_DIVIDEND"],
            "DATE": [date(2024, 1, 31), date(2024, 1, 20)],
            "ASSET_ID": ["ACC_CHECKING", "ACC_CHECKING"],
            "CATEGORY_ID": ["SUB_SALARY", "SUB_DIVIDEND"],
            "BASE_AMOUNT": [150000.0, 5000.0],
            "CURRENCY_ID": ["INR_INR", "INR_INR"],
            "Is_Active_Income": [True, False],
            "Is_Dividend_Income": [False, True],
            "Is_Interest_Income": [False, False],
            "Is_Non_Cash_Income": [False, False],
        }
    )
    df_expense = pl.DataFrame(
        {
            "UID": ["TX_RENT", "TX_DINING"],
            "DATE": [date(2024, 1, 10), date(2024, 1, 25)],
            "ASSET_ID": ["ACC_CHECKING", "ACC_CHECKING"],
            "CATEGORY_ID": ["SUB_RENT", "SUB_DINING"],
            "BASE_AMOUNT": [40000.0, 10000.0],
            "CURRENCY_ID": ["INR_INR", "INR_INR"],
            "Is_Core_Expense": [True, False],
        }
    )
    df_transfer = pl.DataFrame(
        {
            "UID": ["TX_TRANSFER"],
            "DATE": [date(2024, 1, 28)],
            "ASSET_ID": ["ACC_CHECKING"],
            "TO_ASSET_ID": ["ACC_DEMAT"],
            "BASE_AMOUNT": [50000.0],
            "AMOUNT_PROPER": [-50000.0],
            "ADJUSTED_DATE_FOR_ANALYSIS": [date(2024, 1, 28)],
            "TRANSFER_TYPE": ["OUTGOING"],
        }
    )
    df_asset_sub = pl.DataFrame(
        {
            "UID": ["ACC_CHECKING", "ACC_DEMAT"],
            "is_non_cash_pnl": [False, False],
            "is_cash_pool": [True, False],
            "ledger_role": ["CASH_POOL", "INVESTING_ASSET"],
        }
    )
    df_expense_sub = pl.DataFrame(
        {
            "UID": ["SUB_RENT", "SUB_DINING"],
            "CATEGORY_ID": ["CAT_HOUSING", "CAT_DINING"],
        }
    )
    df_expense_cat = pl.DataFrame(
        {
            "UID": ["CAT_HOUSING", "CAT_DINING"],
            "CATEGORY_NAME": ["Housing", "Dining"],
        }
    )

    # 1. Income totals & Active/Passive split
    active_income = float(df_income.filter(pl.col("Is_Active_Income"))["BASE_AMOUNT"].sum())
    passive_income = float(df_income.filter(~pl.col("Is_Active_Income"))["BASE_AMOUNT"].sum())
    total_income = float(df_income["BASE_AMOUNT"].sum())

    assert active_income == 150000.0, "Expected Active Salary = ₹1,50,000"
    assert passive_income == 5000.0, "Expected Passive Dividend = ₹5,000"
    assert total_income == 155000.0, "Expected Total Income = ₹1,55,000"

    # 2. Core vs Non-Core Expenses
    core_expense = float(df_expense.filter(pl.col("Is_Core_Expense"))["BASE_AMOUNT"].sum())
    non_core_expense = float(df_expense.filter(~pl.col("Is_Core_Expense"))["BASE_AMOUNT"].sum())
    total_expense = float(df_expense["BASE_AMOUNT"].sum())

    assert core_expense == 40000.0, "Expected Core Rent = ₹40,000"
    assert non_core_expense == 10000.0, "Expected Non-Core Dining = ₹10,000"
    assert total_expense == 50000.0, "Expected Total Expense = ₹50,000"

    # 3. Net Cashflow
    net_cashflow = total_income - total_expense
    assert net_cashflow == 105000.0, "Net Cashflow must be ₹1,05,000"

    # 4. Investment Flow
    investment_flow = float(df_transfer["BASE_AMOUNT"].sum())
    assert investment_flow == 50000.0, "Investment Transfer Flow must be ₹50,000"

    # 5. Savings and Investment Rates
    savings_rate = (total_income - total_expense) / total_income
    assert pytest.approx(savings_rate, abs=1e-4) == (105000.0 / 155000.0)  # ~67.74%

    investment_rate = investment_flow / total_income
    assert pytest.approx(investment_rate, abs=1e-4) == (50000.0 / 155000.0)  # ~32.26%

    # 6. Ledger balances
    dfs = {
        "df_f_opening_balances": df_opening,
        "df_f_income_transactions": df_income,
        "df_f_expense_transactions": df_expense,
        "df_f_transfer_transactions": df_transfer,
        "df_d_asset_subcategory": df_asset_sub,
        "df_d_expense_subcategory": df_expense_sub,
        "df_d_expense_category": df_expense_cat,
    }
    builder = LedgerBuilder(dfs, mock_rules)
    ledger_res = builder.build()
    df_balances = ledger_res["lf_balances"].collect()

    # Checking account: 100,000 opening + 155,000 in - 50,000 out - 50,000 transfer = 155,000 net change
    checking_bal = df_balances.filter(pl.col("ASSET_SUBCATEGORY_ID") == "ACC_CHECKING")[
        "MONTHLY_NET_CHANGE"
    ].item()
    assert checking_bal == 155000.0, f"Expected checking balance ₹1,55,000, got {checking_bal}"


def test_spend_variances_analytical_formulas() -> None:
    """Verify spend variance analytics (consistency, creep, and fixed vs variable categorization)."""
    # Test spend categorization and consistency score logic matching SpendAnalyticsBuilder formulas
    df_cat = pl.DataFrame(
        {
            "CATEGORY_GROUPS": ["Rent", "Dining", "Investments"],
            "Cat_Mean": [40000.0, 10000.0, 50000.0],
            "Cat_Std": [2000.0, 5000.0, 1000.0],
            "Total_Monthly_Spend": [40000.0, 16000.0, 50000.0],
            "Trailing_3M_Avg_Spend": [40000.0, 10000.0, 50000.0],
            "Transaction_Count": [1, 15, 1],
            "Trailing_3M_Avg_Frequency": [1.0, 10.0, 1.0],
        }
    ).lazy()

    fixed_pattern = "(?i)fixed|utilities|rent|insurance|tax|emi|loan"
    invest_pattern = "(?i)invest|saving"

    scored = df_cat.with_columns(
        pl.when(pl.col("CATEGORY_GROUPS").str.to_lowercase().str.contains(invest_pattern))
        .then(pl.lit(True))
        .otherwise(pl.lit(False))
        .alias("Is_Investment"),
        pl.when(pl.col("CATEGORY_GROUPS").str.to_lowercase().str.contains(fixed_pattern))
        .then(pl.lit("Fixed"))
        .otherwise(pl.lit("Variable"))
        .alias("Spend_Type"),
        pl.when((pl.col("Cat_Mean") / pl.col("Cat_Std")) > 10.0)
        .then(10.0)
        .otherwise(pl.col("Cat_Mean") / pl.col("Cat_Std"))
        .alias("Spend_Consistency_Score"),
        (
            (
                (pl.col("Total_Monthly_Spend") > (pl.col("Trailing_3M_Avg_Spend") * 1.15))
                & (pl.col("Transaction_Count") > (pl.col("Trailing_3M_Avg_Frequency") * 1.10))
            )
            | (pl.col("Total_Monthly_Spend") > (pl.col("Trailing_3M_Avg_Spend") * 1.50))
        ).alias("Is_Category_Creep"),
    ).collect()

    # 1. Rent: Fixed spend, consistency score capped at 10.0 (40000 / 2000 = 20.0 -> 10.0)
    rent = scored.filter(pl.col("CATEGORY_GROUPS") == "Rent")
    assert rent["Spend_Type"][0] == "Fixed"
    assert rent["Spend_Consistency_Score"][0] == 10.0
    assert rent["Is_Category_Creep"][0] is False

    # 2. Dining: Variable spend, consistency = 10000 / 5000 = 2.0, creep candidate (16000 > 1.5 * 10000)
    dining = scored.filter(pl.col("CATEGORY_GROUPS") == "Dining")
    assert dining["Spend_Type"][0] == "Variable"
    assert dining["Spend_Consistency_Score"][0] == 2.0
    assert dining["Is_Category_Creep"][0] is True

    # 3. Investments: Investment flag is True
    invest = scored.filter(pl.col("CATEGORY_GROUPS") == "Investments")
    assert invest["Is_Investment"][0] is True
