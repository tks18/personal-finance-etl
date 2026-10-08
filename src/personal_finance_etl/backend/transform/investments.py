from datetime import datetime, timezone
from typing import Any

import polars as pl


def get_purchase_reference(
    df_lazy: pl.LazyFrame,
    instrument_col: str,
    date_col: str,
    price_col: str,
    qty_col: str,
    extra_group_cols: list[str] | None = None,
) -> pl.LazyFrame:
    """
    Translates DAX SUMMARIZE + CALCULATE(SUM) for Purchases.
    Groups by Instrument, ISIN, Date, and Price, then sums the Quantity.
    Returns: ISIN, Date, Price, Quantity, Value
    """
    group_cols = [
        "__file_name__",
        "__folder_path__",
        "__file_category__",
        "ISIN",
        pl.col(instrument_col).alias("Instrument name"),
        pl.col(date_col).alias("Date"),
        pl.col(price_col).alias("Price"),
    ]
    if extra_group_cols:
        group_cols.extend(extra_group_cols)

    df_grouped = (
        df_lazy
        # SUMMARIZE equivalent
        .group_by(group_cols)
        # CALCULATE(SUM(Quantity)) equivalent
        .agg(pl.col(qty_col).sum().alias("Quantity"))
        # DAX: Value = Quantity * Price
        .with_columns((pl.col("Quantity") * pl.col("Price")).alias("Value"))
    )
    return df_grouped


def get_sale_reference(
    df_sale_lazy: pl.LazyFrame,
    df_purchase_ref_lazy: pl.LazyFrame,
    instrument_col: str,
    date_col: str,
    price_col: str,
    qty_col: str,
    extra_group_cols: list[str] | None = None,
) -> pl.LazyFrame:
    """
    Translates DAX SUMMARIZE + CALCULATE(SUM) for Sales.
    Also calculates the Rolling Average Buy Price based on historical purchases.
    """

    group_cols = [
        "__file_name__",
        "__folder_path__",
        "__file_category__",
        "ISIN",
        pl.col(instrument_col).alias("Instrument name"),
        pl.col(date_col).alias("Date"),
        pl.col(price_col).alias("Sell_Price"),
    ]
    if extra_group_cols:
        group_cols.extend(extra_group_cols)

    # Step 1: Base Sale Aggregation (SUMMARIZE + SUM(Quantity))
    df_sale_grouped = (
        df_sale_lazy.group_by(group_cols)
        .agg(pl.col(qty_col).sum().alias("Quantity"))
        .with_columns((pl.col("Quantity") * pl.col("Sell_Price")).alias("Sell_Value"))
    )

    # Step 2: Cumulative Sum of Purchases (Rolling calculation for DAX VAR Qty & VAR Val)
    # We sort by ISIN and Date, then calculate rolling sums to get total historical buys up to each date
    rolling_cols = [
        pl.col("Quantity").cum_sum().over("ISIN").alias("Cum_Buy_Qty"),
        pl.col("Value").cum_sum().over("ISIN").alias("Cum_Buy_Val"),
    ]
    if "Value_Local" in df_purchase_ref_lazy.collect_schema().names():
        rolling_cols.append(pl.col("Value_Local").cum_sum().over("ISIN").alias("Cum_Buy_Val_Local"))

    df_purchase_rolling = df_purchase_ref_lazy.sort(["ISIN", "Date"]).with_columns(rolling_cols)

    # Step 3: ASOF Join (Replicating FILTER(Date <= Sale Date))
    # join_asof perfectly matches each sale to the most recent historical purchase state
    df_final = (
        df_sale_grouped.sort(["ISIN", "Date"])  # Both frames must be sorted by the join keys
        .with_columns(pl.col("Date"))
        .join_asof(
            df_purchase_rolling.sort(["ISIN", "Date"]),
            on="Date",
            by="ISIN",
            strategy="backward",  # Matches the closest date <= Sale Date
            suffix="_purchase",
        )
        # Calculate final DAX columns
        .with_columns(
            # Buy Price = DIVIDE(Cum_Buy_Val, Cum_Buy_Qty, 0)
            pl.when(pl.col("Cum_Buy_Qty").is_null() | (pl.col("Cum_Buy_Qty") == 0))
            .then(0.0)
            .otherwise(pl.col("Cum_Buy_Val") / pl.col("Cum_Buy_Qty"))
            .alias("Buy_Price")
        )
    )
    if "Cum_Buy_Val_Local" in df_final.collect_schema().names():
        df_final = df_final.with_columns(
            pl.when(pl.col("Cum_Buy_Qty").is_null() | (pl.col("Cum_Buy_Qty") == 0))
            .then(0.0)
            .otherwise(pl.col("Cum_Buy_Val_Local") / pl.col("Cum_Buy_Qty"))
            .alias("Buy_Price_Local")
        ).with_columns((pl.col("Quantity") * pl.col("Buy_Price_Local")).alias("Buy_Value_Local"))

    df_final = df_final.with_columns(
        [
            (pl.col("Quantity") * pl.col("Buy_Price")).alias("Buy_Value"),
            (pl.col("Sell_Price") - pl.col("Buy_Price")).alias("Unit_PnL"),
        ]
    ).with_columns((pl.col("Unit_PnL") * pl.col("Quantity")).alias("Total_PnL"))

    return df_final


