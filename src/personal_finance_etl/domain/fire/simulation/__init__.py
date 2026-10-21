"""Monte Carlo stochastic simulation kernel and FIRE probability engine facade.

Owns
----
- get_monte_carlo_fire_batch: Vectorized Polars batch mapping function converting time series features into stochastic distributions.
- _run_mc_simulations_numba: High-performance Numba JIT-compiled Monte Carlo simulation kernel.

Does not own
-------------
- Deterministic FIRE targets (owned by domain.fire.deterministic).
- Historical inflation series construction (owned by domain.fire.inflation).
"""

from __future__ import annotations

from personal_finance_etl.domain.fire.simulation.batch import get_monte_carlo_fire_batch
from personal_finance_etl.domain.fire.simulation.kernel import _run_mc_simulations_numba

__all__ = ["_run_mc_simulations_numba", "get_monte_carlo_fire_batch"]
