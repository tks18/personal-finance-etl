from collections.abc import Mapping
from typing import Any

import numpy as np
import polars as pl


class FireForecastingBuilder:
    """
    Constructs the FIRE & Wealth Forecasting presentation model.
    """

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: dict[str, Any],
        lf_risk: pl.LazyFrame,
        rules=None,
    ):
        self.dfs = dfs
        self.base_lf = base_lf
        self.lf_risk = lf_risk
        self.rules = rules

    def build(self) -> pl.LazyFrame:
        lf_monthly_totals = self.base_lf["lf_monthly_totals"]

        lf_fire_base = (
            lf_monthly_totals.select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "Total_Net_Worth",
                    "Total_Net_Worth_Market",
                    "Total_Income",
                    "Total_Core_Expense",
                    "Total_Expense",
                    "INFLATION_YOY_PCT",
                    "CPI_INDEX",
                ]
            )
            .with_columns(
                pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
                (pl.col("Total_Income") - pl.col("Total_Core_Expense")).alias("Net_Savings"),
                (pl.col("Total_Income") - pl.col("Total_Expense")).alias("Net_Savings_Total"),
            )
            .sort("MONTH_START_DATE")
        )

        df_inv_port = self.dfs.get("df_f_tf_investment_analytics_portfolio")
        tax_rate = (
            self.rules.assumptions.tax.rates.equity_ltcg
            if self.rules and hasattr(self.rules.assumptions.tax, "rates")
            else 0.125
        )

        if df_inv_port is not None:
            lf_inv_port = (
                df_inv_port.lazy() if isinstance(df_inv_port, pl.DataFrame) else df_inv_port
            )
            lf_inv_port_mapped = lf_inv_port.with_columns(
                pl.col("Closing_Date").dt.month_end().alias("MONTH_END_DATE")
            )
            lf_inv_port_latest = lf_inv_port_mapped.group_by("MONTH_END_DATE").agg(
                pl.col("Closing_Date").max().alias("Max_Closing_Date")
            )
            lf_inv_port_agg = (
                lf_inv_port_mapped.join(lf_inv_port_latest, on="MONTH_END_DATE")
                .filter(pl.col("Closing_Date") == pl.col("Max_Closing_Date"))
                .select(
                    [
                        "MONTH_END_DATE",
                        pl.col("Total_Current_Value").alias("Port_Market_Value"),
                        pl.col("Total_Invested_Value").alias("Port_Book_Value"),
                    ]
                )
            )

            lf_fire_base = (
                lf_fire_base.join(
                    lf_inv_port_agg,
                    on="MONTH_END_DATE",
                    how="left",
                )
                .with_columns(
                    pl.col("Port_Market_Value").fill_null(0.0),
                    pl.col("Port_Book_Value").fill_null(0.0),
                )
                .with_columns(
                    pl.when(pl.col("Port_Market_Value") > pl.col("Port_Book_Value"))
                    .then(
                        pl.col("Total_Net_Worth_Market")
                        - ((pl.col("Port_Market_Value") - pl.col("Port_Book_Value")) * tax_rate)
                    )
                    .otherwise(pl.col("Total_Net_Worth_Market"))
                    .alias("Total_Net_Worth_Market")
                )
                .drop(["Port_Market_Value", "Port_Book_Value"])
            )

        swr = self.rules.assumptions.fire.swr_multiplier if self.rules else 25.0
        coast_real_return = self.rules.assumptions.fire.coast_fi_real_return if self.rules else 0.05
        coast_years = self.rules.assumptions.fire.coast_fi_years if self.rules else 10
        lean_ratio = self.rules.assumptions.fire.lean_fi_ratio if self.rules else 0.7
        mc_iterations = self.rules.assumptions.monte_carlo.iterations if self.rules else 1000
        mc_max_months = self.rules.assumptions.monte_carlo.max_months if self.rules else 480
        mc_volatility = self.rules.assumptions.monte_carlo.annual_volatility if self.rules else 0.15

        cma_real_return = (
            self.rules.assumptions.cma.expected_real_return
            if self.rules and hasattr(self.rules.assumptions, "cma")
            else 0.05
        )
        cma_fat_tail = (
            self.rules.assumptions.cma.fat_tail_multiplier
            if self.rules and hasattr(self.rules.assumptions, "cma")
            else 1.2
        )
        lf_fire_forecast = (
            lf_fire_base.with_columns(
                pl.col("Total_Core_Expense")
                .rolling_mean(window_size=3)
                .alias("Trailing_3M_Avg_Spend"),
                pl.col("Total_Core_Expense")
                .rolling_mean(window_size=6)
                .alias("Trailing_6M_Avg_Spend"),
                pl.col("Total_Core_Expense")
                .rolling_sum(window_size=12)
                .alias("Trailing_12M_Spend"),
                pl.col("Net_Savings").rolling_mean(window_size=6).alias("Trailing_6M_Avg_Savings"),
                pl.col("Net_Savings").rolling_sum(window_size=12).alias("Trailing_12M_Savings"),
                pl.col("Total_Expense")
                .rolling_mean(window_size=3)
                .alias("Trailing_3M_Avg_Total_Spend"),
                pl.col("Total_Expense")
                .rolling_mean(window_size=6)
                .alias("Trailing_6M_Avg_Total_Spend"),
                pl.col("Total_Expense")
                .rolling_sum(window_size=12)
                .alias("Trailing_12M_Total_Spend"),
                pl.col("Net_Savings_Total")
                .rolling_mean(window_size=6)
                .alias("Trailing_6M_Avg_Total_Savings"),
                pl.col("Net_Savings_Total")
                .rolling_sum(window_size=12)
                .alias("Trailing_12M_Total_Savings"),
            )
            .with_columns(
                (pl.col("Trailing_12M_Spend") * swr).alias("Target_FI_Today"),
                (pl.col("Trailing_12M_Total_Spend") * swr).alias("Target_FI_Today_Total"),
            )
            .with_columns(
                pl.when(pl.col("Target_FI_Today") > 0)
                .then(pl.col("Total_Net_Worth_Market") / pl.col("Target_FI_Today"))
                .otherwise(0.0)
                .alias("Current_FI_Coverage_Pct"),
                pl.when(pl.col("Trailing_3M_Avg_Spend") > 0)
                .then(pl.col("Total_Net_Worth_Market") / pl.col("Trailing_3M_Avg_Spend"))
                .otherwise(0.0)
                .alias("Runway_Months"),
                pl.when(pl.col("Target_FI_Today_Total") > 0)
                .then(pl.col("Total_Net_Worth_Market") / pl.col("Target_FI_Today_Total"))
                .otherwise(0.0)
                .alias("Current_FI_Coverage_Pct_Total"),
                pl.when(pl.col("Trailing_3M_Avg_Total_Spend") > 0)
                .then(pl.col("Total_Net_Worth_Market") / pl.col("Trailing_3M_Avg_Total_Spend"))
                .otherwise(0.0)
                .alias("Runway_Months_Total"),
            )
        )

        # Probabilistic Monte Carlo Simulation for FIRE using map_batches
        def monte_carlo_fire_batch(s: pl.Series, **kwargs) -> pl.Series:
            df = s.struct.unnest()
            pv = df["Total_Net_Worth_Market"].to_numpy().astype(float)
            pmt = df["Trailing_6M_Avg_Savings"].to_numpy().astype(float)
            fv = df["Target_FI_Today"].to_numpy().astype(float)
            pmt_total = df["Trailing_6M_Avg_Total_Savings"].to_numpy().astype(float)
            fv_total = df["Target_FI_Today_Total"].to_numpy().astype(float)
            inf_rates = df["INFLATION_YOY_PCT"].to_numpy().astype(float)
            year_month = df["YEAR_MONTH"].to_list()

            n_rows = len(pv)
            out_p90, out_p50, out_p10 = np.zeros(n_rows), np.zeros(n_rows), np.zeros(n_rows)
            out_total_p90, out_total_p50, out_total_p10 = (
                np.zeros(n_rows),
                np.zeros(n_rows),
                np.zeros(n_rows),
            )
            out_nom_p50, out_total_nom_p50 = np.zeros(n_rows), np.zeros(n_rows)
            prob_success = np.zeros(n_rows)
            prob_success_total = np.zeros(n_rows)

            iterations = mc_iterations
            max_months = mc_max_months
            decum_months = 360

            # Using fat-tail adjusted volatility
            vol_r = (mc_volatility * cma_fat_tail) / np.sqrt(12)

            # Apply 50 basis points of estimated annual tax drag on yields in taxable brokerage accounts
            tax_drag = 0.005
            mean_r = (cma_real_return - tax_drag) / 12.0

            for i in range(n_rows):
                row_seed = int(str(year_month[i]).replace("-", ""))
                rng = np.random.default_rng(row_seed)

                valid_fire = (fv[i] > pv[i]) and (pmt[i] > 0)
                valid_total = (fv_total[i] > pv[i]) and (pmt_total[i] > 0)

                # SWR withdrawal amounts (real)
                withdraw_fire = fv[i] / swr / 12.0 if swr > 0 else 0
                withdraw_total = fv_total[i] / swr / 12.0 if swr > 0 else 0

                # Stochastic Inflation Array (Random Walk with Drift)
                inf_base = inf_rates[i] if not np.isnan(inf_rates[i]) else 0.04
                inf_shocks = rng.normal(
                    loc=0.0, scale=0.015 / np.sqrt(12), size=(iterations, max_months)
                )
                inf_paths = np.clip(inf_base + np.cumsum(inf_shocks, axis=1), 0.0, 0.15)
                cum_inf_multiplier = np.cumprod(1.0 + (inf_paths / 12.0), axis=1)

                if valid_fire or valid_total:
                    # Accumulation phase multipliers (Fat-tail Student's t)
                    returns_acc = (
                        rng.standard_t(df=4, size=(iterations, max_months)) * (vol_r / np.sqrt(2))
                        + mean_r
                    )
                    # Merton Jump-Diffusion (5% annual chance of 20% crash)
                    jump_prob_monthly = 0.05 / 12.0
                    jump_magnitude = -0.20
                    jumps_acc = rng.binomial(1, jump_prob_monthly, size=(iterations, max_months))
                    returns_acc = returns_acc + (jumps_acc * jump_magnitude)

                    multipliers = 1.0 + returns_acc
                else:
                    multipliers = None

                # CORE FIRE
                if not valid_fire:
                    if np.isnan(fv[i]) or np.isnan(pv[i]) or np.isnan(pmt[i]) or pmt[i] <= 0:
                        out_p90[i], out_p50[i], out_p10[i] = np.nan, np.nan, np.nan
                        prob_success[i] = np.nan
                    else:
                        out_p90[i], out_p50[i], out_p10[i] = 0.0, 0.0, 0.0
                        prob_success[i] = 1.0  # Already FI
                else:
                    assert multipliers is not None
                    wealth = np.empty((iterations, max_months))
                    wealth[:, 0] = pv[i]
                    for m in range(1, max_months):
                        wealth[:, m] = wealth[:, m - 1] * multipliers[:, m] + pmt[i]

                    reached = wealth >= fv[i]
                    months_to_fire = np.argmax(reached, axis=1).astype(float)
                    never_reached = ~np.any(reached, axis=1)
                    months_to_fire[never_reached] = np.nan

                    out_p90[i] = (
                        float(np.percentile(months_to_fire[~never_reached], 90))
                        if np.any(~never_reached)
                        else np.nan
                    )
                    out_p50[i] = (
                        float(np.percentile(months_to_fire[~never_reached], 50))
                        if np.any(~never_reached)
                        else np.nan
                    )
                    out_p10[i] = (
                        float(np.percentile(months_to_fire[~never_reached], 10))
                        if np.any(~never_reached)
                        else np.nan
                    )

                    if np.any(~never_reached):
                        valid_p = np.where(~never_reached)[0]
                        hit_m = months_to_fire[~never_reached].astype(int)
                        nom_targets = fv[i] * cum_inf_multiplier[valid_p, hit_m]
                        out_nom_p50[i] = float(np.percentile(nom_targets, 50))
                    else:
                        out_nom_p50[i] = np.nan

                    # Decumulation phase (SORR)
                    success_count = 0
                    valid_paths = np.where(~never_reached)[0]
                    if len(valid_paths) > 0:
                        returns_dec = (
                            rng.standard_t(df=4, size=(len(valid_paths), decum_months))
                            * (vol_r / np.sqrt(2))
                            + mean_r
                        )
                        jumps_dec = rng.binomial(
                            1, 0.05 / 12.0, size=(len(valid_paths), decum_months)
                        )
                        returns_dec = returns_dec + (jumps_dec * -0.20)
                        mult_dec = 1.0 + returns_dec

                        dec_wealth = np.empty((len(valid_paths), decum_months))
                        dec_wealth[:, 0] = fv[i]  # Start at target FI
                        for m in range(1, decum_months):
                            dec_wealth[:, m] = dec_wealth[:, m - 1] * mult_dec[:, m] - withdraw_fire

                        survived = np.all(dec_wealth > 0, axis=1)
                        success_count = np.sum(survived)
                        prob_success[i] = success_count / len(valid_paths)
                    else:
                        prob_success[i] = 0.0

                # TOTAL FIRE
                if not valid_total:
                    if (
                        np.isnan(fv_total[i])
                        or np.isnan(pv[i])
                        or np.isnan(pmt_total[i])
                        or pmt_total[i] <= 0
                    ):
                        out_total_p90[i], out_total_p50[i], out_total_p10[i] = (
                            np.nan,
                            np.nan,
                            np.nan,
                        )
                        prob_success_total[i] = np.nan
                    else:
                        out_total_p90[i], out_total_p50[i], out_total_p10[i] = 0.0, 0.0, 0.0
                        prob_success_total[i] = 1.0
                else:
                    assert multipliers is not None
                    wealth_total = np.empty((iterations, max_months))
                    wealth_total[:, 0] = pv[i]
                    for m in range(1, max_months):
                        wealth_total[:, m] = (
                            wealth_total[:, m - 1] * multipliers[:, m] + pmt_total[i]
                        )

                    reached_total = wealth_total >= fv_total[i]
                    months_to_fire_total = np.argmax(reached_total, axis=1).astype(float)
                    never_reached_total = ~np.any(reached_total, axis=1)
                    months_to_fire_total[never_reached_total] = np.nan

                    out_total_p90[i] = (
                        float(np.percentile(months_to_fire_total[~never_reached_total], 90))
                        if np.any(~never_reached_total)
                        else np.nan
                    )
                    out_total_p50[i] = (
                        float(np.percentile(months_to_fire_total[~never_reached_total], 50))
                        if np.any(~never_reached_total)
                        else np.nan
                    )
                    out_total_p10[i] = (
                        float(np.percentile(months_to_fire_total[~never_reached_total], 10))
                        if np.any(~never_reached_total)
                        else np.nan
                    )

                    if np.any(~never_reached_total):
                        valid_p_t = np.where(~never_reached_total)[0]
                        hit_m_t = months_to_fire_total[~never_reached_total].astype(int)
                        nom_targets_total = fv_total[i] * cum_inf_multiplier[valid_p_t, hit_m_t]
                        out_total_nom_p50[i] = float(np.percentile(nom_targets_total, 50))
                    else:
                        out_total_nom_p50[i] = np.nan

                    success_count_total = 0
                    valid_paths_total = np.where(~never_reached_total)[0]
                    if len(valid_paths_total) > 0:
                        returns_dec_total = (
                            rng.standard_t(df=4, size=(len(valid_paths_total), decum_months))
                            * (vol_r / np.sqrt(2))
                            + mean_r
                        )
                        jumps_dec_total = rng.binomial(
                            1, 0.05 / 12.0, size=(len(valid_paths_total), decum_months)
                        )
                        returns_dec_total = returns_dec_total + (jumps_dec_total * -0.20)
                        mult_dec_total = 1.0 + returns_dec_total

                        dec_wealth_total = np.empty((len(valid_paths_total), decum_months))
                        dec_wealth_total[:, 0] = fv_total[i]
                        for m in range(1, decum_months):
                            dec_wealth_total[:, m] = (
                                dec_wealth_total[:, m - 1] * mult_dec_total[:, m] - withdraw_total
                            )

                        survived_total = np.all(dec_wealth_total > 0, axis=1)
                        success_count_total = np.sum(survived_total)
                        prob_success_total[i] = success_count_total / len(valid_paths_total)
                    else:
                        prob_success_total[i] = 0.0

            return pl.Series(
                [
                    {
                        "Months_To_FI_Conservative_P90": p90,
                        "Months_To_FI_Base_P50": p50,
                        "Months_To_FI_Aggressive_P10": p10,
                        "Months_To_FI_Total_Conservative_P90": tp90,
                        "Months_To_FI_Total_Base_P50": tp50,
                        "Months_To_FI_Total_Aggressive_P10": tp10,
                        "Probability_Of_Success_Pct": ps * 100 if not np.isnan(ps) else None,
                        "Probability_Of_Success_Total_Pct": pst * 100
                        if not np.isnan(pst)
                        else None,
                        "Target_FI_Future_Nominal_P50": np.nan
                        if np.isnan(nom) or nom == 0
                        else nom,
                        "Target_FI_Total_Future_Nominal_P50": np.nan
                        if np.isnan(tnom) or tnom == 0
                        else tnom,
                    }
                    for p90, p50, p10, tp90, tp50, tp10, ps, pst, nom, tnom in zip(
                        out_p90,
                        out_p50,
                        out_p10,
                        out_total_p90,
                        out_total_p50,
                        out_total_p10,
                        prob_success,
                        prob_success_total,
                        out_nom_p50,
                        out_total_nom_p50,
                        strict=True,
                    )
                ]
            )

        lf_fire_forecast = (
            lf_fire_forecast.with_columns(
                pl.struct(
                    [
                        "Total_Net_Worth_Market",
                        "Trailing_6M_Avg_Savings",
                        "Target_FI_Today",
                        "Trailing_6M_Avg_Total_Savings",
                        "Target_FI_Today_Total",
                        "YEAR_MONTH",
                        "INFLATION_YOY_PCT",
                    ]
                )
                .map_batches(
                    monte_carlo_fire_batch,
                    return_dtype=pl.Struct(
                        [
                            pl.Field("Months_To_FI_Conservative_P90", pl.Float64),
                            pl.Field("Months_To_FI_Base_P50", pl.Float64),
                            pl.Field("Months_To_FI_Aggressive_P10", pl.Float64),
                            pl.Field("Months_To_FI_Total_Conservative_P90", pl.Float64),
                            pl.Field("Months_To_FI_Total_Base_P50", pl.Float64),
                            pl.Field("Months_To_FI_Total_Aggressive_P10", pl.Float64),
                            pl.Field("Probability_Of_Success_Pct", pl.Float64),
                            pl.Field("Probability_Of_Success_Total_Pct", pl.Float64),
                            pl.Field("Target_FI_Future_Nominal_P50", pl.Float64),
                            pl.Field("Target_FI_Total_Future_Nominal_P50", pl.Float64),
                        ]
                    ),
                )
                .alias("mc_results")
            )
            .unnest("mc_results")
            .with_columns(
                # Legacy linear for reference
                pl.when(
                    (pl.col("Trailing_6M_Avg_Savings") > 0)
                    & (pl.col("Target_FI_Today") > pl.col("Total_Net_Worth_Market"))
                )
                .then(
                    (pl.col("Target_FI_Today") - pl.col("Total_Net_Worth_Market"))
                    / pl.col("Trailing_6M_Avg_Savings")
                )
                .otherwise(0.0)
                .alias("Estimated_Months_To_FI_Linear"),
                pl.when(
                    (pl.col("Trailing_6M_Avg_Total_Savings") > 0)
                    & (pl.col("Target_FI_Today_Total") > pl.col("Total_Net_Worth_Market"))
                )
                .then(
                    (pl.col("Target_FI_Today_Total") - pl.col("Total_Net_Worth_Market"))
                    / pl.col("Trailing_6M_Avg_Total_Savings")
                )
                .otherwise(0.0)
                .alias("Estimated_Months_To_FI_Total_Linear"),
                pl.lit(cma_real_return).alias("Real_Return_Assumed_Pct"),
                pl.max_horizontal(
                    0.0, pl.col("Target_FI_Today") - pl.col("Total_Net_Worth_Market")
                ).alias("FI_Gap"),
                pl.max_horizontal(
                    0.0, pl.col("Target_FI_Today_Total") - pl.col("Total_Net_Worth_Market")
                ).alias("FI_Gap_Total"),
                (pl.col("Target_FI_Today") / ((1.0 + coast_real_return) ** coast_years)).alias(
                    "Coast_FI_Today"
                ),
                (
                    pl.col("Target_FI_Today_Total") / ((1.0 + coast_real_return) ** coast_years)
                ).alias("Coast_FI_Today_Total"),
                (pl.col("Target_FI_Today") * lean_ratio).alias("Lean_FI_Today"),
                (pl.col("Target_FI_Today_Total") * lean_ratio).alias("Lean_FI_Today_Total"),
                pl.when(pl.col("Total_Net_Worth_Market") > 0)
                .then(pl.col("Trailing_12M_Spend") / pl.col("Total_Net_Worth_Market"))
                .otherwise(0.0)
                .alias("Withdrawal_Rate_If_Retired_Now"),
                pl.when(pl.col("Total_Net_Worth_Market") > 0)
                .then(pl.col("Trailing_12M_Total_Spend") / pl.col("Total_Net_Worth_Market"))
                .otherwise(0.0)
                .alias("Withdrawal_Rate_If_Retired_Now_Total"),
            )
            .with_columns(
                (pl.col("FI_Gap") - pl.col("FI_Gap").shift(1)).alias("FI_Gap_Monthly_Trend"),
                (pl.col("FI_Gap_Total") - pl.col("FI_Gap_Total").shift(1)).alias(
                    "FI_Gap_Total_Monthly_Trend"
                ),
                pl.when(
                    (pl.col("Months_To_FI_Base_P50") > 0)
                    & pl.col("Months_To_FI_Base_P50").is_not_nan()
                    & pl.col("Months_To_FI_Base_P50").is_not_null()
                    & (pl.col("Total_Income") > 0)
                )
                .then((pl.col("FI_Gap") / pl.col("Months_To_FI_Base_P50")) / pl.col("Total_Income"))
                .otherwise(0.0)
                .alias("Savings_Rate_Required"),
                pl.when(
                    (pl.col("Months_To_FI_Total_Base_P50") > 0)
                    & pl.col("Months_To_FI_Total_Base_P50").is_not_nan()
                    & pl.col("Months_To_FI_Total_Base_P50").is_not_null()
                    & (pl.col("Total_Income") > 0)
                )
                .then(
                    (pl.col("FI_Gap_Total") / pl.col("Months_To_FI_Total_Base_P50"))
                    / pl.col("Total_Income")
                )
                .otherwise(0.0)
                .alias("Savings_Rate_Required_Total"),
                (pl.col("Months_To_FI_Base_P50") / 12.0).alias("Years_To_FI_P50"),
                (pl.col("Months_To_FI_Total_Base_P50") / 12.0).alias("Years_To_FI_Total_P50"),
                pl.col("Target_FI_Future_Nominal_P50")
                .fill_null(pl.col("Target_FI_Today"))
                .alias("Target_FI_Future_Nominal"),
                pl.col("Target_FI_Total_Future_Nominal_P50")
                .fill_null(pl.col("Target_FI_Today_Total"))
                .alias("Target_FI_Total_Future_Nominal"),
                pl.when(
                    pl.col("Months_To_FI_Base_P50").is_not_nan()
                    & pl.col("Months_To_FI_Base_P50").is_not_null()
                )
                .then(
                    pl.col("MONTH_START_DATE").dt.offset_by(
                        pl.format(
                            "{}mo", pl.col("Months_To_FI_Base_P50").cast(pl.Int64, strict=False)
                        )
                    )
                )
                .otherwise(pl.lit(None).cast(pl.Date))
                .alias("Projected_FI_Date_P50"),
                pl.when(
                    pl.col("Months_To_FI_Total_Base_P50").is_not_nan()
                    & pl.col("Months_To_FI_Total_Base_P50").is_not_null()
                )
                .then(
                    pl.col("MONTH_START_DATE").dt.offset_by(
                        pl.format(
                            "{}mo",
                            pl.col("Months_To_FI_Total_Base_P50").cast(pl.Int64, strict=False),
                        )
                    )
                )
                .otherwise(pl.lit(None).cast(pl.Date))
                .alias("Projected_FI_Date_Total_P50"),
                pl.col("Current_FI_Coverage_Pct").alias("NW_Percentile_of_FI"),
                pl.col("Current_FI_Coverage_Pct_Total").alias("NW_Percentile_of_FI_Total"),
            )
            .join(
                self.lf_risk.select(["MONTH_START_DATE", "Drawdown_Pct"]),
                on="MONTH_START_DATE",
                how="left",
            )
            .with_columns(
                (
                    pl.col("Total_Net_Worth_Market") - pl.col("Total_Net_Worth_Market").shift(1)
                ).alias("Wealth_Velocity"),
                pl.col("Drawdown_Pct").fill_null(0.0),
            )
            .with_columns(
                (pl.col("Wealth_Velocity") - pl.col("Wealth_Velocity").shift(1)).alias(
                    "Wealth_Acceleration"
                ),
                pl.when(pl.col("Drawdown_Pct") < -0.20)
                .then(0.05)
                .when(pl.col("Drawdown_Pct") < -0.10)
                .then(0.045)
                .otherwise(0.04)
                .alias("CAPE_Adjusted_SWR"),
                ((pl.col("Total_Income") * 12.0) * (1 - (1.05) ** -30) / 0.05).alias(
                    "Human_Capital_Value"
                ),
            )
            .with_columns(
                (pl.col("Total_Net_Worth_Market") * pl.col("CAPE_Adjusted_SWR") * 1.2 / 12.0).alias(
                    "Guyton_Klinger_Ceiling"
                ),
                (pl.col("Total_Net_Worth_Market") * pl.col("CAPE_Adjusted_SWR") * 0.8 / 12.0).alias(
                    "Guyton_Klinger_Floor"
                ),
                pl.when(pl.col("Total_Net_Worth_Market") > 0)
                .then(pl.col("Human_Capital_Value") / pl.col("Total_Net_Worth_Market"))
                .otherwise(None)
                .alias("Human_to_Financial_Capital_Ratio"),
            )
            .select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "YEAR_MONTH",
                    "Total_Net_Worth",
                    "Total_Net_Worth_Market",
                    "Trailing_6M_Avg_Spend",
                    "Trailing_6M_Avg_Savings",
                    "INFLATION_YOY_PCT",
                    "Real_Return_Assumed_Pct",
                    "Target_FI_Today",
                    "Coast_FI_Today",
                    "Lean_FI_Today",
                    "Target_FI_Future_Nominal",
                    "Current_FI_Coverage_Pct",
                    "NW_Percentile_of_FI",
                    "FI_Gap",
                    "FI_Gap_Monthly_Trend",
                    "Estimated_Months_To_FI_Linear",
                    "Months_To_FI_Conservative_P90",
                    "Months_To_FI_Base_P50",
                    "Months_To_FI_Aggressive_P10",
                    "Probability_Of_Success_Pct",
                    "Years_To_FI_P50",
                    "Projected_FI_Date_P50",
                    "Runway_Months",
                    "Withdrawal_Rate_If_Retired_Now",
                    "Savings_Rate_Required",
                    "Trailing_6M_Avg_Total_Spend",
                    "Trailing_6M_Avg_Total_Savings",
                    "Target_FI_Today_Total",
                    "Coast_FI_Today_Total",
                    "Lean_FI_Today_Total",
                    "Target_FI_Total_Future_Nominal",
                    "Current_FI_Coverage_Pct_Total",
                    "NW_Percentile_of_FI_Total",
                    "FI_Gap_Total",
                    "FI_Gap_Total_Monthly_Trend",
                    "Estimated_Months_To_FI_Total_Linear",
                    "Months_To_FI_Total_Conservative_P90",
                    "Months_To_FI_Total_Base_P50",
                    "Months_To_FI_Total_Aggressive_P10",
                    "Probability_Of_Success_Total_Pct",
                    "Years_To_FI_Total_P50",
                    "Projected_FI_Date_Total_P50",
                    "Runway_Months_Total",
                    "Withdrawal_Rate_If_Retired_Now_Total",
                    "Savings_Rate_Required_Total",
                    "Wealth_Velocity",
                    "Wealth_Acceleration",
                    "CAPE_Adjusted_SWR",
                    "Guyton_Klinger_Floor",
                    "Guyton_Klinger_Ceiling",
                    "Human_Capital_Value",
                    "Human_to_Financial_Capital_Ratio",
                ]
            )
        )
        return lf_fire_forecast
