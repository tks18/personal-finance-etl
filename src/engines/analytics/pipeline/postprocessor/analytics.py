import math
from datetime import date
import polars as pl

from src.utils.helpers import to_date_obj

class AdvancedAnalyticsCalculator:
    """Calculates Sharpe, MDD, Sortino ratios."""
    @staticmethod
    def calculate(df_port: pl.DataFrame, unique_dates: list[date], portfolio_terminals: dict[date, dict]) -> pl.DataFrame:
        pt_records = []
        for d in unique_dates:
            d_obj = to_date_obj(d)
            if d_obj:
                pt_entry = portfolio_terminals.get(d_obj, portfolio_terminals.get(d, {}))
                pt_records.append(
                    {"Closing_Date": d, "Date_Obj": d_obj, "val": pt_entry.get("val", 0.0)}
                )

        if pt_records:
            df_pt = pl.DataFrame(pt_records).sort("Date_Obj")
            df_pt = (
                df_pt.with_columns(pl.col("val").pct_change().fill_null(0.0).alias("daily_return"))
                .with_columns(
                    pl.col("daily_return")
                    .rolling_std(window_size=252, min_samples=1)
                    .fill_null(0.0)
                    .alias("volatility"),
                    pl.when(pl.col("daily_return") < 0)
                    .then(pl.col("daily_return"))
                    .otherwise(0.0)
                    .rolling_std(window_size=252, min_samples=1)
                    .fill_null(0.0)
                    .alias("downside_volatility"),
                    pl.col("val").cum_max().alias("peak_val"),
                )
                .with_columns(
                    pl.when(pl.col("peak_val") > 0)
                    .then((pl.col("val") - pl.col("peak_val")) / pl.col("peak_val"))
                    .otherwise(0.0)
                    .alias("Portfolio_Max_Drawdown")
                )
            )

            df_port = df_port.join(
                df_pt.select(
                    ["Closing_Date", "volatility", "downside_volatility", "Portfolio_Max_Drawdown"]
                ),
                on="Closing_Date",
                how="left",
            )
            risk_free_rate = 0.06  # Assuming 6% Risk Free Rate for India
            df_port = (
                df_port.with_columns(
                    (pl.col("volatility") * math.sqrt(252)).alias("ann_vol"),
                    (pl.col("downside_volatility") * math.sqrt(252)).alias("ann_down_vol"),
                )
                .with_columns(
                    pl.when(pl.col("ann_vol") > 0)
                    .then((pl.col("Portfolio_XIRR") - risk_free_rate) / pl.col("ann_vol"))
                    .otherwise(0.0)
                    .alias("Portfolio_Sharpe_Ratio"),
                    pl.when(pl.col("ann_down_vol") > 0)
                    .then((pl.col("Portfolio_XIRR") - risk_free_rate) / pl.col("ann_down_vol"))
                    .otherwise(0.0)
                    .alias("Portfolio_Sortino_Ratio"),
                )
                .drop(["volatility", "downside_volatility", "ann_vol", "ann_down_vol"])
            )
        else:
            df_port = df_port.with_columns(
                pl.lit(0.0).alias("Portfolio_Max_Drawdown"),
                pl.lit(0.0).alias("Portfolio_Sharpe_Ratio"),
                pl.lit(0.0).alias("Portfolio_Sortino_Ratio"),
            )
            
        return df_port
