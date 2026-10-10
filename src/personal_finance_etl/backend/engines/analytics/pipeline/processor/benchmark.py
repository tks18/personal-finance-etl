import math
from bisect import bisect_right
from datetime import date, datetime

import polars as pl

from personal_finance_etl.backend.utils.helpers import to_date_obj


class BenchmarkPriceProvider:
    """Validated benchmark lookup with bounded previous-close fallback.

    Transaction and month-end dates often fall on weekends or market holidays.
    For those dates, use the latest prior valid close only when it is no more than
    ``max_staleness_days`` calendar days old. Missing/stale prices remain missing;
    the provider never fabricates a zero or looks forward in time.
    """

    bm_price_map: dict[date, float]
    MAX_STALENESS_DAYS = 7

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
        self._dates: list[date] = []
        if prebuilt_map is not None:
            self._load_map(prebuilt_map)
            return

        if df_b is None or not bench_id or not str(bench_id).strip():
            return

        required = {"ID", "Date", "Close"}
        missing = sorted(required - set(df_b.columns))
        if missing:
            raise ValueError(f"Benchmark data is missing required columns: {missing}")

        b_subset = df_b.filter(pl.col("ID").cast(pl.String) == str(bench_id).strip()).sort("Date")
        for row in b_subset.select(["Date", "Close"]).to_dicts():
            raw_date = row["Date"]
            d_val = (
                raw_date
                if isinstance(raw_date, date) and not isinstance(raw_date, datetime)
                else to_date_obj(raw_date)
            )
            if d_val is None:
                raise ValueError(
                    f"Benchmark {bench_id!r} contains an invalid observation date: {raw_date!r}"
                )
            raw_price = row["Close"]
            if raw_price is None:
                raise ValueError(
                    f"Benchmark {bench_id!r} has a null close on {d_val}; "
                    "missing observations must remain unavailable."
                )
            price = float(raw_price)
            if not math.isfinite(price) or price <= 0:
                raise ValueError(
                    f"Benchmark {bench_id!r} has an invalid close on {d_val}: {raw_price!r}"
                )
            self.bm_price_map[d_val] = price
        self._dates = sorted(self.bm_price_map)

    def _load_map(self, values: dict[date, float]) -> None:
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
