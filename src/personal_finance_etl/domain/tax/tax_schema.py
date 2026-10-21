"""Canonical TaxEvent schema definition and typed dictionaries.

Owns
----
- TAX_EVENT_SCHEMA: Strict Typed schema definition for canonical tax events.
- TaxEventDict: Normalized tax event record dictionary structure.

Does not own
-------------
- Deterministic ID hashing (owned by domain.tax.tax_id).
- Evidence normalization and validation (owned by domain.tax.events).
- Statutory income head and sub-head classification rules (owned by domain.tax.classification).
"""

from __future__ import annotations

from datetime import date
from typing import TypedDict

import polars as pl

__all__ = [
    "TAX_EVENT_SCHEMA",
    "TaxEventDict",
]


class TaxEventDict(TypedDict, total=False):
    """Normalized tax event record dictionary."""

    FY: str
    Event_Date: date
    Source_Type: str
    Source_ID: str
    Income_Head: str
    Tax_Sub_Head: str
    Amount_INR: float
    Applied_Rate: float | None
    Estimated_Tax: float | None
    CURRENCY_ID: str | None
    Tax_Status: str
    Tax_Status_Reason: str | None
    ISIN: str | None
    Lot_ID: str | None


TAX_EVENT_SCHEMA: dict[str, pl.DataType] = {
    "Tax_Event_ID": pl.String(),
    "FY": pl.String(),
    "Event_Date": pl.Date(),
    "Source_Type": pl.String(),
    "Source_ID": pl.String(),
    "Income_Head": pl.String(),
    "Tax_Sub_Head": pl.String(),
    "Amount_INR": pl.Float64(),
    "Applied_Rate": pl.Float64(),
    "Estimated_Tax": pl.Float64(),
    "CURRENCY_ID": pl.String(),
    "Tax_Status": pl.String(),
    "Tax_Status_Reason": pl.String(),
    "ISIN": pl.String(),
    "Lot_ID": pl.String(),
}
