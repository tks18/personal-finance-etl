import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.engines.tax.utils.date_utils import add_fy_if_missing


class TaxGoldFormatter:
    """Formats the Tax Engine outputs into the expected Gold DataFrames."""

    def __init__(
        self,
        lf_events: pl.LazyFrame,
        lf_fy_state: pl.LazyFrame,
        lf_liability: pl.LazyFrame,
        lf_set_offs: pl.LazyFrame,
        lf_analytics_lot: pl.LazyFrame,
        df_income: pl.DataFrame,
        df_subcategory: pl.DataFrame,
        rules: FinancialRules | None,
    ):
        self.lf_events = lf_events
        self.lf_fy_state = lf_fy_state
        self.lf_liability = lf_liability
        self.lf_set_offs = lf_set_offs
        self.lf_analytics_lot = lf_analytics_lot
        self.df_income = df_income
        self.df_subcategory = df_subcategory
        self.rules = rules

    def format_tax_year_summary(self) -> pl.LazyFrame:
        schema = {
            "FY": pl.Utf8,
            "Total_Gross_Income": pl.Float64,
            "Total_Excluded_Non_Taxable": pl.Float64,
            "Total_Taxable_Income": pl.Float64,
            "Estimated_Tax_Liability": pl.Float64,
            "Effective_Tax_Rate_Pct": pl.Float64,
        }
        df = self.lf_fy_state.select(
            [
                pl.col("FY"),
                pl.col("Gross_Income").alias("Total_Gross_Income"),
                pl.col("Excluded_Non_Taxable_Income").alias("Total_Excluded_Non_Taxable"),
                pl.col("Tax_Relevant_Income").alias("Total_Taxable_Income"),  # or Net_Taxable
                pl.col("Estimated_Net_Tax_Position").alias("Estimated_Tax_Liability"),
            ]
        )

        df = df.with_columns(
            pl.when(pl.col("Total_Taxable_Income") > 0)
            .then((pl.col("Estimated_Tax_Liability") / pl.col("Total_Taxable_Income")) * 100.0)
            .otherwise(0.0)
            .alias("Effective_Tax_Rate_Pct")
        ).cast(schema)  # type: ignore[arg-type]
        return df

    def format_tax_income_breakdown(self) -> pl.LazyFrame:
        schema = {
            "FY": pl.Utf8,
            "Income_Head": pl.Utf8,
            "Tax_Sub_Head": pl.Utf8,
            "Capital_Gains_Group": pl.Utf8,
            "Source_Type": pl.Utf8,
            "Gross_Amount": pl.Float64,
            "Taxable_Amount": pl.Float64,
        }
        # Capital_Gains_Group may not exist in older pipeline outputs — coalesce to null.
        _schema_names = self.lf_events.collect_schema().names()
        _cg_group_col = (
            pl.col("Capital_Gains_Group")
            if "Capital_Gains_Group" in _schema_names
            else pl.lit(None).cast(pl.Utf8).alias("Capital_Gains_Group")
        )
        df = self.lf_events.with_columns(_cg_group_col.alias("Capital_Gains_Group")).group_by(
            ["FY", "Income_Head", "Tax_Sub_Head", "Capital_Gains_Group", "Source_Type"]
        ).agg(
            [
                pl.col("Gross_Amount").sum().alias("Gross_Amount"),
                pl.col("Taxable_Amount").sum().alias("Taxable_Amount"),
                pl.col("Estimated_Tax").sum().alias("Estimated_Tax"),
            ]
        )

        df = df.cast(schema)  # type: ignore[arg-type]
        return df


    def format_tax_reconciliation(self) -> pl.LazyFrame:
        schema = {
            "FY": pl.Utf8,
            "Tax_Sub_Head": pl.Utf8,
            "Source_Type": pl.Utf8,
            "Gross_Source_Amount": pl.Float64,
            "Excluded_Non_Taxable_Amount": pl.Float64,
            "Tax_Event_Amount": pl.Float64,
            "Realized_Investment_Gain_Loss": pl.Float64,
            "Set_Off_Amount": pl.Float64,
            "Net_Taxable_Amount": pl.Float64,
            "Estimated_Tax": pl.Float64,
            "Tax_Credits": pl.Float64,
            "Estimated_Net_Tax_Position": pl.Float64,
            "Event_Count": pl.Int64,
            "Check_Required_Count": pl.Int64,
        }

        # Non-taxable streams from df_income
        df_ledger = self.df_income.lazy().join(
            self.df_subcategory.lazy().select(["UID", "Tax_Sub_Head", "Taxability"]),
            left_on="CATEGORY_ID",
            right_on="UID",
            how="left",
        )
        df_ledger = add_fy_if_missing(df_ledger, "DATE")
        df_non_tax = (
            df_ledger.filter(pl.col("Taxability") == "non_taxable")
            .group_by(["FY", "Tax_Sub_Head"])
            .agg(pl.col("BASE_AMOUNT").sum().alias("Excluded_Non_Taxable_Amount"))
            .with_columns(pl.lit("LEDGER").alias("Source_Type"))
        )

        df_evt = self.lf_events.group_by(["FY", "Tax_Sub_Head", "Source_Type"]).agg(
            [
                pl.col("Gross_Amount").sum().alias("Tax_Event_Gross"),
                pl.col("Taxable_Amount").sum().alias("Tax_Event_Amount"),
                pl.col("Realized_Gain_Loss").sum().alias("Realized_Investment_Gain_Loss"),
                pl.col("Estimated_Tax").sum().alias("Estimated_Tax"),
                pl.len().alias("Event_Count"),
                pl.when(pl.col("Tax_Status") == "CHECK_REQUIRED")
                .then(1)
                .otherwise(0)
                .sum()
                .alias("Check_Required_Count"),
            ]
        )

        df = df_evt.join(df_non_tax, on=["FY", "Tax_Sub_Head", "Source_Type"], how="full")
        df = df.with_columns(
            pl.coalesce(["FY", "FY_right"]).alias("FY"),
            pl.coalesce(["Tax_Sub_Head", "Tax_Sub_Head_right"]).alias("Tax_Sub_Head"),
            pl.coalesce(["Source_Type", "Source_Type_right"]).alias("Source_Type"),
        ).fill_null(0.0)

        # Aggregate set-off amounts per FY from the loss set-off processor output.
        # Set_Off_Amount represents total losses applied (intra-year + brought-forward) per FY.
        df_so_agg = (
            self.lf_set_offs.filter(pl.col("Tax_Method") == "capital_gains")
            .group_by("FY")
            .agg(pl.col("Set_Off_Amount").sum().alias("Set_Off_Amount"))
        )

        df = df.join(df_so_agg, on="FY", how="left")
        df = df.with_columns(
            (pl.col("Tax_Event_Gross") + pl.col("Excluded_Non_Taxable_Amount")).alias(
                "Gross_Source_Amount"
            ),
            pl.col("Set_Off_Amount").fill_null(0.0),
            pl.col("Tax_Event_Amount").alias("Net_Taxable_Amount"),
            pl.lit(0.0).alias("Tax_Credits"),
        ).with_columns(
            (pl.col("Estimated_Tax") - pl.col("Tax_Credits")).alias("Estimated_Net_Tax_Position")
        )

        df = df.select([c for c in schema.keys()]).cast(schema)  # type: ignore[arg-type]
        return df
