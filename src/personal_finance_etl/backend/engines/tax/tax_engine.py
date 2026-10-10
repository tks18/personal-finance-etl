import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.engines.tax.core.base_events import BaseEventsBuilder
from personal_finance_etl.backend.engines.tax.core.forecast import TaxLiabilityForecastBuilder
from personal_finance_etl.backend.engines.tax.core.fy_state import FYStateBuilder
from personal_finance_etl.backend.engines.tax.core.gold_formatter import TaxGoldFormatter
from personal_finance_etl.backend.engines.tax.core.liability import LiabilityCalculator
from personal_finance_etl.backend.engines.tax.core.set_offs import LossSetOffProcessor


class TaxEngine:
    def __init__(
        self,
        df_income: pl.DataFrame,
        df_realized_events: pl.DataFrame,
        df_subcategory: pl.DataFrame,
        df_market: pl.DataFrame,
        df_analytics_lot: pl.DataFrame,
        df_macro: pl.DataFrame,
        rules: FinancialRules | None,
        rules_snapshot_id: str = "UNKNOWN",
    ):
        self.df_income = df_income
        self.df_realized_events = df_realized_events
        self.df_subcategory = df_subcategory
        self.df_market = df_market
        self.df_analytics_lot = df_analytics_lot
        self.df_macro = df_macro
        self.rules = rules
        self.rules_snapshot_id = rules_snapshot_id

    def run(self) -> dict[str, pl.DataFrame]:
        """Execute the Tax Engine and return materialized tables."""
        builder = BaseEventsBuilder(
            df_income=self.df_income,
            df_realized_events=self.df_realized_events,
            df_subcategory=self.df_subcategory,
            rules=self.rules,
            rules_snapshot_id=self.rules_snapshot_id,
            df_macro=self.df_macro,
        )
        lf_tax_events = builder.build()

        processor = LossSetOffProcessor(lf_events=lf_tax_events, rules=self.rules)
        lf_set_offs = processor.process()

        calculator = LiabilityCalculator(
            lf_tax_events=lf_tax_events,
            lf_set_offs=lf_set_offs,
            rules=self.rules,
        )
        lf_tax_liability = calculator.calculate()

        fy_builder = FYStateBuilder(
            lf_events=lf_tax_events,
            lf_set_offs=lf_set_offs,
            lf_liability=lf_tax_liability,
            df_income=self.df_income,
            df_subcategory=self.df_subcategory,
            rules=self.rules,
        )
        lf_tax_fy_state = fy_builder.build()

        formatter = TaxGoldFormatter(
            lf_events=lf_tax_events,
            lf_fy_state=lf_tax_fy_state,
            lf_liability=lf_tax_liability,
            lf_set_offs=lf_set_offs,
            lf_analytics_lot=self.df_analytics_lot.lazy(),
            df_income=self.df_income,
            df_subcategory=self.df_subcategory,
            rules=self.rules,
        )

        lf_p_tax_year_summary = formatter.format_tax_year_summary()
        lf_p_tax_income_breakdown = formatter.format_tax_income_breakdown()
        lf_p_tax_reconciliation = formatter.format_tax_reconciliation()

        # 6. Liability Forecast Builder (Lazy)
        # Note: forecast_builder returns a LazyFrame
        forecast_builder = TaxLiabilityForecastBuilder(
            dfs={
                "df_f_investment_analytics_lot": self.df_analytics_lot,
                "df_d_macro_parameters": self.df_macro,
            },
            base_lf={
                "lf_inc_agg": self.df_income.lazy().join(self.df_subcategory.lazy(), left_on="CATEGORY_ID", right_on="UID", how="left")
            },
            rules=self.rules
        )
        lf_forecast = forecast_builder.build()

        # Collect all tables as LazyFrames, then do one pl.collect_all()
        lazy_frames = [
            lf_tax_events,
            lf_tax_fy_state,
            lf_p_tax_year_summary,
            lf_p_tax_income_breakdown,
            lf_p_tax_reconciliation,
            lf_forecast,
        ]

        collected = pl.collect_all(lazy_frames, engine="streaming")

        return {
            "df_f_tax_events": collected[0],
            "df_f_tax_fy_state": collected[1],
            "df_p_tax_year_summary": collected[2],
            "df_p_tax_income_breakdown": collected[3],
            "df_p_tax_reconciliation": collected[4],
            "df_p_investment_tax_liability_forecast": collected[5],
        }
