"""Common investment dimension, reference, and fact transformations.

Owns
----
- Purchase reference aggregation (SUMMARIZE + SUM Quantity and Value).
- Sale reference aggregation with rolling average buy price (ASOF join).
- Staging investment market data consolidation across asset classes.
- Deterministic Purchase_ID and Sale_ID generation via canonical hashing.
- Investment purchase and sale fact table generation.
- Investment master dimension consolidation (d_Investment_Master).

Does not own
-------------
- Stateful lot matching or FIFO portfolio execution (owned by domain.investments.lots).
- Physical table insertion into DuckDB (owned by infrastructure.warehouse).
"""

from collections.abc import Mapping
from datetime import UTC, datetime

import polars as pl

from personal_finance_etl.domain.common.identity import generate_deterministic_id


def get_purchase_reference(
    df_lazy: pl.LazyFrame,
    instrument_col: str,
    date_col: str,
    price_col: str,
    qty_col: str,
    extra_group_cols: list[str] | None = None,
) -> pl.LazyFrame:
    """Translate DAX SUMMARIZE + CALCULATE(SUM) for Purchases.

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


def _compute_purchase_rolling(df_purchase_ref_lazy: pl.LazyFrame) -> pl.LazyFrame:
    """Calculate cumulative purchase quantity and value over ISIN."""
    rolling_cols = [
        pl.col("Quantity").cum_sum().over("ISIN").alias("Cum_Buy_Qty"),
        pl.col("Value").cum_sum().over("ISIN").alias("Cum_Buy_Val"),
    ]
    if "Value_Local" in df_purchase_ref_lazy.collect_schema().names():
        rolling_cols.append(pl.col("Value_Local").cum_sum().over("ISIN").alias("Cum_Buy_Val_Local"))
    return df_purchase_ref_lazy.sort(["ISIN", "Date"]).with_columns(rolling_cols)


def _join_and_calculate_pnl(
    df_sale_grouped: pl.LazyFrame, df_purchase_rolling: pl.LazyFrame
) -> pl.LazyFrame:
    """Join sale lots with purchase rolling averages via backward ASOF join."""
    df_final = (
        df_sale_grouped.sort(["ISIN", "Date"])
        .with_columns(pl.col("Date"))
        .join_asof(
            df_purchase_rolling.sort(["ISIN", "Date"]),
            on="Date",
            by="ISIN",
            strategy="backward",
            suffix="_purchase",
        )
        .with_columns(
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

    return df_final.with_columns(
        (pl.col("Quantity") * pl.col("Buy_Price")).alias("Buy_Value"),
        (pl.col("Sell_Price") - pl.col("Buy_Price")).alias("Unit_PnL"),
    ).with_columns((pl.col("Unit_PnL") * pl.col("Quantity")).alias("Total_PnL"))


def get_sale_reference(
    df_sale_lazy: pl.LazyFrame,
    df_purchase_ref_lazy: pl.LazyFrame,
    instrument_col: str,
    date_col: str,
    price_col: str,
    qty_col: str,
    extra_group_cols: list[str] | None = None,
) -> pl.LazyFrame:
    """Translate DAX SUMMARIZE + CALCULATE(SUM) for Sales.

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

    df_sale_grouped = (
        df_sale_lazy.group_by(group_cols)
        .agg(pl.col(qty_col).sum().alias("Quantity"))
        .with_columns((pl.col("Quantity") * pl.col("Sell_Price")).alias("Sell_Value"))
    )
    df_purchase_rolling = _compute_purchase_rolling(df_purchase_ref_lazy)
    return _join_and_calculate_pnl(df_sale_grouped, df_purchase_rolling)


def _normalize_currency_and_fx(df: pl.LazyFrame, default_currency_id: str) -> pl.LazyFrame:
    """Fill missing CURRENCY_ID and resolve default 1.0 FX_Rate."""
    cols = df.collect_schema().names()
    if "CURRENCY_ID" not in cols:
        df = df.with_columns(pl.lit(default_currency_id).alias("CURRENCY_ID"))
    else:
        df = df.with_columns(pl.col("CURRENCY_ID").fill_null(default_currency_id))

    if "FX_Rate" not in cols:
        df = df.with_columns(
            pl.when(pl.col("CURRENCY_ID") == pl.lit(default_currency_id))
            .then(pl.lit(1.0))
            .otherwise(pl.lit(None).cast(pl.Float64))
            .alias("FX_Rate")
        )
    else:
        df = df.with_columns(
            pl.when(
                pl.col("FX_Rate").is_null() & (pl.col("CURRENCY_ID") == pl.lit(default_currency_id))
            )
            .then(pl.lit(1.0))
            .otherwise(pl.col("FX_Rate"))
            .alias("FX_Rate")
        )
    return df


