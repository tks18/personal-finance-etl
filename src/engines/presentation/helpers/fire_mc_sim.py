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

from src.config.financial_rules import FinancialRules


@njit(fastmath=True, parallel=True, cache=True)
def _run_mc_simulations_numba(
    pv_arr: npt.NDArray[np.float64],
    pmt_core_arr: npt.NDArray[np.float64],
    fv_core_arr: npt.NDArray[np.float64],
    burn_core_arr: npt.NDArray[np.float64],
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
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
    npt.NDArray[np.float64],
]:
    n_rows = len(pv_arr)

    # Core Outputs (16 arrays)
    out_p90_c = np.full(n_rows, np.nan)
    out_p50_c = np.full(n_rows, np.nan)
    out_p10_c = np.full(n_rows, np.nan)
    out_nom_p50_c = np.full(n_rows, np.nan)
    prob_success_c = np.zeros(n_rows)
    out_runway_p90_c = np.full(n_rows, np.nan)
    out_runway_p50_c = np.full(n_rows, np.nan)
    out_runway_p10_c = np.full(n_rows, np.nan)
    out_terminal_wealth_p50_c = np.full(n_rows, np.nan)
    out_terminal_wealth_p10_c = np.full(n_rows, np.nan)
    out_terminal_wealth_nom_p50_c = np.full(n_rows, np.nan)
    out_max_drawdown_p50_c = np.full(n_rows, np.nan)
    out_lost_savings_ev_c = np.full(n_rows, np.nan)
    out_peak_inf_p50_c = np.full(n_rows, np.nan)
    out_sorr_cagr_p10_c = np.full(n_rows, np.nan)
    out_avg_swr_p50_c = np.full(n_rows, np.nan)

    # Total Outputs (16 arrays)
    out_p90_t = np.full(n_rows, np.nan)
    out_p50_t = np.full(n_rows, np.nan)
    out_p10_t = np.full(n_rows, np.nan)
    out_nom_p50_t = np.full(n_rows, np.nan)
    prob_success_t = np.zeros(n_rows)
    out_runway_p90_t = np.full(n_rows, np.nan)
    out_runway_p50_t = np.full(n_rows, np.nan)
    out_runway_p10_t = np.full(n_rows, np.nan)
    out_terminal_wealth_p50_t = np.full(n_rows, np.nan)
    out_terminal_wealth_p10_t = np.full(n_rows, np.nan)
    out_terminal_wealth_nom_p50_t = np.full(n_rows, np.nan)
    out_max_drawdown_p50_t = np.full(n_rows, np.nan)
    out_lost_savings_ev_t = np.full(n_rows, np.nan)
    out_peak_inf_p50_t = np.full(n_rows, np.nan)
    out_sorr_cagr_p10_t = np.full(n_rows, np.nan)
    out_avg_swr_p50_t = np.full(n_rows, np.nan)

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
        pmt_c = pmt_core_arr[i]
        fv_c = fv_core_arr[i]
        burn_c = burn_core_arr[i]
        pmt_t = pmt_total_arr[i]
        fv_t = fv_total_arr[i]
        burn_t = burn_total_arr[i]

        inf_base = inf_rates[i]
        if np.isnan(inf_base):
            inf_base = 0.04

        current_age_m = current_age_months_arr[i]

        if np.isnan(fv_c) or np.isnan(pv) or np.isnan(pmt_c):
            prob_success_c[i] = np.nan
            prob_success_t[i] = np.nan
            continue

        # Arrays for storing iteration metrics
        m_fi_c = np.full(iterations, np.nan)
        m_fi_t = np.full(iterations, np.nan)
        nom_targ_c = np.full(iterations, np.nan)
        nom_targ_t = np.full(iterations, np.nan)
        term_w_c = np.full(iterations, np.nan)
        term_w_t = np.full(iterations, np.nan)
        term_w_nom_c = np.full(iterations, np.nan)
        term_w_nom_t = np.full(iterations, np.nan)
        runway_m_c = np.zeros(iterations)
        runway_m_t = np.zeros(iterations)
        dds_c = np.full(iterations, np.nan)
        dds_t = np.full(iterations, np.nan)
        lost_sav_c = np.zeros(iterations)
        lost_sav_t = np.zeros(iterations)
        p_infs = np.full(iterations, np.nan)
        cagrs_c = np.full(iterations, np.nan)
        cagrs_t = np.full(iterations, np.nan)
        swrs_c = np.full(iterations, np.nan)
        swrs_t = np.full(iterations, np.nan)

        surv_count_c = 0
        surv_count_t = 0
        valid_decum_c = 0
        valid_decum_t = 0
        max_runway_possible = target_lifespan_months - current_age_m

        for j in range(iterations):
            # Macro State
            current_state = 0
            inf_path = inf_base
            cum_inf = 1.0
            unemployment_months = 0
            path_peak_inf = inf_path

            # Core State
            w_c = pv
            hit_m_c = -1
            dec_w_c = 0.0
            dec_nom_c = 0.0
            peak_w_c = pv
            max_dd_c = 0.0
            path_ls_c = 0.0
            surv_c = True
            curr_wd_c = 0.0
            init_rt_c = 0.0
            swr_sum_c = 0.0
            w_5y_c = 0.0
            dec_w_c_init = 0.0
            surv_m_c = 0

            if pv >= fv_c:
                hit_m_c = 0
                dec_w_c = pv
                dec_w_c_init = pv
                dec_nom_c = fv_c
                curr_wd_c = (fv_c / swr / 12.0) if swr > 0 else 0.0
                init_rt_c = 1.0 / swr if swr > 0 else 0.04

            # Total State
            w_t = pv
            hit_m_t = -1
            dec_w_t = 0.0
            dec_nom_t = 0.0
            peak_w_t = pv
            max_dd_t = 0.0
            path_ls_t = 0.0
            surv_t = True
            curr_wd_t = 0.0
            init_rt_t = 0.0
            swr_sum_t = 0.0
            w_5y_t = 0.0
            dec_w_t_init = 0.0
            surv_m_t = 0

            if pv >= fv_t:
                hit_m_t = 0
                dec_w_t = pv
                dec_w_t_init = pv
                dec_nom_t = fv_t
                curr_wd_t = (fv_t / swr / 12.0) if swr > 0 else 0.0
                init_rt_t = 1.0 / swr if swr > 0 else 0.04

            # Runway States Embedded
            r_w_c = pv
            r_w_t = pv
            r_m_c = max_runway_possible
            r_m_t = max_runway_possible
            alv_c = pv > 0 and burn_c > 0
            alv_t = pv > 0 and burn_t > 0

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

                # === CORE ===
                if hit_m_c == -1 and pv < fv_c:
                    if mean_r > 0.0001:
                        num = fv_c + pmt_c / mean_r
                        den = w_c + pmt_c / mean_r
                        t_fi = (
                            int(np.ceil(np.log(num / den) / np.log(1.0 + mean_r)))
                            if (num > 0 and den > 0)
                            else max_months
                        )
                    else:
                        t_fi = int(np.ceil((fv_c - w_c) / pmt_c)) if pmt_c > 0 else max_months

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

                    path_ls_c = path_ls_c * (1.0 + mean_r)
                    eff_pmt_c = -burn_c * (1.0 - hc_cov) if is_unemployed else pmt_c
                    if is_unemployed:
                        path_ls_c += pmt_c + burn_c * (1.0 - hc_cov)

                    ret = z_ret_eq * (p_vol / np.sqrt(2.0)) + p_drift
                    eff_jump = jump_eq * eq_w
                    w_c = w_c * (1.0 + ret) * (1.0 + eff_jump) + eff_pmt_c

                    if w_c > peak_w_c:
                        peak_w_c = w_c
                    dd = (peak_w_c - w_c) / peak_w_c
                    if dd > max_dd_c:
                        max_dd_c = dd

                    if w_c >= fv_c and m <= max_months:
                        hit_m_c = m
                        dec_w_c = w_c
                        dec_w_c_init = w_c
                        dec_nom_c = fv_c * cum_inf
                        curr_wd_c = (fv_c / swr / 12.0) if swr > 0 else 0.0
                        init_rt_c = 1.0 / swr if swr > 0 else 0.04
                elif hit_m_c != -1 or pv >= fv_c:
                    if surv_c:
                        d = m - hit_m_c
                        surv_m_c = d
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
                            curr_rt = (curr_wd_c * 12.0) / max(dec_w_c, 1.0)
                            if curr_rt > (init_rt_c * gk_upper):
                                curr_wd_c *= gk_cut
                            elif curr_rt < (init_rt_c * gk_lower):
                                curr_wd_c *= gk_raise

                        swr_sum_c += curr_wd_c * 12.0
                        ret = z_ret_eq * (p_vol / np.sqrt(2.0)) + p_drift
                        eff_jump = jump_eq * eq_w

                        eff_ret = (1.0 + ret) * (1.0 + eff_jump)
                        if gp_dyn_debt and eff_ret < 1.0 and d <= sorr_months:
                            dec_w_c = (dec_w_c - curr_wd_c) * eff_ret
                        else:
                            dec_w_c = dec_w_c * eff_ret - curr_wd_c

                        if dec_w_c > peak_w_c:
                            peak_w_c = dec_w_c
                        dd = (peak_w_c - dec_w_c) / peak_w_c
                        if dd > max_dd_c:
                            max_dd_c = dd

                        if d == sorr_months:
                            w_5y_c = dec_w_c

                        if dec_w_c <= 0.0:
                            surv_c = False
                            dec_w_c = 0.0

                # === TOTAL ===
                if hit_m_t == -1 and pv < fv_t:
                    if mean_r > 0.0001:
                        num = fv_t + pmt_t / mean_r
                        den = w_t + pmt_t / mean_r
                        t_fi = (
                            int(np.ceil(np.log(num / den) / np.log(1.0 + mean_r)))
                            if (num > 0 and den > 0)
                            else max_months
                        )
                    else:
                        t_fi = int(np.ceil((fv_t - w_t) / pmt_t)) if pmt_t > 0 else max_months

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

                    path_ls_t = path_ls_t * (1.0 + mean_r)
                    eff_pmt_t = -burn_t * (1.0 - hc_cov) if is_unemployed else pmt_t
                    if is_unemployed:
                        path_ls_t += pmt_t + burn_t * (1.0 - hc_cov)

                    ret = z_ret_eq * (p_vol / np.sqrt(2.0)) + p_drift
                    eff_jump = jump_eq * eq_w
                    w_t = w_t * (1.0 + ret) * (1.0 + eff_jump) + eff_pmt_t

                    if w_t > peak_w_t:
                        peak_w_t = w_t
                    dd = (peak_w_t - w_t) / peak_w_t
                    if dd > max_dd_t:
                        max_dd_t = dd

                    if w_t >= fv_t and m <= max_months:
                        hit_m_t = m
                        dec_w_t = w_t
                        dec_w_t_init = w_t
                        dec_nom_t = fv_t * cum_inf
                        curr_wd_t = (fv_t / swr / 12.0) if swr > 0 else 0.0
                        init_rt_t = 1.0 / swr if swr > 0 else 0.04
                elif hit_m_t != -1 or pv >= fv_t:
                    if surv_t:
                        d = m - hit_m_t
                        surv_m_t = d
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
                            curr_rt = (curr_wd_t * 12.0) / max(dec_w_t, 1.0)
                            if curr_rt > (init_rt_t * gk_upper):
                                curr_wd_t *= gk_cut
                            elif curr_rt < (init_rt_t * gk_lower):
                                curr_wd_t *= gk_raise

                        swr_sum_t += curr_wd_t * 12.0
                        ret = z_ret_eq * (p_vol / np.sqrt(2.0)) + p_drift
                        eff_jump = jump_eq * eq_w

                        eff_ret = (1.0 + ret) * (1.0 + eff_jump)
                        if gp_dyn_debt and eff_ret < 1.0 and d <= sorr_months:
                            dec_w_t = (dec_w_t - curr_wd_t) * eff_ret
                        else:
                            dec_w_t = dec_w_t * eff_ret - curr_wd_t

                        if dec_w_t > peak_w_t:
                            peak_w_t = dec_w_t
                        dd = (peak_w_t - dec_w_t) / peak_w_t
                        if dd > max_dd_t:
                            max_dd_t = dd

                        if d == sorr_months:
                            w_5y_t = dec_w_t

                        if dec_w_t <= 0.0:
                            surv_t = False
                            dec_w_t = 0.0

                # === RUNWAY ===
                if alv_c:
                    eq_w_r = gp_target_eq
                    debt_drift_m = (1.0 + gp_debt_ret - expense_drag) ** (1.0 / 12.0) - 1.0
                    p_drift_r = (s_drift * eq_w_r) + (debt_drift_m * (1.0 - eq_w_r))
                    p_vol_r = np.sqrt(
                        (s_vol * eq_w_r) ** 2
                        + ((gp_debt_vol / np.sqrt(12.0)) * (1.0 - eq_w_r)) ** 2
                    )
                    ret_r_c = z_ret_r * (p_vol_r / np.sqrt(2.0)) + p_drift_r
                    eff_jump_r_c = jump_r * eq_w_r
                    r_w_c = r_w_c * (1.0 + ret_r_c) * (1.0 + eff_jump_r_c) - burn_c
                    if r_w_c <= 0.0:
                        r_m_c = m
                        alv_c = False

                if alv_t:
                    eq_w_r = gp_target_eq
                    debt_drift_m = (1.0 + gp_debt_ret - expense_drag) ** (1.0 / 12.0) - 1.0
                    p_drift_r = (s_drift * eq_w_r) + (debt_drift_m * (1.0 - eq_w_r))
                    p_vol_r = np.sqrt(
                        (s_vol * eq_w_r) ** 2
                        + ((gp_debt_vol / np.sqrt(12.0)) * (1.0 - eq_w_r)) ** 2
                    )
                    ret_r_t = z_ret_r * (p_vol_r / np.sqrt(2.0)) + p_drift_r
                    eff_jump_r_t = jump_r * eq_w_r
                    r_w_t = r_w_t * (1.0 + ret_r_t) * (1.0 + eff_jump_r_t) - burn_t
                    if r_w_t <= 0.0:
                        r_m_t = m
                        alv_t = False

            # Store iteration metrics for CORE
            if hit_m_c != -1 and hit_m_c <= max_months:
                m_fi_c[j] = hit_m_c
                nom_targ_c[j] = dec_nom_c
                valid_decum_c += 1
                months_decum_c = max_runway_possible - hit_m_c

                term_w_c[j] = dec_w_c
                term_w_nom_c[j] = dec_w_c * cum_inf
                if months_decum_c > 0:
                    # NOTE (survivor bias): swrs_c[j] = nan for failed paths (see line ~514),
                    # so out_avg_swr_p50_c is computed only over paths where the portfolio
                    # survived to end-of-horizon — it overstates withdrawal sustainability.
                    swrs_c[j] = (
                        (swr_sum_c / surv_m_c) / dec_w_c_init
                        if surv_m_c > 0 and dec_w_c_init > 0
                        else 0.0
                    )
                    if months_decum_c >= sorr_months:
                        if w_5y_c > 0.0:
                            cagrs_c[j] = (w_5y_c / dec_w_c_init) ** (12.0 / sorr_months) - 1.0
                        else:
                            cagrs_c[j] = -1.0
                    else:
                        cagrs_c[j] = (dec_w_c / dec_w_c_init) ** (12.0 / months_decum_c) - 1.0
                else:
                    swrs_c[j] = 1.0 / swr if swr > 0 else 0.04
                    cagrs_c[j] = 0.0
                if surv_c:
                    surv_count_c += 1
            else:
                m_fi_c[j] = np.nan
                nom_targ_c[j] = np.nan
                term_w_c[j] = w_c
                term_w_nom_c[j] = w_c * cum_inf
                swrs_c[j] = np.nan
                cagrs_c[j] = np.nan

            dds_c[j] = max_dd_c
            lost_sav_c[j] = path_ls_c

            # Store iteration metrics for TOTAL
            if hit_m_t != -1 and hit_m_t <= max_months:
                m_fi_t[j] = hit_m_t
                nom_targ_t[j] = dec_nom_t
                valid_decum_t += 1
                months_decum_t = max_runway_possible - hit_m_t

                term_w_t[j] = dec_w_t
                term_w_nom_t[j] = dec_w_t * cum_inf
                if months_decum_t > 0:
                    # NOTE (survivor bias): swrs_t[j] = nan for failed paths (see line ~548),
                    # so out_avg_swr_p50_t is computed only over paths where the portfolio
                    # survived to end-of-horizon — it overstates withdrawal sustainability.
                    swrs_t[j] = (
                        (swr_sum_t / surv_m_t) / dec_w_t_init
                        if surv_m_t > 0 and dec_w_t_init > 0
                        else 0.0
                    )
                    if months_decum_t >= sorr_months:
                        if w_5y_t > 0.0:
                            cagrs_t[j] = (w_5y_t / dec_w_t_init) ** (12.0 / sorr_months) - 1.0
                        else:
                            cagrs_t[j] = -1.0
                    else:
                        cagrs_t[j] = (dec_w_t / dec_w_t_init) ** (12.0 / months_decum_t) - 1.0
                else:
                    swrs_t[j] = 1.0 / swr if swr > 0 else 0.04
                    cagrs_t[j] = 0.0
                if surv_t:
                    surv_count_t += 1
            else:
                m_fi_t[j] = np.nan
                nom_targ_t[j] = np.nan
                term_w_t[j] = w_t
                term_w_nom_t[j] = w_t * cum_inf
                swrs_t[j] = np.nan
                cagrs_t[j] = np.nan

            dds_t[j] = max_dd_t
            lost_sav_t[j] = path_ls_t

            p_infs[j] = path_peak_inf

            runway_m_c[j] = r_m_c
            runway_m_t[j] = r_m_t

        # --- Aggregation CORE ---
        v_m_c = m_fi_c[~np.isnan(m_fi_c)]
        v_nom_c = nom_targ_c[~np.isnan(nom_targ_c)]
        if len(v_m_c) > 0:
            out_p90_c[i] = np.percentile(v_m_c, 90.0)
            out_p50_c[i] = np.percentile(v_m_c, 50.0)
            out_p10_c[i] = np.percentile(v_m_c, 10.0)
            out_nom_p50_c[i] = np.percentile(v_nom_c, 50.0)

        # Independent Metrics (Runway, Terminal Wealth, Drawdown, Lost Savings, Inflation)
        out_runway_p90_c[i] = np.percentile(runway_m_c, 90.0)
        out_runway_p50_c[i] = np.percentile(runway_m_c, 50.0)
        out_runway_p10_c[i] = np.percentile(runway_m_c, 10.0)

        v_term_c = term_w_c[~np.isnan(term_w_c)]
        if len(v_term_c) > 0:
            out_terminal_wealth_p50_c[i] = np.percentile(v_term_c, 50.0)
            out_terminal_wealth_p10_c[i] = np.percentile(v_term_c, 10.0)

        v_term_nom_c = term_w_nom_c[~np.isnan(term_w_nom_c)]
        if len(v_term_nom_c) > 0:
            out_terminal_wealth_nom_p50_c[i] = np.percentile(v_term_nom_c, 50.0)

        v_dd_c = dds_c[~np.isnan(dds_c)]
        if len(v_dd_c) > 0:
            out_max_drawdown_p50_c[i] = np.percentile(v_dd_c, 50.0)

        v_ls_c = lost_sav_c[~np.isnan(lost_sav_c)]
        if len(v_ls_c) > 0:
            out_lost_savings_ev_c[i] = np.mean(v_ls_c)

        v_pi_c = p_infs[~np.isnan(p_infs)]
        if len(v_pi_c) > 0:
            out_peak_inf_p50_c[i] = np.percentile(v_pi_c, 50.0)

        if valid_decum_c > 0:
            prob_success_c[i] = surv_count_c / valid_decum_c
            v_sorr_c = cagrs_c[~np.isnan(cagrs_c)]
            if len(v_sorr_c) > 0:
                out_sorr_cagr_p10_c[i] = np.percentile(v_sorr_c, 10.0)
            v_swr_c = swrs_c[~np.isnan(swrs_c)]
            if len(v_swr_c) > 0:
                out_avg_swr_p50_c[i] = np.percentile(v_swr_c, 50.0)
        else:
            prob_success_c[i] = 0.0

        # --- Aggregation TOTAL ---
        v_m_t = m_fi_t[~np.isnan(m_fi_t)]
        v_nom_t = nom_targ_t[~np.isnan(nom_targ_t)]
        if len(v_m_t) > 0:
            out_p90_t[i] = np.percentile(v_m_t, 90.0)
            out_p50_t[i] = np.percentile(v_m_t, 50.0)
            out_p10_t[i] = np.percentile(v_m_t, 10.0)
            out_nom_p50_t[i] = np.percentile(v_nom_t, 50.0)

        # Independent Metrics (Runway, Terminal Wealth, Drawdown, Lost Savings, Inflation)
        out_runway_p90_t[i] = np.percentile(runway_m_t, 90.0)
        out_runway_p50_t[i] = np.percentile(runway_m_t, 50.0)
        out_runway_p10_t[i] = np.percentile(runway_m_t, 10.0)

        v_term_t = term_w_t[~np.isnan(term_w_t)]
        if len(v_term_t) > 0:
            out_terminal_wealth_p50_t[i] = np.percentile(v_term_t, 50.0)
            out_terminal_wealth_p10_t[i] = np.percentile(v_term_t, 10.0)

        v_term_nom_t = term_w_nom_t[~np.isnan(term_w_nom_t)]
        if len(v_term_nom_t) > 0:
            out_terminal_wealth_nom_p50_t[i] = np.percentile(v_term_nom_t, 50.0)

        v_dd_t = dds_t[~np.isnan(dds_t)]
        if len(v_dd_t) > 0:
            out_max_drawdown_p50_t[i] = np.percentile(v_dd_t, 50.0)

        v_ls_t = lost_sav_t[~np.isnan(lost_sav_t)]
        if len(v_ls_t) > 0:
            out_lost_savings_ev_t[i] = np.mean(v_ls_t)

        v_pi_t = p_infs[~np.isnan(p_infs)]
        if len(v_pi_t) > 0:
            out_peak_inf_p50_t[i] = np.percentile(v_pi_t, 50.0)

        if valid_decum_t > 0:
            prob_success_t[i] = surv_count_t / valid_decum_t
            v_sorr_t = cagrs_t[~np.isnan(cagrs_t)]
            if len(v_sorr_t) > 0:
                out_sorr_cagr_p10_t[i] = np.percentile(v_sorr_t, 10.0)
            v_swr_t = swrs_t[~np.isnan(swrs_t)]
            if len(v_swr_t) > 0:
                out_avg_swr_p50_t[i] = np.percentile(v_swr_t, 50.0)
        else:
            prob_success_t[i] = 0.0

    return (
        out_p90_c,
        out_p50_c,
        out_p10_c,
        prob_success_c,
        out_nom_p50_c,
        out_runway_p90_c,
        out_runway_p50_c,
        out_runway_p10_c,
        out_terminal_wealth_p50_c,
        out_terminal_wealth_p10_c,
        out_max_drawdown_p50_c,
        out_lost_savings_ev_c,
        out_peak_inf_p50_c,
        out_sorr_cagr_p10_c,
        out_avg_swr_p50_c,
        out_terminal_wealth_nom_p50_c,
        out_p90_t,
        out_p50_t,
        out_p10_t,
        prob_success_t,
        out_nom_p50_t,
        out_runway_p90_t,
        out_runway_p50_t,
        out_runway_p10_t,
        out_terminal_wealth_p50_t,
        out_terminal_wealth_p10_t,
        out_max_drawdown_p50_t,
        out_lost_savings_ev_t,
        out_peak_inf_p50_t,
        out_sorr_cagr_p10_t,
        out_avg_swr_p50_t,
        out_terminal_wealth_nom_p50_t,
    )


