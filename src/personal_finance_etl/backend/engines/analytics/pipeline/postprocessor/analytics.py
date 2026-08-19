import bisect
import math
from datetime import date
from typing import Any

import numpy as np
import polars as pl
from dateutil.relativedelta import relativedelta

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
            cf_records: list[dict[str, Any]] = []
            for cf in cashflows:
                d_obj = to_date_obj(cf["date"])
                if d_obj:
                    # 'amount' is negative for buys (injections) and positive for sells (withdrawals)
                    cf_records.append({"Date_Obj": d_obj, "injection": -float(cf["amount"])})

            if cf_records:
                df_cf = (
                    pl.DataFrame(cf_records)
                    .group_by("Date_Obj")
                    .agg(pl.col("injection").sum().alias("net_injection"))
                )
                df_pt = df_pt.join(df_cf, on="Date_Obj", how="left").with_columns(
                    pl.col("net_injection").fill_null(0.0)
                )
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
                    pl.when((pl.col("val").shift(1) + pl.when(pl.col("net_injection") > 0).then(pl.col("net_injection")).otherwise(0.0)) > 0)
                    .then(
                        (pl.col("val") - pl.col("val").shift(1) - pl.col("net_injection"))
                        / (pl.col("val").shift(1) + pl.when(pl.col("net_injection") > 0).then(pl.col("net_injection")).otherwise(0.0))
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
                    pl.col("cum_return").cum_max().alias("peak_cum"),
                )
                .with_columns(
                    pl.when(pl.col("peak_cum") > 0)
                    .then((pl.col("cum_return") - pl.col("peak_cum")) / pl.col("peak_cum"))
                    .otherwise(0.0)
                    .alias("Portfolio_Max_Drawdown")
                )
                # ── Benchmark (shadow) returns (Adjusted for Cash flows) ────
                .with_columns(
                    pl.when((pl.col("shadow_val").shift(1) + pl.when(pl.col("net_injection") > 0).then(pl.col("net_injection")).otherwise(0.0)) > 0)
                    .then(
                        (
                            pl.col("shadow_val")
                            - pl.col("shadow_val").shift(1)
                            - pl.col("net_injection")
                        )
                        / (pl.col("shadow_val").shift(1) + pl.when(pl.col("net_injection") > 0).then(pl.col("net_injection")).otherwise(0.0))
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
                    pl.col("bm_cum_return").cum_max().alias("bm_peak_cum"),
                )
                .with_columns(
                    pl.when(pl.col("bm_peak_cum") > 0)
                    .then((pl.col("bm_cum_return") - pl.col("bm_peak_cum")) / pl.col("bm_peak_cum"))
                    .otherwise(0.0)
                    .alias("Portfolio_BM_Max_Drawdown")
                )
            )

            # --- Python-side Time-Range and Drawdown Computation ---
            # Extract lists for faster processing
            dates_list = df_pt["Date_Obj"].to_list()
            cum_rets = df_pt["cum_return"].to_list()
            bm_cum_rets = df_pt["bm_cum_return"].to_list()

            # Drawdowns - Vectorized Rolling Calculation
            daily_rets = df_pt["daily_return"].to_numpy()
            if len(daily_rets) > 0:
                cum = np.cumprod(1.0 + daily_rets)
                roll_max = np.maximum.accumulate(cum)
                is_peak = cum == roll_max

                rolling_peaks: list[date] = []
                rolling_dd_dur: list[int] = []
                rolling_ud_days: list[int] = []
                current_peak = dates_list[0]
                current_ud = 0

                for i in range(len(dates_list)):
                    if is_peak[i]:
                        current_peak = dates_list[i]
                        current_ud = 0
                    else:
                        current_ud += 1

                    rolling_peaks.append(current_peak)
                    rolling_dd_dur.append((dates_list[i] - current_peak).days)
                    rolling_ud_days.append(current_ud)
            else:
                rolling_peaks: list[date] = []
                rolling_dd_dur: list[int] = []
                rolling_ud_days: list[int] = []

            # Time Ranges (Exact Calendar Matching)
            horizons = {
                "1D": relativedelta(days=1),
                "1W": relativedelta(weeks=1),
                "1M": relativedelta(months=1),
                "3M": relativedelta(months=3),
                "6M": relativedelta(months=6),
                "12M": relativedelta(years=1),
                "3Y": relativedelta(years=3),
                "5Y": relativedelta(years=5),
            }

            tr_records: list[dict[str, Any]] = []
            for i, d in enumerate(dates_list):
                rec: dict[str, Any] = {
                    "Closing_Date": df_pt["Closing_Date"][i],
                    "Peak_Date": rolling_peaks[i] if rolling_peaks else None,
                    "Drawdown_Duration": rolling_dd_dur[i] if rolling_dd_dur else 0,
                    "Underwater_Days": int(rolling_ud_days[i]) if rolling_ud_days else 0,
                }
                current_cum = cum_rets[i]
                current_bm_cum = bm_cum_rets[i]

                def get_cum_at(target_d: date) -> tuple[float | None, float | None]:
                    idx = bisect.bisect_right(dates_list, target_d)
                    if idx > 0:
                        return cum_rets[idx - 1], bm_cum_rets[idx - 1]
                    return None, None

                for lbl, delta in horizons.items():
                    past_cum, past_bm_cum = get_cum_at(d - delta)
                    if past_cum is not None and past_cum > 0:
                        rec[f"Return_{lbl}"] = (current_cum / past_cum) - 1.0
                    else:
                        rec[f"Return_{lbl}"] = 0.0

                    if (
                        past_bm_cum is not None
                        and past_bm_cum > 0
                        and past_cum is not None
                        and past_cum > 0
                    ):
                        bm_ret = (current_bm_cum / past_bm_cum) - 1.0
                        rec[f"Alpha_{lbl}"] = rec[f"Return_{lbl}"] - bm_ret
                    else:
                        rec[f"Alpha_{lbl}"] = 0.0

                # YTD (Prior Year End)
                target_ytd = date(d.year - 1, 12, 31)
                past_cum, past_bm_cum = get_cum_at(target_ytd)
                if past_cum is not None and past_cum > 0:
                    rec["Return_YTD"] = (current_cum / past_cum) - 1.0
                else:
                    rec["Return_YTD"] = 0.0
                if (
                    past_bm_cum is not None
                    and past_bm_cum > 0
                    and past_cum is not None
                    and past_cum > 0
                ):
                    rec["Alpha_YTD"] = rec["Return_YTD"] - ((current_bm_cum / past_bm_cum) - 1.0)
                else:
                    rec["Alpha_YTD"] = 0.0

                # FY_YTD (Prior FY End)
                fy_year = d.year if d.month >= 4 else d.year - 1
                target_fy_ytd = date(fy_year, 3, 31)
                past_cum, past_bm_cum = get_cum_at(target_fy_ytd)
                if past_cum is not None and past_cum > 0:
                    rec["Return_FY_YTD"] = (current_cum / past_cum) - 1.0
                else:
                    rec["Return_FY_YTD"] = 0.0
                if (
                    past_bm_cum is not None
                    and past_bm_cum > 0
                    and past_cum is not None
                    and past_cum > 0
                ):
                    rec["Alpha_FY_YTD"] = rec["Return_FY_YTD"] - (
                        (current_bm_cum / past_bm_cum) - 1.0
                    )
                else:
                    rec["Alpha_FY_YTD"] = 0.0

                tr_records.append(rec)

            df_tr = pl.DataFrame(tr_records)
            df_pt = df_pt.join(df_tr, on="Closing_Date", how="left")

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
                        "Peak_Date",
                        "Drawdown_Duration",
                        "Underwater_Days",
                        "Return_1D",
                        "Return_1W",
                        "Return_1M",
                        "Return_3M",
                        "Return_6M",
                        "Return_12M",
                        "Return_3Y",
                        "Return_5Y",
                        "Return_YTD",
                        "Return_FY_YTD",
                        "Alpha_1D",
                        "Alpha_1W",
                        "Alpha_1M",
                        "Alpha_3M",
                        "Alpha_6M",
                        "Alpha_12M",
                        "Alpha_3Y",
                        "Alpha_5Y",
                        "Alpha_YTD",
                        "Alpha_FY_YTD",
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
                    pl.col("Portfolio_Max_Drawdown").cum_min().alias("Historical_Max_DD"),
                    pl.col("Portfolio_BM_Max_Drawdown").cum_min().alias("Historical_BM_Max_DD"),
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
                    pl.when(pl.col("Historical_Max_DD") < -1e-4)
                    .then(pl.col("annualized_twr") / pl.col("Historical_Max_DD").abs())
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
                    pl.when(pl.col("Historical_BM_Max_DD") < -1e-4)
                    .then(pl.col("bm_annualized_twr") / pl.col("Historical_BM_Max_DD").abs())
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
                        "ann_vol",
                        "ann_down_vol",
                        "bm_volatility",
                        "bm_downside_volatility",
                        "bm_ann_vol",
                        "bm_ann_down_vol",
                        "risk_free_rate",
                    ]
                )
            )
        else:
            df_port = df_port.with_columns(
                pl.lit(0.0).alias("Portfolio_Max_Drawdown"),
                pl.lit(0.0).alias("Historical_Max_DD"),
                pl.lit(0.0).alias("Portfolio_Sharpe_Ratio"),
                pl.lit(0.0).alias("Portfolio_Sortino_Ratio"),
                pl.lit(0.0).alias("Portfolio_Calmar_Ratio"),
                pl.lit(0.0).alias("Portfolio_BM_Max_Drawdown"),
                pl.lit(0.0).alias("Historical_BM_Max_DD"),
                pl.lit(0.0).alias("Portfolio_BM_Sharpe_Ratio"),
                pl.lit(0.0).alias("Portfolio_BM_Sortino_Ratio"),
                pl.lit(0.0).alias("Portfolio_BM_Calmar_Ratio"),
                pl.lit(0.0).alias("Portfolio_Sharpe_Alpha"),
                pl.lit(0.0).alias("Portfolio_Sortino_Alpha"),
                pl.lit(0.0).alias("Portfolio_Calmar_Alpha"),
                pl.lit(0.0).alias("annualized_twr"),
                pl.lit(0.0).alias("bm_annualized_twr"),
                pl.lit(None).alias("Peak_Date").cast(pl.Date),
                pl.lit(0).alias("Drawdown_Duration").cast(pl.Int64),
                pl.lit(0).alias("Underwater_Days").cast(pl.Int64),
                *[
                    pl.lit(0.0).alias(f"Return_{lbl}")
                    for lbl in ["1D", "1W", "1M", "3M", "6M", "12M", "3Y", "5Y", "YTD", "FY_YTD"]
                ],
                *[
                    pl.lit(0.0).alias(f"Alpha_{lbl}")
                    for lbl in ["1D", "1W", "1M", "3M", "6M", "12M", "3Y", "5Y", "YTD", "FY_YTD"]
                ],
            )

        return df_port