def transform_stg_investment_market_data(
    refs: list[pl.LazyFrame], default_currency_id: str
) -> pl.LazyFrame:
    """
    Translates DAX UNION + SUMMARIZE.
    Concatenates the aggregated tables and selects the final columns.
    """
    df_union = pl.concat(refs, how="diagonal_relaxed")

    cols = df_union.collect_schema().names()
    if "__file_category__" not in cols:
        df_union = df_union.with_columns(pl.lit("Indian").alias("__file_category__"))
    else:
        df_union = df_union.with_columns(pl.col("__file_category__").fill_null("Indian"))
    if "Closing_Price_Local" not in cols:
        df_union = df_union.with_columns(pl.col("Closing_Price").alias("Closing_Price_Local"))
    else:
        df_union = df_union.with_columns(
            pl.col("Closing_Price_Local").fill_null(pl.col("Closing_Price"))
        )
    if "Buy_Price_Local" not in cols:
        df_union = df_union.with_columns(pl.col("Buy_Price").alias("Buy_Price_Local"))
    else:
        df_union = df_union.with_columns(pl.col("Buy_Price_Local").fill_null(pl.col("Buy_Price")))
    if "Closing_Value_Local" not in cols:
        df_union = df_union.with_columns(pl.col("Closing_Value").alias("Closing_Value_Local"))
    else:
        df_union = df_union.with_columns(
            pl.col("Closing_Value_Local").fill_null(pl.col("Closing_Value"))
        )
    if "Buy_Value_Local" not in cols:
        df_union = df_union.with_columns(pl.col("Buy_Value").alias("Buy_Value_Local"))
    else:
        df_union = df_union.with_columns(pl.col("Buy_Value_Local").fill_null(pl.col("Buy_Value")))
    if "FX_Rate" not in cols:
        df_union = df_union.with_columns(pl.lit(1.0).alias("FX_Rate"))
    else:
        df_union = df_union.with_columns(pl.col("FX_Rate").fill_null(1.0))

    if "CURRENCY_ID" not in cols:
        df_union = df_union.with_columns(pl.lit(default_currency_id).alias("CURRENCY_ID"))
    else:
        df_union = df_union.with_columns(pl.col("CURRENCY_ID").fill_null(default_currency_id))

    if "Data_Provider" not in cols:
        df_union = df_union.with_columns(pl.lit("Broker Statement").alias("Data_Provider"))
    else:
        df_union = df_union.with_columns(pl.col("Data_Provider").fill_null("Broker Statement"))

    if "Extraction_Time" not in cols:
        # Use a placeholder timestamp for local files/broker statements
        default_time = datetime(2000, 1, 1, tzinfo=timezone.utc)  # noqa: UP017
        df_union = df_union.with_columns(pl.lit(default_time).alias("Extraction_Time"))
    else:
        default_time = datetime(2000, 1, 1, tzinfo=timezone.utc)  # noqa: UP017
        df_union = df_union.with_columns(pl.col("Extraction_Time").fill_null(default_time))

    if "Is_Imputed" not in cols:
        df_union = df_union.with_columns(pl.lit(False).alias("Is_Imputed"))
    else:
        df_union = df_union.with_columns(pl.col("Is_Imputed").fill_null(False))

    select_cols = [
        "__file_name__",
        "__folder_path__",
        "Date",
        "ISIN",
        "__file_category__",
        "Quantity",
        "Closing_Price_Local",
        "Buy_Price_Local",
        "Closing_Value_Local",
        "Buy_Value_Local",
        "FX_Rate",
        "Closing_Price",
        "Buy_Price",
        "Closing_Value",
        "Buy_Value",
        "Unit_PnL",
        "Total_PnL",
        "CURRENCY_ID",
    ]
    df_final = (
        df_union.select(select_cols)
        .unique()
        .sort(["ISIN", "Date", "Quantity", "Buy_Price", "Closing_Price"])
    )
    return df_final


