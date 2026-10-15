"""Financial Independence & Retire Early (FIRE) simulation domain.

Owns
----
- Deterministic FI milestone calculations (Target FI, Lean FI, Coast FI via WealthRiskAnalyticsBuilder).
- Inflation modeling and real-return adjustments (InflationBuilder).
- Forward budget forecasting (calculate_budget_forecast).
- Monte Carlo simulation coordination and Numba numerical kernel (get_monte_carlo_fire_batch, _run_mc_simulations_numba).
- Stochastic scenario forecasting and replay provenance (derive_monthly_seed, derive_simulation_seed_offset, build_monthly_seed_expr).

Does not own
-------------
- Configuration loading (owned by config.financial_rules).
- Gold FIRE table persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from personal_finance_etl.domain.fire.deterministic import WealthRiskAnalyticsBuilder
from personal_finance_etl.domain.fire.forecasting import calculate_budget_forecast
from personal_finance_etl.domain.fire.inflation import InflationBuilder
from personal_finance_etl.domain.fire.reproducibility import (
    build_monthly_seed_expr,
    derive_monthly_seed,
    derive_simulation_seed_offset,
)
from personal_finance_etl.domain.fire.simulation import (
    _run_mc_simulations_numba,
    get_monte_carlo_fire_batch,
)

__all__ = [
    "InflationBuilder",
    "WealthRiskAnalyticsBuilder",
    "_run_mc_simulations_numba",
    "build_monthly_seed_expr",
    "calculate_budget_forecast",
    "derive_monthly_seed",
    "derive_simulation_seed_offset",
    "get_monte_carlo_fire_batch",
]
