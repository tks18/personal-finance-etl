"""Typed calculation results and financial calculation statuses.

Owns
----
- CalculationStatus canonical computation and observation statuses.
- XirrResult typed result of an XIRR calculation.
- CagrResult typed result of a CAGR calculation.
- CpiResult typed result of a CPI index derivation.

Does not own
-------------
- Specific quantitative portfolio state (owned by domain.investments).
- Raw numerical solvers (owned by domain.investments.performance).
"""

from dataclasses import dataclass
from enum import StrEnum


class CalculationStatus(StrEnum):
    """Canonical financial computation and observation statuses."""

    VALID = "VALID"
    MISSING_INPUT = "MISSING_INPUT"
    INVALID_INPUT = "INVALID_INPUT"
    UNDEFINED = "UNDEFINED"
    NO_OBSERVATION = "NO_OBSERVATION"
    STALE_EVIDENCE = "STALE_EVIDENCE"
    NON_CONVERGENT = "NON_CONVERGENT"
    COMPUTATION_ERROR = "COMPUTATION_ERROR"


@dataclass(frozen=True)
class XirrResult:
    """Typed result of an XIRR calculation. Replaces bare float | NaN propagation.

    Invariant: value is None when status != 'VALID'.

    Statuses
    --------
    VALID : Solver converged; ``value`` is reliable.
    INVALID_INPUT : Degenerate cashflows (all same sign, empty, < 2 entries).
    UNDEFINED : Solver returned None (e.g. zero-length holding period).
    NON_CONVERGENT : Newton's method did not converge within tolerance.
    """

    value: float | None
    status: CalculationStatus | str
    reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Return True only when the solver converged and the value is trustworthy."""
        return self.status in (CalculationStatus.VALID, "VALID")

    def as_float(self, fallback: float = float("nan")) -> float:
        """Return the numeric value, or *fallback* (default NaN) if not VALID.

        Using NaN as the default fallback (rather than 0.0) ensures that
        downstream aggregations surface the missing computation rather than
        silently treating it as a zero return.
        """
        return self.value if self.value is not None else fallback


@dataclass(frozen=True)
class CagrResult:
    """Typed result of a CAGR calculation. Replaces bare float sentinel 0.0.

    Invariant: value is None when status != 'VALID'.

    Statuses
    --------
    VALID : Calculated successfully; ``value`` is reliable.
    INVALID_INPUT : Degenerate inputs (start_val <= 0, end_val <= 0, days <= 0).
    UNDEFINED : Zero holding period or economically undefined ratio.
    COMPUTATION_ERROR : Arithmetic overflow or numerical failure.
    """

    value: float | None
    status: CalculationStatus | str
    reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Return True only when CAGR was calculated successfully."""
        return self.status in (CalculationStatus.VALID, "VALID")

    def as_float(self, fallback: float = float("nan")) -> float:
        """Return the numeric value, or *fallback* (default NaN) if not VALID."""
        return self.value if self.value is not None else fallback


@dataclass(frozen=True)
class CpiResult:
    """Typed result of a CPI index derivation. Prevents fallback to 100.0 masquerading as success.

    Invariant: value is None when status != 'VALID'.

    Statuses
    --------
    VALID : Latest CPI derived successfully from series.
    NO_OBSERVATION : No inflation series observations found in source tables.
    INVALID_INPUT : Inflation parameter inputs are invalid or incomplete.
    COMPUTATION_ERROR : Unexpected computation exception during derivation.
    """

    value: float | None
    status: CalculationStatus | str
    reason: str | None = None

    @property
    def is_valid(self) -> bool:
        """Return True only when CPI was derived successfully."""
        return self.status in (CalculationStatus.VALID, "VALID")

    def as_float(self, fallback: float = float("nan")) -> float:
        """Return the numeric value, or *fallback* (default NaN) if not VALID."""
        return self.value if self.value is not None else fallback
