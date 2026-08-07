from collections.abc import Mapping

import polars as pl
import polars.selectors as cs

from src.engines.presentation.core.inflation_builder import InflationBuilder
from src.engines.presentation.core.ledger_builder import LedgerBuilder
from src.engines.presentation.core.net_worth_builder import NetWorthBuilder
from src.engines.presentation.helpers.risk_metrics import RiskMetricsBuilder
from src.engines.presentation.modules.budget_forecast import BudgetForecastBuilder
from src.engines.presentation.modules.income_streams import IncomeStreamsBuilder
from src.engines.presentation.modules.investment_analytics import InvestmentAnalyticsBuilder
from src.engines.presentation.modules.monthly_cashflow_summary import MonthlyCashflowSummaryBuilder
from src.engines.presentation.modules.spend_analytics import SpendAnalyticsBuilder
from src.engines.presentation.modules.tax_liability_forecast import TaxLiabilityForecastBuilder
from src.engines.presentation.modules.wealth_risk_analytics import WealthRiskAnalyticsBuilder
from src.utils.logger import logger


class WealthPresentationEngine:
    """
    Presentation Engine for Wealth & Cashflow metrics.
    Consumes LazyFrames and produces aggregated summary tables suitable for BI dashboards.
    """

    def __init__(self, rules):
        self.rules = rules

    def run(self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame]) -> dict[str, pl.LazyFrame]:
        """
        Takes collected DataFrames from the primary ETL, converts them to LazyFrames,
        performs presentation-tier aggregations, and returns them to be collected.
        """
        # 1. Core Builders (Inflation, Ledger, Net Worth)
        inflation_res = InflationBuilder(dfs, rules=self.rules).build()
        if not inflation_res:
            return {}

        ledger_res = LedgerBuilder(dfs, rules=self.rules).build()
        if not ledger_res:
            return {}

        net_worth_res = NetWorthBuilder(dfs, inflation_res, ledger_res).build()

        base_lf = {**inflation_res, **ledger_res, **net_worth_res}

        results: dict[str, pl.LazyFrame] = {}

        # 2. Net Worth Monthly Summary
        results["df_p_tf_net_worth_monthly_summary"] = base_lf["lf_nw_summary"]

        # 4. Category Spend Analytics
        results["df_p_tf_category_spend_analytics"] = SpendAnalyticsBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        # 5. Income Streams & Passive Yield
        results["df_p_tf_income_streams_monthly"] = IncomeStreamsBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        # 6. Tax Liability Forecast
        results["df_p_tf_tax_liability_forecast"] = TaxLiabilityForecastBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        # 7. Budget Forecast
        results["df_p_tf_budget_forecast_monthly"] = BudgetForecastBuilder(
            base_lf, rules=self.rules
        ).build()

        # 8. Investment Analytics (Merged Sector, Rebalancing, Attribution, Tax Harvesting)
        results["df_p_tf_investment_analytics"] = InvestmentAnalyticsBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        # 9. Wealth Risk Analytics (Merged FIRE + Risk Metrics)
        lf_risk = RiskMetricsBuilder(dfs, base_lf, rules=self.rules).build()
        results["df_p_tf_wealth_risk_analytics"] = WealthRiskAnalyticsBuilder(
            dfs, base_lf, lf_risk, rules=self.rules
        ).build()

        # 10. Monthly Cashflow Summary (now includes Financial Ratios)
        results["df_p_tf_monthly_cashflow_summary"] = MonthlyCashflowSummaryBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        logger.info(
            f"  -> Built {sum(1 for v in results.values() if v is not None)} BI presentation tables in DAG."
        )

        # 8. Post-Processing: Clean NaN values for BI compatibility (DuckDB / Power BI)
        return {
            key: lf.with_columns(cs.float().fill_nan(None))
            for key, lf in results.items()
            if lf is not None
        }
