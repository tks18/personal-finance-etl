"""Wealth and net worth domain analytics.

Owns
----
- Net worth builder and calculation across asset classes (NetWorthBuilder).
- Wealth health scoring and financial resilience ratios (HealthScorer, calculate_budget_health_score).
- Investment management analytics, rebalancing drift, and tax harvesting priority (InvestmentAnalyticsBuilder).

Does not own
-------------
- Portfolio snapshots (owned by domain.investments).
- Desktop GUI rendering (owned by presentation.desktop).
"""

from __future__ import annotations

from personal_finance_etl.domain.wealth.analytics import InvestmentAnalyticsBuilder
from personal_finance_etl.domain.wealth.net_worth import NetWorthBuilder
from personal_finance_etl.domain.wealth.scoring import HealthScorer, calculate_budget_health_score

__all__ = [
    "HealthScorer",
    "InvestmentAnalyticsBuilder",
    "NetWorthBuilder",
    "calculate_budget_health_score",
]
