# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownMemberType=false
# pyright: reportAttributeAccessIssue=false

"""Monte Carlo stochastic simulation kernel and FIRE probability engine.

Owns
----
- get_monte_carlo_fire_batch: Vectorized Polars batch mapping function converting time series features into stochastic distributions.

Does not own
-------------
- Numba numerical simulation kernel (owned by domain.fire.simulation.kernel).
- Deterministic FIRE targets (owned by domain.fire.deterministic).
- Historical inflation series construction (owned by domain.fire.inflation).
"""

from __future__ import annotations

from collections.abc import Callable

import numba.typed
import numpy as np
import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.fire.simulation.kernel import _run_mc_simulations_numba

__all__ = ["_run_mc_simulations_numba", "get_monte_carlo_fire_batch"]


def get_monte_carlo_fire_batch(
    rules: FinancialRules, cma_real_return: float, cma_fat_tail: float
) -> Callable[..., pl.Series]:
    """Return a vectorized Polars batch-mapping function executing Monte Carlo simulations.

    Parameters
    ----------
    rules : FinancialRules
        Financial rules containing Monte Carlo simulation parameters.
    cma_real_return : float
        Capital market assumption expected real return.
    cma_fat_tail : float
        Capital market assumption fat-tail multiplier for volatility.

    Returns
    -------
    Callable[..., pl.Series]
        Polars batch function mapping a struct series of inputs to simulation distribution percentiles.
    """

    # Exception TYP-001 [NUMBA_OR_LIBRARY_LIMITATION]: Polars UDF struct mapper accepts optional keyword arguments
    # pylint: disable=too-many-locals
    def monte_carlo_fire_batch(s: pl.Series, **kwargs: object) -> pl.Series:
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

        # Exception TYP-001 [NUMBA_OR_LIBRARY_LIMITATION]: numba.typed.List lacks static typing constructor stubs
        gens = numba.typed.List()  # pyright: ignore[reportCallIssue]
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