def get_f_tf_investment_purchase_data(
    refs: list[pl.LazyFrame], default_currency_id: str
) -> pl.LazyFrame:
    """Translates DAX UNION + SUMMARIZE for Purchases."""
    df_union = pl.concat(refs, how="diagonal_relaxed")

    cols = df_union.collect_schema().names()
    if "__file_category__" not in cols:
        df_union = df_union.with_columns(pl.lit("Indian").alias("__file_category__"))
    else:
        df_union = df_union.with_columns(pl.col("__file_category__").fill_null("Indian"))
    if "Price_Local" not in cols:
        df_union = df_union.with_columns(pl.col("Price").alias("Price_Local"))
    else:
        df_union = df_union.with_columns(pl.col("Price_Local").fill_null(pl.col("Price")))
    if "Value_Local" not in cols:
        df_union = df_union.with_columns(pl.col("Value").alias("Value_Local"))
    else:
        df_union = df_union.with_columns(pl.col("Value_Local").fill_null(pl.col("Value")))
    if "FX_Rate" not in cols:
        df_union = df_union.with_columns(pl.lit(1.0).alias("FX_Rate"))
    else:
        df_union = df_union.with_columns(pl.col("FX_Rate").fill_null(1.0))
    if "CURRENCY_ID" not in cols:
        df_union = df_union.with_columns(pl.lit(default_currency_id).alias("CURRENCY_ID"))
    else:
        df_union = df_union.with_columns(pl.col("CURRENCY_ID").fill_null(default_currency_id))

    select_cols = [
        "__file_name__",
        "__folder_path__",
        "ISIN",
        "Date",
        "__file_category__",
        "Price_Local",
        "Value_Local",
        "FX_Rate",
        "Price",
        "Quantity",
        "Value",
        "CURRENCY_ID",
    ]
    df_final = df_union.select(select_cols).unique().sort(["ISIN", "Date", "Quantity", "Price"])
    return df_final


