import calendar
from datetime import date

import polars as pl
from dateutil.relativedelta import relativedelta


def get_stg_calendar_ref(
    f_inc_lazy: pl.LazyFrame,
    f_exp_lazy: pl.LazyFrame,
    f_trans_lazy: pl.LazyFrame,
    f_opbal_lazy: pl.LazyFrame,
    stg_mkt_lazy: pl.LazyFrame,
    f_pur_lazy: pl.LazyFrame,
    f_sale_lazy: pl.LazyFrame,
) -> tuple[date, date]:
    """
    Translates stg_CalendarRef.
    Unions the DATE columns from all 7 fact tables to find the min and max dates.
    """

    def safe_date_cast(col_name: str) -> pl.Expr:
        return pl.coalesce(
            [
                # 1. If it's already a Date or Datetime, this cast succeeds
                pl.col(col_name).cast(pl.Date, strict=False),
                # 2. If it's a standard string Date ("YYYY-MM-DD")
                pl.col(col_name).cast(pl.String).str.to_date("%Y-%m-%d", strict=False),
                # 3. If it's a standard string Date ("DD-MM-YYYY")
                pl.col(col_name).cast(pl.String).str.to_date("%d-%m-%Y", strict=False),
                # 4. If it's a string Datetime ("YYYY-MM-DD HH:MM:SS")
                pl.col(col_name)
                .cast(pl.String)
                .str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False)
                .dt.date(),
            ]
        ).alias("DATE")

    df_union = pl.concat(
        [
            f_inc_lazy.select(safe_date_cast("DATE")),
            f_exp_lazy.select(safe_date_cast("DATE")),
            f_trans_lazy.select(safe_date_cast("DATE")),
            f_opbal_lazy.select(safe_date_cast("ZTXDATESTR")),
            stg_mkt_lazy.select(safe_date_cast("Date")),
            f_pur_lazy.select(safe_date_cast("Date")),
            f_sale_lazy.select(safe_date_cast("Date")),
        ]
    ).unique()

    # We collect this immediately because we need the scalar min/max values to generate the calendar range
    df_collected = df_union.drop_nulls().collect()

    min_date = df_collected["DATE"].min()
    max_date = df_collected["DATE"].max()

    from typing import cast

    return cast(date, min_date), cast(date, max_date)


