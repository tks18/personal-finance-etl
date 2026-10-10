import hashlib
import json
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
    """Generate a stable deterministic ID using Canonical ID Serialization v2.

    v2 serializes fields as a JSON array of [key, canonical_value] pairs.
    This eliminates the v1 ambiguity where delimiter characters in values
    could produce identical pre-hash payloads for distinct field maps.

    The "v2" tag in the payload ensures v2 IDs never collide with v1 IDs
    even when the namespace and field values are identical.

    Args:
        namespace: ID namespace string (e.g. 'PURCHASE', 'LOT', 'TAX').
        fields: Ordered dict of identity fields. Insertion order is canonical.

    Returns:
        Deterministic ID string of the form ``{NAMESPACE}_{16-hex-chars}``.
    """
    pairs = [[canonicalize_value(k), canonicalize_value(v)] for k, v in fields.items()]
    payload = json.dumps([namespace, "v2", pairs], ensure_ascii=False, separators=(",", ":")
                         ).encode("utf-8")
    hash_str = hashlib.sha256(payload).hexdigest()
    return f"{namespace}_{hash_str[:16]}"
