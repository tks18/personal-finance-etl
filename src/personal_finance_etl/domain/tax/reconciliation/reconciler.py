"""Tax presentation marts and reconciliation domain logic.

Owns
----
- TaxGoldFormatter / TaxReconciler: Formats evidence-based Gold tax analytical views:
  - df_p_tax_year_summary
  - df_p_tax_income_breakdown
  - df_p_tax_reconciliation
- Evidence audit reconciliation between ledger income and Quant realized events.
- Exposing completeness flags for indicative tax liability estimates.

Does not own
-------------
- Statutory set-off, loss carry-forward, or final tax liability (evidence only).
- Tax event normalization and schema validation (owned by domain.tax.events).
- Presentation schemas and aggregation expressions (owned by domain.tax.reconciliation.schemas).
- Storage and warehouse table registration (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from collections.abc import Sequence

import polars as pl

from personal_finance_etl.domain.tax.reconciliation.schemas import (
    RECON_NUMERIC_ZERO_DEFAULTS,
    TAX_INCOME_BREAKDOWN_SCHEMA,
    TAX_RECONCILIATION_SCHEMA,
    TAX_YEAR_SUMMARY_SCHEMA,
    build_fy_agg_expressions,
    build_fy_completeness_columns,
    build_income_breakdown_agg,
    build_income_breakdown_columns,
    build_recon_agg_expressions,
    build_recon_completeness_columns,
)

__all__ = ["TaxGoldFormatter", "TaxReconciler"]

_TAX_YEAR_SUMMARY_SCHEMA = TAX_YEAR_SUMMARY_SCHEMA
_TAX_INCOME_BREAKDOWN_SCHEMA = TAX_INCOME_BREAKDOWN_SCHEMA
_TAX_RECONCILIATION_SCHEMA = TAX_RECONCILIATION_SCHEMA
_RECON_NUMERIC_ZERO_DEFAULTS = RECON_NUMERIC_ZERO_DEFAULTS


class TaxGoldFormatter:
    """Aggregate canonical TaxEvents into additive, evidence-only Gold marts.

    Tax credits are kept separate from income and realized gains/losses remain signed.
    This layer never estimates statutory tax liability or performs tax set-off.
    """

    def __init__(
        self,
        lf_events: pl.LazyFrame,
        df_income: pl.DataFrame,
        df_subcategory: pl.DataFrame,
        investment_exclusion_uids: Sequence[str] = (),
    ) -> None:
        self.lf_events = lf_events
        self.df_income = df_income
        self.df_subcategory = df_subcategory
        self.investment_exclusion_uids = frozenset(
            str(uid).strip() for uid in investment_exclusion_uids if str(uid).strip()
        )

    def format_tax_year_summary(self) -> pl.LazyFrame:
        """Return FY totals with available estimates and explicit completeness.

        Returns
        -------
        pl.LazyFrame
            LazyFrame for gold.Tax_Year_Summary.
        """
        aggregated = self.lf_events.group_by("FY").agg(build_fy_agg_expressions())
        return (
            aggregated.with_columns(build_fy_completeness_columns())
            .drop("_Investment_Tax_Sum", "_Ledger_Tax_Sum")
            .select(list(_TAX_YEAR_SUMMARY_SCHEMA))
            .cast(_TAX_YEAR_SUMMARY_SCHEMA)
            .sort("FY")
        )

    def format_tax_income_breakdown(self) -> pl.LazyFrame:
        """Return signed amounts and partial estimates, with explicit completeness.

        Returns
        -------
        pl.LazyFrame
            LazyFrame for gold.Tax_Income_Breakdown.
        """
        aggregated = self.lf_events.group_by(
            ["FY", "Income_Head", "Tax_Sub_Head", "Source_Type"]
        ).agg(build_income_breakdown_agg())
        return (
            aggregated.with_columns(build_income_breakdown_columns())
            .drop("_Estimated_Tax_Sum")
            .select(list(_TAX_INCOME_BREAKDOWN_SCHEMA))
            .cast(_TAX_INCOME_BREAKDOWN_SCHEMA)
            .sort(["FY", "Income_Head", "Tax_Sub_Head", "Source_Type"])
        )

    def _build_recon_event_summary(self) -> pl.LazyFrame:
        """Summarize canonical TaxEvents grouped by FY and Tax_Sub_Head."""
        return (
            self.lf_events.group_by(["FY", "Tax_Sub_Head"])
            .agg(build_recon_agg_expressions())
            .with_columns(build_recon_completeness_columns())
            .drop("_Investment_Tax_Sum", "_Ledger_Tax_Sum")
        )

    def _build_excluded_summaries(
        self, ledger_sources: pl.LazyFrame
    ) -> tuple[pl.LazyFrame, pl.LazyFrame]:
        """Aggregate non-taxable and investment-excluded ledger transactions."""
        excluded_non_taxable = (
            ledger_sources.filter(
                (pl.col("Taxability").str.to_lowercase() == "non_taxable")
                & ~pl.col("CATEGORY_ID").is_in(list(self.investment_exclusion_uids))
            )
            .group_by(["FY", "Tax_Sub_Head"])
            .agg(
                pl.col("BASE_AMOUNT").sum().alias("Excluded_Non_Taxable_Amount"),
                pl.len().cast(pl.Int64).alias("Excluded_Non_Taxable_Event_Count"),
            )
        )
        excluded_investments = (
            ledger_sources.filter(pl.col("CATEGORY_ID").is_in(list(self.investment_exclusion_uids)))
            .group_by(["FY", "Tax_Sub_Head"])
            .agg(
                pl.col("BASE_AMOUNT").sum().alias("Excluded_Investment_Ledger_Amount"),
                pl.len().cast(pl.Int64).alias("Excluded_Investment_Ledger_Event_Count"),
            )
        )
        return excluded_non_taxable, excluded_investments

    def format_tax_reconciliation(self) -> pl.LazyFrame:
        """Reconcile canonical events with source evidence and expose estimate coverage.

        Returns
        -------
        pl.LazyFrame
            LazyFrame for gold.Tax_Reconciliation.
        """
        event_summary = self._build_recon_event_summary()
        ledger_sources = self._ledger_source_evidence()
        excluded_non_taxable, excluded_investments = self._build_excluded_summaries(ledger_sources)

        combined = (
            event_summary.join(
                excluded_non_taxable, on=["FY", "Tax_Sub_Head"], how="full", coalesce=True
            )
            .join(excluded_investments, on=["FY", "Tax_Sub_Head"], how="full", coalesce=True)
            .with_columns(
                pl.when(
                    (pl.col("Quant_Event_Count").fill_null(0) > 0)
                    & (pl.col("Excluded_Investment_Ledger_Event_Count").fill_null(0) > 0)
                )
                .then(
                    pl.col("Quant_Realized_Gain_Loss") - pl.col("Excluded_Investment_Ledger_Amount")
                )
                .otherwise(pl.lit(None, dtype=pl.Float64))
                .alias("Investment_Source_Difference_INR")
            )
            .with_columns(
                [
                    pl.col(column).fill_null(0).alias(column)
                    for column in _RECON_NUMERIC_ZERO_DEFAULTS
                ]
            )
        )
        return (
            combined.select(list(_TAX_RECONCILIATION_SCHEMA))
            .cast(_TAX_RECONCILIATION_SCHEMA)
            .sort(["FY", "Tax_Sub_Head"])
        )

    def _validate_ledger_reconciliation_inputs(self) -> None:
        """Validate presence of required income and subcategory columns."""
        required_income = {"DATE", "CATEGORY_ID", "BASE_AMOUNT"}
        missing_income = sorted(required_income - set(self.df_income.columns))
        if missing_income:
            raise ValueError(
                "Income transactions are missing columns required for tax reconciliation: "
                f"{missing_income}"
            )

        required_subcategory = {"UID", "Tax_Sub_Head", "Taxability"}
        missing_subcategory = sorted(required_subcategory - set(self.df_subcategory.columns))
        if missing_subcategory:
            raise ValueError(
                "Income subcategory dimension is missing columns required for tax "
                f"reconciliation: {missing_subcategory}"
            )

        duplicate_uids = self.df_subcategory.group_by("UID").len().filter(pl.col("len") > 1)
        if not duplicate_uids.is_empty():
            values = duplicate_uids.get_column("UID").cast(pl.String).to_list()
            raise ValueError(
                "Income subcategory dimension contains duplicate UIDs; tax reconciliation "
                f"would multiply ledger amounts: {values[:10]}"
            )

    @staticmethod
    def _derive_ledger_fy(income: pl.LazyFrame, has_fy: bool) -> pl.LazyFrame:
        """Derive standard Indian Fiscal Year string if not already present."""
        if not has_fy:
            return (
                income.with_columns(
                    pl.col("DATE")
                    .dt.offset_by("-3mo")
                    .dt.year()
                    .cast(pl.String)
                    .alias("_FY_START_YEAR")
                )
                .with_columns(
                    (
                        pl.col("_FY_START_YEAR")
                        + "-"
                        + (pl.col("_FY_START_YEAR").cast(pl.Int32) + 1)
                        .cast(pl.String)
                        .str.slice(2, 2)
                    ).alias("FY")
                )
                .drop("_FY_START_YEAR")
            )
        return income.with_columns(pl.col("FY").cast(pl.String))

    def _ledger_source_evidence(self) -> pl.LazyFrame:
        """Join ledger amounts to one validated subcategory row for reconciliation."""
        self._validate_ledger_reconciliation_inputs()

        if self.df_income.is_empty():
            return pl.DataFrame(
                schema={
                    "FY": pl.String,
                    "CATEGORY_ID": pl.String,
                    "BASE_AMOUNT": pl.Float64,
                    "Tax_Sub_Head": pl.String,
                    "Taxability": pl.String,
                }
            ).lazy()

        income = self.df_income.lazy().with_columns(
            pl.col("CATEGORY_ID").cast(pl.String),
            pl.col("BASE_AMOUNT").cast(pl.Float64, strict=True),
            pl.col("DATE").cast(pl.Date, strict=True),
        )
        subcategories = self.df_subcategory.lazy().select(
            pl.col("UID").cast(pl.String).alias("CATEGORY_ID"),
            pl.col("Tax_Sub_Head").cast(pl.String),
            pl.col("Taxability").cast(pl.String),
        )
        income = income.join(subcategories, on="CATEGORY_ID", how="left")
        income = self._derive_ledger_fy(income, "FY" in self.df_income.columns)

        return income.with_columns(
            pl.col("Tax_Sub_Head").fill_null("CHECK_REQUIRED"),
            pl.col("Taxability").fill_null("review"),
        ).select("FY", "CATEGORY_ID", "BASE_AMOUNT", "Tax_Sub_Head", "Taxability")


TaxReconciler = TaxGoldFormatter
