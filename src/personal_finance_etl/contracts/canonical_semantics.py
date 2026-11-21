"""Authoritative canonical semantic enumerations.

Owns
----
- HouseholdCategoryKind: Bounded semantic classification for household categories (income vs expense).
- HouseholdTransactionKind: Bounded semantic classification for household transaction observations.
- InvestmentAction: Source-agnostic canonical action for investment transaction events.

Does not own
------------
- Source-specific numeric or string codes (e.g. INOUTCOME transaction type codes 0/1/3/4 or BUY/REDEEM strings).
- Silver financial classification rules (e.g. active vs passive income, core vs non-core expenses).
- FIFO or tax lot matching algorithms (owned by domain.investments.lots).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "HouseholdCategoryKind",
    "HouseholdTransactionKind",
    "InvestmentAction",
]


class HouseholdCategoryKind(StrEnum):
    """Authoritative semantic classification for household category nodes."""

    INCOME = "income"
    EXPENSE = "expense"


class HouseholdTransactionKind(StrEnum):
    """Authoritative semantic classification for household transaction events."""

    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER_OUT = "transfer_out"
    TRANSFER_IN = "transfer_in"
    TRANSFER = "transfer"


class InvestmentAction(StrEnum):
    """Authoritative canonical action classification for investment transactions."""

    BUY = "buy"
    SELL = "sell"
    SPLIT = "split"
    BONUS = "bonus"
    DIVIDEND_REINVEST = "dividend_reinvest"
    RECONCILIATION = "reconciliation"
