"""Pattern matching and adjustment classification for Indian Rights Entitlement ISINs.

Owns
----
- is_indian_rights_entitlement_isin: Heuristic matching for candidate Indian Rights Entitlement codes.
- is_zero_proceeds_re_adjustment: Validation for zero-proceeds non-transaction adjustments.

Does not own
-------------
- Chronological simulation execution (owned by application.investments.isin_processor).
- Multiprocessing pipeline pooling (owned by application.investments.isin_pipeline).
"""

from __future__ import annotations

import math

__all__ = [
    "is_indian_rights_entitlement_isin",
    "is_zero_proceeds_re_adjustment",
]


def is_indian_rights_entitlement_isin(isin: str | None) -> bool:
    """Return whether an Indian ISIN matches the observed RE code pattern.

    The ``20`` substring is a candidate classifier (Python slice [7:9]), not
    proof of an expiry event. Transaction-level checks are still required.

    Parameters
    ----------
    isin : str | None
        Candidate ISIN string to inspect.

    Returns
    -------
    bool
        True if the string matches the Indian RE pattern, False otherwise.
    """
    if not isin:
        return False

    normalized = isin.strip().upper()
    return len(normalized) == 12 and normalized.startswith("INE") and normalized[7:9] == "20"


def is_zero_proceeds_re_adjustment(
    isin: str,
    quantity: float,
    price: float,
    proceeds: float | None,
) -> bool:
    """Recognize a zero-proceeds adjustment for a candidate Indian RE ISIN.

    Require an explicit zero proceeds value. Missing proceeds are not enough
    evidence to bypass normal sale-price validation.

    Parameters
    ----------
    isin : str
        Instrument ISIN code.
    quantity : float
        Transaction quantity.
    price : float
        Unit transaction price.
    proceeds : float | None
        Total sale proceeds reported by broker.

    Returns
    -------
    bool
        True if transaction qualifies as a zero-proceeds RE adjustment, False otherwise.
    """
    if not is_indian_rights_entitlement_isin(isin) or quantity <= 0:
        return False
    if not math.isfinite(price) or price != 0.0 or proceeds is None:
        return False

    try:
        proceeds_value = float(proceeds)
    except (TypeError, ValueError):
        return False

    return math.isfinite(proceeds_value) and proceeds_value == 0.0
