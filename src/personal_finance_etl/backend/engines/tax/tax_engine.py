from __future__ import annotations

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.engines.tax.core.base_events import BaseEventsBuilder
from personal_finance_etl.backend.engines.tax.core.gold_formatter import TaxGoldFormatter


class TaxEngine:
    """Orchestrate evidence normalization and presentation-only tax aggregates."""

    def __init__(
        self,
        df_income: pl.DataFrame,
        df_realized_events: pl.DataFrame,
        df_subcategory: pl.DataFrame,
        rules: FinancialRules | None,
        df_macro_parameters: pl.DataFrame | None = None,
    ) -> None:
        self.df_income = df_income
        self.df_realized_events = df_realized_events
        self.df_subcategory = df_subcategory
        self.rules = rules
        self.df_macro_parameters = df_macro_parameters

    def run(self) -> dict[str, pl.DataFrame]:
        if self.rules is None:
            raise ValueError("FinancialRules must be provided to execute the Tax Engine.")

        lf_tax_events = BaseEventsBuilder(
            df_income=self.df_income,
            df_realized_events=self.df_realized_events,
            df_subcategory=self.df_subcategory,
            rules=self.rules,
            df_macro_parameters=self.df_macro_parameters,
        ).build()

        exclusions = self.rules.assumptions.tax.investment_exclusions
        investment_exclusion_uids = sorted(
            set(exclusions.stcg_sub_cat_ids) | set(exclusions.ltcg_sub_cat_ids)
        )
        formatter = TaxGoldFormatter(
            lf_events=lf_tax_events,
            df_income=self.df_income,
            df_subcategory=self.df_subcategory,
            investment_exclusion_uids=investment_exclusion_uids,
        )
        lazy_frames = [
            lf_tax_events,
            formatter.format_tax_year_summary(),
            formatter.format_tax_income_breakdown(),
            formatter.format_tax_reconciliation(),
        ]
        collected = pl.collect_all(lazy_frames, engine="streaming")
        return {
            "df_f_tax_events": collected[0],
            "df_p_tax_year_summary": collected[1],
            "df_p_tax_income_breakdown": collected[2],
            "df_p_tax_reconciliation": collected[3],
        }
