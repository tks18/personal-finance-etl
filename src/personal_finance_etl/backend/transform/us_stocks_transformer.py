import dataclasses
from collections import defaultdict, deque
from datetime import date, timedelta
from typing import Any

import polars as pl

from personal_finance_etl.backend.utils.ordering import sort_purchases, sort_sales


def transform_us_market_data(
    df_bronze_prices_lazy: pl.LazyFrame,
    df_purchase_lazy: pl.LazyFrame,
    df_sale_lazy: pl.LazyFrame,
    df_fx_lazy: pl.LazyFrame,
    global_start_date: date,
    global_end_date: date,
) -> pl.LazyFrame:
    """
    Transforms bronze raw US stock prices into a continuous silver daily series,
    builds the FIFO spine, joins FX rates, and calculates PnL.
    """
    df_purchase = df_purchase_lazy.collect()
    df_sale = df_sale_lazy.collect()

    if df_purchase.is_empty():
        return pl.DataFrame().lazy()

    us_purchases = df_purchase.filter(pl.col("__file_category__") == "US Stocks")
    if us_purchases.is_empty():
        return pl.DataFrame().lazy()

    active_isins = us_purchases["ISIN"].unique().to_list()

    # --- Phase 1: Reconstruct FIFO Spine ---
    df_p_us = us_purchases.select(
        ["ISIN", "Date", "Quantity", "Value_Local", "Value", "CURRENCY_ID"]
    ).sort(["ISIN", "Date"])
    df_s_us = (
        df_sale.filter(pl.col("__file_category__") == "US Stocks")
        .select(["ISIN", "Date", "Quantity"])
        .sort(["ISIN", "Date"])
    )

    buys: defaultdict[str, defaultdict[date, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    currency_map: dict[str, str] = {}
    for row in df_p_us.iter_rows(named=True):
        dt = row["Date"]
        if isinstance(dt, date):
            buys[str(row["ISIN"])][dt].append(row)
            currency_map[str(row["ISIN"])] = row["CURRENCY_ID"]

    sells: defaultdict[str, defaultdict[date, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in df_s_us.iter_rows(named=True):
        dt = row["Date"]
        if isinstance(dt, date):
            sells[str(row["ISIN"])][dt].append(row)

    spine_records: list[dict[str, Any]] = []

    @dataclasses.dataclass
    class Lot:
        qty: float
        price_local: float
        price_inr: float

    for isin in active_isins:
        current_date = global_start_date
        lots: deque[Lot] = deque()
        curr_id = currency_map.get(isin)
        if not curr_id:
            raise ValueError(f"Missing CURRENCY_ID for US Stock ISIN: {isin}")

        while current_date <= global_end_date:
            # Apply buys
            day_buys = buys[isin].get(current_date, [])
            for b in sort_purchases(day_buys):
                qty = float(b["Quantity"])
                if qty > 0:
                    lots.append(
                        Lot(
                            qty=qty,
                            price_local=float(b["Value_Local"]) / qty,
                            price_inr=float(b["Value"]) / qty,
                        )
                    )

            # Apply sells
            day_sells = sells[isin].get(current_date, [])
            for s in sort_sales(day_sells):
                sqty = float(s["Quantity"])
                while sqty > 0 and lots:
                    if lots[0].qty > sqty:
                        lots[0].qty -= sqty
                        sqty = 0
                    else:
                        sqty -= lots[0].qty
                        lots.popleft()

            # Group by Buy Price to match the main Indian stock market data lot-level granularity
            lots_by_price: dict[tuple[float, float], float] = defaultdict(float)
            for lot in lots:
                lots_by_price[(lot.price_local, lot.price_inr)] += lot.qty

            for (price_local, price_inr), qty in lots_by_price.items():
                if qty > 0:
                    spine_records.append(
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

    df_spine_eager = pl.DataFrame(
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

    if df_spine_eager.is_empty():
        return pl.DataFrame().lazy()

    df_spine = df_spine_eager.lazy()

    # Historical prices may only flow forward from an observation on or before the
    # valuation date. Keep the source observation date long enough to enforce a
    # bounded staleness policy; never backward-fill a missing historical price.
    max_price_staleness_days = 7
    invalid_source_prices = (
        df_bronze_prices_lazy.filter(
            pl.col("Closing_Price_Local").is_not_null()
            & (~pl.col("Closing_Price_Local").is_finite() | (pl.col("Closing_Price_Local") <= 0))
            & ~pl.col("Is_Closure_Gap").fill_null(False)
        )
        .select(["ISIN", "Date", "Closing_Price_Local"])
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
    df_spine = df_spine.sort("Date")
    df_spine = (
        df_spine.join_asof(
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
        df_spine.filter(
            pl.col("Closing_Price_Local").is_null()
            | ~pl.col("Closing_Price_Local").is_finite()
            | (pl.col("Closing_Price_Local") <= 0)
            | pl.col("Price_Age_Days").is_null()
            | (pl.col("Price_Age_Days") > max_price_staleness_days)
        )
        .select(["ISIN", "Date", "Price_Observation_Date", "Price_Age_Days", "Closing_Price_Local"])
        .limit(10)
        .collect()
    )
    if not invalid_prices.is_empty():
        raise ValueError(
            "Missing, non-positive, non-finite, or stale US stock prices. "
            f"Maximum permitted observation age is {max_price_staleness_days} calendar days. "
            f"Examples: {invalid_prices.to_dicts()}"
        )

    # --- Phase 3: FX Translation ---
    # CurrencyTransformer has already forward-filled only from prior observations
    # and enforced the same staleness boundary. Do not fill missing FX from future rows.
    df_fx_sorted = (
        df_fx_lazy.select(["Date", "Currency_ID", "FX_Rate"])
        .rename({"Currency_ID": "CURRENCY_ID"})
        .sort("Date")
    )
    df_spine = df_spine.sort("Date")
    df_spine = df_spine.join_asof(
        df_fx_sorted, on="Date", by="CURRENCY_ID", strategy="backward"
    ).sort(["ISIN", "Date"])

    invalid_fx = (
        df_spine.filter(
            pl.col("FX_Rate").is_null() | ~pl.col("FX_Rate").is_finite() | (pl.col("FX_Rate") <= 0)
        )
        .select(["ISIN", "Date", "CURRENCY_ID", "FX_Rate"])
        .limit(10)
        .collect()
    )
    if not invalid_fx.is_empty():
        raise ValueError(
            "Missing, non-positive, or non-finite FX rates for US stock valuation. "
            f"Examples: {invalid_fx.to_dicts()}"
        )

    df_spine = df_spine.with_columns(
        [
            (pl.col("Closing_Price_Local") * pl.col("FX_Rate")).alias("Closing_Price"),
            pl.col("Buy_Price_INR").alias("Buy_Price"),
            pl.col("Buy_Value_INR").alias("Buy_Value"),
        ]
    )

    df_spine = df_spine.with_columns(
        [
            (pl.col("Quantity") * pl.col("Closing_Price")).alias("Closing_Value"),
            (pl.col("Quantity") * pl.col("Closing_Price_Local")).alias("Closing_Value_Local"),
            (pl.col("Closing_Price") - pl.col("Buy_Price")).alias("Unit_PnL"),
        ]
    )

    df_spine = df_spine.with_columns(
        [
            (pl.col("Unit_PnL") * pl.col("Quantity")).alias("Total_PnL"),
            pl.lit("US Stocks").alias("__file_category__"),
        ]
    )

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

    df_spine = df_spine.filter(pl.col("Quantity") >= 0)

    return df_spine.select(select_cols).lazy()
