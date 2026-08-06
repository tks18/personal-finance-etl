import math
from datetime import date

import polars as pl

from src.utils.helpers import to_date_obj


class AdvancedAnalyticsCalculator:
    """Calculates Sharpe, MDD, Sortino ratios."""

    def __init__(self, fy_table, rules):
        self.fy_table = fy_table
        self.rules = rules

    def calculate(
        self, df_port: pl.DataFrame, unique_dates: list[date], portfolio_terminals: dict[date, dict]
    ) -> pl.DataFrame:
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
            if df_pt.height > 1:
                avg_days = (df_pt["Date_Obj"][-1] - df_pt["Date_Obj"][0]).days / (df_pt.height - 1)
                annual_periods = max(1, int(round(365.0 / max(1.0, avg_days))))
            else:
                annual_periods = 12

            df_pt = (
                df_pt.with_columns(pl.col("val").pct_change().fill_null(0.0).alias("daily_return"))
                .with_columns((pl.col("daily_return") + 1.0).cum_prod().alias("cum_return"))
                .with_columns(
                    pl.when(pl.col("Date_Obj").cum_count() > 1)
                    .then(
                        pl.col("cum_return").pow(
                            365.0
                            / pl.max_horizontal(
                                1.0,
                                (pl.col("Date_Obj") - pl.col("Date_Obj").first()).dt.total_days(),
                            )
                        )
                        - 1.0
                    )
                    .otherwise(0.0)
                    .alias("annualized_twr")
                )
                .with_columns(
                    pl.col("daily_return")
                    .rolling_std(window_size=annual_periods, min_samples=1)
                    .fill_null(0.0)
                    .alias("volatility"),
                    pl.when(pl.col("daily_return") < 0)
                    .then(pl.col("daily_return"))
                    .otherwise(0.0)
                    .rolling_std(window_size=annual_periods, min_samples=1)
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
                    [
                        "Closing_Date",
                        "volatility",
                        "downside_volatility",
                        "Portfolio_Max_Drawdown",
                        "annualized_twr",
                    ]
                ),
                on="Closing_Date",
                how="left",
            )

            if self.fy_table is not None:
                rfr_list = [
                    {"Closing_Date": d, "risk_free_rate": self.fy_table.get_risk_free_rate(d)}
                    for d in unique_dates
                ]
                df_rfr = pl.DataFrame(rfr_list)
            else:
                fallback_rfr = (
                    self.rules.assumptions.macro.fallback_risk_free_rate if self.rules else 0.06
                )
                df_rfr = pl.DataFrame(
                    [{"Closing_Date": d, "risk_free_rate": fallback_rfr} for d in unique_dates]
                )

            df_port = df_port.join(df_rfr, on="Closing_Date", how="left")

            df_port = (
                df_port.with_columns(
                    (pl.col("volatility") * math.sqrt(annual_periods)).alias("ann_vol"),
                    (pl.col("downside_volatility") * math.sqrt(annual_periods)).alias(
                        "ann_down_vol"
                    ),
                )
                .with_columns(
                    pl.when(pl.col("ann_vol") > 0)
                    .then((pl.col("annualized_twr") - pl.col("risk_free_rate")) / pl.col("ann_vol"))
                    .otherwise(0.0)
                    .alias("Portfolio_Sharpe_Ratio"),
                    pl.when(pl.col("ann_down_vol") > 0)
                    .then(
                        (pl.col("annualized_twr") - pl.col("risk_free_rate"))
                        / pl.col("ann_down_vol")
                    )
                    .otherwise(0.0)
                    .alias("Portfolio_Sortino_Ratio"),
                )
                .drop(
                    [
                        "volatility",
                        "downside_volatility",
                        "ann_vol",
                        "ann_down_vol",
                        "annualized_twr",
                        "risk_free_rate",
                    ]
                )
            )
        else:
            df_port = df_port.with_columns(
                pl.lit(0.0).alias("Portfolio_Max_Drawdown"),
                pl.lit(0.0).alias("Portfolio_Sharpe_Ratio"),
                pl.lit(0.0).alias("Portfolio_Sortino_Ratio"),
            )

        return df_port
