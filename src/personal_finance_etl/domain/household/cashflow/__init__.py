"""Household cashflow domain models and statement builders.

Owns
----
- CashflowStatementBuilder: Reconciles direct method cashflows across CASH_POOL assets.
- MonthlyCashflowSummaryBuilder: Aggregates cashflow efficiency, savings rates, and burn ratios.

Does not own
-------------
- Ledger accounting transactions (owned by domain.household.ledger).
- Presentation schemas or persistence (owned by presentation and infrastructure.warehouse).
"""

from __future__ import annotations

from personal_finance_etl.domain.household.cashflow.statement import CashflowStatementBuilder
from personal_finance_etl.domain.household.cashflow.summary import MonthlyCashflowSummaryBuilder

__all__ = ["CashflowStatementBuilder", "MonthlyCashflowSummaryBuilder"]
