import datetime

import polars as pl


def get_stg_calendar_ref(
    f_inc_lazy: pl.LazyFrame,
    f_exp_lazy: pl.LazyFrame,
    f_trans_lazy: pl.LazyFrame,
    f_opbal_lazy: pl.LazyFrame,
    stg_mkt_lazy: pl.LazyFrame,
    f_pur_lazy: pl.LazyFrame,
    f_sale_lazy: pl.LazyFrame,
) -> pl.LazyFrame:
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

    df_bounds_lazy = df_union.drop_nulls().select(
        pl.min("DATE").alias("min_date"), pl.max("DATE").alias("max_date")
    )

    return df_bounds_lazy


def transform_d_calendar(df_bounds_lazy: pl.LazyFrame) -> pl.LazyFrame:
    """
    Generates all 40 requested time-intelligence columns for the Calendar Master.
    Assumes an April 1st - March 31st Financial Year.
    """
    df_cal = df_bounds_lazy.select(
        pl.date_ranges(
            pl.col("min_date").dt.truncate("1mo").dt.offset_by("-1mo"),
            pl.col("max_date").dt.month_end(),
            "1d",
        ).alias("Date")
    ).explode("Date")

    df_transformed = (
        df_cal
        # Block 1: Base Numeric and String Extractions
        .with_columns(
            [
                pl.col("Date").dt.day().alias("Day"),
                pl.col("Date").dt.strftime("%A").alias("Day_Name"),
                pl.col("Date").dt.strftime("%a").alias("Day_Name_Short"),
                pl.col("Date").dt.ordinal_day().alias("Day_Ordinal"),
                pl.col("Date").dt.weekday().alias("Weekday"),
                pl.col("Date").dt.week().alias("Week"),
                pl.col("Date").dt.month().alias("Month"),
                pl.col("Date").dt.strftime("%B").alias("Month_Name"),
                pl.col("Date").dt.strftime("%b").alias("Month_Name_Short"),
                pl.col("Date").dt.quarter().alias("Quarter"),
                pl.col("Date").dt.year().alias("Year"),
                pl.col("Date").dt.offset_by("-3mo").alias("FY_Shift"),
                pl.col("Date").dt.truncate("1mo").alias("Start_of_Month"),
                pl.col("Date").dt.month_end().alias("End_of_Month"),
                pl.col("Date").dt.truncate("1w").alias("Start_of_Week"),
            ]
        )
        # Block 2: Dependent Dates (Quarters and Weeks)
        .with_columns(
            [
                pl.col("Start_of_Week").dt.offset_by("6d").alias("End_of_Week"),
                (
                    pl.col("Year").cast(pl.String)
                    + "-"
                    + ((pl.col("Quarter") - 1) * 3 + 1).cast(pl.String).str.pad_start(2, "0")
                    + "-01"
                )
                .str.to_date("%Y-%m-%d", strict=False)
                .alias("Start_of_Quarter"),
            ]
        )
        # Block 3a: Dependent End of Quarter and FY Extracts
        .with_columns(
            [
                pl.col("Start_of_Quarter")
                .dt.offset_by("3mo")
                .dt.offset_by("-1d")
                .alias("End_of_Quarter"),
                pl.col("FY_Shift").dt.year().alias("FY_Year"),
                pl.col("FY_Shift").dt.month().alias("FY_Month"),
                pl.col("FY_Shift").dt.quarter().alias("FY_Quarter"),
                pl.col("Week").alias("Week_Ordinal"),
            ]
        )
        # Block 3b: SPLIT HERE - Safe to reference End of Quarter now
        .with_columns(
            [
                pl.col("Start_of_Month").alias("FY_Start_of_Month"),
                pl.col("End_of_Month").alias("FY_End_of_Month"),
                pl.col("Start_of_Quarter").alias("FY_Start_of_Quarter"),
                pl.col("End_of_Quarter").alias("FY_End_of_Quarter"),
            ]
        )
        # Block 4: Ordinal Suffix Helper & Labels
        .with_columns(
            [
                pl.when(pl.col("Day_Ordinal").is_in([11, 12, 13]))
                .then(pl.lit("th"))
                .when((pl.col("Day_Ordinal") % 10) == 1)
                .then(pl.lit("st"))
                .when((pl.col("Day_Ordinal") % 10) == 2)
                .then(pl.lit("nd"))
                .when((pl.col("Day_Ordinal") % 10) == 3)
                .then(pl.lit("rd"))
                .otherwise(pl.lit("th"))
                .alias("_day_suffix"),
                pl.when(pl.col("Week_Ordinal").is_in([11, 12, 13]))
                .then(pl.lit("th"))
                .when((pl.col("Week_Ordinal") % 10) == 1)
                .then(pl.lit("st"))
                .when((pl.col("Week_Ordinal") % 10) == 2)
                .then(pl.lit("nd"))
                .when((pl.col("Week_Ordinal") % 10) == 3)
                .then(pl.lit("rd"))
                .otherwise(pl.lit("th"))
                .alias("_week_suffix"),
            ]
        )
        .with_columns(
            [
                (pl.col("Day_Ordinal").cast(pl.String) + pl.col("_day_suffix")).alias(
                    "Day_Ordinal_Name"
                ),
                (pl.col("Week_Ordinal").cast(pl.String) + pl.col("_week_suffix")).alias(
                    "Week_Ordinal_Name"
                ),
                (pl.lit("Q") + pl.col("Quarter").cast(pl.String)).alias("Quarter_Name"),
                (pl.lit("Q") + pl.col("FY_Quarter").cast(pl.String)).alias("FY_Quarter_Name"),
                (
                    pl.col("FY_Year").cast(pl.String)
                    + "-"
                    + (pl.col("FY_Year") + 1).cast(pl.String).str.slice(2, 2)
                ).alias("Financial_Year"),
                pl.col("Date").dt.strftime("%B %Y").alias("Month_Year"),
                pl.col("Date").dt.strftime("%b-%y").alias("Short_Month_Year"),
                pl.col("Date").dt.strftime("%b '%y").alias("V_Short_Month_Year"),
                (pl.lit("Week ") + pl.col("Week").cast(pl.String)).alias("Week_Name"),
                pl.when(pl.col("Weekday").is_in([6, 7])).then(1).otherwise(0).alias("IS_WEEKEND"),
            ]
        )
        # Block 5: Final Cross-Concatenations
        .with_columns(
            [
                (pl.col("Quarter_Name") + "-" + pl.col("Year").cast(pl.String)).alias(
                    "Quarter_Year"
                ),
                (pl.col("FY_Quarter_Name") + "-" + pl.col("Financial_Year")).alias(
                    "FY_Quarter_Year"
                ),
                (
                    pl.lit("W")
                    + pl.col("Week").cast(pl.String)
                    + "-"
                    + pl.col("Year").cast(pl.String)
                ).alias("Week_Year"),
                (pl.col("Week_Name") + " - " + pl.col("Year").cast(pl.String)).alias(
                    "Week_Name_Year"
                ),
            ]
        )
        # Block 6: Advanced BI Dimensions (Ordinals and Relative Time)
        .with_columns(
            [
                (pl.col("Year") * 100 + pl.col("Month")).alias("Month_Ordinal"),
                (pl.col("Year") * 10 + pl.col("Quarter")).alias("Quarter_Ordinal"),
                (pl.col("FY_Year") * 100 + pl.col("FY_Month")).alias("FY_Month_Ordinal"),
                (pl.col("FY_Year") * 10 + pl.col("FY_Quarter")).alias("FY_Quarter_Ordinal"),
                pl.col("Date").dt.month_end().dt.day().alias("Days_in_Month"),
            ]
        )
        .with_columns(
            [
                (pl.col("Date") == pl.col("End_of_Month")).alias("Is_Last_Day_Of_Month"),
                (pl.col("Date") == pl.col("End_of_Quarter")).alias("Is_Last_Day_Of_Quarter"),
                ((pl.col("Month") == 12) & (pl.col("Day") == 31)).alias("Is_Last_Day_Of_Year"),
                ((pl.col("Month") == 3) & (pl.col("Day") == 31)).alias("Is_Last_Day_Of_FY"),
                pl.col("Month").is_in([3, 6, 9, 12]).alias("Is_Quarter_End_Month"),
                pl.col("Month").is_in([2, 3]).alias("Is_Tax_Harvesting_Season"),
                (pl.col("Day").cast(pl.Float64) / pl.col("Days_in_Month").cast(pl.Float64)).alias(
                    "Month_Progress_Pct"
                ),
                pl.when(
                    (pl.col("Year") % 4 == 0)
                    & ((pl.col("Year") % 100 != 0) | (pl.col("Year") % 400 == 0))
                )
                .then(366)
                .otherwise(365)
                .alias("Days_in_Year"),
                (
                    pl.col("Date").dt.ordinal_day().cast(pl.Float64)
                    / pl.when(
                        (pl.col("Year") % 4 == 0)
                        & ((pl.col("Year") % 100 != 0) | (pl.col("Year") % 400 == 0))
                    )
                    .then(366.0)
                    .otherwise(365.0)
                ).alias("Year_Progress_Pct"),
                (
                    pl.col("Start_of_Month") == pl.lit(datetime.date.today()).dt.truncate("1mo")
                ).alias("Is_Current_Month"),
                (pl.col("Year") == datetime.date.today().year).alias("Is_Current_Year"),
                (pl.col("Date") > datetime.date.today()).alias("Is_Future_Date"),
                # YTD Logic
                (
                    (pl.col("Year") == datetime.date.today().year)
                    & (pl.col("Date") <= datetime.date.today())
                ).alias("Is_YTD"),
            ]
        )
        .with_columns(
            [
                (
                    pl.col("Start_of_Month")
                    == pl.lit(datetime.date.today()).dt.truncate("1mo").dt.offset_by("-1mo")
                ).alias("Is_Previous_Month"),
                (pl.col("Year") == (datetime.date.today().year - 1)).alias("Is_Previous_Year"),
            ]
        )
        # We need to calculate Current FY dynamically to set Is_Current_FY
        .with_columns(
            pl.lit(datetime.date.today()).dt.offset_by("-3mo").dt.year().alias("_current_fy")
        )
        .with_columns(
            [
                (pl.col("FY_Year") == pl.col("_current_fy")).alias("Is_Current_FY"),
                (
                    (pl.col("FY_Year") == pl.col("_current_fy"))
                    & (pl.col("Date") <= datetime.date.today())
                ).alias("Is_FY_YTD"),
            ]
        )
        .with_columns(
            # Quarter Logic
            (
                (pl.col("Year") == datetime.date.today().year)
                & (pl.col("Quarter") == pl.lit(datetime.date.today()).dt.quarter())
            ).alias("Is_Current_Quarter"),
            (
                (
                    pl.col("Start_of_Quarter")
                    == pl.lit(datetime.date.today()).dt.offset_by("-3mo").dt.truncate("1mo")
                )
                & pl.when(pl.lit(datetime.date.today()).dt.month().is_in([1, 4, 7, 10]))
                .then(True)
                .otherwise(False)
            ).alias("Is_Previous_Quarter"),  # Simplified previous quarter proxy
        )
        # Clean up
        .drop(["FY_Shift", "_day_suffix", "_week_suffix", "_current_fy"])
        .select(
            [
                # Base Date
                "Date",
                
                # Day Properties
                "Day",
                "Day_Name",
                "Day_Name_Short",
                "Day_Ordinal",
                "Day_Ordinal_Name",
                "Weekday",
                "IS_WEEKEND",
                
                # Week Properties
                "Week",
                "Week_Ordinal",
                "Week_Ordinal_Name",
                "Week_Name",
                "Week_Year",
                "Week_Name_Year",
                "Start_of_Week",
                "End_of_Week",
                
                # Month Properties
                "Month",
                "Month_Name",
                "Month_Name_Short",
                "Month_Year",
                "Short_Month_Year",
                "V_Short_Month_Year",
                "Month_Ordinal",
                "Start_of_Month",
                "End_of_Month",
                "Days_in_Month",
                "Month_Progress_Pct",
                
                # Quarter Properties
                "Quarter",
                "Quarter_Name",
                "Quarter_Year",
                "Quarter_Ordinal",
                "Start_of_Quarter",
                "End_of_Quarter",
                
                # Year Properties
                "Year",
                "Days_in_Year",
                "Year_Progress_Pct",
                
                # Financial Year Properties
                "Financial_Year",
                "FY_Year",
                "FY_Month",
                "FY_Month_Ordinal",
                "FY_Quarter",
                "FY_Quarter_Name",
                "FY_Quarter_Year",
                "FY_Quarter_Ordinal",
                "FY_Start_of_Month",
                "FY_End_of_Month",
                "FY_Start_of_Quarter",
                "FY_End_of_Quarter",
                
                # Boolean / Snapshot Flags
                "Is_Last_Day_Of_Month",
                "Is_Last_Day_Of_Quarter",
                "Is_Last_Day_Of_Year",
                "Is_Last_Day_Of_FY",
                "Is_Quarter_End_Month",
                "Is_Tax_Harvesting_Season",
                "Is_Current_Month",
                "Is_Previous_Month",
                "Is_Current_Quarter",
                "Is_Previous_Quarter",
                "Is_Current_Year",
                "Is_Previous_Year",
                "Is_Current_FY",
                "Is_YTD",
                "Is_FY_YTD",
                "Is_Future_Date",
            ]
        )
    )

    return df_transformed
