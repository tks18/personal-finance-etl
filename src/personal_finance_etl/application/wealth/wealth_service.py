"""Wealth and presentation orchestrator service.

Owns
----
- WealthService: Orchestrates analytical DAG execution across inflation, ledger, net worth,
  spend analytics, budget forecasting, income streams, investment analytics, wealth risk (FIRE),
  and cashflow statements.
- Cleans floating-point NaN values to null for DuckDB/Power BI presentation compatibility.

Does not own
-------------
- Financial domain business logic or formulas (owned by domain.household, domain.wealth, domain.fire).
- Extraction or ingestion coordination (owned by application.ingestion).
- DuckDB Gold table registration (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping

import polars as pl
import polars.selectors as cs

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.calculation import CalculationStatus
from personal_finance_etl.domain.fire.deterministic import WealthRiskAnalyticsBuilder
from personal_finance_etl.domain.fire.inflation import InflationBuilder
from personal_finance_etl.domain.household.budget import (
    BudgetForecastBuilder,
    SpendAnalyticsBuilder,
)
from personal_finance_etl.domain.household.cashflow import (
    CashflowStatementBuilder,
    MonthlyCashflowSummaryBuilder,
)
from personal_finance_etl.domain.household.income import IncomeStreamsBuilder
from personal_finance_etl.domain.household.ledger import LedgerBuilder
from personal_finance_etl.domain.wealth.analytics import InvestmentAnalyticsBuilder
from personal_finance_etl.domain.wealth.net_worth import NetWorthBuilder

logger = logging.getLogger(__name__)

__all__ = ["WealthPresentationEngine", "WealthService"]


class WealthService:
    """Presentation service orchestrating wealth, household, and FIRE analytical models.

    Consumes Silver-tier LazyFrames and produces unified Gold-tier presentation summary tables.
    """

    def __init__(self, rules: FinancialRules, root_seed: str = "default_seed") -> None:
        self.rules = rules
        self.root_seed = root_seed

    def run(self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame]) -> dict[str, pl.LazyFrame]:
        """Execute the presentation DAG across household, wealth, and FIRE builders.

        Parameters
        ----------
        dfs : Mapping[str, pl.DataFrame | pl.LazyFrame]
            Collection of Silver-tier tables and dimensions.

        Returns
        -------
        dict[str, pl.LazyFrame]
            Dictionary of computed presentation LazyFrames with NaN values cleaned to nulls.
        """
        logger.debug("[ENGINE:PRESENTATION] Starting Wealth Engine presentation layer builds...")
        logger.debug(
            "[ENGINE:PRESENTATION] Imputing missing data (NaN) with 0.0 for BI Engine compatibility..."
        )

        # 1. Core Builders (Inflation, Ledger, Net Worth)
        inflation_res = InflationBuilder(dfs, rules=self.rules).build()
        if not inflation_res:
            return {}

        cpi_res = inflation_res.get("cpi_result")
        if cpi_res and cpi_res.status == CalculationStatus.COMPUTATION_ERROR:
            raise RuntimeError(
                f"Inflation computation failed: {cpi_res.reason}. "
                "Aborting presentation DAG to prevent corrupted downstream FIRE state."
            )

        ledger_res = LedgerBuilder(dfs, rules=self.rules).build()
        if not ledger_res:
            return {}

        net_worth_res = NetWorthBuilder(
            dfs, inflation_res, ledger_res, self.rules.DEFAULT_CURRENCY_ID
        ).build()

        base_lf: dict[str, pl.LazyFrame] = {
            "lf_months": inflation_res["lf_months"],
            "lf_inflation": inflation_res["lf_inflation"],
            **ledger_res,
            **net_worth_res,
        }

        results: dict[str, pl.LazyFrame] = {}

        # 2. Net Worth Monthly Summary
        results["df_p_tf_net_worth_monthly_summary"] = base_lf["lf_nw_summary"]
        results["df_p_tf_wealth_monthly_totals"] = base_lf["lf_monthly_totals"]

        # 3. Category Spend Analytics
        results["df_p_tf_category_spend_analytics"] = SpendAnalyticsBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        # 4. Income Streams & Passive Yield
        results["df_p_tf_income_streams_monthly"] = IncomeStreamsBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        # 5. Budget Forecast
        results["df_p_tf_budget_forecast_monthly"] = BudgetForecastBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        # 6. Investment Analytics (Merged Sector, Rebalancing, Attribution, Tax Harvesting)
        results["df_p_tf_investment_analytics"] = InvestmentAnalyticsBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        # 7. Wealth Risk Analytics (FIRE Forecasting)
        wealth_risk_res = WealthRiskAnalyticsBuilder(
            dfs, base_lf, rules=self.rules, root_seed=self.root_seed
        ).build()
        results.update(wealth_risk_res)

        # 8. Monthly Cashflow Summary (now includes Financial Ratios)
        results["df_p_tf_monthly_cashflow_summary"] = MonthlyCashflowSummaryBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        # 9. Direct Method Cashflow Statement
        results["df_p_tf_cashflow_activity_summary"] = CashflowStatementBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        logger.debug("  -> Built %d BI presentation tables in DAG.", len(results))

        # 10. Post-Processing: Clean NaN values for BI compatibility (DuckDB / Power BI)
        return {key: lf.with_columns(cs.float().fill_nan(None)) for key, lf in results.items()}


WealthPresentationEngine = WealthService
