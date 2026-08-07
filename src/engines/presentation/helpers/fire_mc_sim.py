import numpy as np
import polars as pl
from numba import njit


@njit
def _run_mc_simulations_numba(
    pv_arr,
    pmt_arr,
    fv_arr,
    burn_arr,
    inf_rates,
    seed_ints,
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
        np.random.seed(seed_ints[i])

        pv = pv_arr[i]
        pmt = pmt_arr[i]
        fv = fv_arr[i]
        burn_rate = burn_arr[i]
        inf_base = inf_rates[i]
        if np.isnan(inf_base):
            inf_base = 0.04

        current_age_m = current_age_months_arr[i]

        if np.isnan(fv) or np.isnan(pv) or np.isnan(pmt):
            prob_success[i] = np.nan
            continue

        valid = fv > pv

        if not valid:
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
            runway_m = max_runway_possible

            if pv > 0 and burn_rate > 0:
                for d in range(1, max_runway_possible + 1):
                    # Market Returns & Jumps (using real returns, no inflation needed on withdrawals)
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


def get_monte_carlo_fire_batch(rules, cma_real_return, cma_fat_tail):
    """
    Factory that returns the map_batches function for Polars.
    """

    def monte_carlo_fire_batch(s: pl.Series, **kwargs) -> pl.Series:
        df = s.struct.unnest()
        pv = df["Total_Net_Worth_Market_Af_Tax"].to_numpy().astype(float)
        pmt = df["Trailing_6M_Avg_Savings"].to_numpy().astype(float)
        fv = df["Target_FI_Today"].to_numpy().astype(float)
        burn_core = df["Trailing_6M_Avg_Spend"].to_numpy().astype(float)

        pmt_total = df["Trailing_6M_Avg_Total_Savings"].to_numpy().astype(float)
        fv_total = df["Target_FI_Today_Total"].to_numpy().astype(float)
        inf_rates = df["INFLATION_YOY_PCT"].to_numpy().astype(float)
        seed_ints = df["Seed_Int"].to_numpy().astype(np.int32)
        burn_total = df["Trailing_6M_Avg_Total_Spend"].to_numpy().astype(float)

        swr = rules.assumptions.fire.swr_multiplier
        mc_iterations = rules.assumptions.monte_carlo.iterations
        mc_max_months = rules.assumptions.monte_carlo.max_months
        mc_volatility = rules.assumptions.monte_carlo.annual_volatility

        iterations = mc_iterations
        max_months = mc_max_months

        # Pre-calculated in Polars
        current_age_months = df["Age_Months"].to_numpy().astype(np.int32)

        # Establish total target lifespan in months
        target_age = rules.assumptions.monte_carlo.desired_target_age
        target_lifespan_months = int(target_age * 12)

        # Volatility and Return Setup
        vol_r = (mc_volatility * cma_fat_tail) / np.sqrt(12)
        tax_drag = 0.005
        jump_prob_annual = 0.05
        jump_magnitude = -0.20

        # Merton drift compensator to ensure the CAGR hits the target despite crashes (geometric conversion)
        mean_r = (1.0 + cma_real_return - tax_drag - (jump_prob_annual * jump_magnitude)) ** (
            1.0 / 12.0
        ) - 1.0

        # Execute Core FIRE Vector
        out_p90, out_p50, out_p10, prob_success, out_nom_p50, run_p90, run_p50, run_p10 = (
            _run_mc_simulations_numba(
                pv,
                pmt,
                fv,
                burn_core,
                inf_rates,
                seed_ints,
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
            seed_ints,
            iterations,
            max_months,
            vol_r,
            mean_r,
            swr,
            current_age_months,
            target_lifespan_months,
        )

        df_out = pl.DataFrame(
            {
                "Months_To_FI_Conservative_P90": out_p90,
                "Months_To_FI_Base_P50": out_p50,
                "Months_To_FI_Aggressive_P10": out_p10,
                "Months_To_FI_Total_Conservative_P90": out_total_p90,
                "Months_To_FI_Total_Base_P50": out_total_p50,
                "Months_To_FI_Total_Aggressive_P10": out_total_p10,
                "Probability_Of_Success_Pct": prob_success * 100.0,
                "Probability_Of_Success_Total_Pct": prob_success_total * 100.0,
                "Target_FI_Future_Nominal_P50": np.where(
                    np.isnan(out_nom_p50) | (out_nom_p50 == 0), np.nan, out_nom_p50
                ),
                "Target_FI_Total_Future_Nominal_P50": np.where(
                    np.isnan(out_total_nom_p50) | (out_total_nom_p50 == 0),
                    np.nan,
                    out_total_nom_p50,
                ),
                "Runway_Months_Stressed_P10": run_p10,
                "Runway_Months_Base_P50": run_p50,
                "Runway_Months_Total_Stressed_P10": run_t_p10,
                "Runway_Months_Total_Base_P50": run_t_p50,
            }
        )
        return df_out.to_struct("")

    return monte_carlo_fire_batch
