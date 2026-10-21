"""Household financial domain.

Owns
----
- Household ledger modelling (LedgerBuilder).
- Cashflow statement generation and monthly summaries (CashflowStatementBuilder, MonthlyCashflowSummaryBuilder).
- Deterministic budget forecasting (BudgetForecastBuilder).
- Expense and spending analytics (ExpenseAnalyticsBuilder, SpendAnalyticsBuilder).
- Income stream analysis (IncomeStreamsBuilder).

Does not own
-------------
- Raw extraction of SQLite or CSV evidence (owned by infrastructure.providers).
- Investment lot accounting (owned by domain.investments).
- UI presentation or tab rendering (owned by presentation).
"""

from personal_finance_etl.domain.household.budget import BudgetForecastBuilder
from personal_finance_etl.domain.household.cashflow import (
    CashflowStatementBuilder,
    MonthlyCashflowSummaryBuilder,
)
from personal_finance_etl.domain.household.expense import (
    ExpenseAnalyticsBuilder,
    SpendAnalyticsBuilder,
)
from personal_finance_etl.domain.household.income import IncomeStreamsBuilder
from personal_finance_etl.domain.household.ledger import LedgerBuilder

__all__ = [
    "BudgetForecastBuilder",
    "CashflowStatementBuilder",
    "ExpenseAnalyticsBuilder",
    "IncomeStreamsBuilder",
    "LedgerBuilder",
    "MonthlyCashflowSummaryBuilder",
    "SpendAnalyticsBuilder",
]