def get_monte_carlo_fire_batch(
    rules: FinancialRules, cma_real_return: float, cma_fat_tail: float
) -> Callable[..., pl.Series]:
    def monte_carlo_fire_batch(s: pl.Series, **kwargs: Any) -> pl.Series:
        df = s.struct.unnest()
        pv = df["Total_Net_Worth_Market_Af_Tax"].to_numpy().astype(float)
        pmt_c = df["Trailing_12M_Avg_Savings"].to_numpy().astype(float)
        fv_c = df["Target_FI_Today"].to_numpy().astype(float)
        burn_c = df["Trailing_12M_Avg_Spend"].to_numpy().astype(float)

        pmt_t = df["Trailing_12M_Avg_Total_Savings"].to_numpy().astype(float)
        fv_t = df["Target_FI_Today_Total"].to_numpy().astype(float)
        burn_t = df["Trailing_12M_Avg_Total_Spend"].to_numpy().astype(float)

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
            pmt_c,
            fv_c,
            burn_c,
            pmt_t,
            fv_t,
            burn_t,
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
                "Months_To_FI_Total_Conservative_P90": res[16],
                "Months_To_FI_Total_Base_P50": res[17],
                "Months_To_FI_Total_Aggressive_P10": res[18],
                "Probability_Of_Success_Pct": res[3],
                "Probability_Of_Success_Total_Pct": res[19],
                "Target_FI_Future_Nominal_P50": np.where(
                    np.isnan(res[4]) | (res[4] == 0), np.nan, res[4]
                ),
                "Target_FI_Total_Future_Nominal_P50": np.where(
                    np.isnan(res[20]) | (res[20] == 0), np.nan, res[20]
                ),
                "Runway_Months_Stressed_P10": res[7],
                "Runway_Months_Base_P50": res[6],
                "Runway_Months_Total_Stressed_P10": res[23],
                "Runway_Months_Total_Base_P50": res[22],
                "Terminal_Wealth_P50": res[8],
                "Terminal_Wealth_P10": res[9],
                "Max_Drawdown_Pct_P50": res[10],
                "Compounded_Lost_Savings_EV": res[11],
                "Peak_Inflation_Experienced_Pct": res[12],
                "Decumulation_First_5Y_CAGR_P10": res[13],
                "Average_Realized_Withdrawal_Rate_P50": res[14],
                "Terminal_Wealth_Nominal_P50": res[15],
                "Terminal_Wealth_Total_Nominal_P50": res[31],
            }
        )
        return df_out.to_struct("")

    return monte_carlo_fire_batch
