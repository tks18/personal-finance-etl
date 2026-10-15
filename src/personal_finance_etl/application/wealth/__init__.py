"""Wealth and financial planning application services.

Owns
----
- WealthService: Coordinates net worth, cashflow statement, budget, wealth risk, and FIRE workflows.
- WealthPresentationEngine: Architectural alias for WealthService.

Does not own
-------------
- Net worth domain builder (owned by domain.wealth.net_worth).
- Monte Carlo numerical kernel (owned by domain.fire.simulation).
- UI reporting or charts (owned by presentation).
"""

from __future__ import annotations

from personal_finance_etl.application.wealth.wealth_service import (
    WealthPresentationEngine,
    WealthService,
)

__all__ = ["WealthPresentationEngine", "WealthService"]
