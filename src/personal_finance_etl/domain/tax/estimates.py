"""Tax estimation and ordinary income rate resolution domain logic.

Owns
----
- TaxEstimator: Resolves applicable ordinary income slab rates from macro parameter tables.
- Cleans and bounds tax rates and estimated tax figures.
- Provides indicative estimate calculations for ledger income events.

Does not own
-------------
- Statutory set-off, loss carry-forward, or final liability (presentation only).
- Income classification rules (owned by domain.tax.classification).
- TaxEvent schema and normalization (owned by domain.tax.events).
"""

from __future__ import annotations

import math
from datetime import date

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.market.macro import FYMacroParametersTable

__all__ = ["TaxEstimator"]


class TaxEstimator:
    """Calculates indicative tax rates and estimates for taxable events."""

    @staticmethod
    def resolve_ordinary_income_rate(
        macro_table: FYMacroParametersTable | None,
        rules: FinancialRules | None,
        event_date: date,
    ) -> float | None:
        """Resolve a configured ordinary-income estimate rate for the event date.

        Parameters
        ----------
        macro_table : FYMacroParametersTable | None
            Loaded fiscal year macro parameters table.
        rules : FinancialRules | None
            Global financial rules configuration.
        event_date : date
            Date of the income event.

        Returns
        -------
        float | None
            Ordinary income tax rate between 0.0 and 1.0, or None if unavailable.
        """
        if macro_table is not None:
            rate = macro_table.get_ordinary_income_rate(event_date)
        elif rules is not None:
            rate = rules.assumptions.macro.fallback_ordinary_income_rate
        else:
            return None

        try:
            rate_val = float(rate)
        except (TypeError, ValueError, OverflowError):
            return None

        return rate_val if math.isfinite(rate_val) and 0.0 <= rate_val <= 1.0 else None

    @staticmethod
    def clean_optional_finite_number(value: object) -> float | None:
        """Return a finite numeric value, preserving missing/invalid values as None."""
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError, OverflowError):
            return None
        return number if math.isfinite(number) else None

    @classmethod
    def clean_applied_rate(cls, value: object) -> float | None:
        """Clean and bound a tax rate to [0.0, 1.0]."""
        num = cls.clean_optional_finite_number(value)
        return num if num is not None and 0.0 <= num <= 1.0 else None

    @classmethod
    def clean_estimated_tax(cls, value: object) -> float | None:
        """Clean and bound an estimated tax amount to non-negative."""
        num = cls.clean_optional_finite_number(value)
        return num if num is not None and num >= 0.0 else None
