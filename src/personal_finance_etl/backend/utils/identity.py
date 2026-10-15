"""DEPRECATED - Legacy identity utility shim module.

This module has been deactivated as part of Phase 2 of the Grand Refactor.
Canonical deterministic ID generation now resides in:
`personal_finance_etl.domain.common.identity`

This file is maintained strictly as a backwards-compatible pass-through delegation shim.
Do not edit or add logic here.
"""

from personal_finance_etl.domain.common.identity import (
    _IDENTITY_FIELD_ORDERS,  # pyright: ignore[reportPrivateUsage]
    _ordered_identity_fields,  # pyright: ignore[reportPrivateUsage]
    canonicalize_value,
    generate_deterministic_id,
)

__all__ = [
    "_IDENTITY_FIELD_ORDERS",
    "_ordered_identity_fields",
    "canonicalize_value",
    "generate_deterministic_id",
]
