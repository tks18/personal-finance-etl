"""Deterministic entity identity generation using Canonical ID Serialization v2.

Owns
----
- Canonical ID Serialization v2 for all business and financial entities.
- Stable field ordering for established identity contracts (PURCHASE, SALE, LOT, REALIZED, RECON, TAX).
- Canonical string serialization of dates, booleans, floating-point/decimal numbers, and Unicode.
- Cryptographic SHA-256 deterministic ID generation.

Does not own
-------------
- Entity schema definitions or record containers (owned by domain.*.contracts).
- Storage or persistence of entities (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

# Preserve the established v2 serialization order for known identity contracts.
# This makes the output independent of caller dict construction order without
# silently changing existing IDs. Add a contract here whenever a namespace's
# defining fields change.
_IDENTITY_FIELD_ORDERS: dict[str, tuple[tuple[str, ...], ...]] = {
    "PURCHASE": (("ISIN", "Date", "Price", "Quantity", "CURRENCY_ID"),),
    "SALE": (("ISIN", "Date", "Sell_Price", "Quantity", "CURRENCY_ID"),),
    "LOT": (
        ("ISIN", "Purchase_ID", "Quantity", "Date"),
        ("ISIN", "Date", "Quantity", "Price", "Currency", "Event"),
        ("ISIN", "Date", "Quantity", "Price", "Currency", "Event", "Recon_Group"),
        ("ISIN", "Event", "Recon_Group"),
    ),
    "REALIZED": (("Sale_ID", "Lot_ID"),),
    "RECON_GROUP": (
        (
            "ISIN",
            "Reconciliation_Date",
            "Adjustment_Type",
            "Broker_Quantity",
            "Reconstructed_Quantity",
            "Broker_Cost_Basis",
            "Reconstructed_Cost_Basis",
        ),
    ),
    "RECON_EVENT": (("Reconciliation_Group_ID", "Lot_ID", "Adjustment_Type"),),
    "RECON_LOT_GROUP": (("ISIN", "Reconciliation_Date", "Adjustment_Type", "Quantity"),),
    "TAX": (("Source_Type", "Source_ID", "Tax_Sub_Head"),),
}


def canonicalize_value(val: object) -> str:
    """Normalize any Python value into a canonical string for deterministic hashing.

    Parameters
    ----------
    val : object
        The value to normalize.

    Returns
    -------
    str
        Deterministic string representation.
    """
    match val:
        case None:
            return "<NULL>"
        case bool():
            return "true" if val else "false"
        case datetime():
            return val.isoformat()
        case date():
            return val.strftime("%Y-%m-%d")
        case int() | float() | Decimal():
            try:
                d = Decimal(str(val)).normalize()
                if d.is_zero():
                    return "0"
                return format(d, "f")
            except InvalidOperation:
                return str(val)
        case str():
            nfc = unicodedata.normalize("NFC", val)
            return nfc.strip()
        case _:
            return str(val).strip()


def _ordered_identity_fields(
    namespace: str, fields: Mapping[str, object]
) -> list[tuple[str, object]]:
    """Return identity fields in a contract-defined, caller-order-independent order."""
    keys = set(fields)
    for field_order in _IDENTITY_FIELD_ORDERS.get(namespace, ()):
        if keys == set(field_order):
            return [(key, fields[key]) for key in field_order]

    # Unknown/new contracts remain deterministic rather than inheriting insertion
    # order. Add a namespace contract above if its field order must be semantic.
    return [(key, fields[key]) for key in sorted(fields)]


def generate_deterministic_id(namespace: str, fields: Mapping[str, object]) -> str:
    """Generate a stable deterministic ID using Canonical ID Serialization v2.

    Parameters
    ----------
    namespace : str
        The entity namespace prefix (e.g., 'PURCHASE', 'SALE', 'LOT', 'TAX').
    fields : Mapping[str, object]
        Dictionary of identifying fields for the entity.

    Returns
    -------
    str
        Prefix and first 16 characters of SHA-256 hex digest, formatted as '{namespace}_{hash}'.
    """
    pairs = [
        [canonicalize_value(key), canonicalize_value(value)]
        for key, value in _ordered_identity_fields(namespace, fields)
    ]
    payload = json.dumps(
        [namespace, "v2", pairs], ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    hash_str = hashlib.sha256(payload).hexdigest()
    return f"{namespace}_{hash_str[:16]}"
