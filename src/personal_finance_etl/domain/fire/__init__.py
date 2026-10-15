"""Financial Independence & Retire Early (FIRE) simulation domain.

Owns
----
- Deterministic FI milestone calculations (Target FI, Lean FI, Coast FI).
- Inflation modeling and real-return adjustments.
- Monte Carlo simulation coordination and Numba numerical kernel.
- Stochastic scenario forecasting and replay provenance.

Does not own
-------------
- Configuration loading (owned by config.financial_rules).
- Gold FIRE table persistence (owned by infrastructure.warehouse).
"""

