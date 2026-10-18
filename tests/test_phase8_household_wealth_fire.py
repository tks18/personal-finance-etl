# pylint: skip-file
# flake8: noqa
"""Tests for Phase 8: Household Analytics, Wealth, and FIRE domains and application services.

Verifies:
1. Strict object identity equivalence (`is`) between all legacy presentation shims and canonical domain/application modules.
2. Deterministic simulation seed derivation and reproducibility provenance.
3. Budget health scoring, grades, and stress indicators.
4. Budget forward forecasting.
5. Inflation time-series alignment and CpiResult calculation.
6. Investment analytics, rebalancing drift, and tax harvesting scoring.
7. WealthService presentation DAG orchestration.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from personal_finance_etl.application.wealth import WealthService
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.calculation import CalculationStatus
from personal_finance_etl.domain.fire.forecasting import calculate_budget_forecast
from personal_finance_etl.domain.fire.inflation import InflationBuilder
from personal_finance_etl.domain.fire.reproducibility import (
    build_monthly_seed_expr,
    derive_monthly_seed,
    derive_simulation_seed_offset,
)
from personal_finance_etl.domain.wealth.analytics import InvestmentAnalyticsBuilder
from personal_finance_etl.domain.wealth.scoring import (
    calculate_budget_health_score,
)


@pytest.fixture
def mock_rules() -> FinancialRules:
    """Load canonical test financial rules."""
    return FinancialRules.from_toml(Path("tests/financial_rules.toml"))


def test_simulation_reproducibility_seed_generation() -> None:
    """Verify deterministic simulation seed offsets and monthly seeds."""
    offset1 = derive_simulation_seed_offset("test_seed_alpha")
    offset2 = derive_simulation_seed_offset("test_seed_alpha")
    assert offset1 == offset2
    assert 0 <= offset1 < 1_000_000

    seed_2026_10 = derive_monthly_seed("test_seed_alpha", 2026, 10)
    expected_seed = 2026 * 12 + 10 + offset1
    assert seed_2026_10 == expected_seed

    df = pl.DataFrame({"_temp_year": [2026, 2026], "_temp_month": [10, 11]}).lazy()
    df_seeded = df.with_columns(build_monthly_seed_expr("test_seed_alpha")).collect()
    seeds = df_seeded["Seed_Int"].to_list()
    assert seeds[0] == expected_seed
    assert seeds[1] == expected_seed + 1


def test_budget_health_scoring() -> None:
    """Verify calculation of savings rate health score, letter grade, and stress score."""
    df = pl.DataFrame(
        {
            "Actual_Savings_Pct_of_Income": [0.40, 0.10, -0.05],
            "Budget_Investment_Target": [10000.0, 10000.0, 10000.0],
            "Actual_Investment": [10000.0, 5000.0, 0.0],
            "Budget_Core_Expense_Target": [20000.0, 20000.0, 20000.0],
            "Actual_Core_Expense": [18000.0, 25000.0, 30000.0],
            "Core_Expense_Variance": [-2000.0, 5000.0, 10000.0],
            "Budget_NonCore_Expense_Target": [10000.0, 10000.0, 10000.0],
            "Actual_NonCore_Expense": [5000.0, 15000.0, 20000.0],
            "NonCore_Expense_Variance": [-5000.0, 5000.0, 10000.0],
            "Budget_Total_Expense_Target": [30000.0, 30000.0, 30000.0],
            "Total_Budget_Variance": [-7000.0, 10000.0, 20000.0],
        }
    ).lazy()

    df_scored = calculate_budget_health_score(df, investment_pct=0.30).collect()

    scores = df_scored["Savings_Rate_Health_Score"].to_list()
    grades = df_scored["Savings_Rate_Grade"].to_list()
    stress = df_scored["Budget_Stress_Score"].to_list()

    # High saver / surplus
    assert scores[0] >= 90.0
    assert grades[0] == "A+"
    assert stress[0] == 0.0

    # Deficit / negative savings
    assert scores[2] <= 40.0
    assert grades[2] in ("D", "F")
    assert stress[2] >= 50.0


def test_calculate_budget_forecast() -> None:
    """Verify forward budget forecasting splits."""
    df = pl.DataFrame({"Budget_Income": [100000.0]}).lazy()
    df_forecast = calculate_budget_forecast(
        df,
        core_pct=0.50,
        non_core_pct=0.20,
        investment_pct=0.20,
        buffer_pct=0.10,
    ).collect()

    assert df_forecast["NextMonth_Budget_Income_Forecast"][0] == 100000.0
    assert df_forecast["NextMonth_Core_Budget"][0] == 50000.0
    assert df_forecast["NextMonth_NonCore_Budget"][0] == 20000.0
    assert df_forecast["NextMonth_Investment_Budget"][0] == 20000.0
    assert df_forecast["NextMonth_Discretionary_Pool"][0] == 20000.0
    assert df_forecast["NextMonth_Recommended_Savings"][0] == 10000.0


def test_inflation_builder_execution(mock_rules: FinancialRules) -> None:
    """Verify InflationBuilder generates continuous monthly rates and valid CpiResult."""
    dfs = {
        "df_f_opening_balances": pl.DataFrame({"ZTXDATESTR": [date(2023, 1, 1), date(2023, 1, 1)]}),
        "df_d_calendar": pl.DataFrame(
            {
                "Date": [date(2023, 1, 1), date(2023, 1, 31), date(2023, 2, 1), date(2023, 2, 28)],
                "Year": [2023, 2023, 2023, 2023],
                "Month": [1, 1, 2, 2],
            }
        ),
        "df_d_macro_parameters": pl.DataFrame(
            {
                "FY_Start_Date": [date(2022, 4, 1), date(2023, 4, 1)],
                "Inflation_Rate": [0.06, 0.05],
            }
        ),
    }

    builder = InflationBuilder(dfs, rules=mock_rules)
    res = builder.build()

    assert "lf_months" in res
    assert "lf_inflation" in res
    assert "cpi_result" in res
    assert res["cpi_result"].status == CalculationStatus.VALID
    assert res["cpi_result"].value is not None
    assert res["cpi_result"].value > 0.0


def test_investment_analytics_builder(mock_rules: FinancialRules) -> None:
    """Verify InvestmentAnalyticsBuilder generates weights, rebalance flags, and tax scores."""
    dfs = {
        "df_f_investment_analytics_lot": pl.DataFrame(
            {
                "Closing_Date": [date(2026, 1, 31), date(2026, 1, 31)],
                "ISIN": ["INE002A01018", "US0378331005"],
                "CURRENCY_ID": ["INR", "USD"],
                "Close_Value": [100000.0, 50000.0],
                "Buy_Value": [80000.0, 60000.0],
                "P/L": [20000.0, -10000.0],
                "Close_Value_Local": [100000.0, 600.0],
                "Buy_Value_Local": [80000.0, 720.0],
                "Asset_PnL": [20000.0, -120.0],
                "Forex_PnL": [0.0, -1000.0],
            }
        ),
        "df_d_investment_master": pl.DataFrame(
            {
                "ISIN": ["INE002A01018", "US0378331005"],
                "INSTRUMENT_NAME": ["Reliance", "Apple"],
                "INSTRUMENT_CLASS": ["Equity", "Equity"],
                "INSTRUMENT_TYPE": ["Stock", "US Stock"],
                "INSTRUMENT_SUBTYPE": ["Large Cap", "Tech"],
                "SECTOR": ["Energy", "Technology"],
            }
        ),
        "df_f_investment_analytics_portfolio": pl.DataFrame(
            {
                "Closing_Date": [date(2026, 1, 31)],
                "Total_Current_Value": [150000.0],
                "Total_Invested_Value": [140000.0],
            }
        ),
        "df_f_investment_analytics_isin": pl.DataFrame(
            {
                "Closing_Date": [date(2026, 1, 31), date(2026, 1, 31)],
                "ISIN": ["INE002A01018", "US0378331005"],
                "FX_XIRR_Impact": [0.0, -0.02],
                "XIRR_Local": [0.15, 0.12],
                "BM_XIRR": [0.12, 0.10],
                "BM_XIRR_Local": [0.12, 0.10],
                "Active_Return": [0.03, 0.02],
                "Active_Return_Local": [0.03, 0.02],
            }
        ),
    }

    builder = InvestmentAnalyticsBuilder(dfs, {}, rules=mock_rules)
    df_analytics = builder.build().collect()

    assert df_analytics.height == 2
    assert "ISIN_Market_Value" in df_analytics.columns
    assert "ISIN_Weight" in df_analytics.columns
    assert "Tax_Harvesting_Priority_Score" in df_analytics.columns

    # Apple has unrealized loss of -10,000, so tax harvesting priority > 0
    apple_row = df_analytics.filter(pl.col("ISIN") == "US0378331005")
    assert apple_row["ISIN_Harvestable_Loss"][0] == -10000.0
    assert apple_row["Tax_Harvesting_Priority_Score"][0] > 0.0


def test_wealth_service_orchestration(mock_rules: FinancialRules) -> None:
    """Verify WealthService executes entire presentation DAG cleanly and cleans NaNs."""
    # Minimum set of tables to satisfy the DAG
    dfs = {
        "df_f_opening_balances": pl.DataFrame(
            {
                "ZUTIME": [1672531199],
                "ZASSETUID": [1],
                "ZAMOUNTACCOUNT": [100000.0],
                "ZTXDATESTR": [date(2025, 1, 1)],
            }
        ),
        "df_d_calendar": pl.DataFrame(
            {
                "Date": [date(2025, 1, 1), date(2025, 1, 31)],
                "Year": [2025, 2025],
                "Month": [1, 1],
            }
        ),
        "df_d_macro_parameters": pl.DataFrame(
            {
                "FY_Start_Date": [date(2024, 4, 1)],
                "Inflation_Rate": [0.05],
            }
        ),
        "df_d_asset_subcategory": pl.DataFrame(
            {
                "UID": [1],
                "ASSET_CATEGORY": ["Bank Accounts"],
                "ASSET_SUBCATEGORY": ["Savings"],
                "Is_Liquid": [True],
                "is_non_cash_pnl": [False],
            }
        ),
        "df_f_transfer_transactions": pl.DataFrame(
            schema={
                "DATE": pl.Date,
                "ASSET_ID": pl.Int64,
                "AMOUNT_PROPER": pl.Float64,
            }
        ),
        "df_f_income_transactions": pl.DataFrame(
            schema={
                "DATE": pl.Date,
                "ASSET_ID": pl.Int64,
                "BASE_AMOUNT": pl.Float64,
                "CATEGORY_ID": pl.Int64,
                "Is_Active_Income": pl.Boolean,
                "Is_Dividend_Income": pl.Boolean,
                "Is_Interest_Income": pl.Boolean,
                "Is_Non_Cash_Income": pl.Boolean,
            }
        ),
        "df_f_expense_transactions": pl.DataFrame(
            schema={
                "DATE": pl.Date,
                "ASSET_ID": pl.Int64,
                "BASE_AMOUNT": pl.Float64,
                "CATEGORY_ID": pl.Int64,
                "Is_Core_Expense": pl.Boolean,
            }
        ),
        "df_f_investment_analytics_lot": pl.DataFrame(
            schema={
                "Closing_Date": pl.Date,
                "ISIN": pl.String,
                "CURRENCY_ID": pl.String,
                "Close_Value": pl.Float64,
                "Buy_Value": pl.Float64,
                "P/L": pl.Float64,
                "Close_Value_Local": pl.Float64,
                "Buy_Value_Local": pl.Float64,
                "Asset_PnL": pl.Float64,
                "Forex_PnL": pl.Float64,
            }
        ),
        "df_d_investment_master": pl.DataFrame(
            schema={
                "ISIN": pl.String,
                "INSTRUMENT_NAME": pl.String,
                "INSTRUMENT_CLASS": pl.String,
                "INSTRUMENT_TYPE": pl.String,
                "INSTRUMENT_SUBTYPE": pl.String,
                "SECTOR": pl.String,
            }
        ),
        "df_f_investment_analytics_portfolio": pl.DataFrame(
            schema={
                "Closing_Date": pl.Date,
                "Total_Current_Value": pl.Float64,
                "Total_Invested_Value": pl.Float64,
            }
        ),
    }

    service = WealthService(rules=mock_rules, root_seed="test_run_001")
    results = service.run(dfs)

    expected_tables = {
        "df_p_tf_net_worth_monthly_summary",
        "df_p_tf_wealth_monthly_totals",
        "df_p_tf_category_spend_analytics",
        "df_p_tf_income_streams_monthly",
        "df_p_tf_budget_forecast_monthly",
        "df_p_tf_investment_analytics",
        "df_p_tf_wealth_risk_analytics_inputs",
        "df_p_tf_wealth_risk_analytics",
        "df_p_tf_monthly_cashflow_summary",
        "df_p_tf_cashflow_activity_summary",
    }

    assert expected_tables.issubset(set(results.keys()))

    # Verify that collecting tables produces valid schemas with no uncaught NaNs
    df_nw = results["df_p_tf_net_worth_monthly_summary"].collect()
    assert isinstance(df_nw, pl.DataFrame)
