import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules


class HarvestRecommendationCalculator:
    """Calculates Stepup and Harvest Recommendations."""

    @staticmethod
    def calculate(lazy_df: pl.LazyFrame, rules: FinancialRules) -> pl.LazyFrame:
        wait_days = rules.assumptions.tax.harvest_wait_days_threshold if rules else 90

        # Derive foreign equity TAX_SUBTYPE exclusions from config if available;
        # fall back to the known set for backward compatibility.
        _foreign_subtypes: list[str] = [
            "us_listed",
            "us_stocks",
            "foreign",
            "us_equity",
            "international",
        ]

        lazy_df = lazy_df.with_columns(
            (
                (pl.col("Holding_Type") == "LTCG")
                & (pl.col("TAX_TYPE").str.to_lowercase() == "equity")
                # Section 112A step-up applies only to listed Indian equity.
                & ~pl.col("TAX_SUBTYPE").str.to_lowercase().is_in(_foreign_subtypes)
                & (pl.col("Unrealized_LTCG") > 0)
                & (pl.col("Unrealized_LTCG") <= pl.col("Equity_LTCG_Exemption"))
            ).alias("Stepup_Eligible"),
            (
                (pl.col("Unrealized_Loss") < 0)
                & ~(
                    (pl.col("TAX_TYPE").str.to_lowercase() == "debt")
                    & (pl.col("Holding_Type") == "STCG")
                )
            ).alias("Can_Harvest_Loss"),
        )

        lazy_df = lazy_df.with_columns(
            pl.when(pl.col("Can_Harvest_Loss"))
            .then(pl.lit("HARVEST_LOSS"))
            .when((pl.col("Holding_Type") == "LTCG") & pl.col("Stepup_Eligible"))
            .then(pl.lit("HARVEST_LTCG_EXEMPT"))
            .when(
                (pl.col("Holding_Type") == "STCG")
                & (pl.col("Days_To_LTCG") > 0)
                & (pl.col("Days_To_LTCG") <= wait_days)
                & (pl.col("P/L") > 0)
            )
            .then(pl.lit("WAIT_FOR_LTCG"))
            .otherwise(pl.lit("HOLD"))
            .alias("Harvest_Recommendation")
        )

        return lazy_df
