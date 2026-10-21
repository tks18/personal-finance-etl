"""Investment portfolio and currency market value injection for net worth calculations.

Owns
----
- aggregate_portfolio_analytics: Aggregate latest portfolio valuations snapped to month end.
- aggregate_currency_analytics: Aggregate foreign currency balances snapped to month end.
- inject_portfolio_market_values: Join portfolio and currency valuations into monthly totals.

Does not own
-------------
- Overall monthly balance aggregation (owned by domain.wealth.net_worth).
- Investment analytics calculation (owned by application.investments).
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

__all__ = [
    "aggregate_currency_analytics",
    "aggregate_portfolio_analytics",
    "inject_portfolio_market_values",
]


def aggregate_portfolio_analytics(df_inv_port: pl.DataFrame | pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate latest portfolio valuations for each month end.

    Parameters
    ----------
    df_inv_port : pl.DataFrame | pl.LazyFrame
        Investment portfolio analytics mart.

    Returns
    -------
    pl.LazyFrame
        Valuations grouped by month end date.
    """
    lf_inv_port = df_inv_port.lazy() if isinstance(df_inv_port, pl.DataFrame) else df_inv_port
    lf_inv_port_mapped = lf_inv_port.with_columns(
        pl.col("Closing_Date").dt.month_end().alias("MONTH_END_DATE")
    )
    lf_inv_port_latest = lf_inv_port_mapped.group_by("MONTH_END_DATE").agg(
        pl.col("Closing_Date").max().alias("Max_Closing_Date")
    )
    return (
        lf_inv_port_mapped.join(lf_inv_port_latest, on="MONTH_END_DATE")
        .filter(pl.col("Closing_Date") == pl.col("Max_Closing_Date"))
        .select(
            [
                "MONTH_END_DATE",
                pl.col("Total_Current_Value").alias("Closing_Investment_Market_Value"),
                pl.col("Total_Invested_Value").alias("Closing_Investment_Book_Value"),
                pl.col("XIRR").alias("Closing_Investment_XIRR"),
                pl.col("Unrealized_PL").alias("Closing_Unrealized_PL"),
                pl.col("Asset_PnL").alias("Closing_Asset_PnL"),
                pl.col("Forex_PnL").alias("Closing_Forex_PnL"),
            ]
        )
    )


def aggregate_currency_analytics(
    df_inv_curr: pl.DataFrame | pl.LazyFrame,
    default_currency_id: str,
) -> pl.LazyFrame:
    """Aggregate foreign currency balances snapped to month end.

    Parameters
    ----------
    df_inv_curr : pl.DataFrame | pl.LazyFrame
        Currency analytics mart.
    default_currency_id : str
        Default base currency ID.

    Returns
    -------
    pl.LazyFrame
        Foreign currency exposure by month end date.
    """
    lf_inv_curr = df_inv_curr.lazy() if isinstance(df_inv_curr, pl.DataFrame) else df_inv_curr
    return (
        lf_inv_curr.with_columns(pl.col("Closing_Date").dt.month_end().alias("MONTH_END_DATE"))
        .filter(pl.col("CURRENCY_ID") != default_currency_id)
        .group_by("MONTH_END_DATE")
        .agg(
            pl.col("Total_Current_Value")
            .sum()
            .fill_null(0.0)
            .alias("Total_Foreign_Currency_Exposure")
        )
    )


