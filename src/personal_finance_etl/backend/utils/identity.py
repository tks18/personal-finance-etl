import hashlib
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


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


def generate_deterministic_id(namespace: str, fields: dict[str, Any]) -> str:
    """
    Generates a Canonical ID using Canonical ID Serialization v1.

    Args:
        namespace: The ID namespace (e.g., 'PURCHASE', 'SALE', 'LOT')
        fields: An ordered dictionary of fields defining the identity.
                The insertion order dictates the field order in serialization.

    Returns:
        The deterministic ID string.
    """
    canonical_parts: list[str] = []
    for key, val in fields.items():
        k_canon = canonicalize_value(key)
        v_canon = canonicalize_value(val)
        canonical_parts.append(f"{k_canon}={v_canon}")

    payload = "|".join([namespace] + canonical_parts).encode("utf-8")
    hash_str = hashlib.sha256(payload).hexdigest()
    return f"{namespace}_{hash_str[:16]}"
