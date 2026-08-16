import math
from datetime import date
from typing import Any

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.engines.analytics.rules.macro import FYMacroParametersTable
from personal_finance_etl.backend.utils.helpers import to_date_obj


class AdvancedAnalyticsCalculator:
    """Calculates Sharpe, Sortino, Calmar, MDD ratios for portfolio and its benchmark."""

    def __init__(self, fy_table: FYMacroParametersTable, rules: FinancialRules | None) -> None:
        self.fy_table = fy_table
        self.rules = rules

    def calculate(
        self,
        df_port: pl.DataFrame,
        unique_dates: list[date],
        portfolio_terminals: dict[date, dict[str, Any]],
        cashflows: list[dict[str, Any]],
    ) -> pl.DataFrame:
        pt_records: list[dict[str, Any]] = []
        for d in unique_dates:
            d_obj = to_date_obj(d)
            if d_obj:
                pt_entry = portfolio_terminals.get(d_obj, portfolio_terminals.get(d, {}))
                pt_records.append(
                    {
                        "Closing_Date": d,
                        "Date_Obj": d_obj,
                        "val": pt_entry.get("val", 0.0),
                        # shadow_val = what benchmark portfolio would be worth
                        "shadow_val": pt_entry.get("shadow_val", 0.0),
                    }
                )

        if pt_records:
            df_pt = pl.DataFrame(pt_records).sort("Date_Obj")
            
            # Aggregate cash flows by date to compute net injection
            cf_records = []
            for cf in cashflows:
                d_obj = to_date_obj(cf["date"])
                if d_obj:
                    # 'amount' is negative for buys (injections) and positive for sells (withdrawals)
                    cf_records.append({"Date_Obj": d_obj, "injection": -float(cf["amount"])})
            
            if cf_records:
                df_cf = pl.DataFrame(cf_records).group_by("Date_Obj").agg(pl.col("injection").sum().alias("net_injection"))
                df_pt = df_pt.join(df_cf, on="Date_Obj", how="left").with_columns(pl.col("net_injection").fill_null(0.0))
            else:
                df_pt = df_pt.with_columns(pl.lit(0.0).alias("net_injection"))

            if df_pt.height > 1:
                avg_days = (df_pt["Date_Obj"][-1] - df_pt["Date_Obj"][0]).days / (df_pt.height - 1)
                annual_periods = max(1, int(round(365.0 / max(1.0, avg_days))))
            else:
                annual_periods = 12

            sqrt_ann = math.sqrt(annual_periods)

            df_pt = (
                # ── Portfolio (actual) returns (Adjusted for Cash flows) ──────────
                df_pt.with_columns(
                    pl.when((pl.col("val").shift(1) + (pl.col("net_injection") * 0.5)) > 0)
                    .then(
                        (pl.col("val") - pl.col("val").shift(1) - pl.col("net_injection"))
                        / (pl.col("val").shift(1) + (pl.col("net_injection") * 0.5))
                    )
                    .otherwise(0.0)
                    .alias("daily_return")
                )
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
                    # Sortino semi-deviation: replace positive returns with 0.0,
                    # square the results, take the rolling mean, and square root it.
                    # This correctly computes the Root Mean Square of negative returns.
                    pl.when(pl.col("daily_return") < 0)
                    .then(pl.col("daily_return"))
                    .otherwise(0.0)
                    .pow(2)
                    .rolling_mean(window_size=annual_periods, min_samples=1)
                    .sqrt()
                    .fill_null(0.0)
                    .alias("downside_volatility"),
                    pl.col("val").cum_max().alias("peak_val"),
                )
                .with_columns(
                    pl.when(pl.col("peak_val") > 0)
                    .then((pl.col("val") - pl.col("peak_val")) / pl.col("peak_val"))
                    .otherwise(0.0)
                    .cum_min()
                    .alias("Portfolio_Max_Drawdown")
                )
                # ── Benchmark (shadow) returns (Adjusted for Cash flows) ────
                .with_columns(
                    pl.when((pl.col("shadow_val").shift(1) + (pl.col("net_injection") * 0.5)) > 0)
                    .then(
                        (pl.col("shadow_val") - pl.col("shadow_val").shift(1) - pl.col("net_injection"))
                        / (pl.col("shadow_val").shift(1) + (pl.col("net_injection") * 0.5))
                    )
                    .otherwise(0.0)
                    .alias("bm_daily_return")
                )
                .with_columns((pl.col("bm_daily_return") + 1.0).cum_prod().alias("bm_cum_return"))
                .with_columns(
                    pl.when(pl.col("Date_Obj").cum_count() > 1)
                    .then(
                        pl.col("bm_cum_return").pow(
                            365.0
                            / pl.max_horizontal(
                                1.0,
                                (pl.col("Date_Obj") - pl.col("Date_Obj").first()).dt.total_days(),
                            )
                        )
                        - 1.0
                    )
                    .otherwise(0.0)
                    .alias("bm_annualized_twr")
                )
                .with_columns(
                    pl.col("bm_daily_return")
                    .rolling_std(window_size=annual_periods, min_samples=1)
                    .fill_null(0.0)
                    .alias("bm_volatility"),
                    # Benchmark Sortino semi-deviation: same fix as portfolio.
                    pl.when(pl.col("bm_daily_return") < 0)
                    .then(pl.col("bm_daily_return"))
                    .otherwise(0.0)
                    .pow(2)
                    .rolling_mean(window_size=annual_periods, min_samples=1)
                    .sqrt()
                    .fill_null(0.0)
                    .alias("bm_downside_volatility"),
                    pl.col("shadow_val").cum_max().alias("bm_peak_val"),
                )
                .with_columns(
                    pl.when(pl.col("bm_peak_val") > 0)
                    .then((pl.col("shadow_val") - pl.col("bm_peak_val")) / pl.col("bm_peak_val"))
                    .otherwise(0.0)
                    .cum_min()
                    .alias("Portfolio_BM_Max_Drawdown")
                )
            )

            df_port = df_port.join(
                df_pt.select(
                    [
                        "Closing_Date",
                        "volatility",
                        "downside_volatility",
                        "annualized_twr",
                        "Portfolio_Max_Drawdown",
                        "bm_volatility",
                        "bm_downside_volatility",
                        "bm_annualized_twr",
                        "Portfolio_BM_Max_Drawdown",
                    ]
                ),
                on="Closing_Date",
                how="left",
            )

            rfr_list = [
                {"Closing_Date": d, "risk_free_rate": self.fy_table.get_risk_free_rate(d)}
                for d in unique_dates
            ]
            df_rfr = pl.DataFrame(rfr_list)
            df_port = df_port.join(df_rfr, on="Closing_Date", how="left")

            df_port = (
                df_port.with_columns(
                    # Annualise period volatilities
                    (pl.col("volatility") * sqrt_ann).alias("ann_vol"),
                    (pl.col("downside_volatility") * sqrt_ann).alias("ann_down_vol"),
                    (pl.col("bm_volatility") * sqrt_ann).alias("bm_ann_vol"),
                    (pl.col("bm_downside_volatility") * sqrt_ann).alias("bm_ann_down_vol"),
                )
                .with_columns(
                    # ── Portfolio risk-adjusted ratios ──────────────────────
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
                    pl.when(pl.col("Portfolio_Max_Drawdown") < -1e-4)
                    .then(pl.col("annualized_twr") / pl.col("Portfolio_Max_Drawdown").abs())
                    .otherwise(0.0)
                    .alias("Portfolio_Calmar_Ratio"),
                    # ── Benchmark risk-adjusted ratios ──────────────────────
                    pl.when(pl.col("bm_ann_vol") > 0)
                    .then(
                        (pl.col("bm_annualized_twr") - pl.col("risk_free_rate"))
                        / pl.col("bm_ann_vol")
                    )
                    .otherwise(0.0)
                    .alias("Portfolio_BM_Sharpe_Ratio"),
                    pl.when(pl.col("bm_ann_down_vol") > 0)
                    .then(
                        (pl.col("bm_annualized_twr") - pl.col("risk_free_rate"))
                        / pl.col("bm_ann_down_vol")
                    )
                    .otherwise(0.0)
                    .alias("Portfolio_BM_Sortino_Ratio"),
                    pl.when(pl.col("Portfolio_BM_Max_Drawdown") < -1e-4)
                    .then(pl.col("bm_annualized_twr") / pl.col("Portfolio_BM_Max_Drawdown").abs())
                    .otherwise(0.0)
                    .alias("Portfolio_BM_Calmar_Ratio"),
                )
                .with_columns(
                    # ── Alpha = portfolio ratio minus benchmark ratio ────────
                    (pl.col("Portfolio_Sharpe_Ratio") - pl.col("Portfolio_BM_Sharpe_Ratio")).alias(
                        "Portfolio_Sharpe_Alpha"
                    ),
                    (
                        pl.col("Portfolio_Sortino_Ratio") - pl.col("Portfolio_BM_Sortino_Ratio")
                    ).alias("Portfolio_Sortino_Alpha"),
                    (pl.col("Portfolio_Calmar_Ratio") - pl.col("Portfolio_BM_Calmar_Ratio")).alias(
                        "Portfolio_Calmar_Alpha"
                    ),
                )
                .drop(
                    [
                        "volatility",
                        "downside_volatility",
                        "annualized_twr",
                        "ann_vol",
                        "ann_down_vol",
                        "bm_volatility",
                        "bm_downside_volatility",
                        "bm_annualized_twr",
                        "bm_ann_vol",
                        "bm_ann_down_vol",
                        "risk_free_rate",
                    ]
                )
            )
        else:
            df_port = df_port.with_columns(
                pl.lit(0.0).alias("Portfolio_Max_Drawdown"),
                pl.lit(0.0).alias("Portfolio_Sharpe_Ratio"),
                pl.lit(0.0).alias("Portfolio_Sortino_Ratio"),
                pl.lit(0.0).alias("Portfolio_Calmar_Ratio"),
                pl.lit(0.0).alias("Portfolio_BM_Max_Drawdown"),
                pl.lit(0.0).alias("Portfolio_BM_Sharpe_Ratio"),
                pl.lit(0.0).alias("Portfolio_BM_Sortino_Ratio"),
                pl.lit(0.0).alias("Portfolio_BM_Calmar_Ratio"),
                pl.lit(0.0).alias("Portfolio_Sharpe_Alpha"),
                pl.lit(0.0).alias("Portfolio_Sortino_Alpha"),
                pl.lit(0.0).alias("Portfolio_Calmar_Alpha"),
            )

        return df_port
