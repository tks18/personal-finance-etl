from collections.abc import Mapping
from typing import Any

import numpy as np
import polars as pl
from numba import njit


class FireForecastingBuilder:
    """
    Constructs the FIRE & Wealth Forecasting presentation model.
    """

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: dict[str, Any],
        lf_risk: pl.LazyFrame,
        rules,
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
                    "Liquid_Assets_Market",
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
        tax_rate = self.rules.assumptions.tax.rates.equity_ltcg

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
                    .alias("Total_Net_Worth_Market_Af_Tax")
                )
                .drop(["Port_Market_Value", "Port_Book_Value"])
            )

        swr = self.rules.assumptions.fire.swr_multiplier
        coast_real_return = self.rules.assumptions.fire.coast_fi_real_return
        coast_years = self.rules.assumptions.fire.coast_fi_years
        lean_ratio = self.rules.assumptions.fire.lean_fi_ratio
        mc_iterations = self.rules.assumptions.monte_carlo.iterations
        mc_max_months = self.rules.assumptions.monte_carlo.max_months
        mc_volatility = self.rules.assumptions.monte_carlo.annual_volatility

        cma_real_return = self.rules.assumptions.cma.expected_real_return
        cma_fat_tail = self.rules.assumptions.cma.fat_tail_multiplier
        lf_fire_forecast = (
            lf_fire_base.sort("MONTH_START_DATE")
            .with_columns(
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
                .then(pl.col("Total_Net_Worth_Market_Af_Tax") / pl.col("Target_FI_Today"))
                .otherwise(0.0)
                .alias("Current_FI_Coverage_Pct"),
                pl.when(pl.col("Trailing_3M_Avg_Spend") > 0)
                .then(pl.col("Total_Net_Worth_Market_Af_Tax") / pl.col("Trailing_3M_Avg_Spend"))
                .otherwise(0.0)
                .alias("Runway_Months_Linear"),
                pl.when(pl.col("Target_FI_Today_Total") > 0)
                .then(pl.col("Total_Net_Worth_Market_Af_Tax") / pl.col("Target_FI_Today_Total"))
                .otherwise(0.0)
                .alias("Current_FI_Coverage_Pct_Total"),
                pl.when(pl.col("Trailing_3M_Avg_Total_Spend") > 0)
                .then(
                    pl.col("Total_Net_Worth_Market_Af_Tax") / pl.col("Trailing_3M_Avg_Total_Spend")
                )
                .otherwise(0.0)
                .alias("Runway_Months_Total_Linear"),
            )
        )

        @njit
        def _run_mc_simulations_numba(
            pv_arr,
            pmt_arr,
            fv_arr,
            burn_arr,
            inf_rates,
            year_month_ints,
            iterations,
            max_months,
            vol_r,
            mean_r,
            swr,
            current_age_months_arr,
            target_lifespan_months,
        ):
            n_rows = len(pv_arr)
            out_p90 = np.full(n_rows, np.nan)
            out_p50 = np.full(n_rows, np.nan)
            out_p10 = np.full(n_rows, np.nan)
            out_nom_p50 = np.full(n_rows, np.nan)
            prob_success = np.zeros(n_rows)

            # Variables for Runway Months
            out_runway_p90, out_runway_p50, out_runway_p10 = (
                np.full(n_rows, np.nan),
                np.full(n_rows, np.nan),
                np.full(n_rows, np.nan),
            )

            # Simulation Parameters
            theta = 0.1  # Speed of mean reversion for inflation
            sigma_inf = 0.015 / np.sqrt(12.0)
            monthly_jump_prob = 0.05 / 12.0

            for i in range(n_rows):
                np.random.seed(year_month_ints[i])

                pv = pv_arr[i]
                pmt = pmt_arr[i]
                fv = fv_arr[i]
                burn_rate = burn_arr[i]
                inf_base = inf_rates[i]
                if np.isnan(inf_base):
                    inf_base = 0.04

                current_age_m = current_age_months_arr[i]

                valid = (fv > pv) and (pmt > 0)

                if not valid:
                    if np.isnan(fv) or np.isnan(pv) or np.isnan(pmt) or pmt <= 0:
                        prob_success[i] = np.nan
                    else:
                        out_p90[i], out_p50[i], out_p10[i] = 0.0, 0.0, 0.0
                        prob_success[i] = 1.0  # Already FI
                    continue

                months_to_fire = np.full(iterations, np.nan)
                nom_targets = np.full(iterations, np.nan)
                runway_months = np.zeros(iterations)

                survived_count = 0
                valid_decum = 0
                max_runway_possible = target_lifespan_months - current_age_m

                for j in range(iterations):
                    wealth = pv
                    hit_month = -1
                    inf_path = inf_base
                    cum_inf = 1.0

                    # --- Accumulation Phase ---
                    for m in range(1, max_months + 1):
                        # OU Stochastic Inflation
                        shock = np.random.normal(0.0, sigma_inf)
                        inf_path = inf_path + theta * (inf_base - inf_path) + shock
                        # Sanity bounds for macro inflation
                        if inf_path < 0.0:
                            inf_path = 0.0
                        elif inf_path > 0.15:
                            inf_path = 0.15

                        cum_inf *= 1.0 + (inf_path / 12.0)

                        # Returns & Jump Diffusion
                        ret = np.random.standard_t(4) * (vol_r / np.sqrt(2.0)) + mean_r
                        jump = -0.20 if np.random.random() < monthly_jump_prob else 0.0

                        wealth = wealth * (1.0 + ret + jump) + pmt

                        if wealth >= fv:
                            hit_month = m
                            break

                    # --- Decumulation Phase ---
                    if hit_month != -1:
                        months_to_fire[j] = hit_month
                        nom_targets[j] = fv * cum_inf
                        valid_decum += 1

                        # Dynamic lifespan check
                        months_left = target_lifespan_months - (current_age_m + hit_month)

                        if months_left > 0:
                            dec_wealth = wealth  # Start with exact overshoot wealth
                            current_withdraw = fv / swr / 12.0
                            initial_rate = 1.0 / swr if swr > 0 else 0.04

                            survived = True
                            for d in range(1, months_left + 1):
                                # Guyton-Klinger Guardrails applied annually
                                if d % 12 == 0:
                                    current_rate = (current_withdraw * 12.0) / max(dec_wealth, 1.0)
                                    if current_rate > (initial_rate * 1.2):
                                        current_withdraw *= 0.90
                                    elif current_rate < (initial_rate * 0.8):
                                        current_withdraw *= 1.10

                                ret = np.random.standard_t(4) * (vol_r / np.sqrt(2.0)) + mean_r
                                jump = -0.20 if np.random.random() < monthly_jump_prob else 0.0

                                dec_wealth = dec_wealth * (1.0 + ret + jump) - current_withdraw
                                if dec_wealth <= 0.0:
                                    survived = False
                                    break

                            if survived:
                                survived_count += 1
                        else:
                            # Achieved FI after or exactly at target age, technically successful
                            survived_count += 1
                    r_wealth = pv
                    r_withdraw = burn_rate
                    r_inf_path = inf_base
                    runway_m = max_runway_possible

                    if pv > 0 and burn_rate > 0:
                        for d in range(1, max_runway_possible + 1):
                            # Inflate current lifestyle expenses
                            shock = np.random.normal(0.0, sigma_inf)
                            r_inf_path = r_inf_path + theta * (inf_base - r_inf_path) + shock
                            if r_inf_path < 0.0:
                                r_inf_path = 0.0
                            elif r_inf_path > 0.15:
                                r_inf_path = 0.15

                            r_withdraw *= 1.0 + (r_inf_path / 12.0)

                            # Market Returns & Jumps
                            ret = np.random.standard_t(4) * (vol_r / np.sqrt(2.0)) + mean_r
                            jump = -0.20 if np.random.random() < monthly_jump_prob else 0.0

                            r_wealth = r_wealth * (1.0 + ret + jump) - r_withdraw

                            if r_wealth <= 0.0:
                                runway_m = d
                                break
                    else:
                        runway_m = 0.0

                    runway_months[j] = runway_m

                # --- Aggregation ---
                # Filter NaNs for valid percentile calculation
                v_months = months_to_fire[~np.isnan(months_to_fire)]
                v_noms = nom_targets[~np.isnan(nom_targets)]

                if len(v_months) > 0:
                    out_p90[i] = np.percentile(v_months, 90)
                    out_p50[i] = np.percentile(v_months, 50)
                    out_p10[i] = np.percentile(v_months, 10)
                    out_nom_p50[i] = np.percentile(v_noms, 50)
                    out_runway_p90[i] = np.percentile(runway_months, 90)  # Favorable market
                    out_runway_p50[i] = np.percentile(runway_months, 50)  # Base market
                    out_runway_p10[i] = np.percentile(
                        runway_months, 10
                    )  # 10th Percentile: Crash scenario (Your true safety net)

                if valid_decum > 0:
                    prob_success[i] = survived_count / valid_decum
                else:
                    prob_success[i] = 0.0

            return (
                out_p90,
                out_p50,
                out_p10,
                prob_success,
                out_nom_p50,
                out_runway_p90,
                out_runway_p50,
                out_runway_p10,
            )

        # Probabilistic Monte Carlo Simulation for FIRE using map_batches
        def monte_carlo_fire_batch(s: pl.Series, **kwargs) -> pl.Series:
            df = s.struct.unnest()
            pv = df["Total_Net_Worth_Market_Af_Tax"].to_numpy().astype(float)
            pmt = df["Trailing_6M_Avg_Savings"].to_numpy().astype(float)
            fv = df["Target_FI_Today"].to_numpy().astype(float)
            burn_core = df["Trailing_6M_Avg_Spend"].to_numpy().astype(float)

            pmt_total = df["Trailing_6M_Avg_Total_Savings"].to_numpy().astype(float)
            fv_total = df["Target_FI_Today_Total"].to_numpy().astype(float)
            inf_rates = df["INFLATION_YOY_PCT"].to_numpy().astype(float)
            year_month = df["YEAR_MONTH"].to_list()
            burn_total = df["Trailing_6M_Avg_Total_Spend"].to_numpy().astype(float)

            iterations = mc_iterations
            max_months = mc_max_months

            # Numba requires concrete dtypes. Convert year_months to reproducible int seeds (e.g., 202608)
            year_month_ints = np.array(
                [int(ym.replace("-", "")) for ym in year_month], dtype=np.int32
            )

            # Establish target age and dob
            dob_str = self.rules.assumptions.monte_carlo.date_of_birth
            dob_year, dob_month, _ = map(int, dob_str.split("-"))

            # Dynamically calculate exact age in months at every row utilizing vectorization
            current_age_months = np.array(
                [(int(ym[:4]) - dob_year) * 12 + (int(ym[5:7]) - dob_month) for ym in year_month],
                dtype=np.int32,
            )

            # Establish total target lifespan in months
            target_age = self.rules.assumptions.monte_carlo.desired_target_age
            target_lifespan_months = int(target_age * 12)

            # Volatility and Return Setup
            vol_r = (mc_volatility * cma_fat_tail) / np.sqrt(12)
            tax_drag = 0.005
            jump_prob_annual = 0.05
            jump_magnitude = -0.20

            # Merton drift compensator to ensure the CAGR hits the target despite crashes
            mean_r = (cma_real_return - tax_drag - (jump_prob_annual * jump_magnitude)) / 12.0

            # Execute Core FIRE Vector
            out_p90, out_p50, out_p10, prob_success, out_nom_p50, run_p90, run_p50, run_p10 = (
                _run_mc_simulations_numba(
                    pv,
                    pmt,
                    fv,
                    burn_core,
                    inf_rates,
                    year_month_ints,
                    iterations,
                    max_months,
                    vol_r,
                    mean_r,
                    swr,
                    current_age_months,
                    target_lifespan_months,
                )
            )

            # Execute Total FIRE Vector
            (
                out_total_p90,
                out_total_p50,
                out_total_p10,
                prob_success_total,
                out_total_nom_p50,
                run_t_p90,
                run_t_p50,
                run_t_p10,
            ) = _run_mc_simulations_numba(
                pv,
                pmt_total,
                fv_total,
                burn_total,
                inf_rates,
                year_month_ints,
                iterations,
                max_months,
                vol_r,
                mean_r,
                swr,
                current_age_months,
                target_lifespan_months,
            )

            return pl.Series(
                [
                    {
                        "Months_To_FI_Conservative_P90": p90,
                        "Months_To_FI_Base_P50": p50,
                        "Months_To_FI_Aggressive_P10": p10,
                        "Months_To_FI_Total_Conservative_P90": tp90,
                        "Months_To_FI_Total_Base_P50": tp50,
                        "Months_To_FI_Total_Aggressive_P10": tp10,
                        "Runway_Months_Stressed_P10": r_10,
                        "Runway_Months_Base_P50": r_50,
                        "Runway_Months_Total_Stressed_P10": rt_10,
                        "Runway_Months_Total_Base_P50": rt_50,
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
                    for p90, p50, p10, tp90, tp50, tp10, ps, pst, nom, tnom, r_10, r_50, rt_10, rt_50 in zip(
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
                        run_p10,
                        run_p50,
                        run_t_p10,
                        run_t_p50,
                        strict=True,
                    )
                ]
            )

        lf_fire_forecast = (
            lf_fire_forecast.with_columns(
                pl.struct(
                    [
                        "Total_Net_Worth_Market_Af_Tax",
                        "Trailing_6M_Avg_Savings",
                        "Trailing_6M_Avg_Spend",
                        "Trailing_6M_Avg_Total_Spend",
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
                            pl.Field("Runway_Months_Stressed_P10", pl.Float64),
                            pl.Field("Runway_Months_Base_P50", pl.Float64),
                            pl.Field("Runway_Months_Total_Stressed_P10", pl.Float64),
                            pl.Field("Runway_Months_Total_Base_P50", pl.Float64),
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
                    & (pl.col("Target_FI_Today") > pl.col("Total_Net_Worth_Market_Af_Tax"))
                )
                .then(
                    (pl.col("Target_FI_Today") - pl.col("Total_Net_Worth_Market_Af_Tax"))
                    / pl.col("Trailing_6M_Avg_Savings")
                )
                .otherwise(0.0)
                .alias("Estimated_Months_To_FI_Linear"),
                pl.when(
                    (pl.col("Trailing_6M_Avg_Total_Savings") > 0)
                    & (pl.col("Target_FI_Today_Total") > pl.col("Total_Net_Worth_Market_Af_Tax"))
                )
                .then(
                    (pl.col("Target_FI_Today_Total") - pl.col("Total_Net_Worth_Market_Af_Tax"))
                    / pl.col("Trailing_6M_Avg_Total_Savings")
                )
                .otherwise(0.0)
                .alias("Estimated_Months_To_FI_Total_Linear"),
                pl.lit(cma_real_return).alias("Real_Return_Assumed_Pct"),
                pl.max_horizontal(
                    0.0, pl.col("Target_FI_Today") - pl.col("Total_Net_Worth_Market_Af_Tax")
                ).alias("FI_Gap"),
                pl.max_horizontal(
                    0.0, pl.col("Target_FI_Today_Total") - pl.col("Total_Net_Worth_Market_Af_Tax")
                ).alias("FI_Gap_Total"),
                (pl.col("Target_FI_Today") / ((1.0 + coast_real_return) ** coast_years)).alias(
                    "Coast_FI_Today"
                ),
                (
                    pl.col("Target_FI_Today_Total") / ((1.0 + coast_real_return) ** coast_years)
                ).alias("Coast_FI_Today_Total"),
                (pl.col("Target_FI_Today") * lean_ratio).alias("Lean_FI_Today"),
                (pl.col("Target_FI_Today_Total") * lean_ratio).alias("Lean_FI_Today_Total"),
                pl.when(pl.col("Total_Net_Worth_Market_Af_Tax") > 0)
                .then(pl.col("Trailing_12M_Spend") / pl.col("Total_Net_Worth_Market_Af_Tax"))
                .otherwise(0.0)
                .alias("Withdrawal_Rate_If_Retired_Now"),
                pl.when(pl.col("Total_Net_Worth_Market_Af_Tax") > 0)
                .then(pl.col("Trailing_12M_Total_Spend") / pl.col("Total_Net_Worth_Market_Af_Tax"))
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
            .sort("MONTH_START_DATE")
            .with_columns(
                (
                    pl.col("Total_Net_Worth_Market_Af_Tax")
                    - pl.col("Total_Net_Worth_Market_Af_Tax").shift(1)
                ).alias("Wealth_Velocity"),
                pl.col("Drawdown_Pct").fill_null(0.0),
            )
            .with_columns(
                (pl.col("Wealth_Velocity") - pl.col("Wealth_Velocity").shift(1)).alias(
                    "Wealth_Acceleration"
                ),
                pl.when(pl.col("Drawdown_Pct") < -0.20)
                .then(self.rules.assumptions.fire.cape_swr_floor)
                .when(pl.col("Drawdown_Pct") < -0.10)
                .then(self.rules.assumptions.fire.cape_swr_ceiling)
                .otherwise(self.rules.assumptions.fire.cape_swr_base)
                .alias("CAPE_Adjusted_SWR"),
                pl.when(
                    (
                        self.rules.assumptions.fire.human_capital_max_age
                        - (
                            pl.col("MONTH_START_DATE").dt.year()
                            - int(self.rules.assumptions.monte_carlo.date_of_birth[:4])
                        )
                    )
                    > 0
                )
                .then(
                    (
                        (pl.col("Total_Income") * 12.0)
                        * (
                            1
                            - (1.0 + self.rules.assumptions.fire.human_capital_discount_rate)
                            ** -(
                                self.rules.assumptions.fire.human_capital_max_age
                                - (
                                    pl.col("MONTH_START_DATE").dt.year()
                                    - int(self.rules.assumptions.monte_carlo.date_of_birth[:4])
                                )
                            )
                        )
                    )
                    / self.rules.assumptions.fire.human_capital_discount_rate
                )
                .otherwise(0.0)
                .alias("Human_Capital_Value"),
            )
            .with_columns(
                (
                    pl.col("Total_Net_Worth_Market_Af_Tax")
                    * pl.col("CAPE_Adjusted_SWR")
                    * 1.2
                    / 12.0
                ).alias("Guyton_Klinger_Ceiling"),
                (
                    pl.col("Total_Net_Worth_Market_Af_Tax")
                    * pl.col("CAPE_Adjusted_SWR")
                    * 0.8
                    / 12.0
                ).alias("Guyton_Klinger_Floor"),
                pl.when(pl.col("Total_Net_Worth_Market_Af_Tax") > 0)
                .then(pl.col("Human_Capital_Value") / pl.col("Total_Net_Worth_Market_Af_Tax"))
                .otherwise(None)
                .alias("Human_to_Financial_Capital_Ratio"),
            )
            .with_columns(
                pl.when(pl.col("Trailing_6M_Avg_Total_Savings") > 0)
                .then(pl.col("Wealth_Velocity") / pl.col("Trailing_6M_Avg_Total_Savings"))
                .otherwise(0.0)
                .alias("Velocity_vs_Savings_Ratio"),
                (
                    pl.col("Estimated_Months_To_FI_Linear")
                    - (pl.col("Estimated_Months_To_FI_Linear").shift(1) - 1.0)
                ).alias("Model_Error_Months_To_FI"),
                pl.when(
                    (
                        pl.col("Total_Net_Worth_Market").shift(1)
                        - pl.col("Total_Net_Worth_Market_Af_Tax").shift(1)
                    )
                    > 0
                )
                .then(
                    (
                        (pl.col("Total_Net_Worth_Market") - pl.col("Total_Net_Worth_Market_Af_Tax"))
                        - (
                            pl.col("Total_Net_Worth_Market").shift(1)
                            - pl.col("Total_Net_Worth_Market_Af_Tax").shift(1)
                        )
                    )
                    / (
                        pl.col("Total_Net_Worth_Market").shift(1)
                        - pl.col("Total_Net_Worth_Market_Af_Tax").shift(1)
                    )
                )
                .otherwise(0.0)
                .alias("Net_Worth_Post_Tax_Delta_Pct"),
            )
            .select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "YEAR_MONTH",
                    "Total_Income",
                    "Total_Core_Expense",
                    "Total_Expense",
                    "Net_Savings",
                    "Net_Savings_Total",
                    "Total_Net_Worth",
                    "Total_Net_Worth_Market",
                    "Total_Net_Worth_Market_Af_Tax",
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
                    "Runway_Months_Linear",
                    "Runway_Months_Stressed_P10",
                    "Runway_Months_Base_P50",
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
                    "Runway_Months_Total_Linear",
                    "Runway_Months_Total_Stressed_P10",
                    "Runway_Months_Total_Base_P50",
                    "Withdrawal_Rate_If_Retired_Now_Total",
                    "Savings_Rate_Required_Total",
                    "Wealth_Velocity",
                    "Wealth_Acceleration",
                    "CAPE_Adjusted_SWR",
                    "Velocity_vs_Savings_Ratio",
                    "Model_Error_Months_To_FI",
                    "Net_Worth_Post_Tax_Delta_Pct",
                    "Guyton_Klinger_Floor",
                    "Guyton_Klinger_Ceiling",
                    "Human_Capital_Value",
                    "Human_to_Financial_Capital_Ratio",
                ]
            )
        )
        return lf_fire_forecast
