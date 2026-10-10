from __future__ import annotations

from collections.abc import Sequence

import polars as pl


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

        Estimate totals sum only known event estimates. A partial total remains visible,
        while the missing count and completeness flag make its limitations explicit.
        A total is null only when no event in that source group has an estimate.
        """
        schema = {
            "FY": pl.String,
            "Total_Ledger_Income": pl.Float64,
            "Total_Investment_Gain_Loss": pl.Float64,
            "Total_Tax_Credits": pl.Float64,
            "Total_Estimated_Investment_Tax": pl.Float64,
            "Investment_Tax_Estimate_Count": pl.Int64,
            "Investment_Tax_Estimate_Missing_Count": pl.Int64,
            "Investment_Tax_Estimate_Complete": pl.Boolean,
            "Total_Estimated_Ledger_Tax": pl.Float64,
            "Ledger_Tax_Estimate_Count": pl.Int64,
            "Ledger_Tax_Estimate_Missing_Count": pl.Int64,
            "Ledger_Tax_Estimate_Complete": pl.Boolean,
            "Total_Event_Count": pl.Int64,
            "Ready_Count": pl.Int64,
            "Check_Required_Count": pl.Int64,
        }
        aggregated = self.lf_events.group_by("FY").agg(
            pl.col("Amount_INR")
            .filter(pl.col("Source_Type") == "LEDGER")
            .sum()
            .alias("Total_Ledger_Income"),
            pl.col("Amount_INR")
            .filter(pl.col("Source_Type") == "QUANT")
            .sum()
            .alias("Total_Investment_Gain_Loss"),
            pl.col("Amount_INR")
            .filter(pl.col("Source_Type") == "TAX_CREDIT")
            .sum()
            .alias("Total_Tax_Credits"),
            pl.col("Estimated_Tax")
            .filter(pl.col("Source_Type") == "QUANT")
            .sum()
            .alias("_Investment_Tax_Sum"),
            (pl.col("Source_Type").eq("QUANT") & pl.col("Estimated_Tax").is_not_null())
            .sum()
            .cast(pl.Int64)
            .alias("Investment_Tax_Estimate_Count"),
            (pl.col("Source_Type").eq("QUANT") & pl.col("Estimated_Tax").is_null())
            .sum()
            .cast(pl.Int64)
            .alias("Investment_Tax_Estimate_Missing_Count"),
            pl.col("Estimated_Tax")
            .filter(pl.col("Source_Type") == "LEDGER")
            .sum()
            .alias("_Ledger_Tax_Sum"),
            (pl.col("Source_Type").eq("LEDGER") & pl.col("Estimated_Tax").is_not_null())
            .sum()
            .cast(pl.Int64)
            .alias("Ledger_Tax_Estimate_Count"),
            (pl.col("Source_Type").eq("LEDGER") & pl.col("Estimated_Tax").is_null())
            .sum()
            .cast(pl.Int64)
            .alias("Ledger_Tax_Estimate_Missing_Count"),
            pl.len().cast(pl.Int64).alias("Total_Event_Count"),
            (pl.col("Tax_Status") == "READY").sum().cast(pl.Int64).alias("Ready_Count"),
            (pl.col("Tax_Status") == "CHECK_REQUIRED")
            .sum()
            .cast(pl.Int64)
            .alias("Check_Required_Count"),
        )
        return (
            aggregated.with_columns(
                pl.when(pl.col("Investment_Tax_Estimate_Count") > 0)
                .then(pl.col("_Investment_Tax_Sum"))
                .otherwise(pl.lit(None, dtype=pl.Float64))
                .alias("Total_Estimated_Investment_Tax"),
                pl.when(pl.col("Ledger_Tax_Estimate_Count") > 0)
                .then(pl.col("_Ledger_Tax_Sum"))
                .otherwise(pl.lit(None, dtype=pl.Float64))
                .alias("Total_Estimated_Ledger_Tax"),
                pl.when(
                    (
                        pl.col("Investment_Tax_Estimate_Count")
                        + pl.col("Investment_Tax_Estimate_Missing_Count")
                    )
                    > 0
                )
                .then(
                    (pl.col("Investment_Tax_Estimate_Count") > 0)
                    & (pl.col("Investment_Tax_Estimate_Missing_Count") == 0)
                )
                .otherwise(pl.lit(None, dtype=pl.Boolean))
                .alias("Investment_Tax_Estimate_Complete"),
                pl.when(
                    (
                        pl.col("Ledger_Tax_Estimate_Count")
                        + pl.col("Ledger_Tax_Estimate_Missing_Count")
                    )
                    > 0
                )
                .then(
                    (pl.col("Ledger_Tax_Estimate_Count") > 0)
                    & (pl.col("Ledger_Tax_Estimate_Missing_Count") == 0)
                )
                .otherwise(pl.lit(None, dtype=pl.Boolean))
                .alias("Ledger_Tax_Estimate_Complete"),
            )
            .drop("_Investment_Tax_Sum", "_Ledger_Tax_Sum")
            .select(list(schema))
            .cast(schema)  # type: ignore[arg-type]
            .sort("FY")
        )

    def format_tax_income_breakdown(self) -> pl.LazyFrame:
        """Return signed amounts and partial estimates, with explicit completeness."""
        schema = {
            "FY": pl.String,
            "Income_Head": pl.String,
            "Tax_Sub_Head": pl.String,
            "Source_Type": pl.String,
            "Event_Amount_INR": pl.Float64,
            "Estimated_Tax_INR": pl.Float64,
            "Estimated_Tax_Event_Count": pl.Int64,
            "Estimated_Tax_Missing_Count": pl.Int64,
            "Estimated_Tax_Complete": pl.Boolean,
            "Event_Count": pl.Int64,
            "Ready_Count": pl.Int64,
            "Check_Required_Count": pl.Int64,
        }
        # Tax credits remain a separate source category and do not receive tax estimates.
        aggregated = self.lf_events.group_by(
            ["FY", "Income_Head", "Tax_Sub_Head", "Source_Type"]
        ).agg(
            pl.col("Amount_INR").sum().alias("Event_Amount_INR"),
            pl.col("Estimated_Tax").sum().alias("_Estimated_Tax_Sum"),
            (
                pl.col("Source_Type").is_in(["LEDGER", "QUANT"])
                & pl.col("Estimated_Tax").is_not_null()
            )
            .sum()
            .cast(pl.Int64)
            .alias("Estimated_Tax_Event_Count"),
            (pl.col("Source_Type").is_in(["LEDGER", "QUANT"]) & pl.col("Estimated_Tax").is_null())
            .sum()
            .cast(pl.Int64)
            .alias("Estimated_Tax_Missing_Count"),
            pl.len().cast(pl.Int64).alias("Event_Count"),
            (pl.col("Tax_Status") == "READY").sum().cast(pl.Int64).alias("Ready_Count"),
            (pl.col("Tax_Status") == "CHECK_REQUIRED")
            .sum()
            .cast(pl.Int64)
            .alias("Check_Required_Count"),
        )
        return (
            aggregated.with_columns(
                pl.when(
                    pl.col("Source_Type").is_in(["LEDGER", "QUANT"])
                    & (pl.col("Estimated_Tax_Event_Count") > 0)
                )
                .then(pl.col("_Estimated_Tax_Sum"))
                .otherwise(pl.lit(None, dtype=pl.Float64))
                .alias("Estimated_Tax_INR"),
                pl.when(pl.col("Source_Type").is_in(["LEDGER", "QUANT"]))
                .then(
                    (pl.col("Estimated_Tax_Event_Count") > 0)
                    & (pl.col("Estimated_Tax_Missing_Count") == 0)
                )
                .otherwise(pl.lit(None, dtype=pl.Boolean))
                .alias("Estimated_Tax_Complete"),
            )
            .drop("_Estimated_Tax_Sum")
            .select(list(schema))
            .cast(schema)  # type: ignore[arg-type]
            .sort(["FY", "Income_Head", "Tax_Sub_Head", "Source_Type"])
        )

    def format_tax_reconciliation(self) -> pl.LazyFrame:
        """Reconcile canonical events with source evidence and expose estimate coverage.

        Estimate amounts sum known estimates only. Counts and completeness flags make
        partial coverage explicit. Tax credits remain separate and no set-off is applied.
        """
        schema = {
            "FY": pl.String,
            "Tax_Sub_Head": pl.String,
            "Ledger_Tax_Event_Amount": pl.Float64,
            "Excluded_Non_Taxable_Amount": pl.Float64,
            "Excluded_Non_Taxable_Event_Count": pl.Int64,
            "Excluded_Investment_Ledger_Amount": pl.Float64,
            "Excluded_Investment_Ledger_Event_Count": pl.Int64,
            "Quant_Realized_Gain_Loss": pl.Float64,
            "Estimated_Investment_Tax": pl.Float64,
            "Estimated_Tax_Event_Count": pl.Int64,
            "Estimated_Tax_Missing_Count": pl.Int64,
            "Estimated_Investment_Tax_Complete": pl.Boolean,
            "Estimated_Ledger_Tax": pl.Float64,
            "Ledger_Tax_Estimate_Count": pl.Int64,
            "Ledger_Tax_Estimate_Missing_Count": pl.Int64,
            "Estimated_Ledger_Tax_Complete": pl.Boolean,
            "Tax_Credit_Amount": pl.Float64,
            "Tax_Event_Amount": pl.Float64,
            "Investment_Source_Difference_INR": pl.Float64,
            "Ledger_Event_Count": pl.Int64,
            "Quant_Event_Count": pl.Int64,
            "Tax_Credit_Event_Count": pl.Int64,
            "Check_Required_Count": pl.Int64,
        }
        event_summary = (
            self.lf_events.group_by(["FY", "Tax_Sub_Head"])
            .agg(
                pl.col("Amount_INR")
                .filter(pl.col("Source_Type") == "LEDGER")
                .sum()
                .alias("Ledger_Tax_Event_Amount"),
                pl.col("Amount_INR")
                .filter(pl.col("Source_Type") == "QUANT")
                .sum()
                .alias("Quant_Realized_Gain_Loss"),
                pl.col("Estimated_Tax")
                .filter(pl.col("Source_Type") == "QUANT")
                .sum()
                .alias("_Investment_Tax_Sum"),
                (pl.col("Source_Type").eq("QUANT") & pl.col("Estimated_Tax").is_not_null())
                .sum()
                .cast(pl.Int64)
                .alias("Estimated_Tax_Event_Count"),
                (pl.col("Source_Type").eq("QUANT") & pl.col("Estimated_Tax").is_null())
                .sum()
                .cast(pl.Int64)
                .alias("Estimated_Tax_Missing_Count"),
                pl.col("Estimated_Tax")
                .filter(pl.col("Source_Type") == "LEDGER")
                .sum()
                .alias("_Ledger_Tax_Sum"),
                (pl.col("Source_Type").eq("LEDGER") & pl.col("Estimated_Tax").is_not_null())
                .sum()
                .cast(pl.Int64)
                .alias("Ledger_Tax_Estimate_Count"),
                (pl.col("Source_Type").eq("LEDGER") & pl.col("Estimated_Tax").is_null())
                .sum()
                .cast(pl.Int64)
                .alias("Ledger_Tax_Estimate_Missing_Count"),
                pl.col("Amount_INR")
                .filter(pl.col("Source_Type") == "TAX_CREDIT")
                .sum()
                .alias("Tax_Credit_Amount"),
                (pl.col("Source_Type") == "LEDGER")
                .sum()
                .cast(pl.Int64)
                .alias("Ledger_Event_Count"),
                (pl.col("Source_Type") == "QUANT").sum().cast(pl.Int64).alias("Quant_Event_Count"),
                (pl.col("Source_Type") == "TAX_CREDIT")
                .sum()
                .cast(pl.Int64)
                .alias("Tax_Credit_Event_Count"),
                (pl.col("Tax_Status") == "CHECK_REQUIRED")
                .sum()
                .cast(pl.Int64)
                .alias("Check_Required_Count"),
            )
            .with_columns(
                pl.when(pl.col("Estimated_Tax_Event_Count") > 0)
                .then(pl.col("_Investment_Tax_Sum"))
                .otherwise(pl.lit(None, dtype=pl.Float64))
                .alias("Estimated_Investment_Tax"),
                pl.when(pl.col("Ledger_Tax_Estimate_Count") > 0)
                .then(pl.col("_Ledger_Tax_Sum"))
                .otherwise(pl.lit(None, dtype=pl.Float64))
                .alias("Estimated_Ledger_Tax"),
                pl.when(pl.col("Quant_Event_Count") > 0)
                .then(
                    (pl.col("Estimated_Tax_Event_Count") > 0)
                    & (pl.col("Estimated_Tax_Missing_Count") == 0)
                )
                .otherwise(pl.lit(None, dtype=pl.Boolean))
                .alias("Estimated_Investment_Tax_Complete"),
                pl.when(pl.col("Ledger_Event_Count") > 0)
                .then(
                    (pl.col("Ledger_Tax_Estimate_Count") > 0)
                    & (pl.col("Ledger_Tax_Estimate_Missing_Count") == 0)
                )
                .otherwise(pl.lit(None, dtype=pl.Boolean))
                .alias("Estimated_Ledger_Tax_Complete"),
                (
                    pl.col("Ledger_Tax_Event_Amount").fill_null(0.0)
                    + pl.col("Quant_Realized_Gain_Loss").fill_null(0.0)
                ).alias("Tax_Event_Amount"),
            )
            .drop("_Investment_Tax_Sum", "_Ledger_Tax_Sum")
        )

        ledger_sources = self._ledger_source_evidence()
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
        )
        numeric_zero_defaults = [
            "Ledger_Tax_Event_Amount",
            "Excluded_Non_Taxable_Amount",
            "Excluded_Non_Taxable_Event_Count",
            "Excluded_Investment_Ledger_Amount",
            "Excluded_Investment_Ledger_Event_Count",
            "Quant_Realized_Gain_Loss",
            "Tax_Credit_Amount",
            "Tax_Event_Amount",
            "Ledger_Event_Count",
            "Estimated_Tax_Event_Count",
            "Estimated_Tax_Missing_Count",
            "Ledger_Tax_Estimate_Count",
            "Ledger_Tax_Estimate_Missing_Count",
            "Quant_Event_Count",
            "Tax_Credit_Event_Count",
            "Check_Required_Count",
        ]
        combined = combined.with_columns(
            [pl.col(column).fill_null(0).alias(column) for column in numeric_zero_defaults]
        )
        return combined.select(list(schema)).cast(schema).sort(["FY", "Tax_Sub_Head"])  # type: ignore

    def _ledger_source_evidence(self) -> pl.LazyFrame:
        """Join ledger amounts to one validated subcategory row for reconciliation."""
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
        if "FY" not in self.df_income.columns:
            income = (
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
        else:
            income = income.with_columns(pl.col("FY").cast(pl.String))

        return income.with_columns(
            pl.col("Tax_Sub_Head").fill_null("CHECK_REQUIRED"),
            pl.col("Taxability").fill_null("review"),
        ).select("FY", "CATEGORY_ID", "BASE_AMOUNT", "Tax_Sub_Head", "Taxability")
