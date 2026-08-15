from datetime import date, datetime, timedelta

import polars as pl

from personal_finance_etl.backend.utils.helpers import to_date_obj


class BenchmarkPriceProvider:
    def __init__(
        self,
        bench_id: str | None,
        df_b: pl.DataFrame | None,
        prebuilt_map: dict[date, float] | None = None,
    ):
        if prebuilt_map is not None:
            self.bm_price_map = prebuilt_map
            return

        self.bm_price_map: dict[date, float] = {}
        if df_b is not None and bench_id and str(bench_id).strip():
            try:
                b_subset = df_b.filter(pl.col("ID").cast(pl.String) == str(bench_id).strip()).sort(
                    "Date"
                )
                last_date, last_price = None, None
                for row in b_subset.select(["Date", "Close"]).to_dicts():
                    d_val = row["Date"]
                    if not isinstance(d_val, date):
                        d_val = to_date_obj(d_val)
                    if d_val:
                        p_val = float(row["Close"])
                        if last_date is not None and last_price is not None:
                            curr = last_date + timedelta(days=1)
                            while curr < d_val:
                                self.bm_price_map[curr] = last_price
                                curr += timedelta(days=1)
                        self.bm_price_map[d_val] = p_val
                        last_date, last_price = d_val, p_val
            except Exception:
                pass

    def get_bm_price(self, dt: date | datetime | str | None) -> float | None:
        if not dt:
            return None
        dt_val = dt if isinstance(dt, date) and not isinstance(dt, datetime) else to_date_obj(dt)
        if dt_val is None:
            return None
        return self.bm_price_map.get(dt_val)
