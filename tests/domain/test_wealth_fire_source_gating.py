# pyright: reportPrivateUsage=false
"""Domain-tier test suite for source-of-calculation gating in Wealth and FIRE analytics.

Owns
----
- Verification of NetWorthBuilder calculation gating when INVESTMENT_ACCOUNTING, WEALTH, or FOREIGN_ASSET_ENRICHMENT are disabled.
- Verification that WealthRiskAnalyticsBuilder skips Monte Carlo numerical kernels when FIRE is disabled and emits nulls.
- Verification that deterministic FI metrics (Target FI, Coast FI, Lean FI, SWR, linear runway) remain calculated without FIRE.
- Verification that after-tax net worth skips investment portfolio haircut when INVESTMENT_ACCOUNTING is disabled.

Does not own
-------------
- Full pipeline execution orchestration (owned by tests/application/test_wealth_fire_composition.py).
- Capability graph and topological resolution (owned by tests/contracts/test_capabilities.py).
- AST architectural boundary enforcement (owned by tests/architecture/test_boundaries.py).
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.fire.deterministic import WealthRiskAnalyticsBuilder
from personal_finance_etl.domain.wealth.net_worth import NetWorthBuilder


@pytest.fixture
def sample_domain_dfs() -> dict[str, pl.DataFrame]:
    """Provide minimal Silver/dimension tables for domain builder tests."""
    return {
        "df_f_opening_balances": pl.DataFrame(
            {
                "ZUTIME": [1672531199],
                "ZASSETUID": [1],
                "ZAMOUNTACCOUNT": [500000.0],
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
                "Inflation_Rate": [0.06],
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
        "df_d_investment_master": pl.DataFrame(
            {
                "ISIN": ["INE002A01018"],
                "CATEGORY_ID": [1],
            }
        ),
        "df_f_investment_analytics_isin": pl.DataFrame(
            {
                "ISIN": ["INE002A01018"],
                "Closing_Date": [date(2025, 1, 31)],
                "Total_Current_Value": [120000.0],
                "Total_Invested_Value": [100000.0],
                "Asset_PnL": [20000.0],
                "Forex_PnL": [0.0],
            }
        ),
        "df_f_investment_analytics_portfolio": pl.DataFrame(
            {
                "Closing_Date": [date(2025, 1, 31)],
                "Total_Current_Value": [120000.0],
                "Total_Invested_Value": [100000.0],
                "XIRR": [0.15],
                "Unrealized_PL": [20000.0],
                "Asset_PnL": [20000.0],
                "Forex_PnL": [0.0],
            }
        ),
        "df_f_investment_analytics_currency": pl.DataFrame(
            {
                "Closing_Date": [date(2025, 1, 31)],
                "CURRENCY_ID": ["USD"],
                "Total_Current_Value": [50000.0],
            }
        ),
    }


@pytest.fixture
def sample_inflation_res() -> dict[str, pl.LazyFrame]:
    """Provide mock inflation builder output."""
    lf_months = pl.DataFrame(
        {
            "MONTH_START_DATE": [date(2025, 1, 1)],
            "MONTH_END_DATE": [date(2025, 1, 31)],
            "YEAR": [2025],
            "MONTH": [1],
        }
    ).lazy()
    lf_inflation = pl.DataFrame(
        {
            "MONTH_START_DATE": [date(2025, 1, 1)],
            "CPI_INDEX": [100.0],
            "INFLATION_YOY_PCT": [0.06],
        }
    ).lazy()
    return {"lf_months": lf_months, "lf_inflation": lf_inflation}


@pytest.fixture
def sample_ledger_res() -> dict[str, pl.LazyFrame]:
    """Provide mock ledger builder output."""
    lf_activity = pl.DataFrame(
        {
            "MONTH_START_DATE": [date(2025, 1, 1)],
            "MONTH_END_DATE": [date(2025, 1, 31)],
            "ASSET_SUBCATEGORY_ID": [1],
            "Income_Inflow": [150000.0],
            "Cash_Income_Inflow": [150000.0],
            "Non_Cash_Income_Inflow": [0.0],
            "Expense_Outflow": [50000.0],
            "Core_Expense_Outflow": [40000.0],
            "Cash_Expense_Outflow": [50000.0],
            "Non_Cash_Expense_Outflow": [0.0],
            "Net_Transfers": [0.0],
            "MONTHLY_NET_CHANGE": [100000.0],
        }
    ).lazy()
    lf_balances = pl.DataFrame(
        {
            "MONTH_END_DATE": [date(2025, 1, 31)],
            "ASSET_SUBCATEGORY_ID": [1],
            "DB_Opening_Balance": [500000.0],
        }
    ).lazy()
    return {"lf_activity": lf_activity, "lf_balances": lf_balances}


def test_net_worth_builder_source_gating_investments_inactive(
    sample_domain_dfs: dict[str, pl.DataFrame],
    sample_inflation_res: dict[str, pl.LazyFrame],
    sample_ledger_res: dict[str, pl.LazyFrame],
) -> None:
    """Verify that when investment capability is inactive, investment metrics are emitted as None."""
    builder = NetWorthBuilder(
        sample_domain_dfs,
        sample_inflation_res,
        sample_ledger_res,
        default_currency_id="INR",
        is_investment_active=False,
        is_foreign_active=False,
        is_wealth_active=True,
    )
    res = builder.build()
    df_nw = res["lf_nw_summary"].collect()
    df_totals = res["lf_monthly_totals"].collect()

    # Asset summary level: PnL columns are null
    assert df_nw["Closing_Asset_PnL"][0] is None
    assert df_nw["Closing_Forex_PnL"][0] is None
    assert df_nw["Closing_Balance_Market"][0] == df_nw["Closing_Balance"][0]

    # Monthly totals level: investment columns are null
    assert df_totals["Opening_Investment_Book_Value"][0] is None
    assert df_totals["Closing_Investment_Book_Value"][0] is None
    assert df_totals["Investment_Book_Value_Delta"][0] is None
    assert df_totals["Opening_Investment_Market_Value"][0] is None
    assert df_totals["Closing_Investment_Market_Value"][0] is None
    assert df_totals["Investment_Market_Value_Delta"][0] is None
    assert df_totals["Opening_Investment_XIRR"][0] is None
    assert df_totals["Closing_Investment_XIRR"][0] is None
    assert df_totals["Opening_Unrealized_PL"][0] is None
    assert df_totals["Closing_Unrealized_PL"][0] is None
    assert df_totals["Closing_Asset_PnL"][0] is None


def test_net_worth_builder_source_gating_wealth_inactive(
    sample_domain_dfs: dict[str, pl.DataFrame],
    sample_inflation_res: dict[str, pl.LazyFrame],
    sample_ledger_res: dict[str, pl.LazyFrame],
) -> None:
    """Verify that when wealth capability is inactive (pure household), wealth market metrics are emitted as None."""
    builder = NetWorthBuilder(
        sample_domain_dfs,
        sample_inflation_res,
        sample_ledger_res,
        default_currency_id="INR",
        is_investment_active=False,
        is_foreign_active=False,
        is_wealth_active=False,
    )
    res = builder.build()
    df_totals = res["lf_monthly_totals"].collect()

    # Base household cashflow totals are populated
    assert df_totals["Total_Income"][0] == 150000.0
    assert df_totals["Total_Expense"][0] == 50000.0
    assert df_totals["Net_Cashflow_Month"][0] == 100000.0
    assert df_totals["Total_Net_Worth"][0] == 100000.0

    # Wealth market totals are null
    assert df_totals["Total_Assets_Market"][0] is None
    assert df_totals["Total_Net_Worth_Market"][0] is None
    assert df_totals["Opening_Balance_Asset_Market"][0] is None
    assert df_totals["Closing_Balance_Asset_Market"][0] is None
    assert df_totals["Asset_Market_Delta"][0] is None
    assert df_totals["Liquid_Assets_Market"][0] is None


def test_net_worth_builder_source_gating_foreign_inactive(
    sample_domain_dfs: dict[str, pl.DataFrame],
    sample_inflation_res: dict[str, pl.LazyFrame],
    sample_ledger_res: dict[str, pl.LazyFrame],
) -> None:
    """Verify that when foreign asset enrichment is inactive, foreign exposure columns are emitted as None."""
    builder = NetWorthBuilder(
        sample_domain_dfs,
        sample_inflation_res,
        sample_ledger_res,
        default_currency_id="INR",
        is_investment_active=True,
        is_foreign_active=False,
        is_wealth_active=True,
    )
    res = builder.build()
    df_totals = res["lf_monthly_totals"].collect()

    assert df_totals["Closing_Forex_PnL"][0] is None
    assert df_totals["Total_Foreign_Currency_Exposure"][0] is None
    assert df_totals["Foreign_Exposure_Pct"][0] is None
    # Domestic investment metrics are still populated
    assert df_totals["Closing_Investment_Market_Value"][0] == 120000.0


def test_wealth_risk_builder_source_gating_fire_inactive(
    sample_domain_dfs: dict[str, pl.DataFrame],
    sample_inflation_res: dict[str, pl.LazyFrame],
    sample_ledger_res: dict[str, pl.LazyFrame],
    mock_rules: FinancialRules,
) -> None:
    """Verify that WealthRiskAnalyticsBuilder skips Monte Carlo simulation when FIRE is inactive."""
    nw_builder = NetWorthBuilder(
        sample_domain_dfs,
        sample_inflation_res,
        sample_ledger_res,
        default_currency_id="INR",
        is_investment_active=True,
        is_foreign_active=False,
        is_wealth_active=True,
    )
    base_lf = nw_builder.build()

    fire_builder = WealthRiskAnalyticsBuilder(
        sample_domain_dfs,
        base_lf,
        rules=mock_rules,
        root_seed="test_gating_seed",
        is_fire_active=False,
        is_investment_active=True,
    )
    res = fire_builder.build()
    df_fire = res["df_p_tf_wealth_risk_analytics"].collect()

    # Deterministic FI metrics are present
    assert df_fire["Target_FI_Today"][0] is not None
    assert df_fire["Coast_FI_Today"][0] is not None
    assert df_fire["Lean_FI_Today"][0] is not None
    assert df_fire["FI_Gap"][0] is not None
    assert df_fire["Estimated_Months_To_FI_Linear"][0] is not None
    assert df_fire["Runway_Months_Linear"][0] is not None

    # Monte Carlo simulation columns are None
    assert df_fire["Months_To_FI_Conservative_P90"][0] is None
    assert df_fire["Months_To_FI_Base_P50"][0] is None
    assert df_fire["Months_To_FI_Aggressive_P10"][0] is None
    assert df_fire["Probability_Of_Success_Pct"][0] is None
    assert df_fire["Years_To_FI_P50"][0] is None
    assert df_fire["Projected_FI_Date_P50"][0] is None
    assert df_fire["Runway_Months_Stressed_P10"][0] is None
    assert df_fire["Runway_Months_Base_P50"][0] is None
    assert df_fire["Terminal_Wealth_Nominal_P50"][0] is None
    assert df_fire["Target_FI_Total_Future_Nominal"][0] is None
    assert df_fire["Savings_Rate_Required"][0] is None


def test_wealth_risk_builder_source_gating_investment_inactive(
    sample_domain_dfs: dict[str, pl.DataFrame],
    sample_inflation_res: dict[str, pl.LazyFrame],
    sample_ledger_res: dict[str, pl.LazyFrame],
    mock_rules: FinancialRules,
) -> None:
    """Verify that after-tax net worth skips investment haircut when INVESTMENT_ACCOUNTING is inactive."""
    nw_builder = NetWorthBuilder(
        sample_domain_dfs,
        sample_inflation_res,
        sample_ledger_res,
        default_currency_id="INR",
        is_investment_active=False,
        is_foreign_active=False,
        is_wealth_active=True,
    )
    base_lf = nw_builder.build()

    fire_builder = WealthRiskAnalyticsBuilder(
        sample_domain_dfs,
        base_lf,
        rules=mock_rules,
        root_seed="test_gating_seed",
        is_fire_active=False,
        is_investment_active=False,
    )
    # Validate base inputs directly
    lf_base = fire_builder._prepare_base_inputs(base_lf["lf_monthly_totals"]).collect()
    # Total_Net_Worth_Market_Af_Tax equals Total_Net_Worth_Market with zero haircut
    assert lf_base["Total_Net_Worth_Market_Af_Tax"][0] == lf_base["Total_Net_Worth_Market"][0]
