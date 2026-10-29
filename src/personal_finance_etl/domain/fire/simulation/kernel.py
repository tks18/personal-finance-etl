# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false
# pyright: reportAttributeAccessIssue=false

"""Numba JIT-compiled Monte Carlo simulation numerical kernel.

Owns
----
- _run_mc_simulations_numba: High-performance Numba JIT-compiled Monte Carlo simulation kernel.

Does not own
-------------
- Polars batch mapping and stochastic distribution transforms (owned by domain.fire.simulation.batch).
- Deterministic FIRE targets (owned by domain.fire.deterministic).
- Historical inflation series construction (owned by domain.fire.inflation).
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
import numpy.typing as npt
from numba import njit, prange


class NumbaRngSequence(Protocol):
    """Protocol for sequence of random generators indexed by integers or numpy integers."""

    def __getitem__(self, index: int | np.intp) -> np.random.Generator:
        """Retrieve random generator by integer or numpy integer index.

        Parameters
        ----------
        index : int | np.intp
            Positional index into the generator collection.

        Returns
        -------
        np.random.Generator
            The indexed NumPy generator instance.
        """
        ...


__all__ = ["_run_mc_simulations_numba"]


# pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,too-many-branches,too-many-statements,unused-argument
@njit(fastmath=True, parallel=True, cache=True)
def _run_mc_simulations_numba(
    pv_arr: npt.NDArray[np.float64],
    pmt_total_arr: npt.NDArray[np.float64],
    fv_total_arr: npt.NDArray[np.float64],
    burn_total_arr: npt.NDArray[np.float64],
    inf_rates: npt.NDArray[np.float64],
    seed_ints: npt.NDArray[np.int32],
    # Numba numerical boundary: Sequence of NumPy Generator instances in a numba.typed.List
    gens: NumbaRngSequence,
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
    """Execute high-performance parallelized Monte Carlo simulations via Numba.

    Parameters
    ----------
    pv_arr : npt.NDArray[np.float64]
        Initial portfolio present value vector across scenarios.
    pmt_total_arr : npt.NDArray[np.float64]
        Monthly contribution or savings rate vector.
    fv_total_arr : npt.NDArray[np.float64]
        Future value cashflow target vector.
    burn_total_arr : npt.NDArray[np.float64]
        Monthly expense burn rate vector.
    inf_rates : npt.NDArray[np.float64]
        Historical or expected inflation rate vector.
    seed_ints : npt.NDArray[np.int32]
        Random seeds per thread.
    gens : NumbaRngSequence
        Numba typed list of NumPy pseudo-random number generator instances.
    iterations : int
        Number of simulation trajectories per scenario.
    max_months : int
        Maximum simulation horizon in months.
    vol_r : float
        Annualized volatility parameter.
    mean_r : float
        Annualized expected return drift.
    swr : float
        Safe withdrawal rate fraction.
    current_age_months_arr : npt.NDArray[np.int32]
        Current household member ages in months.
    target_lifespan_months : int
        Simulation planning horizon cap in months.
    tm_flat : npt.NDArray[np.float64]
        Flattened regime transition probability matrix.
    state_bull_params : npt.NDArray[np.float64]
        Bull regime return and volatility parameters.
    state_bear_params : npt.NDArray[np.float64]
        Bear regime return and volatility parameters.
    state_stag_params : npt.NDArray[np.float64]
        Stagflation regime return and volatility parameters.
    hc_shock_prob : float
        Health care shock probability per month.
    hc_shock_min : int
        Minimum health care shock duration in months.
    hc_shock_max : int
        Maximum health care shock duration in months.
    hc_cov : float
        Health care cost of variance / coefficient.
    gp_derisk_start : int
        Month to begin glide-path de-risking.
    gp_rerisk_end : int
        Month to complete glide-path re-risking.
    gp_base_eq : float
        Base equity percentage for glide-path.
    gp_target_eq : float
        Target equity percentage during retirement.
    gp_dyn_debt : bool
        Flag indicating dynamic debt adjustment.
    jump_prob_ann : float
        Annualized market jump/crash probability.
    jump_mag : float
        Jump magnitude fraction.
    gp_debt_ret : float
        Debt return parameter.
    gp_debt_vol : float
        Debt volatility parameter.
    gk_upper : float
        Guyton-Klinker upper capital preservation guardrail.
    gk_lower : float
        Guyton-Klinker lower prosperity guardrail.
    gk_cut : float
        Spending cut percentage on upper guardrail breach.
    gk_raise : float
        Spending raise percentage on lower guardrail breach.
    inf_theta : float
        Mean-reverting inflation speed parameter.
    inf_vol_ann : float
        Annualized inflation volatility.
    inf_max : float
        Maximum allowed inflation cap.
    inf_min : float
        Minimum allowed inflation floor.
    sorr_months : int
        Sequence-of-returns risk evaluation window in months.
    expense_drag : float
        Portfolio management fee and expense drag percentage.

    Returns
    -------
    tuple[npt.NDArray[np.float64], ...]
        16 simulated metric arrays containing percentiles (P90, P50, P10), success probability,
        runways, drawdowns, and terminal wealth.
    """
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

    # Exception TYP-001 [NUMBA_OR_LIBRARY_LIMITATION]: prange is dynamically injected by Numba compilation pass
    for i in prange(n_rows):  # type: ignore[no-untyped-call,attr-defined]
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
                    # NOTE (survivor bias): swrs[j] = nan for failed paths,
                    # so out_avg_swr_p50 is computed only over paths where the portfolio
                    # survived to end-of-horizon — it overstates withdrawal sustainability.
                    swrs[j] = (
                        (swr_sum / surv_m) / dec_w_init if surv_m > 0 and dec_w_init > 0 else 0.0
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
