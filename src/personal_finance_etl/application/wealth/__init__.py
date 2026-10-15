"""Wealth and financial planning application services.

Owns
----
- Coordinating net worth, cashflow statement, budget, and wealth risk workflows.
- Coordinating deterministic FIRE forecasting and Monte Carlo simulations.

Does not own
-------------
- Net worth domain builder (owned by domain.wealth.net_worth).
- Monte Carlo numerical kernel (owned by domain.fire.simulation).
- UI reporting or charts (owned by presentation).
"""
