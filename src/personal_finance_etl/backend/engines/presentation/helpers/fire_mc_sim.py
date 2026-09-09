# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false
# pyright: reportAttributeAccessIssue=false

from collections.abc import Callable
from typing import Any

import numba.typed
import numpy as np
import numpy.typing as npt
import polars as pl
from numba import njit, prange

from personal_finance_etl.backend.config.financial_rules import FinancialRules


@njit(fastmath=True, parallel=True, cache=True)
def _run_mc_simulations_numba(
    pv_arr: npt.NDArray[np.float64],
    pmt_total_arr: npt.NDArray[np.float64],
    fv_total_arr: npt.NDArray[np.float64],
    burn_total_arr: npt.NDArray[np.float64],
    inf_rates: npt.NDArray[np.float64],
    seed_ints: npt.NDArray[np.int32],
    gens: Any,
    iterations: int,
    max_months: int,
    vol_r: float,
    mean_r: float,
    swr: float,
    current_age_months_arr: npt.NDArray[np.int32],
    target_lifespan_months: int,
    tm_flat: npt.NDArray[np.float64],
    state_bull_params: npt.NDArray[np.float64],
    state_bear_params: npt.NDArray[np.float64],
    state_stag_params: npt.NDArray[np.float64],
    hc_shock_prob: float,
    hc_shock_min: int,
    hc_shock_max: int,
    hc_cov: float,
    gp_derisk_start: int,
    gp_rerisk_end: int,
    gp_base_eq: float,
    gp_target_eq: float,
    gp_dyn_debt: bool,
    jump_prob_ann: float,
    jump_mag: float,
    gp_debt_ret: float,
    gp_debt_vol: float,
    gk_upper: float,
    gk_lower: float,
    gk_cut: float,
    gk_raise: float,
    inf_theta: float,
    inf_vol_ann: float,
    inf_max: float,
    inf_min: float,
    sorr_months: int,
    expense_drag: float,
) -> tuple[
    npt.NDArray[np.float64],  # 16 out_p90
    npt.NDArray[np.float64],  # 17 out_p50
    npt.NDArray[np.float64],  # 18 out_p10
    npt.NDArray[np.float64],  # 19 prob_success
    npt.NDArray[np.float64],  # 20 out_nom_p50
    npt.NDArray[np.float64],  # 21 out_runway_p90
    npt.NDArray[np.float64],  # 22 out_runway_p50
    npt.NDArray[np.float64],  # 23 out_runway_p10
    npt.NDArray[np.float64],  # 24 out_terminal_wealth_p50
    npt.NDArray[np.float64],  # 25 out_terminal_wealth_p10
    npt.NDArray[np.float64],  # 26 out_max_drawdown_p50
    npt.NDArray[np.float64],  # 27 out_lost_savings_ev
    npt.NDArray[np.float64],  # 28 out_peak_inf_p50
    npt.NDArray[np.float64],  # 29 out_sorr_cagr_p10
    npt.NDArray[np.float64],  # 30 out_avg_swr_p50
    npt.NDArray[np.float64],  # 31 out_terminal_wealth_nom_p50
]:
    n_rows = len(pv_arr)
    # Total Outputs (16 arrays)
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
    out_terminal_wealth_nom_p50 = np.full(n_rows, np.nan)
    out_max_drawdown_p50 = np.full(n_rows, np.nan)
    out_lost_savings_ev = np.full(n_rows, np.nan)
    out_peak_inf_p50 = np.full(n_rows, np.nan)
    out_sorr_cagr_p10 = np.full(n_rows, np.nan)
    out_avg_swr_p50 = np.full(n_rows, np.nan)

    monthly_jump_prob = jump_prob_ann / 12.0
    theta = inf_theta
    sigma_inf = inf_vol_ann / np.sqrt(12.0)
    hc_monthly_prob = 1.0 - (1.0 - hc_shock_prob) ** (1.0 / 12.0)

    state_params = np.array(
        [
            [state_bull_params[0], state_bull_params[1], state_bull_params[2]],
            [state_bear_params[0], state_bear_params[1], state_bear_params[2]],
            [state_stag_params[0], state_stag_params[1], state_stag_params[2]],
        ]
    )

    for i in prange(n_rows):  # type: ignore
        gen = gens[np.intp(i)]

        pv = pv_arr[i]
        pmt = pmt_total_arr[i]
        fv = fv_total_arr[i]
        burn = burn_total_arr[i]

        inf_base = inf_rates[i]
        if np.isnan(inf_base):
            inf_base = 0.04

        current_age_m = current_age_months_arr[i]

        if np.isnan(fv) or np.isnan(pv) or np.isnan(pmt):
            prob_success[i] = np.nan
            continue  # Arrays for storing iteration metrics

        m_fi = np.full(iterations, np.nan)
        nom_targ = np.full(iterations, np.nan)
        term_w = np.full(iterations, np.nan)
        term_w_nom = np.full(iterations, np.nan)
        runway_m = np.zeros(iterations)
        dds = np.full(iterations, np.nan)
        lost_sav = np.zeros(iterations)
        p_infs = np.full(iterations, np.nan)
        cagrs = np.full(iterations, np.nan)
        swrs = np.full(iterations, np.nan)

        surv_count = 0
        valid_decum = 0
        max_runway_possible = target_lifespan_months - current_age_m

        for j in range(iterations):
            # Macro State
            current_state = 0
            inf_path = inf_base
            cum_inf = 1.0
            unemployment_months = 0
            path_peak_inf = inf_path  # Total State
            w = pv
            hit_m = -1
            dec_w = 0.0
            dec_nom = 0.0
            peak_w = pv
            max_dd = 0.0
            path_ls = 0.0
            surv = True
            curr_wd = 0.0
            init_rt = 0.0
            swr_sum = 0.0
            w_5y = 0.0
            dec_w_init = 0.0
            surv_m = 0
            if pv >= fv:
                hit_m = 0
                dec_w = pv
                dec_w_init = pv
                dec_nom = fv
                curr_wd = (fv / swr / 12.0) if swr > 0 else 0.0
                init_rt = 1.0 / swr if swr > 0 else 0.04

            # Runway States Embedded
            r_w = pv
            r_m = max_runway_possible
            alv = pv > 0 and burn > 0

            # --- Unified Trajectory Loop ---
            for m in range(1, max_runway_possible + 1):
                # 1. Macro Update
                if m == 1 or (m - 1) % 12 == 0:
                    u_trans = gen.uniform(0.0, 1.0)
                    p0 = tm_flat[current_state * 3 + 0]
                    p1 = tm_flat[current_state * 3 + 1]
                    if u_trans < p0:
                        current_state = 0
                    elif u_trans < p0 + p1:
                        current_state = 1
                    else:
                        current_state = 2

                s_drift_ann = state_params[current_state, 0] - expense_drag
                s_drift = (1.0 + s_drift_ann) ** (1.0 / 12.0) - 1.0
                s_vol = state_params[current_state, 1] / np.sqrt(12.0)
                s_inf_target = state_params[current_state, 2]

                shock_inf = gen.normal(0.0, sigma_inf)
                inf_path = inf_path + (theta / 12.0) * (s_inf_target - inf_path) + shock_inf
                if inf_path < inf_min:
                    inf_path = inf_min
                elif inf_path > inf_max:
                    inf_path = inf_max
                if inf_path > path_peak_inf:
                    path_peak_inf = inf_path

                cum_inf *= (1.0 + inf_path) ** (1.0 / 12.0)

                # FIX: Core and Total represent the SAME portfolio in the SAME market.
                # A single equity return draw is shared across both paths so they experience
                # identical market shocks — using independent draws would incorrectly model
                # them as two uncorrelated portfolios. This also saves 2 RNG calls/month.
                z_ret_eq = gen.standard_t(4.0)
                jump_eq = jump_mag if gen.random() < monthly_jump_prob else 0.0

                # Runway is a separate stress-test trajectory (different allocation/burn),
                # but Core-runway and Total-runway still share the same market environment.
                z_ret_r = gen.standard_t(4.0)
                jump_r = jump_mag if gen.random() < monthly_jump_prob else 0.0

                if (current_state == 1 or current_state == 2) and unemployment_months == 0:
                    u_hc = gen.uniform(0.0, 1.0)
                    if u_hc < hc_monthly_prob:
                        span = hc_shock_max - hc_shock_min + 1
                        unemployment_months = hc_shock_min + int(gen.uniform(0.0, span))

                is_unemployed = unemployment_months > 0
                if is_unemployed:
                    unemployment_months -= 1

                # === TRAJECTORY LOOP ===
                if hit_m == -1 and pv < fv:
                    if mean_r > 0.0001:
                        num = fv + pmt / mean_r
                        den = w + pmt / mean_r
                        t_fi = (
                            int(np.ceil(np.log(num / den) / np.log(1.0 + mean_r)))
                            if (num > 0 and den > 0)
                            else max_months
                        )
                    else:
                        t_fi = int(np.ceil((fv - w) / pmt)) if pmt > 0 else max_months

                    eq_w = gp_base_eq
                    if t_fi <= gp_derisk_start and t_fi >= 0:
                        frac = (
                            (gp_derisk_start - t_fi) / gp_derisk_start
                            if gp_derisk_start > 0
                            else 0.0
                        )
                        eq_w = gp_base_eq - frac * (gp_base_eq - gp_target_eq)
                    elif t_fi < 0:
                        eq_w = gp_target_eq

                    debt_drift_m = (1.0 + gp_debt_ret - expense_drag) ** (1.0 / 12.0) - 1.0
                    p_drift = (s_drift * eq_w) + (debt_drift_m * (1.0 - eq_w))
                    p_vol = np.sqrt(
                        (s_vol * eq_w) ** 2 + ((gp_debt_vol / np.sqrt(12.0)) * (1.0 - eq_w)) ** 2
                    )

                    path_ls = path_ls * (1.0 + mean_r)
                    eff_pmt = -burn * (1.0 - hc_cov) if is_unemployed else pmt
                    if is_unemployed:
                        path_ls += pmt + burn * (1.0 - hc_cov)

                    ret = z_ret_eq * (p_vol / np.sqrt(2.0)) + p_drift
                    eff_jump = jump_eq * eq_w
                    w = w * (1.0 + ret) * (1.0 + eff_jump) + eff_pmt

                    if w > peak_w:
                        peak_w = w
                    dd = (peak_w - w) / peak_w
                    if dd > max_dd:
                        max_dd = dd

                    if w >= fv and m <= max_months:
                        hit_m = m
                        dec_w = w
                        dec_w_init = w
                        dec_nom = fv * cum_inf
                        curr_wd = (fv / swr / 12.0) if swr > 0 else 0.0
                        init_rt = 1.0 / swr if swr > 0 else 0.04
                elif hit_m != -1 or pv >= fv:
                    if surv:
                        d = m - hit_m
                        surv_m = d
                        if gp_rerisk_end > 0:
                            if d <= gp_rerisk_end:
                                frac = d / float(gp_rerisk_end)
                                eq_w = gp_target_eq + frac * (gp_base_eq - gp_target_eq)
                            else:
                                eq_w = gp_base_eq
                        else:
                            eq_w = gp_target_eq

                        debt_drift_m = (1.0 + gp_debt_ret - expense_drag) ** (1.0 / 12.0) - 1.0
                        p_drift = (s_drift * eq_w) + (debt_drift_m * (1.0 - eq_w))
                        p_vol = np.sqrt(
                            (s_vol * eq_w) ** 2
                            + ((gp_debt_vol / np.sqrt(12.0)) * (1.0 - eq_w)) ** 2
                        )

                        if d > 0 and d % 12 == 0:
                            curr_rt = (curr_wd * 12.0) / max(dec_w, 1.0)
                            if curr_rt > (init_rt * gk_upper):
                                curr_wd *= gk_cut
                            elif curr_rt < (init_rt * gk_lower):
                                curr_wd *= gk_raise

                        swr_sum += curr_wd * 12.0
                        ret = z_ret_eq * (p_vol / np.sqrt(2.0)) + p_drift
                        eff_jump = jump_eq * eq_w

                        eff_ret = (1.0 + ret) * (1.0 + eff_jump)
                        if gp_dyn_debt and eff_ret < 1.0 and d <= sorr_months:
                            dec_w = (dec_w - curr_wd) * eff_ret
                        else:
                            dec_w = dec_w * eff_ret - curr_wd

                        if dec_w > peak_w:
                            peak_w = dec_w
                        dd = (peak_w - dec_w) / peak_w
                        if dd > max_dd:
                            max_dd = dd

                        if d == sorr_months:
                            w_5y = dec_w

                        if dec_w <= 0.0:
                            surv = False
                            dec_w = 0.0

                # === RUNWAY ===
                if alv:
                    eq_w_r = gp_target_eq
                    debt_drift_m = (1.0 + gp_debt_ret - expense_drag) ** (1.0 / 12.0) - 1.0
                    p_drift_r = (s_drift * eq_w_r) + (debt_drift_m * (1.0 - eq_w_r))
                    p_vol_r = np.sqrt(
                        (s_vol * eq_w_r) ** 2
                        + ((gp_debt_vol / np.sqrt(12.0)) * (1.0 - eq_w_r)) ** 2
                    )
                    ret_r = z_ret_r * (p_vol_r / np.sqrt(2.0)) + p_drift_r
                    eff_jump_r = jump_r * eq_w_r
                    r_w = r_w * (1.0 + ret_r) * (1.0 + eff_jump_r) - burn
                    if r_w <= 0.0:
                        r_m = m
                        alv = False

            # Store iteration metrics
            if hit_m != -1 and hit_m <= max_months:
                m_fi[j] = hit_m
                nom_targ[j] = dec_nom
                valid_decum += 1
                months_decum = max_runway_possible - hit_m

                term_w[j] = dec_w
                term_w_nom[j] = dec_w * cum_inf
                if months_decum > 0:
                    # NOTE (survivor bias): swrs[j] = nan for failed paths (see line ~548),
                    # so out_avg_swr_p50 is computed only over paths where the portfolio
                    # survived to end-of-horizon — it overstates withdrawal sustainability.
                    swrs[j] = (
                        (swr_sum / surv_m) / dec_w_init
                        if surv_m > 0 and dec_w_init > 0
                        else 0.0
                    )
                    if months_decum >= sorr_months:
                        if w_5y > 0.0:
                            cagrs[j] = (w_5y / dec_w_init) ** (12.0 / sorr_months) - 1.0
                        else:
                            cagrs[j] = -1.0
                    else:
                        cagrs[j] = (dec_w / dec_w_init) ** (12.0 / months_decum) - 1.0
                else:
                    swrs[j] = 1.0 / swr if swr > 0 else 0.04
                    cagrs[j] = 0.0
                if surv:
                    surv_count += 1
            else:
                m_fi[j] = np.nan
                nom_targ[j] = np.nan
                term_w[j] = w
                term_w_nom[j] = w * cum_inf
                swrs[j] = np.nan
                cagrs[j] = np.nan

            dds[j] = max_dd
            lost_sav[j] = path_ls

            p_infs[j] = path_peak_inf
            runway_m[j] = r_m

        # --- Aggregation ---
        v_m = m_fi[~np.isnan(m_fi)]
        v_nom = nom_targ[~np.isnan(nom_targ)]
        if len(v_m) > 0:
            out_p90[i] = np.percentile(v_m, 90.0)
            out_p50[i] = np.percentile(v_m, 50.0)
            out_p10[i] = np.percentile(v_m, 10.0)
            out_nom_p50[i] = np.percentile(v_nom, 50.0)

        # Independent Metrics (Runway, Terminal Wealth, Drawdown, Lost Savings, Inflation)
        out_runway_p90[i] = np.percentile(runway_m, 90.0)
        out_runway_p50[i] = np.percentile(runway_m, 50.0)
        out_runway_p10[i] = np.percentile(runway_m, 10.0)

        v_term = term_w[~np.isnan(term_w)]
        if len(v_term) > 0:
            out_terminal_wealth_p50[i] = np.percentile(v_term, 50.0)
            out_terminal_wealth_p10[i] = np.percentile(v_term, 10.0)

        v_term_nom = term_w_nom[~np.isnan(term_w_nom)]
        if len(v_term_nom) > 0:
            out_terminal_wealth_nom_p50[i] = np.percentile(v_term_nom, 50.0)

        v_dd = dds[~np.isnan(dds)]
        if len(v_dd) > 0:
            out_max_drawdown_p50[i] = np.percentile(v_dd, 50.0)

        v_ls = lost_sav[~np.isnan(lost_sav)]
        if len(v_ls) > 0:
            out_lost_savings_ev[i] = np.mean(v_ls)

        v_pi = p_infs[~np.isnan(p_infs)]
        if len(v_pi) > 0:
            out_peak_inf_p50[i] = np.percentile(v_pi, 50.0)

        if valid_decum > 0:
            prob_success[i] = surv_count / valid_decum
            v_sorr = cagrs[~np.isnan(cagrs)]
            if len(v_sorr) > 0:
                out_sorr_cagr_p10[i] = np.percentile(v_sorr, 10.0)
            v_swr = swrs[~np.isnan(swrs)]
            if len(v_swr) > 0:
                out_avg_swr_p50[i] = np.percentile(v_swr, 50.0)
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
        out_terminal_wealth_nom_p50,
    )


