import dataclasses
from collections import defaultdict
from datetime import date, timedelta
from typing import Any

import polars as pl


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
    df_prices = df_bronze_prices_lazy.collect()
    df_purchase = df_purchase_lazy.collect()
    df_sale = df_sale_lazy.collect()
    df_fx = df_fx_lazy.collect()

    if df_purchase.is_empty():
        return pl.DataFrame().lazy()

    us_purchases = df_purchase.filter(pl.col("FILE_CATEGORY") == "US Stocks")
    if us_purchases.is_empty():
        return pl.DataFrame().lazy()

    active_isins = us_purchases["ISIN"].unique().to_list()

    # --- Phase 1: Reconstruct FIFO Spine ---
    df_p_us = us_purchases.select(["ISIN", "Date", "Quantity", "Value_Local", "Value"]).sort(
        ["ISIN", "Date"]
    )
    df_s_us = (
        df_sale.filter(pl.col("FILE_CATEGORY") == "US Stocks")
        .select(["ISIN", "Date", "Quantity"])
        .sort(["ISIN", "Date"])
    )

    buys: defaultdict[str, defaultdict[date, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in df_p_us.iter_rows(named=True):
        dt = row["Date"]
        if isinstance(dt, date):
            buys[str(row["ISIN"])][dt].append(row)

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
        lots: list[Lot] = []

        while current_date <= global_end_date:
            # Apply buys
            for b in buys[isin].get(current_date, []):
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
            for s in sells[isin].get(current_date, []):
                sqty = float(s["Quantity"])
                while sqty > 0 and lots:
                    if lots[0].qty > sqty:
                        lots[0].qty -= sqty
                        sqty = 0
                    else:
                        sqty -= lots[0].qty
                        lots.pop(0)

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
                            "Quantity": qty,
                            "Buy_Value_Local": qty * price_local,
                            "Buy_Value_INR": qty * price_inr,
                            "Buy_Price_Local": price_local,
                            "Buy_Price_INR": price_inr,
                        }
                    )

            current_date += timedelta(days=1)

    df_spine = pl.DataFrame(
        spine_records,
        schema={
            "Date": pl.Date,
            "ISIN": pl.String,
            "Quantity": pl.Float64,
            "Buy_Value_Local": pl.Float64,
            "Buy_Value_INR": pl.Float64,
            "Buy_Price_Local": pl.Float64,
            "Buy_Price_INR": pl.Float64,
        },
    )

    if df_spine.is_empty():
        return pl.DataFrame().lazy()

    # --- Phase 2: Price Enrichment (using ASOF Join) ---
    if not df_prices.is_empty():
        df_prices = df_prices.sort("Date")
        df_spine = df_spine.sort("Date")
        df_spine = df_spine.join_asof(
            df_prices.select(["Date", "ISIN", "Closing_Price_Local"]), 
            on="Date", 
            by="ISIN", 
            strategy="backward"
        ).sort(["ISIN", "Date"]).with_columns(
            pl.col("Closing_Price_Local").backward_fill().fill_null(0.0).over("ISIN")
        )
    else:
        df_spine = df_spine.with_columns(pl.lit(0.0).alias("Closing_Price_Local"))

    # --- Phase 3: FX Translation ---
    if not df_fx.is_empty():
        df_fx_us = df_fx.filter(pl.col("Currency_ID") == "INR_USD").select(["Date", "FX_Rate"]).sort("Date")
        df_spine = df_spine.sort("Date")
        df_spine = df_spine.join_asof(
            df_fx_us, on="Date", strategy="backward"
        ).sort(["ISIN", "Date"]).with_columns(
            pl.col("FX_Rate").backward_fill().fill_null(1.0).over("ISIN")
        )
    else:
        df_spine = df_spine.with_columns(pl.lit(1.0).alias("FX_Rate"))

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
            pl.lit("US Stocks").alias("FILE_CATEGORY"),
            pl.lit("INR_USD").alias("CURRENCY_ID"),
        ]
    )

    select_cols = [
        "Date",
        "ISIN",
        "FILE_CATEGORY",
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

    df_spine = df_spine.filter(pl.col("Quantity") >= 0)
    
    return df_spine.select(select_cols).lazy()

