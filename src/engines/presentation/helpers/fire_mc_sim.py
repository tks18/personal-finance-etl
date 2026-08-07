import numpy as np
import polars as pl
from numba import njit, prange


@njit(fastmath=True, parallel=True, cache=True)
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
    tm_flat,
    state_bull_params,
    state_bear_params,
    state_stag_params,
    hc_shock_prob,
    hc_shock_min,
    hc_shock_max,
    gp_derisk_start,
    gp_rerisk_end,
    gp_base_eq,
    gp_target_eq,
    jump_prob_ann,
    jump_mag,
    gp_debt_ret,
    gp_debt_vol,
    gk_upper,
    gk_lower,
    gk_cut,
    gk_raise,
    inf_theta,
    inf_vol_ann,
    inf_max,
    sorr_months,
):
    n_rows = len(pv_arr)

    out_p90 = np.full(n_rows, np.nan)
    out_p50 = np.full(n_rows, np.nan)
    out_p10 = np.full(n_rows, np.nan)
    out_nom_p50 = np.full(n_rows, np.nan)
    prob_success = np.zeros(n_rows)

    out_runway_p90 = np.full(n_rows, np.nan)
    out_runway_p50 = np.full(n_rows, np.nan)
    out_runway_p10 = np.full(n_rows, np.nan)

    out_terminal_wealth_p50 = np.full(n_rows, np.nan)
    out_terminal_wealth_p10 = np.full(n_rows, np.nan)
    out_max_drawdown_p50 = np.full(n_rows, np.nan)
    out_lost_savings_ev = np.full(n_rows, np.nan)
    out_peak_inf_p50 = np.full(n_rows, np.nan)
    out_sorr_cagr_p10 = np.full(n_rows, np.nan)
    out_avg_swr_p50 = np.full(n_rows, np.nan)

    monthly_jump_prob = jump_prob_ann / 12.0
    theta = inf_theta
    sigma_inf = inf_vol_ann / np.sqrt(12.0)

    # Pre-pack state variables for Numba indexing [state][param]
    # param index: 0 = drift, 1 = vol, 2 = inf_target
    state_params = np.array(
        [
            [state_bull_params[0], state_bull_params[1], state_bull_params[2]],
            [state_bear_params[0], state_bear_params[1], state_bear_params[2]],
            [state_stag_params[0], state_stag_params[1], state_stag_params[2]],
        ]
    )

    for i in prange(n_rows):  # type: ignore
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

        if fv <= pv:
            # Already FI
            out_p90[i], out_p50[i], out_p10[i] = 0.0, 0.0, 0.0
            prob_success[i] = 1.0
            continue

        months_to_fire = np.full(iterations, np.nan)
        nom_targets = np.full(iterations, np.nan)
        runway_months = np.zeros(iterations)

        term_wealth = np.full(iterations, np.nan)
        max_dds = np.full(iterations, np.nan)
        lost_savings = np.zeros(iterations)
        peak_infs = np.full(iterations, np.nan)
        sorr_cagrs = np.full(iterations, np.nan)
        avg_swrs = np.full(iterations, np.nan)

        survived_count = 0
        valid_decum = 0
        max_runway_possible = target_lifespan_months - current_age_m

        # Estimate naive months to FI for glide path scaling
        # Assuming static base case for naive est
        naive_ret = mean_r
        naive_pmt = pmt
        est_m_fi = 0
        w = pv
        while w < fv and est_m_fi < max_months:
            w = w * (1.0 + naive_ret) + naive_pmt
            est_m_fi += 1

        for j in range(iterations):
            wealth = pv
            hit_month = -1
            inf_path = inf_base
            cum_inf = 1.0
            current_state = 0  # Start in Bull
            unemployment_months = 0

            peak_wealth = wealth
            max_dd = 0.0
            path_peak_inf = inf_path
            path_lost_savings = 0.0

            # --- Accumulation Phase ---
            for m in range(1, max_months + 1):
                # Markov State Transition
                u_trans = np.random.uniform(0.0, 1.0)
                # row corresponding to current_state
                p0 = tm_flat[current_state * 3 + 0]
                p1 = tm_flat[current_state * 3 + 1]
                # p2 is remainder

                if u_trans < p0:
                    current_state = 0
                elif u_trans < p0 + p1:
                    current_state = 1
                else:
                    current_state = 2

                # State params
                s_drift = state_params[current_state, 0] / 12.0  # simplified monthly
                s_vol = state_params[current_state, 1] / np.sqrt(12.0)
                s_inf_target = state_params[current_state, 2]

                # Dynamic Glide Path (Equity Weight)
                t_fi = est_m_fi - m
                eq_w = gp_base_eq
                if t_fi <= gp_derisk_start and t_fi >= 0:
                    # Linearly scale down to gp_target_eq
                    # fraction complete of the derisking phase
                    frac = (gp_derisk_start - t_fi) / gp_derisk_start
                    eq_w = gp_base_eq - frac * (gp_base_eq - gp_target_eq)
                elif t_fi < 0:
                    eq_w = gp_target_eq

                # Adjust return based on equity weight (simplified portfolio scalar)
                # Assuming Debt has 0.02 real drift and 0.04 vol
                port_drift = (s_drift * eq_w) + ((gp_debt_ret / 12.0) * (1.0 - eq_w))
                port_vol = (s_vol * eq_w) + ((gp_debt_vol / np.sqrt(12.0)) * (1.0 - eq_w))

                # Human Capital Shock
                if (current_state == 1 or current_state == 2) and unemployment_months == 0:
                    u_hc = np.random.uniform(0.0, 1.0)
                    if u_hc < hc_shock_prob:
                        # np randint doesn't accept arrays well in older numba, safe scalar
                        span = hc_shock_max - hc_shock_min + 1
                        unemployment_months = hc_shock_min + int(np.random.uniform(0.0, span))

                effective_pmt = pmt
                if unemployment_months > 0:
                    effective_pmt = 0.0
                    path_lost_savings += pmt
                    unemployment_months -= 1

                # OU Stochastic Inflation
                shock_inf = np.random.normal(0.0, sigma_inf)
                inf_path = inf_path + theta * (s_inf_target - inf_path) + shock_inf
                if inf_path < 0.0:
                    inf_path = 0.0
                elif inf_path > inf_max:
                    inf_path = inf_max

                if inf_path > path_peak_inf:
                    path_peak_inf = inf_path

                cum_inf *= 1.0 + (inf_path / 12.0)

                # Returns & Jump Diffusion
                ret = np.random.standard_t(4) * (port_vol / np.sqrt(2.0)) + port_drift
                jump = jump_mag if np.random.random() < monthly_jump_prob else 0.0

                wealth = wealth * (1.0 + ret + jump) + effective_pmt

                if wealth > peak_wealth:
                    peak_wealth = wealth
                dd = (peak_wealth - wealth) / peak_wealth
                if dd > max_dd:
                    max_dd = dd

                if wealth >= fv:
                    hit_month = m
                    break

            lost_savings[j] = path_lost_savings
            peak_infs[j] = path_peak_inf

            # --- Decumulation Phase ---
            if hit_month != -1:
                months_to_fire[j] = hit_month
                nom_targets[j] = fv * cum_inf
                valid_decum += 1

                months_left = target_lifespan_months - (current_age_m + hit_month)

                if months_left > 0:
                    dec_wealth = wealth
                    current_withdraw = fv / swr / 12.0
                    initial_rate = 1.0 / swr if swr > 0 else 0.04

                    realized_swr_sum = 0.0
                    survived = True
                    wealth_5y = dec_wealth

                    for d in range(1, months_left + 1):
                        # Markov State Transition
                        u_trans = np.random.uniform(0.0, 1.0)
                        p0 = tm_flat[current_state * 3 + 0]
                        p1 = tm_flat[current_state * 3 + 1]
                        if u_trans < p0:
                            current_state = 0
                        elif u_trans < p0 + p1:
                            current_state = 1
                        else:
                            current_state = 2

                        s_drift = state_params[current_state, 0] / 12.0
                        s_vol = state_params[current_state, 1] / np.sqrt(12.0)

                        # Post-FI Glide Path (re-risking)
                        eq_w = gp_target_eq
                        if d <= gp_rerisk_end and gp_rerisk_end > 0:
                            frac = d / float(gp_rerisk_end)
                            eq_w = gp_target_eq + frac * (gp_base_eq - gp_target_eq)
                        elif d > gp_rerisk_end:
                            eq_w = gp_base_eq

                        port_drift = (s_drift * eq_w) + ((gp_debt_ret / 12.0) * (1.0 - eq_w))
                        port_vol = (s_vol * eq_w) + ((gp_debt_vol / np.sqrt(12.0)) * (1.0 - eq_w))

                        # Guyton-Klinger Guardrails
                        if d % 12 == 0:
                            current_rate = (current_withdraw * 12.0) / max(dec_wealth, 1.0)
                            if current_rate > (initial_rate * gk_upper):
                                current_withdraw *= gk_cut
                            elif current_rate < (initial_rate * gk_lower):
                                current_withdraw *= gk_raise

                        realized_swr_sum += (current_withdraw * 12.0) / max(dec_wealth, 1.0)

                        ret = np.random.standard_t(4) * (port_vol / np.sqrt(2.0)) + port_drift
                        jump = jump_mag if np.random.random() < monthly_jump_prob else 0.0

                        dec_wealth = dec_wealth * (1.0 + ret + jump) - current_withdraw

                        if dec_wealth > peak_wealth:
                            peak_wealth = dec_wealth
                        dd = (peak_wealth - dec_wealth) / peak_wealth
                        if dd > max_dd:
                            max_dd = dd

                        if d == sorr_months:
                            wealth_5y = dec_wealth

                        if dec_wealth <= 0.0:
                            survived = False
                            term_wealth[j] = 0.0
                            avg_swrs[j] = realized_swr_sum / d
                            if d >= sorr_months:
                                sorr_cagrs[j] = (wealth_5y / wealth) ** (12.0 / sorr_months) - 1.0
                            else:
                                sorr_cagrs[j] = -1.0
                            break

                    if survived:
                        survived_count += 1
                        term_wealth[j] = dec_wealth
                        avg_swrs[j] = realized_swr_sum / months_left
                        if months_left >= sorr_months:
                            sorr_cagrs[j] = (wealth_5y / wealth) ** (12.0 / sorr_months) - 1.0
                        else:
                            sorr_cagrs[j] = (dec_wealth / wealth) ** (12.0 / months_left) - 1.0
                else:
                    survived_count += 1
                    term_wealth[j] = wealth
                    avg_swrs[j] = 1.0 / swr if swr > 0 else 0.04
                    sorr_cagrs[j] = 0.0

            max_dds[j] = max_dd

            # Runway Calculation
            r_wealth = pv
            r_withdraw = burn_rate
            runway_m = max_runway_possible

            if pv > 0 and burn_rate > 0:
                for d in range(1, max_runway_possible + 1):
                    ret = np.random.standard_t(4) * (vol_r / np.sqrt(2.0)) + mean_r
                    jump = jump_mag if np.random.random() < monthly_jump_prob else 0.0
                    r_wealth = r_wealth * (1.0 + ret + jump) - r_withdraw
                    if r_wealth <= 0.0:
                        runway_m = d
                        break
            else:
                runway_m = 0.0
            runway_months[j] = runway_m

        # --- Aggregation ---
        v_months = months_to_fire[~np.isnan(months_to_fire)]
        v_noms = nom_targets[~np.isnan(nom_targets)]

        if len(v_months) > 0:
            out_p90[i] = np.percentile(v_months, 90)
            out_p50[i] = np.percentile(v_months, 50)
            out_p10[i] = np.percentile(v_months, 10)
            out_nom_p50[i] = np.percentile(v_noms, 50)

            out_runway_p90[i] = np.percentile(runway_months, 90)
            out_runway_p50[i] = np.percentile(runway_months, 50)
            out_runway_p10[i] = np.percentile(runway_months, 10)

        if valid_decum > 0:
            prob_success[i] = survived_count / valid_decum
            v_term = term_wealth[~np.isnan(term_wealth)]
            if len(v_term) > 0:
                out_terminal_wealth_p50[i] = np.percentile(v_term, 50)
                out_terminal_wealth_p10[i] = np.percentile(v_term, 10)

            v_dd = max_dds[~np.isnan(max_dds)]
            if len(v_dd) > 0:
                out_max_drawdown_p50[i] = np.percentile(v_dd, 50)

            v_ls = lost_savings[~np.isnan(lost_savings)]
            if len(v_ls) > 0:
                out_lost_savings_ev[i] = np.mean(v_ls)

            v_pi = peak_infs[~np.isnan(peak_infs)]
            if len(v_pi) > 0:
                out_peak_inf_p50[i] = np.percentile(v_pi, 50)

            v_sorr = sorr_cagrs[~np.isnan(sorr_cagrs)]
            if len(v_sorr) > 0:
                out_sorr_cagr_p10[i] = np.percentile(v_sorr, 10)

            v_swr = avg_swrs[~np.isnan(avg_swrs)]
            if len(v_swr) > 0:
                out_avg_swr_p50[i] = np.percentile(v_swr, 50)
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
        out_terminal_wealth_p50,
        out_terminal_wealth_p10,
        out_max_drawdown_p50,
        out_lost_savings_ev,
        out_peak_inf_p50,
        out_sorr_cagr_p10,
        out_avg_swr_p50,
    )


