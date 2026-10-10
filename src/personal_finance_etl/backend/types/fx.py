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
    """A single foreign-exchange rate observation.

    Attributes
    ----------
    rate:
        The exchange rate (base currency units per 1 unit of ``currency``).
        ``None`` when the rate is unavailable for this date.
    currency:
        The ISO currency code this observation applies to.
    observation_date:
        The date for which the rate was requested.
    is_interpolated:
        ``True`` when the rate was filled from a neighbouring date rather than
        a direct market observation.  Downstream callers may wish to flag
        interpolated values differently in analytics output.

    Usage
    -----
    Instead of:
        rate = fx_provider.get_rate(d, "USD")
        if rate is None: ...

    Prefer (when migrating call-sites to the new API):
        obs = fx_provider.get_observation(d, "USD")
        if obs.is_missing: ...
        rate = obs.rate
    """

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

