import polars as pl


def add_fy_if_missing(df: pl.LazyFrame, date_col: str) -> pl.LazyFrame:
    """Adds Financial Year (FY) column to a LazyFrame if missing."""
    if "FY" not in df.collect_schema().names():
        df = (
            df.with_columns(
                pl.col(date_col)
                .cast(pl.Date, strict=False)
                .dt.offset_by("-3mo")
                .dt.year()
                .alias("FY_Year")
            )
            .with_columns(
                (
                    pl.col("FY_Year").cast(pl.String)
                    + "-"
                    + (pl.col("FY_Year") + 1).cast(pl.String).str.slice(2, 2)
                ).alias("FY")
            )
            .drop("FY_Year")
        )
    return df