def get_monte_carlo_fire_batch(rules, cma_real_return, cma_fat_tail):
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
        iterations = rules.assumptions.monte_carlo.iterations
        max_months = rules.assumptions.monte_carlo.max_months
        mc_volatility = rules.assumptions.monte_carlo.annual_volatility

        current_age_months = df["Age_Months"].to_numpy().astype(np.int32)
        target_age = rules.assumptions.monte_carlo.desired_target_age
        target_lifespan_months = int(target_age * 12)

        mc_rules = rules.assumptions.monte_carlo
        jd_rules = mc_rules.jump_diffusion

        expense_drag = jd_rules.expense_ratio_drag
        jump_prob_ann = jd_rules.jump_probability_annual
        jump_mag = jd_rules.jump_magnitude

        vol_r = (mc_volatility * cma_fat_tail) / np.sqrt(12)
        mean_r = (1.0 + cma_real_return - expense_drag - (jump_prob_ann * jump_mag)) ** (
            1.0 / 12.0
        ) - 1.0

        tm_flat = np.array(mc_rules.markov_regime.transition_matrix).flatten()
        st_bull = np.array(mc_rules.markov_regime.state_bull)
        st_bear = np.array(mc_rules.markov_regime.state_bear)
        st_stag = np.array(mc_rules.markov_regime.state_stag)

        hc_prob = mc_rules.human_capital.shock_probability
        hc_min = mc_rules.human_capital.shock_duration_min
        hc_max = mc_rules.human_capital.shock_duration_max

        gp_derisk = mc_rules.glide_path.derisk_start_months_prior
        gp_rerisk = mc_rules.glide_path.post_fi_re_risk_months
        gp_base = mc_rules.glide_path.base_equity_weight
        gp_target = mc_rules.glide_path.fi_target_equity_weight
        gp_debt_ret = mc_rules.glide_path.debt_real_return
        gp_debt_vol = mc_rules.glide_path.debt_volatility

        gk_upper = mc_rules.guyton_klinger.withdrawal_upper_threshold
        gk_lower = mc_rules.guyton_klinger.withdrawal_lower_threshold
        gk_cut = mc_rules.guyton_klinger.lifestyle_cut_multiplier
        gk_raise = mc_rules.guyton_klinger.lifestyle_raise_multiplier

        inf_theta = mc_rules.inflation_model.mean_reversion_speed
        inf_vol_ann = mc_rules.inflation_model.volatility_annual
        inf_max = mc_rules.inflation_model.max_inflation_cap

        sorr_months = mc_rules.sorr_cagr_window_months

        core_res = _run_mc_simulations_numba(
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
            tm_flat,
            st_bull,
            st_bear,
            st_stag,
            hc_prob,
            hc_min,
            hc_max,
            gp_derisk,
            gp_rerisk,
            gp_base,
            gp_target,
            jump_prob_ann,
            jump_mag,
            gp_debt_ret,
            gp_debt_vol,
            gk_upper,
            gk_lower,
            gk_cut,
            gk_raise,
            inf_theta,
            inf_vol_ann,
            inf_max,
            sorr_months,
        )

        total_res = _run_mc_simulations_numba(
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
            tm_flat,
            st_bull,
            st_bear,
            st_stag,
            hc_prob,
            hc_min,
            hc_max,
            gp_derisk,
            gp_rerisk,
            gp_base,
            gp_target,
            jump_prob_ann,
            jump_mag,
            gp_debt_ret,
            gp_debt_vol,
            gk_upper,
            gk_lower,
            gk_cut,
            gk_raise,
            inf_theta,
            inf_vol_ann,
            inf_max,
            sorr_months,
        )

        df_out = pl.DataFrame(
            {
                "Months_To_FI_Conservative_P90": core_res[0],
                "Months_To_FI_Base_P50": core_res[1],
                "Months_To_FI_Aggressive_P10": core_res[2],
                "Months_To_FI_Total_Conservative_P90": total_res[0],
                "Months_To_FI_Total_Base_P50": total_res[1],
                "Months_To_FI_Total_Aggressive_P10": total_res[2],
                "Probability_Of_Success_Pct": core_res[3] * 100.0,
                "Probability_Of_Success_Total_Pct": total_res[3] * 100.0,
                "Target_FI_Future_Nominal_P50": np.where(
                    np.isnan(core_res[4]) | (core_res[4] == 0), np.nan, core_res[4]
                ),
                "Target_FI_Total_Future_Nominal_P50": np.where(
                    np.isnan(total_res[4]) | (total_res[4] == 0), np.nan, total_res[4]
                ),
                "Runway_Months_Stressed_P10": core_res[7],
                "Runway_Months_Base_P50": core_res[6],
                "Runway_Months_Total_Stressed_P10": total_res[7],
                "Runway_Months_Total_Base_P50": total_res[6],
                "Terminal_Wealth_P50": core_res[8],
                "Terminal_Wealth_P10": core_res[9],
                "Max_Drawdown_Pct_P50": core_res[10] * 100.0,
                "Lost_Savings_Expected_Value": core_res[11],
                "Peak_Inflation_Experienced_Pct": core_res[12] * 100.0,
                "Decumulation_First_5Y_CAGR_P10": core_res[13] * 100.0,
                "Average_Realized_Withdrawal_Rate_P50": core_res[14] * 100.0,
            }
        )
        return df_out.to_struct("")

    return monte_carlo_fire_batch