def get_f_tf_investment_sale_data(
    refs: list[pl.LazyFrame], default_currency_id: str
) -> pl.LazyFrame:
    """Translates DAX UNION + SUMMARIZE for Sales."""
    df_union = pl.concat(refs, how="diagonal_relaxed")

    cols = df_union.collect_schema().names()
    if "__file_category__" not in cols:
        df_union = df_union.with_columns(pl.lit("Indian").alias("__file_category__"))
    else:
        df_union = df_union.with_columns(pl.col("__file_category__").fill_null("Indian"))
    if "Sell_Price_Local" not in cols:
        df_union = df_union.with_columns(pl.col("Sell_Price").alias("Sell_Price_Local"))
    else:
        df_union = df_union.with_columns(pl.col("Sell_Price_Local").fill_null(pl.col("Sell_Price")))
    if "Sell_Value_Local" not in cols:
        df_union = df_union.with_columns(pl.col("Sell_Value").alias("Sell_Value_Local"))
    else:
        df_union = df_union.with_columns(pl.col("Sell_Value_Local").fill_null(pl.col("Sell_Value")))
    if "Buy_Price_Local" not in cols:
        df_union = df_union.with_columns(pl.col("Buy_Price").alias("Buy_Price_Local"))
    else:
        df_union = df_union.with_columns(pl.col("Buy_Price_Local").fill_null(pl.col("Buy_Price")))
    if "Buy_Value_Local" not in cols:
        df_union = df_union.with_columns(pl.col("Buy_Value").alias("Buy_Value_Local"))
    else:
        df_union = df_union.with_columns(pl.col("Buy_Value_Local").fill_null(pl.col("Buy_Value")))
    if "FX_Rate" not in cols:
        df_union = df_union.with_columns(pl.lit(1.0).alias("FX_Rate"))
    else:
        df_union = df_union.with_columns(pl.col("FX_Rate").fill_null(1.0))
    if "CURRENCY_ID" not in cols:
        df_union = df_union.with_columns(pl.lit(default_currency_id).alias("CURRENCY_ID"))
    else:
        df_union = df_union.with_columns(pl.col("CURRENCY_ID").fill_null(default_currency_id))

    select_cols = [
        "__file_name__",
        "__folder_path__",
        "ISIN",
        "Date",
        "__file_category__",
        "Quantity",
        "Sell_Price_Local",
        "Sell_Value_Local",
        "FX_Rate",
        "Sell_Price",
        "Sell_Value",
        "Buy_Price",
        "Buy_Value",
        "Unit_PnL",
        "Total_PnL",
        "CURRENCY_ID",
    ]
    df_final = (
        df_union.select(select_cols).unique().sort(["ISIN", "Date", "Quantity", "Sell_Price"])
    )
    return df_final


def get_d_investment_master(
    master_refs: list[pl.LazyFrame], stg_benchmark_mapping_lazy: pl.LazyFrame, default_currency_id: str
) -> pl.LazyFrame:
    """
    Translates d_InvestmentMaster.
    Unions the References into a single distinct dimension table,
    then joins the Benchmark Mapping to pull in Sector, Industry, Tax flags, etc.
    """
    df_master_union = pl.concat(master_refs, how="diagonal_relaxed").unique(subset=["ISIN"])

    cols = df_master_union.collect_schema().names()
    if "CURRENCY_ID" not in cols:
        df_master_union = df_master_union.with_columns(pl.lit(default_currency_id).alias("CURRENCY_ID"))
    else:
        df_master_union = df_master_union.with_columns(pl.col("CURRENCY_ID").fill_null(default_currency_id))

    df_final = df_master_union.join(stg_benchmark_mapping_lazy, on="ISIN", how="left").select(
        [
            "ISIN",
            "INSTRUMENT_NAME",
            "INSTRUMENT_HOUSE",
            "INSTRUMENT_CLASS",
            "INSTRUMENT_TYPE",
            "INSTRUMENT_SUBTYPE",
            "CATEGORY_ID",
            pl.col("Sector").alias("SECTOR"),
            pl.col("Industry").alias("INDUSTRY"),
            pl.col("Benchmark_ID").alias("BENCHMARK_ID"),
            pl.col("Tax_Instrument_Type").alias("TAX_TYPE"),
            pl.col("Tax_Instrument_Subtype").alias("TAX_SUBTYPE"),
            pl.col("Country").alias("COUNTRY"),
            pl.col("Geo").alias("GEO"),
            pl.col("Geo_Subtype").alias("GEO_SUBTYPE"),
            pl.col("Yahoo_Ticker").alias("YAHOO_TICKER"),
            "CURRENCY_ID",
        ]
    )
    return df_final