def _fallback_local_columns(df: pl.LazyFrame, pairs: list[tuple[str, str]]) -> pl.LazyFrame:
    """Ensure Local price/value columns exist, falling back to base columns."""
    cols = df.collect_schema().names()
    exprs: list[pl.Expr] = []
    for local_col, base_col in pairs:
        if local_col not in cols:
            exprs.append(pl.col(base_col).alias(local_col))
        else:
            exprs.append(pl.col(local_col).fill_null(pl.col(base_col)).alias(local_col))
    return df.with_columns(exprs) if exprs else df


def _normalize_market_data_metadata(df_union: pl.LazyFrame) -> pl.LazyFrame:
    """Fill default metadata flags and dates for stage market data."""
    cols = df_union.collect_schema().names()
    default_time = datetime(2000, 1, 1, tzinfo=UTC)
    return df_union.with_columns(
        pl.col("__file_category__").fill_null("Indian")
        if "__file_category__" in cols
        else pl.lit("Indian").alias("__file_category__"),
        pl.col("Data_Provider").fill_null("Broker Statement")
        if "Data_Provider" in cols
        else pl.lit("Broker Statement").alias("Data_Provider"),
        pl.col("Extraction_Time").fill_null(default_time)
        if "Extraction_Time" in cols
        else pl.lit(default_time).alias("Extraction_Time"),
        pl.col("Is_Imputed").fill_null(False)
        if "Is_Imputed" in cols
        else pl.lit(False).alias("Is_Imputed"),
        pl.col("Requested_Start").fill_null(pl.col("Date"))
        if "Requested_Start" in cols
        else pl.col("Date").alias("Requested_Start"),
        pl.col("Requested_End").fill_null(pl.col("Date"))
        if "Requested_End" in cols
        else pl.col("Date").alias("Requested_End"),
        pl.col("Is_Closure_Gap").fill_null(False)
        if "Is_Closure_Gap" in cols
        else pl.lit(False).alias("Is_Closure_Gap"),
    )


def transform_stg_investment_market_data(
    refs: list[pl.LazyFrame], default_currency_id: str
) -> pl.LazyFrame:
    """Translate DAX UNION + SUMMARIZE for stage investment market data.

    Concatenates the aggregated tables and selects the final columns.
    """
    df_union = pl.concat(refs, how="diagonal_relaxed")
    pairs = [
        ("Closing_Price_Local", "Closing_Price"),
        ("Buy_Price_Local", "Buy_Price"),
        ("Closing_Value_Local", "Closing_Value"),
        ("Buy_Value_Local", "Buy_Value"),
    ]
    df_union = _fallback_local_columns(df_union, pairs)
    df_union = _normalize_currency_and_fx(df_union, default_currency_id)
    df_union = _normalize_market_data_metadata(df_union)

    select_cols = [
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
        "Data_Provider",
        "Extraction_Time",
        "Requested_Start",
        "Requested_End",
        "Is_Closure_Gap",
        "Is_Imputed",
    ]
    return (
        df_union.select(select_cols)
        .unique()
        .sort(["ISIN", "Date", "Quantity", "Buy_Price", "Closing_Price"])
    )


def _compute_purchase_id(row: Mapping[str, object]) -> str:
    """Generate a deterministic identifier for an individual purchase record.

    Parameters
    ----------
    row : Mapping[str, object]
        Row attributes containing ISIN, Date, Price, Quantity, and CURRENCY_ID.

    Returns
    -------
    str
        Deterministic purchase UUID string prefixed with 'PURCHASE'.
    """
    fields = {
        "ISIN": row["ISIN"],
        "Date": row["Date"],
        "Price": row["Price"],
        "Quantity": row["Quantity"],
        "CURRENCY_ID": row["CURRENCY_ID"],
    }
    return generate_deterministic_id("PURCHASE", fields)


def _batch_compute_purchase_ids(s: pl.Series) -> pl.Series:
    """Compute deterministic purchase IDs across a Struct Series of purchase fields.

    Parameters
    ----------
    s : pl.Series
        Polars Struct series holding ISIN, Date, Price, Quantity, and CURRENCY_ID fields.

    Returns
    -------
    pl.Series
        String Series of generated purchase IDs.
    """
    isins = s.struct.field("ISIN")
    dates = s.struct.field("Date")
    prices = s.struct.field("Price")
    qtys = s.struct.field("Quantity")
    currencies = s.struct.field("CURRENCY_ID")
    ids = [
        _compute_purchase_id(
            {
                "ISIN": isin,
                "Date": dt,
                "Price": price,
                "Quantity": qty,
                "CURRENCY_ID": curr,
            }
        )
        for isin, dt, price, qty, curr in zip(isins, dates, prices, qtys, currencies, strict=False)
    ]
    return pl.Series(ids, dtype=pl.String)


