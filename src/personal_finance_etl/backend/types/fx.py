"""Typed result for FX rate provider lookups.

``FXObservation`` replaces raw ``float | None`` returns from
``FXProvider.get_rate()``.  Callers can now distinguish a genuine rate of 0.0
from a missing observation (which used to be indistinguishable from ``None``
returned as ``float("nan")``).
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class FXObservation:
    """A single foreign-exchange rate observation."""

    rate: float | None
    currency: str
    observation_date: date
    is_interpolated: bool = False

    @property
    def is_missing(self) -> bool:
        """True when no rate is available for this date × currency pair."""
        return self.rate is None

    def as_float(self, fallback: float = float("nan")) -> float:
        """Return the rate, or *fallback* (default NaN) when missing.

        Using NaN as the default makes missing rates visible in aggregations
        (NaN propagates) rather than silently using 1.0 or 0.0.
        """
        return self.rate if self.rate is not None else fallback
