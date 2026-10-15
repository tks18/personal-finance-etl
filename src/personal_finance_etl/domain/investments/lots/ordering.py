"""Canonical ordering policy for same-day FIFO lot sequencing.

Owns
----
- CanonicalOrderPolicy deterministic lot ordering rule for purchases and sales.
- Date ASC -> Price ASC (exact Decimal comparison) -> ID string ASC.
- Module-level sort_purchases and sort_sales functions.

Does not own
-------------
- Stateful FIFO matching algorithm (owned by domain.investments.lots.fifo).
- Identification hashing (owned by domain.common.identity).
"""

from decimal import Decimal
from typing import Any


class CanonicalOrderPolicy:
    """Deterministic lot-ordering policy for FIFO processing.

    Wraps the same-day sort rule as a first-class object so that the policy
    can be injected, tested, and overridden independently of the FIFO engine.

    Usage
    -----
    policy = CanonicalOrderPolicy()
    sorted_purchases = policy.sort_purchases(raw_purchases)
    sorted_sales     = policy.sort_sales(raw_sales)
    """

    def sort_purchases(self, purchases: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort purchase lots: Date ASC → Price ASC (Decimal) → Purchase_ID ASC.

        Parameters
        ----------
        purchases:
            Raw list of purchase dicts as returned by the extractor.

        Returns
        -------
        list[dict]:
            New list sorted according to the canonical ordering rule.
        """
        return sorted(
            purchases,
            key=lambda x: (
                x.get("Date"),
                Decimal(str(x.get("Price", x.get("Buy_Price_Local", 0.0)))),
                str(x.get("Purchase_ID", "")),
            ),
        )

    def sort_sales(self, sales: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Sort sale lots: Date ASC → Sell_Price ASC (Decimal) → Sale_ID ASC.

        Parameters
        ----------
        sales:
            Raw list of sale dicts as returned by the extractor.

        Returns
        -------
        list[dict]:
            New list sorted according to the canonical ordering rule.
        """
        return sorted(
            sales,
            key=lambda x: (
                x.get("Date"),
                Decimal(str(x.get("Sell_Price", x.get("Price", 0.0)))),
                str(x.get("Sale_ID", "")),
            ),
        )


_default_policy = CanonicalOrderPolicy()


def sort_purchases(purchases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort purchases using the canonical ordering policy.

    Delegates to :class:`CanonicalOrderPolicy`. Preserved for backward
    compatibility — prefer instantiating ``CanonicalOrderPolicy`` directly in
    new code so the policy is explicit and testable.
    """
    return _default_policy.sort_purchases(purchases)


def sort_sales(sales: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort sales using the canonical ordering policy.

    Delegates to :class:`CanonicalOrderPolicy`. Preserved for backward
    compatibility — prefer instantiating ``CanonicalOrderPolicy`` directly in
    new code so the policy is explicit and testable.
    """
    return _default_policy.sort_sales(sales)