def _compute_sale_id(row: Mapping[str, object]) -> str:
    """Generate a deterministic identifier for an individual sale record.

    Parameters
    ----------
    row : Mapping[str, object]
        Row attributes containing ISIN, Date, Sell_Price, Quantity, and CURRENCY_ID.

    Returns
    -------
    str
        Deterministic sale UUID string prefixed with 'SALE'.
    """
    fields = {
        "ISIN": row["ISIN"],
        "Date": row["Date"],
        "Sell_Price": row["Sell_Price"],
        "Quantity": row["Quantity"],
        "CURRENCY_ID": row["CURRENCY_ID"],
    }
    return generate_deterministic_id("SALE", fields)


def _batch_compute_sale_ids(s: pl.Series) -> pl.Series:
    """Compute deterministic sale IDs across a Struct Series of sale fields.

    Parameters
    ----------
    s : pl.Series
        Polars Struct series holding ISIN, Date, Sell_Price, Quantity, and CURRENCY_ID fields.

    Returns
    -------
    pl.Series
        String Series of generated sale IDs.
    """
    isins = s.struct.field("ISIN")
    dates = s.struct.field("Date")
    sell_prices = s.struct.field("Sell_Price")
    qtys = s.struct.field("Quantity")
    currencies = s.struct.field("CURRENCY_ID")
    ids = [
        _compute_sale_id(
            {
                "ISIN": isin,
                "Date": dt,
                "Sell_Price": sp,
                "Quantity": qty,
                "CURRENCY_ID": curr,
            }
        )
        for isin, dt, sp, qty, curr in zip(
            isins, dates, sell_prices, qtys, currencies, strict=False
        )
    ]
    return pl.Series(ids, dtype=pl.String)


def get_f_tf_investment_purchase_data(
    refs: list[pl.LazyFrame], default_currency_id: str
) -> pl.LazyFrame:
    """Translate DAX UNION + SUMMARIZE for Purchases."""
    df_union = pl.concat(refs, how="diagonal_relaxed")
    cols = df_union.collect_schema().names()
    if "__file_category__" not in cols:
        df_union = df_union.with_columns(pl.lit("Indian").alias("__file_category__"))
    else:
        df_union = df_union.with_columns(pl.col("__file_category__").fill_null("Indian"))

    pairs = [("Price_Local", "Price"), ("Value_Local", "Value")]
    df_union = _fallback_local_columns(df_union, pairs)
    df_union = _normalize_currency_and_fx(df_union, default_currency_id)

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
    return (
        df_union.select(select_cols)
        .unique()
        .sort(["ISIN", "Date", "Quantity", "Price"])
        .with_columns(
            pl.struct(["ISIN", "Date", "Price", "Quantity", "CURRENCY_ID"])
            .map_batches(_batch_compute_purchase_ids, return_dtype=pl.String)
            .alias("Purchase_ID")
        )
    )


def get_f_tf_investment_sale_data(
    refs: list[pl.LazyFrame], default_currency_id: str
) -> pl.LazyFrame:
    """Translate DAX UNION + SUMMARIZE for Sales."""
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
    if "CURRENCY_ID" not in cols:
        df_union = df_union.with_columns(pl.lit(default_currency_id).alias("CURRENCY_ID"))
    else:
        df_union = df_union.with_columns(pl.col("CURRENCY_ID").fill_null(default_currency_id))

    if "FX_Rate" not in cols:
        df_union = df_union.with_columns(
            pl.when(pl.col("CURRENCY_ID") == pl.lit(default_currency_id))
            .then(pl.lit(1.0))
            .otherwise(pl.lit(None).cast(pl.Float64))
            .alias("FX_Rate")
        )
    else:
        df_union = df_union.with_columns(
            pl.when(
                pl.col("FX_Rate").is_null() & (pl.col("CURRENCY_ID") == pl.lit(default_currency_id))
            )
            .then(pl.lit(1.0))
            .otherwise(pl.col("FX_Rate"))
            .alias("FX_Rate")
        )

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
        df_union.select(select_cols)
        .unique()
        .sort(["ISIN", "Date", "Quantity", "Sell_Price"])
        .with_columns(
            pl.struct(["ISIN", "Date", "Sell_Price", "Quantity", "CURRENCY_ID"])
            .map_batches(_batch_compute_sale_ids, return_dtype=pl.String)
            .alias("Sale_ID")
        )
    )
    return df_final


def get_d_investment_master(
    master_refs: list[pl.LazyFrame],
    stg_benchmark_mapping_lazy: pl.LazyFrame,
    default_currency_id: str,
) -> pl.LazyFrame:
    """Translate d_InvestmentMaster dimensional data.

    Unions the References into a single distinct dimension table,
    then joins the Benchmark Mapping to pull in Sector, Industry, Tax flags, etc.
    """
    df_master_union = pl.concat(master_refs, how="diagonal_relaxed").unique(subset=["ISIN"])

    cols = df_master_union.collect_schema().names()
    if "CURRENCY_ID" not in cols:
        df_master_union = df_master_union.with_columns(
            pl.lit(default_currency_id).alias("CURRENCY_ID")
        )
    else:
        df_master_union = df_master_union.with_columns(
            pl.col("CURRENCY_ID").fill_null(default_currency_id)
        )

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
