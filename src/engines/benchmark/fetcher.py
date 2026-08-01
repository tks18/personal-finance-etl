import time
from datetime import date, timedelta

import polars as pl
import yfinance as yf  # type: ignore[import-untyped]


class BenchmarkDataFetcher:
    """Handles fetching and normalising single ticker data from yfinance."""

    @staticmethod
    def fetch_ticker(
        row: dict[str, str],
        start_dt: date,
        end_dt: date,
        fetch_start: date,
        df_full_idx: pl.DataFrame,
        cached_df: pl.DataFrame | None = None,
    ) -> tuple[pl.DataFrame, dict[str, str], str | None]:
        ticker = str(row.get("yF_Ticker", "")).strip()
        if not ticker:
            return pl.DataFrame(), row, f"Warning: Skipping empty ticker row ID {row.get('ID')}"

        try:
            ticker_cached = None
            if cached_df is not None and not cached_df.is_empty():
                ticker_cached = cached_df.filter(pl.col("yF_Ticker") == ticker)
                if not ticker_cached.is_empty():
                    max_date_val = ticker_cached.select(pl.max("Date")).item()
                    if max_date_val and max_date_val >= start_dt:
                        if max_date_val >= end_dt:
                            df_full = ticker_cached.filter(
                                (pl.col("Date") >= start_dt) & (pl.col("Date") <= end_dt)
                            )
                            df_full = df_full_idx.join(df_full, on="Date", how="left")
                            df_full = df_full.with_columns(
                                pl.col("Close").forward_fill().backward_fill(),
                                pl.lit(row["ID"]).alias("ID"),
                                pl.lit(row["Benchmark_Name"]).alias("Benchmark_Name"),
                                pl.lit(ticker).alias("yF_Ticker"),
                                pl.lit(row["Currency"]).alias("Currency"),
                            )
                            return df_full, row, f"✓ Cached {ticker}"
                        else:
                            fetch_start = max_date_val + timedelta(days=1)

            hist_pd = None
            if fetch_start <= end_dt:
                for attempt in range(3):
                    try:
                        ticker_obj = yf.Ticker(ticker)
                        hist_pd = ticker_obj.history(
                            start=fetch_start, end=end_dt + timedelta(days=1)
                        )
                        break
                    except Exception as e:
                        if attempt == 2:
                            raise e
                        time.sleep(1 + attempt * 2)

            if (hist_pd is None or hist_pd.empty) and fetch_start <= end_dt:
                return pl.DataFrame(), row, f"Warning: No data available for {ticker}"

            df_new = pl.DataFrame()
            if hist_pd is not None and not hist_pd.empty:
                hist_pd.index = hist_pd.index.tz_localize(None).normalize()  # type: ignore[attr-defined]
                hist_pl = pl.from_pandas(hist_pd.reset_index())

                if "Date" not in hist_pl.columns:
                    hist_pl = hist_pl.rename({"index": "Date"})

                df_new = hist_pl.select(
                    [pl.col("Date").cast(pl.Date), pl.col("Close").cast(pl.Float64)]
                )

                # Reindex using a join against the expected range
                expected_range = pl.DataFrame(
                    {"Date": pl.date_range(fetch_start, end_dt, "1d", eager=True).cast(pl.Date)}
                )
                df_new = expected_range.join(df_new, on="Date", how="left").with_columns(
                    pl.col("Close").forward_fill().backward_fill(),
                    pl.lit(row["ID"]).alias("ID"),
                    pl.lit(row["Benchmark_Name"]).alias("Benchmark_Name"),
                    pl.lit(ticker).alias("yF_Ticker"),
                    pl.lit(row["Currency"]).alias("Currency"),
                )

            if ticker_cached is not None and not ticker_cached.is_empty():
                df_full = pl.concat([ticker_cached, df_new], how="vertical")
            else:
                df_full = df_new

            df_full = df_full_idx.join(df_full, on="Date", how="left").with_columns(
                pl.col("Close").forward_fill().backward_fill(),
                pl.lit(row["ID"]).alias("ID"),
                pl.lit(row["Benchmark_Name"]).alias("Benchmark_Name"),
                pl.lit(ticker).alias("yF_Ticker"),
                pl.lit(row["Currency"]).alias("Currency"),
            )

            warn_msg = None
            if hist_pd is not None and not hist_pd.empty:
                pct_drops = hist_pd["Close"].pct_change()
                huge_drops = pct_drops[pct_drops < -0.4]
                if not huge_drops.empty:
                    drop_dts = [d.strftime("%Y-%m-%d") for d in huge_drops.index]
                    warn_msg = f"⚠ Anomalous drops (>40%) in {ticker} on {', '.join(drop_dts)} (Unadjusted split?)"

            msg = f"✓ Fetched {ticker}" if not warn_msg else f"✓ Fetched {ticker}. {warn_msg}"
            return df_full, row, msg

        except Exception as e:
            return pl.DataFrame(), row, f"Error on {ticker}: {str(e)}"
