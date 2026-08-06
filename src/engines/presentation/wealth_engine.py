from collections.abc import Mapping

import polars as pl
import polars.selectors as cs

from src.engines.presentation.modules.base_metrics import BaseMetricsBuilder
from src.engines.presentation.modules.budget_forecast import BudgetForecastBuilder
from src.engines.presentation.modules.financial_ratios import FinancialRatiosBuilder
from src.engines.presentation.modules.fire_forecasting import FireForecastingBuilder
from src.engines.presentation.modules.income_streams import IncomeStreamsBuilder
from src.engines.presentation.modules.investment_snapshot import InvestmentSnapshotBuilder
from src.engines.presentation.modules.monthly_cashflow_summary import MonthlyCashflowSummaryBuilder
from src.engines.presentation.modules.performance_attribution import PerformanceAttributionBuilder
from src.engines.presentation.modules.portfolio_rebalancing import PortfolioRebalancingBuilder
from src.engines.presentation.modules.risk_metrics import RiskMetricsBuilder
from src.engines.presentation.modules.sector_allocation import SectorAllocationBuilder
from src.engines.presentation.modules.spend_analytics import SpendAnalyticsBuilder
from src.engines.presentation.modules.tax_analytics import TaxAnalyticsBuilder
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
        # 1. Base Aggregations (Net Worth Summary, Ledger, etc.)
        base_lf = BaseMetricsBuilder(dfs, rules=self.rules).build()

        if not base_lf:
            return {}

        results: dict[str, pl.LazyFrame] = {}

        # 2. Net Worth Monthly Summary
        results["df_p_tf_net_worth_monthly_summary"] = base_lf["lf_nw_summary"]

        # 3. Financial Ratios Monthly
        results["df_p_tf_financial_ratios_monthly"] = FinancialRatiosBuilder(
            base_lf, rules=self.rules
        ).build()

        # 4. Category Spend Analytics
        results["df_p_tf_category_spend_analytics"] = SpendAnalyticsBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        # 5. Income Streams & Passive Yield
        results["df_p_tf_income_streams_monthly"] = IncomeStreamsBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        # 6. Advanced Analytics (Risk, Sectors, Tax Harvesting, Rebalancing, Tax Forecast, Performance Attribution)
        results["df_p_tf_risk_metrics"] = RiskMetricsBuilder(dfs, base_lf, rules=self.rules).build()
        results["df_p_tf_sector_allocation_monthly"] = SectorAllocationBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        tax_builder = TaxAnalyticsBuilder(dfs, base_lf, rules=self.rules)
        results["df_p_tf_tax_harvesting"] = tax_builder.build_tax_harvesting()
        results["df_p_tf_tax_liability_forecast"] = tax_builder.build_tax_liability_forecast()

        results["df_p_tf_portfolio_rebalancing_plan"] = PortfolioRebalancingBuilder(
            dfs, base_lf, rules=self.rules
        ).build()
        results["df_p_tf_performance_attribution"] = PerformanceAttributionBuilder(
            dfs, base_lf, rules=self.rules
        ).build()

        # 7. Budget Forecast (40/20/30+10 rule, 3-month forward plan)
        results["df_p_tf_budget_forecast_monthly"] = BudgetForecastBuilder(
            base_lf, rules=self.rules
        ).build()

        # 8. FIRE & Wealth Forecasting
        results["df_p_tf_fire_forecasting_monthly"] = FireForecastingBuilder(
            dfs, base_lf, results["df_p_tf_risk_metrics"], rules=self.rules
        ).build()

        # 9. Investment Snapshots (ISIN & Portfolio level)
        snapshot_builder = InvestmentSnapshotBuilder(dfs, base_lf, rules=self.rules)
        results["df_p_tf_investment_snapshot_isin"] = snapshot_builder.build_isin()
        results["df_p_tf_investment_snapshot_portfolio"] = snapshot_builder.build_portfolio()

        # 10. Monthly Cashflow Summary
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