def transform_d_calendar(min_date: date, max_date: date) -> pl.LazyFrame:
    """
    Generates all 40 requested time-intelligence columns for the Calendar Master.
    Assumes an April 1st - March 31st Financial Year.
    """
    start_date = min_date.replace(day=1) - relativedelta(months=1)
    last_day_of_max_month = calendar.monthrange(max_date.year, max_date.month)[1]
    end_date = max_date.replace(day=last_day_of_max_month)

    df_cal = pl.DataFrame({"Date": pl.date_range(start_date, end_date, "1d", eager=True)}).lazy()

    df_transformed = (
        df_cal
        # Block 1: Base Numeric and String Extractions
        .with_columns(
            [
                pl.col("Date").dt.day().alias("Day"),
                pl.col("Date").dt.strftime("%A").alias("Day Name"),
                pl.col("Date").dt.strftime("%a").alias("Day Name Short"),
                pl.col("Date").dt.ordinal_day().alias("Day Ordinal"),
                pl.col("Date").dt.weekday().alias("Weekday"),
                pl.col("Date").dt.week().alias("Week"),
                pl.col("Date").dt.month().alias("Month"),
                pl.col("Date").dt.strftime("%B").alias("Month Name"),
                pl.col("Date").dt.strftime("%b").alias("Month Name Short"),
                pl.col("Date").dt.quarter().alias("Quarter"),
                pl.col("Date").dt.year().alias("Year"),
                pl.col("Date").dt.offset_by("-3mo").alias("FY_Shift"),
                pl.col("Date").dt.truncate("1mo").alias("Start of Month"),
                pl.col("Date").dt.month_end().alias("End of Month"),
                pl.col("Date").dt.truncate("1w").alias("Start of Week"),
            ]
        )
        # Block 2: Dependent Dates (Quarters and Weeks)
        .with_columns(
            [
                pl.col("Start of Week").dt.offset_by("6d").alias("End of Week"),
                (
                    pl.col("Year").cast(pl.String)
                    + "-"
                    + ((pl.col("Quarter") - 1) * 3 + 1).cast(pl.String).str.pad_start(2, "0")
                    + "-01"
                )
                .str.to_date("%Y-%m-%d", strict=False)
                .alias("Start of Quarter"),
            ]
        )
        # Block 3a: Dependent End of Quarter and FY Extracts
        .with_columns(
            [
                pl.col("Start of Quarter")
                .dt.offset_by("3mo")
                .dt.offset_by("-1d")
                .alias("End of Quarter"),
                pl.col("FY_Shift").dt.year().alias("FY Year"),
                pl.col("FY_Shift").dt.month().alias("FY Month"),
                pl.col("FY_Shift").dt.quarter().alias("FY Quarter"),
                pl.col("Week").alias("Week Ordinal"),
            ]
        )
        # Block 3b: SPLIT HERE - Safe to reference End of Quarter now
        .with_columns(
            [
                pl.col("Start of Month").alias("FY Start of Month"),
                pl.col("End of Month").alias("FY End of Month"),
                pl.col("Start of Quarter").alias("FY Start of Quarter"),
                pl.col("End of Quarter").alias("FY End of Quarter"),
            ]
        )
        # Block 4: String Concat and Labels
        .with_columns(
            [
                (pl.lit("Day ") + pl.col("Day Ordinal").cast(pl.String)).alias("Day Ordinal Name"),
                (pl.lit("Wk ") + pl.col("Week Ordinal").cast(pl.String)).alias("Week Ordinal Name"),
                (pl.lit("Q") + pl.col("Quarter").cast(pl.String)).alias("Quarter Name"),
                (pl.lit("Q") + pl.col("FY Quarter").cast(pl.String)).alias("FY Quarter Name"),
                (
                    pl.lit("FY")
                    + pl.col("FY Year").cast(pl.String).str.slice(2, 2)
                    + "-"
                    + (pl.col("FY Year") + 1).cast(pl.String).str.slice(2, 2)
                ).alias("Financial Year"),
                pl.col("Date").dt.strftime("%B %Y").alias("Month - Year"),
                pl.col("Date").dt.strftime("%b-%y").alias("Short Month - Year"),
                pl.col("Date").dt.strftime("%b '%y").alias("V Short Month - Year"),
                (pl.lit("Week ") + pl.col("Week").cast(pl.String)).alias("Week Name"),
                pl.when(pl.col("Weekday").is_in([6, 7])).then(1).otherwise(0).alias("IS_WEEKEND"),
            ]
        )
        # Block 5: Final Cross-Concatenations
        .with_columns(
            [
                (pl.col("Quarter Name") + "-" + pl.col("Year").cast(pl.String)).alias(
                    "Quarter - Year"
                ),
                (pl.col("FY Quarter Name") + "-" + pl.col("Financial Year")).alias(
                    "FY Quarter - Year"
                ),
                (
                    pl.lit("W")
                    + pl.col("Week").cast(pl.String)
                    + "-"
                    + pl.col("Year").cast(pl.String)
                ).alias("Week - Year"),
                (pl.col("Week Name") + " - " + pl.col("Year").cast(pl.String)).alias(
                    "Week Name - Year"
                ),
            ]
        )
        # Clean up
        .drop("FY_Shift")
        .select(
            [
                "Date",
                "Day",
                "Day Name",
                "Day Name Short",
                "Day Ordinal",
                "Day Ordinal Name",
                "Weekday",
                "Week",
                "Week Ordinal",
                "Week Ordinal Name",
                "Month",
                "Month Name",
                "Month Name Short",
                "Quarter",
                "Quarter Name",
                "Year",
                "FY Month",
                "FY Year",
                "Start of Month",
                "FY Start of Month",
                "FY Quarter",
                "FY Quarter Name",
                "Month - Year",
                "Short Month - Year",
                "Quarter - Year",
                "FY Quarter - Year",
                "Financial Year",
                "Start of Quarter",
                "FY Start of Quarter",
                "End of Month",
                "FY End of Month",
                "End of Quarter",
                "FY End of Quarter",
                "V Short Month - Year",
                "Week - Year",
                "Week Name",
                "Start of Week",
                "End of Week",
                "Week Name - Year",
                "IS_WEEKEND",
            ]
        )
    )

    return df_transformed