def inject_portfolio_market_values(
    lf_monthly_totals: pl.LazyFrame,
    dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
    default_currency_id: str,
) -> pl.LazyFrame:
    """Join portfolio and currency valuations into monthly totals.

    Parameters
    ----------
    lf_monthly_totals : pl.LazyFrame
        Monthly totals before investment market value adjustment.
    dfs : Mapping[str, pl.DataFrame | pl.LazyFrame]
        Input DataFrames map containing portfolio and currency marts.
    default_currency_id : str
        Default base currency ID.

    Returns
    -------
    pl.LazyFrame
        Adjusted monthly totals with mark-to-market valuations.
    """
    df_inv_port = dfs.get("df_f_investment_analytics_portfolio")
    if df_inv_port is not None:
        lf_inv_port_agg = aggregate_portfolio_analytics(df_inv_port)
        df_inv_curr = dfs.get("df_f_investment_analytics_currency")

        if df_inv_curr is not None:
            lf_foreign_exposure = aggregate_currency_analytics(df_inv_curr, default_currency_id)
            lf_inv_port_agg = lf_inv_port_agg.join(
                lf_foreign_exposure, on="MONTH_END_DATE", how="left"
            ).with_columns(pl.col("Total_Foreign_Currency_Exposure").fill_null(0.0))
        else:
            lf_inv_port_agg = lf_inv_port_agg.with_columns(
                pl.lit(0.0).alias("Total_Foreign_Currency_Exposure")
            )

        return (
            lf_monthly_totals.join(
                lf_inv_port_agg,
                on="MONTH_END_DATE",
                how="left",
            )
            .with_columns(
                pl.col("Closing_Investment_Market_Value").fill_null(0.0),
                pl.col("Closing_Investment_Book_Value").fill_null(0.0),
                pl.col("Closing_Investment_XIRR").fill_null(0.0),
                pl.col("Closing_Unrealized_PL").fill_null(0.0),
                pl.col("Closing_Asset_PnL").fill_null(0.0),
                pl.col("Closing_Forex_PnL").fill_null(0.0),
                pl.col("Total_Foreign_Currency_Exposure").fill_null(0.0),
            )
            .with_columns(
                pl.when(pl.col("Total_Net_Worth") > 0)
                .then(pl.col("Total_Foreign_Currency_Exposure") / pl.col("Total_Net_Worth"))
                .otherwise(0.0)
                .alias("Foreign_Exposure_Pct")
            )
            .with_columns(
                pl.when(pl.col("Closing_Investment_Book_Value") > 0)
                .then(
                    pl.col("Total_Assets")
                    - pl.col("Closing_Investment_Book_Value")
                    + pl.col("Closing_Investment_Market_Value")
                )
                .otherwise(pl.col("Total_Assets"))
                .alias("Total_Assets_Market"),
                pl.when(pl.col("Closing_Investment_Book_Value") > 0)
                .then(
                    pl.col("Total_Net_Worth")
                    - pl.col("Closing_Investment_Book_Value")
                    + pl.col("Closing_Investment_Market_Value")
                )
                .otherwise(pl.col("Total_Net_Worth"))
                .alias("Total_Net_Worth_Market"),
                pl.when(pl.col("Closing_Investment_Book_Value") > 0)
                .then(
                    pl.col("Liquid_Assets")
                    - pl.col("Closing_Investment_Book_Value")
                    + pl.col("Closing_Investment_Market_Value")
                )
                .otherwise(pl.col("Liquid_Assets"))
                .alias("Liquid_Assets_Market"),
            )
        )

    return lf_monthly_totals.with_columns(
        pl.col("Total_Assets").alias("Total_Assets_Market"),
        pl.col("Total_Net_Worth").alias("Total_Net_Worth_Market"),
        pl.col("Liquid_Assets").alias("Liquid_Assets_Market"),
        pl.lit(0.0).alias("Closing_Investment_Market_Value"),
        pl.lit(0.0).alias("Closing_Investment_Book_Value"),
        pl.lit(0.0).alias("Closing_Investment_XIRR"),
        pl.lit(0.0).alias("Closing_Unrealized_PL"),
        pl.lit(0.0).alias("Closing_Asset_PnL"),
        pl.lit(0.0).alias("Closing_Forex_PnL"),
        pl.lit(0.0).alias("Total_Foreign_Currency_Exposure"),
        pl.lit(0.0).alias("Foreign_Exposure_Pct"),
    )
