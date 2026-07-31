from collections.abc import Mapping

import polars as pl

from src.engines.presentation.modules.advanced_analytics import AdvancedAnalyticsBuilder
from src.engines.presentation.modules.base_metrics import BaseMetricsBuilder
from src.engines.presentation.modules.financial_ratios import FinancialRatiosBuilder
from src.engines.presentation.modules.fire_forecasting import FireForecastingBuilder
from src.engines.presentation.modules.income_streams import IncomeStreamsBuilder
from src.engines.presentation.modules.spend_analytics import SpendAnalyticsBuilder


class WealthPresentationEngine:
    """
    Presentation Engine for Wealth & Cashflow metrics.
    Consumes LazyFrames and produces aggregated summary tables suitable for BI dashboards.
    """

    def __init__(self):
        pass

    def run(self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame]) -> dict[str, pl.LazyFrame]:
        """
        Takes collected DataFrames from the primary ETL, converts them to LazyFrames,
        performs presentation-tier aggregations, and returns them to be collected.
        """
        # 1. Base Aggregations (Net Worth Summary, Ledger, etc.)
        base_lf = BaseMetricsBuilder(dfs).build()

        if not base_lf:
            return {}

        results: dict[str, pl.LazyFrame] = {}

        # 2. Net Worth Monthly Summary
        results["df_p_tf_net_worth_monthly_summary"] = base_lf["lf_nw_summary"]

        # 3. Financial Ratios Monthly
        results["df_p_tf_financial_ratios_monthly"] = FinancialRatiosBuilder(base_lf).build()

        # 4. Category Spend Analytics
        results["df_p_tf_category_spend_analytics"] = SpendAnalyticsBuilder(dfs, base_lf).build()

        # 5. Income Streams & Passive Yield
        results["df_p_tf_income_streams_monthly"] = IncomeStreamsBuilder(dfs, base_lf).build()

        # 6. FIRE & Wealth Forecasting
        results["df_p_tf_fire_forecasting_monthly"] = FireForecastingBuilder(base_lf).build()

        # 7. Advanced Analytics (Risk, Sectors, Tax Harvesting)
        adv_builder = AdvancedAnalyticsBuilder(dfs, base_lf)
        results["df_p_tf_risk_metrics"] = adv_builder.build_risk_dashboard()
        results["df_p_tf_sector_allocation_monthly"] = adv_builder.build_sector_allocation()
        results["df_p_tf_tax_harvesting"] = adv_builder.build_tax_harvesting()

        return results
