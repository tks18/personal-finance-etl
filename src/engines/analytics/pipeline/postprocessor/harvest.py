import polars as pl

class HarvestRecommendationCalculator:
    """Calculates Stepup and Harvest Recommendations."""
    @staticmethod
    def calculate(lazy_df: pl.LazyFrame) -> pl.LazyFrame:
        lazy_df = lazy_df.with_columns(
            (
                (pl.col("Holding_Type") == "LTCG")
                & (pl.col("TAX_TYPE").str.to_lowercase() == "equity")
                & (pl.col("Unrealized_LTCG") > 0)
                & (pl.col("Unrealized_LTCG") <= pl.col("FY_LTCG_Remaining_Exemption"))
            ).alias("Stepup_Eligible")
        )

        lazy_df = lazy_df.with_columns(
            pl.when(pl.col("Unrealized_Loss") < 0)
            .then(pl.lit("HARVEST_LOSS"))
            .when(pl.col("Holding_Type") == "LTCG", pl.col("Stepup_Eligible"))
            .then(pl.lit("HARVEST_LTCG_EXEMPT"))
            .when(
                (pl.col("Holding_Type") == "STCG")
                & (pl.col("Days_To_LTCG") > 0)
                & (pl.col("Days_To_LTCG") <= 90)
                & (pl.col("P/L") > 0)
            )
            .then(pl.lit("WAIT_FOR_LTCG"))
            .otherwise(pl.lit("HOLD"))
            .alias("Harvest_Recommendation")
        )

        return lazy_df
