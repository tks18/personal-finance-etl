import polars as pl


class HarvestRecommendationCalculator:
    """Calculates Stepup and Harvest Recommendations."""

    @staticmethod
    def calculate(lazy_df: pl.LazyFrame, rules=None) -> pl.LazyFrame:
        wait_days = 90
        if rules and rules.assumptions:
            wait_days = rules.assumptions.tax.harvest_wait_days_threshold

        lazy_df = lazy_df.with_columns(
            (
                (pl.col("Holding_Type") == "LTCG")
                & (pl.col("TAX_TYPE").str.to_lowercase() == "equity")
                & (pl.col("Unrealized_LTCG") > 0)
                & (pl.col("Unrealized_LTCG") <= pl.col("FY_LTCG_Remaining_Exemption"))
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
