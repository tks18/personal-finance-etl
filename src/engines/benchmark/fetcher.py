import time
import pandas as pd
import polars as pl
import yfinance as yf  # type: ignore[import-untyped]


class BenchmarkDataFetcher:
    """Handles fetching and normalising single ticker data from yfinance."""
    @staticmethod
    def fetch_ticker(
        row: dict[str, str],
        start_dt: pd.Timestamp,
        end_dt: pd.Timestamp,
        fetch_start: pd.Timestamp,
        full_idx: pd.DatetimeIndex,
        cached_df: pl.DataFrame | None = None,
    ) -> tuple[pd.DataFrame, dict[str, str], str | None]:
        ticker = str(row.get("yF_Ticker", "")).strip()
        if not ticker:
            return pd.DataFrame(), row, f"Warning: Skipping empty ticker row ID {row.get('ID')}"

        try:
            ticker_cached = None
            if cached_df is not None and not cached_df.is_empty():
                ticker_cached = cached_df.filter(pl.col("yF_Ticker") == ticker)
                if not ticker_cached.is_empty():
                    max_date_val = ticker_cached.select(pl.max("Date")).item()
                    if max_date_val and pd.to_datetime(max_date_val) >= start_dt:
                        if pd.to_datetime(max_date_val) >= end_dt:
                            df_full = ticker_cached.filter(
                                (pl.col("Date") >= start_dt.date())
                                & (pl.col("Date") <= end_dt.date())
                            ).to_pandas()
                            df_full["Date"] = pd.to_datetime(df_full["Date"])
                            df_full = (
                                df_full.set_index("Date")
                                .reindex(full_idx)
                                .reset_index(names=["Date"])
                            )
                            df_full["Close"] = df_full["Close"].ffill().bfill()
                            df_full["ID"] = row["ID"]
                            df_full["Benchmark_Name"] = row["Benchmark_Name"]
                            df_full["yF_Ticker"] = ticker
                            df_full["Currency"] = row["Currency"]
                            return df_full, row, f"✓ Cached {ticker}"
                        else:
                            fetch_start = pd.to_datetime(max_date_val) + pd.Timedelta(days=1)

            hist = pd.DataFrame()
            if fetch_start <= end_dt:
                for attempt in range(3):
                    try:
                        ticker_obj = yf.Ticker(ticker)
                        hist = ticker_obj.history(
                            start=fetch_start, end=end_dt + pd.Timedelta(days=1)
                        )
                        break
                    except Exception as e:
                        if attempt == 2:
                            raise e
                        time.sleep(1 + attempt * 2)

            if hist.empty and fetch_start <= end_dt:
                return pd.DataFrame(), row, f"Warning: No data available for {ticker}"

            df_new = pd.DataFrame()
            if not hist.empty:
                hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
                df_new = (
                    hist[["Close"]]
                    .reindex(pd.date_range(start=fetch_start, end=end_dt))
                    .ffill()
                    .bfill()
                )
                df_new = df_new.reset_index(names=["Date"])
                df_new["ID"] = row["ID"]
                df_new["Benchmark_Name"] = row["Benchmark_Name"]
                df_new["yF_Ticker"] = ticker
                df_new["Currency"] = row["Currency"]

            if ticker_cached is not None and not ticker_cached.is_empty():
                df_cached_pd = ticker_cached.to_pandas()
                df_cached_pd["Date"] = pd.to_datetime(df_cached_pd["Date"])
                df_full = pd.concat([df_cached_pd, df_new], ignore_index=True)
            else:
                df_full = df_new

            df_full = df_full.set_index("Date").reindex(full_idx).reset_index(names=["Date"])
            df_full["Close"] = df_full["Close"].ffill().bfill()
            df_full["ID"] = row["ID"]
            df_full["Benchmark_Name"] = row["Benchmark_Name"]
            df_full["yF_Ticker"] = ticker
            df_full["Currency"] = row["Currency"]

            warn_msg = None
            if not hist.empty:
                pct_drops = hist["Close"].pct_change()
                huge_drops = pct_drops[pct_drops < -0.4]
                if not huge_drops.empty:
                    drop_dts = pd.to_datetime(huge_drops.index).strftime("%Y-%m-%d").tolist()
                    warn_msg = f"⚠ Anomalous drops (>40%) in {ticker} on {', '.join(drop_dts)} (Unadjusted split?)"

            msg = f"✓ Fetched {ticker}" if not warn_msg else f"✓ Fetched {ticker}. {warn_msg}"
            return df_full, row, msg

        except Exception as e:
            return pd.DataFrame(), row, f"Error on {ticker}: {str(e)}"
