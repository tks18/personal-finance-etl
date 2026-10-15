"""DEPRECATED: Legacy Monte Carlo simulation module.

Superseded by `personal_finance_etl.domain.fire.simulation`.
Maintained as a pass-through delegation shim for backward compatibility.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.domain.fire.simulation import (
    _run_mc_simulations_numba,
    get_monte_carlo_fire_batch,
)

warnings.warn(
    "personal_finance_etl.backend.engines.presentation.helpers.fire_mc_sim is deprecated. "
    "Use personal_finance_etl.domain.fire.simulation instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["_run_mc_simulations_numba", "get_monte_carlo_fire_batch"]
