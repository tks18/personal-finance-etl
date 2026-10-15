"""Foreign exchange (FX) observation and rate domain models.

Owns
----
- FXObservation record for point-in-time exchange rates.
- Distinction between valid observed rates and missing rates.

Does not own
-------------
- External API calls to Yahoo Finance (owned by infrastructure.providers.market).
- Multi-currency portfolio accounting (owned by domain.investments).
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
        """Return True when no rate is available for this date × currency pair."""
        return self.rate is None

    def as_float(self, fallback: float = float("nan")) -> float:
        """Return the rate, or *fallback* (default NaN) when missing.

        Using NaN as the default makes missing rates visible in aggregations
        (NaN propagates) rather than silently using 1.0 or 0.0.
        """
        return self.rate if self.rate is not None else fallback

