"""Benchmark valuation provider and historical close lookup.

Owns
----
- BenchmarkPriceProvider: Validated benchmark price lookup with bounded previous-close
  fallback for weekends and market holidays.

Does not own
-------------
- Benchmark API extraction and network retrieval (owned by infrastructure.providers.market.benchmark).
- Transformation of raw benchmark observations into Silver (owned by domain.market.benchmarks).
"""

import math
from bisect import bisect_right
from datetime import date, datetime
from typing import cast

import polars as pl

from personal_finance_etl.domain.common.dates import to_date_obj


class BenchmarkPriceProvider:
    """Validated benchmark lookup with bounded previous-close fallback.

    Transaction and month-end dates often fall on weekends or market holidays.
    For those dates, use the latest prior valid close only when it is no more than
    ``max_staleness_days`` calendar days old. Missing/stale prices remain missing;
    the provider never fabricates a zero or looks forward in time.
    """

    bm_price_map: dict[date, float]
    _dates: list[date]
    MAX_STALENESS_DAYS = 7

    @staticmethod
    def _parse_row_price(bench_id: str, row: dict[str, object]) -> tuple[date, float]:
        """Validate date and finite positive close price from a benchmark row."""
        raw_date = cast(str | date | datetime | None, row.get("Date"))
        d_val = (
            raw_date
            if isinstance(raw_date, date) and not isinstance(raw_date, datetime)
            else to_date_obj(raw_date)
        )
        if d_val is None:
            raise ValueError(
                f"Benchmark {bench_id!r} contains an invalid observation date: {raw_date!r}"
            )
        raw_price = row.get("Close")
        if raw_price is None:
            raise ValueError(
                f"Benchmark {bench_id!r} has a null close on {d_val}; "
                "missing observations must remain unavailable."
            )
        price = float(cast(float | int | str, raw_price))
        if not math.isfinite(price) or price <= 0:
            raise ValueError(
                f"Benchmark {bench_id!r} has an invalid close on {d_val}: {raw_price!r}"
            )
        return d_val, price

    def _load_dataframe(self, bench_id: str, df_b: pl.DataFrame) -> None:
        """Filter and load benchmark closing prices from DataFrame."""
        required = {"ID", "Date", "Close"}
        missing = sorted(required - set(df_b.columns))
        if missing:
            raise ValueError(f"Benchmark data is missing required columns: {missing}")

        b_subset = df_b.filter(pl.col("ID").cast(pl.String) == str(bench_id).strip()).sort("Date")
        for row in b_subset.select(["Date", "Close"]).to_dicts():
            d_val, price = self._parse_row_price(bench_id, row)
            self.bm_price_map[d_val] = price
        self._dates = sorted(self.bm_price_map)

    def __init__(
        self,
        bench_id: str | None,
        df_b: pl.DataFrame | None,
        prebuilt_map: dict[date, float] | None = None,
        max_staleness_days: int = MAX_STALENESS_DAYS,
    ):
        if max_staleness_days < 0:
            raise ValueError("max_staleness_days cannot be negative")
        self.max_staleness_days = max_staleness_days
        self.bm_price_map = {}
        self._dates = []
        if prebuilt_map is not None:
            self._load_map(prebuilt_map)
            return

        if df_b is not None and bench_id and str(bench_id).strip():
            self._load_dataframe(str(bench_id).strip(), df_b)

    def _load_map(self, values: dict[date, float]) -> None:
        """Populate internal benchmark price map from an existing date-to-price mapping.

        Parameters
        ----------
        values : dict[date, float]
            Dictionary of dates to benchmark prices.

        Raises
        ------
        ValueError
            If any date is invalid or if any price is non-finite or non-positive.
        """
        for raw_date, raw_price in values.items():
            d_val = (
                raw_date
                if raw_date and not isinstance(raw_date, datetime)
                else to_date_obj(raw_date)
            )
            if d_val is None:
                raise ValueError(f"Invalid date in prebuilt benchmark map: {raw_date!r}")
            price = float(raw_price)
            if not math.isfinite(price) or price <= 0:
                raise ValueError(
                    f"Invalid benchmark price in prebuilt map for {d_val}: {raw_price!r}"
                )
            self.bm_price_map[d_val] = price
        self._dates = sorted(self.bm_price_map)

    def get_bm_price(self, dt: date | datetime | str | None) -> float | None:
        """Retrieve benchmark closing price for date with bounded prior-close fallback.

        Parameters
        ----------
        dt : date | datetime | str | None
            Requested evaluation date.

        Returns
        -------
        float | None
            Exact or nearest prior benchmark close within max_staleness_days,
            or None if date is missing, invalid, or exceeds staleness bounds.
        """
        if dt is None:
            return None
        dt_val = dt if isinstance(dt, date) and not isinstance(dt, datetime) else to_date_obj(dt)
        if dt_val is None or not self._dates:
            return None
        exact = self.bm_price_map.get(dt_val)
        if exact is not None:
            return exact
        idx = bisect_right(self._dates, dt_val) - 1
        if idx < 0:
            return None
        prior_date = self._dates[idx]
        if (dt_val - prior_date).days > self.max_staleness_days:
            return None
        return self.bm_price_map[prior_date]


__all__ = ["BenchmarkPriceProvider"]
