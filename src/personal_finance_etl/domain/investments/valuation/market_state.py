"""US stock market state, continuous valuation spine, and FIFO lot tracking.

Owns
----
- EMPTY_US_MARKET_SCHEMA declarative schema definition.
- Reconstruction of the continuous daily US stock FIFO spine.
- Backward as-of join with Bronze prices and staleness enforcement (maximum 7 days).
- FX translation and local/INR PnL calculations.

Does not own
-------------
- Yahoo Finance price acquisition (owned by infrastructure.providers.market.us_market).
- Database table insertion (owned by infrastructure.warehouse).
"""

import dataclasses
from collections import defaultdict, deque
from datetime import date, timedelta
from typing import cast

import polars as pl

from personal_finance_etl.domain.investments.contracts import MarketSpineRecord, TradeRecord
from personal_finance_etl.domain.investments.lots.ordering import sort_purchases, sort_sales

EMPTY_US_MARKET_SCHEMA: dict[str, type[pl.DataType] | pl.DataType] = {
    "Date": pl.Date,
    "ISIN": pl.String,
    "__file_category__": pl.String,
    "Quantity": pl.Float64,
    "Closing_Price_Local": pl.Float64,
    "Buy_Price_Local": pl.Float64,
    "Closing_Value_Local": pl.Float64,
    "Buy_Value_Local": pl.Float64,
    "FX_Rate": pl.Float64,
    "Closing_Price": pl.Float64,
    "Buy_Price": pl.Float64,
    "Closing_Value": pl.Float64,
    "Buy_Value": pl.Float64,
    "Unit_PnL": pl.Float64,
    "Total_PnL": pl.Float64,
    "CURRENCY_ID": pl.String,
    "Data_Provider": pl.String,
    "Extraction_Time": pl.String,
    "Requested_Start": pl.Date,
    "Requested_End": pl.Date,
    "Is_Closure_Gap": pl.Boolean,
    "Is_Imputed": pl.Boolean,
}


@dataclasses.dataclass
class _UsLot:
    """Internal lot state tracking quantity and unit costs in local and base currency."""

    qty: float
    price_local: float
    price_inr: float


def _simulate_isin_lots(
    isin: str,
    curr_id: str,
    buys: dict[date, list[TradeRecord]],
    sells: dict[date, list[TradeRecord]],
    start_date: date,
    end_date: date,
) -> list[MarketSpineRecord]:
    """Reconstruct daily FIFO lot balances for a single US equity instrument.

    Parameters
    ----------
    isin : str
        Instrument identifier.
    curr_id : str
        Currency code of the asset.
    buys : dict[date, list[TradeRecord]]
        Date-indexed purchase transactions.
    sells : dict[date, list[TradeRecord]]
        Date-indexed sale transactions.
    start_date : date
        Simulation window starting boundary.
    end_date : date
        Simulation window ending boundary.

    Returns
    -------
    list[MarketSpineRecord]
        List of daily expanded lot records.
    """
    records: list[MarketSpineRecord] = []
    current_date = start_date
    lots: deque[_UsLot] = deque()

    while current_date <= end_date:
        day_buys = buys.get(current_date, [])
        for b in sort_purchases(day_buys):
            qty = float(b["Quantity"])
            if qty > 0:
                b_val_local = float(b.get("Value_Local") or 0.0)
                b_val_inr = float(b.get("Value") or 0.0)
                lots.append(
                    _UsLot(
                        qty=qty,
                        price_local=b_val_local / qty,
                        price_inr=b_val_inr / qty,
                    )
                )

        day_sells = sells.get(current_date, [])
        for s in sort_sales(day_sells):
            sqty = float(s["Quantity"])
            while sqty > 0 and lots:
                if lots[0].qty > sqty:
                    lots[0].qty -= sqty
                    sqty = 0
                else:
                    sqty -= lots[0].qty
                    lots.popleft()

        lots_by_price: dict[tuple[float, float], float] = defaultdict(float)
        for lot in lots:
            lots_by_price[(lot.price_local, lot.price_inr)] += lot.qty

        for (price_local, price_inr), qty in lots_by_price.items():
            if qty > 0:
                records.append(
                    {
                        "Date": current_date,
                        "ISIN": isin,
                        "CURRENCY_ID": curr_id,
                        "Quantity": qty,
                        "Buy_Value_Local": qty * price_local,
                        "Buy_Value_INR": qty * price_inr,
                        "Buy_Price_Local": price_local,
                        "Buy_Price_INR": price_inr,
                    }
                )

        current_date += timedelta(days=1)

    return records


