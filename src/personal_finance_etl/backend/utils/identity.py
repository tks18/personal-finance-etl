import hashlib
import json
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

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


def canonicalize_value(val: Any) -> str:
    if val is None:
        return "<NULL>"
    elif isinstance(val, bool):
        return "true" if val else "false"
    elif isinstance(val, datetime):
        return val.isoformat()
    elif isinstance(val, date):
        return val.strftime("%Y-%m-%d")
    elif isinstance(val, (int, float, Decimal)):
        try:
            d = Decimal(str(val)).normalize()
            if d.is_zero():
                return "0"
            return format(d, "f")
        except InvalidOperation:
            return str(val)
    elif isinstance(val, str):
        nfc = unicodedata.normalize("NFC", val)
        return nfc.strip()
    else:
        return str(val).strip()


def _ordered_identity_fields(namespace: str, fields: dict[str, Any]) -> list[tuple[str, Any]]:
    """Return identity fields in a contract-defined, caller-order-independent order."""
    keys = set(fields)
    for field_order in _IDENTITY_FIELD_ORDERS.get(namespace, ()):
        if keys == set(field_order):
            return [(key, fields[key]) for key in field_order]

    # Unknown/new contracts remain deterministic rather than inheriting insertion
    # order. Add a namespace contract above if its field order must be semantic.
    return [(key, fields[key]) for key in sorted(fields)]


def generate_deterministic_id(namespace: str, fields: dict[str, Any]) -> str:
    """Generate a stable deterministic ID using Canonical ID Serialization v2.

    Known namespaces retain their established field order and hashes. New or
    changed field sets use sorted keys until an explicit order is registered.
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
