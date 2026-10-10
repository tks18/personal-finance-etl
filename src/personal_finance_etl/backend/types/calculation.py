"""Typed result containers for financial calculations.

Separating these from `types/analytics.py` keeps domain types (SnapshotRecord,
CashflowRecord) decoupled from pure-math result types (XirrResult).
"""

from dataclasses import dataclass


@dataclass
class XirrResult:
    """Typed result of an XIRR calculation. Replaces bare float | NaN propagation.

    Invariant: value is None when status != 'VALID'.

    Statuses
    --------
    VALID           Solver converged; ``value`` is reliable.
    INVALID_INPUT   Degenerate cashflows (all same sign, empty, < 2 entries).
    UNDEFINED       Solver returned None (e.g. zero-length holding period).
    NON_CONVERGENT  Newton's method did not converge within tolerance.
    """

    value: float | None  # None for all non-VALID statuses
    status: str  # VALID | UNDEFINED | NON_CONVERGENT | INVALID_INPUT
    reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """True only when the solver converged and the value is trustworthy."""
        return self.status == "VALID"

    def as_float(self, fallback: float = float("nan")) -> float:
        """Return the numeric value, or *fallback* (default NaN) if not VALID.

        Using NaN as the default fallback (rather than 0.0) ensures that
        downstream aggregations surface the missing computation rather than
        silently treating it as a zero return.
        """
        return self.value if self.value is not None else fallback