def get_monte_carlo_fire_batch(
    rules: FinancialRules, cma_real_return: float, cma_fat_tail: float
) -> Callable[..., pl.Series]:
    def monte_carlo_fire_batch(s: pl.Series, **kwargs: Any) -> pl.Series:
        df = s.struct.unnest()
        pv = df["Total_Net_Worth_Market_Af_Tax"].to_numpy().astype(float)
        pmt = df["Trailing_12M_Avg_Total_Savings"].to_numpy().astype(float)
        fv = df["Target_FI_Today_Total"].to_numpy().astype(float)
        burn = df["Trailing_12M_Avg_Total_Spend"].to_numpy().astype(float)

        inf_rates = df["INFLATION_YOY_PCT"].to_numpy().astype(float)
        seed_ints = df["Seed_Int"].to_numpy().astype(np.int32)

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
        hc_cov = mc_rules.human_capital.unemployment_benefit_coverage_pct

        gp_derisk = mc_rules.glide_path.derisk_start_months_prior
        gp_rerisk = mc_rules.glide_path.post_fi_re_risk_months
        gp_base = mc_rules.glide_path.base_equity_weight
        gp_target = mc_rules.glide_path.fi_target_equity_weight
        gp_debt_ret = mc_rules.glide_path.debt_real_return
        gp_debt_vol = mc_rules.glide_path.debt_volatility
        gp_dyn_debt = mc_rules.glide_path.dynamic_debt_drawdown_first

        gk_upper = mc_rules.guyton_klinger.withdrawal_upper_threshold
        gk_lower = mc_rules.guyton_klinger.withdrawal_lower_threshold
        gk_cut = mc_rules.guyton_klinger.lifestyle_cut_multiplier
        gk_raise = mc_rules.guyton_klinger.lifestyle_raise_multiplier

        inf_theta = mc_rules.inflation_model.mean_reversion_speed
        inf_vol_ann = mc_rules.inflation_model.volatility_annual
        inf_max = mc_rules.inflation_model.max_inflation_cap
        inf_min = mc_rules.inflation_model.min_deflation_floor

        sorr_months = mc_rules.sorr_cagr_window_months

        gens = numba.typed.List()  # type: ignore
        for seed in seed_ints:
            gens.append(np.random.default_rng(seed))

        res = _run_mc_simulations_numba(
            pv,
            pmt,
            fv,
            burn,
            inf_rates,
            seed_ints,
            gens,
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
            hc_cov,
            gp_derisk,
            gp_rerisk,
            gp_base,
            gp_target,
            gp_dyn_debt,
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
            inf_min,
            sorr_months,
            expense_drag,
        )

        df_out = pl.DataFrame(
            {
                "Months_To_FI_Conservative_P90": res[0],
                "Months_To_FI_Base_P50": res[1],
                "Months_To_FI_Aggressive_P10": res[2],
                "Probability_Of_Success_Pct": res[3],
                "Target_FI_Future_Nominal_P50": np.where(
                    np.isnan(res[4]) | (res[4] == 0), np.nan, res[4]
                ),
                "Runway_Months_Stressed_P10": res[7],
                "Runway_Months_Base_P50": res[6],
                "Terminal_Wealth_Nominal_P50": res[15],
            }
        )
        return df_out.to_struct("")

    return monte_carlo_fire_batch