def _build_us_fifo_spine(
    us_purchases: pl.DataFrame,
    df_sale: pl.DataFrame,
    global_start_date: date,
    global_end_date: date,
) -> pl.DataFrame:
    """Reconstruct daily continuous FIFO spine across all active US stocks.

    Parameters
    ----------
    us_purchases : pl.DataFrame
        Filtered US purchases dataframe.
    df_sale : pl.DataFrame
        Collected sales dataframe.
    global_start_date : date
        Start date boundary.
    global_end_date : date
        End date boundary.

    Returns
    -------
    pl.DataFrame
        Eager spine dataframe.
    """
    active_isins = us_purchases["ISIN"].unique().to_list()
    df_p_us = us_purchases.select(
        ["ISIN", "Date", "Quantity", "Value_Local", "Value", "CURRENCY_ID"]
    ).sort(["ISIN", "Date"])
    df_s_us = (
        df_sale.filter(pl.col("__file_category__") == "US Stocks")
        .select(["ISIN", "Date", "Quantity"])
        .sort(["ISIN", "Date"])
    )

    buys: defaultdict[str, defaultdict[date, list[TradeRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    currency_map: dict[str, str] = {}
    for raw_p in df_p_us.to_dicts():
        dt = raw_p.get("Date")
        if isinstance(dt, date):
            buys[str(raw_p["ISIN"])][dt].append(cast(TradeRecord, raw_p))
            currency_map[str(raw_p["ISIN"])] = str(raw_p["CURRENCY_ID"])

    sells: defaultdict[str, defaultdict[date, list[TradeRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for raw_s in df_s_us.to_dicts():
        dt = raw_s.get("Date")
        if isinstance(dt, date):
            sells[str(raw_s["ISIN"])][dt].append(cast(TradeRecord, raw_s))

    spine_records: list[MarketSpineRecord] = []
    for isin in active_isins:
        curr_id = currency_map.get(isin)
        if not curr_id:
            raise ValueError(f"Missing CURRENCY_ID for US Stock ISIN: {isin}")
        isin_records = _simulate_isin_lots(
            isin=isin,
            curr_id=curr_id,
            buys=buys[isin],
            sells=sells[isin],
            start_date=global_start_date,
            end_date=global_end_date,
        )
        spine_records.extend(isin_records)

    return pl.DataFrame(
        spine_records,
        schema={
            "Date": pl.Date,
            "ISIN": pl.String,
            "CURRENCY_ID": pl.String,
            "Quantity": pl.Float64,
            "Buy_Value_Local": pl.Float64,
            "Buy_Value_INR": pl.Float64,
            "Buy_Price_Local": pl.Float64,
            "Buy_Price_INR": pl.Float64,
        },
    )


def _join_and_validate_prices(
    df_spine: pl.LazyFrame,
    df_bronze_prices_lazy: pl.LazyFrame,
    max_price_staleness_days: int = 7,
) -> pl.LazyFrame:
    """Join bronze prices via backward as-of merge and enforce staleness boundaries.

    Parameters
    ----------
    df_spine : pl.LazyFrame
        Lazy spine dataframe.
    df_bronze_prices_lazy : pl.LazyFrame
        Lazy bronze price quotes.
    max_price_staleness_days : int, default 7
        Maximum allowed days without fresh price quote.

    Returns
    -------
    pl.LazyFrame
        Spine lazyframe enriched with prices and staleness indicators.
    """
    invalid_source_prices = (
        df_bronze_prices_lazy.filter(
            pl.col("Closing_Price_Local").is_not_null()
            & (~pl.col("Closing_Price_Local").is_finite() | (pl.col("Closing_Price_Local") <= 0))
            & ~pl.col("Is_Closure_Gap").fill_null(False)
        )
        .select(["ISIN", "Date", "Closing_Price_Local"])
        # Materialization Boundary: VALIDATION_DIAGNOSTIC
        # Materialize bounded sample (max 10) of invalid source prices for structured error diagnostics
        .limit(10)
        .collect()
    )
    if not invalid_source_prices.is_empty():
        raise ValueError(
            "Bronze contains non-positive or non-finite US stock prices not marked as "
            f"closure gaps: {invalid_source_prices.to_dicts()}"
        )

    df_prices = (
        df_bronze_prices_lazy.filter(
            pl.col("Closing_Price_Local").is_not_null()
            & pl.col("Closing_Price_Local").is_finite()
            & (pl.col("Closing_Price_Local") > 0)
            & ~pl.col("Is_Closure_Gap").fill_null(False)
        )
        .select(
            [
                "Date",
                "ISIN",
                "Closing_Price_Local",
                "Data_Provider",
                "Extraction_Time",
                "Requested_Start",
                "Requested_End",
                "Is_Closure_Gap",
            ]
        )
        .with_columns(pl.col("Date").alias("Price_Observation_Date"))
        .sort("Date")
    )

    enriched_spine = (
        df_spine.sort("Date")
        .join_asof(
            df_prices,
            on="Date",
            by="ISIN",
            strategy="backward",
        )
        .sort(["ISIN", "Date"])
        .with_columns(
            (pl.col("Date") - pl.col("Price_Observation_Date"))
            .dt.total_days()
            .alias("Price_Age_Days"),
            pl.col("Is_Closure_Gap").fill_null(False).alias("Is_Closure_Gap"),
        )
        .with_columns(
            (
                pl.col("Price_Observation_Date").is_null()
                | (pl.col("Price_Observation_Date") != pl.col("Date"))
                | pl.col("Is_Closure_Gap")
            ).alias("Is_Imputed")
        )
    )

    invalid_prices = (
        enriched_spine.filter(
            pl.col("Closing_Price_Local").is_null()
            | ~pl.col("Closing_Price_Local").is_finite()
            | (pl.col("Closing_Price_Local") <= 0)
            | pl.col("Price_Age_Days").is_null()
            | (pl.col("Price_Age_Days") > max_price_staleness_days)
        )
        .select(["ISIN", "Date", "Price_Observation_Date", "Price_Age_Days", "Closing_Price_Local"])
        # Materialization Boundary: VALIDATION_DIAGNOSTIC
        # Materialize bounded sample (max 10) of missing or stale US stock prices for error diagnostics
        .limit(10)
        .collect()
    )
    if not invalid_prices.is_empty():
        raise ValueError(
            "Missing, non-positive, non-finite, or stale US stock prices. "
            f"Maximum permitted observation age is {max_price_staleness_days} calendar days. "
            f"Examples: {invalid_prices.to_dicts()}"
        )

    return enriched_spine


def _join_fx_and_calculate_pnl(
    df_spine: pl.LazyFrame,
    df_fx_lazy: pl.LazyFrame,
) -> pl.LazyFrame:
    """Join currency FX rates and derive unit and total PnL metrics.

    Parameters
    ----------
    df_spine : pl.LazyFrame
        Lazy spine dataframe with prices.
    df_fx_lazy : pl.LazyFrame
        Lazy FX rates dataframe.

    Returns
    -------
    pl.LazyFrame
        Final transformed US market dataset.
    """
    df_fx_sorted = (
        df_fx_lazy.select(["Date", "Currency_ID", "FX_Rate"])
        .rename({"Currency_ID": "CURRENCY_ID"})
        .sort("Date")
    )
    joined_spine = (
        df_spine.sort("Date")
        .join_asof(df_fx_sorted, on="Date", by="CURRENCY_ID", strategy="backward")
        .sort(["ISIN", "Date"])
    )

    invalid_fx = (
        joined_spine.filter(
            pl.col("FX_Rate").is_null() | ~pl.col("FX_Rate").is_finite() | (pl.col("FX_Rate") <= 0)
        )
        .select(["ISIN", "Date", "CURRENCY_ID", "FX_Rate"])
        # Materialization Boundary: VALIDATION_DIAGNOSTIC
        # Materialize bounded sample (max 10) of invalid FX rates for error diagnostics
        .limit(10)
        .collect()
    )
    if not invalid_fx.is_empty():
        raise ValueError(
            "Missing, non-positive, or non-finite FX rates for US stock valuation. "
            f"Examples: {invalid_fx.to_dicts()}"
        )

    return (
        joined_spine.with_columns(
            [
                (pl.col("Closing_Price_Local") * pl.col("FX_Rate")).alias("Closing_Price"),
                pl.col("Buy_Price_INR").alias("Buy_Price"),
                pl.col("Buy_Value_INR").alias("Buy_Value"),
            ]
        )
        .with_columns(
            [
                (pl.col("Quantity") * pl.col("Closing_Price")).alias("Closing_Value"),
                (pl.col("Quantity") * pl.col("Closing_Price_Local")).alias("Closing_Value_Local"),
                (pl.col("Closing_Price") - pl.col("Buy_Price")).alias("Unit_PnL"),
            ]
        )
        .with_columns(
            [
                (pl.col("Unit_PnL") * pl.col("Quantity")).alias("Total_PnL"),
                pl.lit("US Stocks").alias("__file_category__"),
            ]
        )
        .filter(pl.col("Quantity") >= 0)
        .select(
            [
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
        )
    )


def transform_us_market_data(
    df_bronze_prices_lazy: pl.LazyFrame,
    df_purchase_lazy: pl.LazyFrame,
    df_sale_lazy: pl.LazyFrame,
    df_fx_lazy: pl.LazyFrame,
    global_start_date: date,
    global_end_date: date,
) -> pl.LazyFrame:
    """Transform bronze raw US stock prices into a continuous silver daily series.

    Build the FIFO spine, join FX rates, and calculate PnL.
    """
    # Materialization Boundary: STATEFUL_ALGORITHM_BOUNDARY
    # Materialize purchase and sale records for sequential FIFO inventory lot matching
    df_purchase = df_purchase_lazy.collect()
    df_sale = df_sale_lazy.collect()

    if df_purchase.is_empty():
        return pl.DataFrame(schema=EMPTY_US_MARKET_SCHEMA).lazy()

    us_purchases = df_purchase.filter(pl.col("__file_category__") == "US Stocks")
    if us_purchases.is_empty():
        return pl.DataFrame(schema=EMPTY_US_MARKET_SCHEMA).lazy()

    df_spine_eager = _build_us_fifo_spine(
        us_purchases=us_purchases,
        df_sale=df_sale,
        global_start_date=global_start_date,
        global_end_date=global_end_date,
    )
    if df_spine_eager.is_empty():
        return pl.DataFrame(schema=EMPTY_US_MARKET_SCHEMA).lazy()

    df_spine_with_prices = _join_and_validate_prices(
        df_spine=df_spine_eager.lazy(),
        df_bronze_prices_lazy=df_bronze_prices_lazy,
    )

    return _join_fx_and_calculate_pnl(
        df_spine=df_spine_with_prices,
        df_fx_lazy=df_fx_lazy,
    ).lazy()
