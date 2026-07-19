"""
BenchmarkEngine: Downloads and processes benchmark OHLC data via yfinance.

Uses ThreadPoolExecutor for highly concurrent fetching, implements robust
request Session handling with retries, and securely cleans data via forward
and backward filling to prevent edge cases with missing dates.
Supports caching from previous ETL runs to minimize API calls.
"""

import queue
import concurrent.futures
import time
import os
import glob
import sqlite3

import pandas as pd
import polars as pl
import yfinance as yf


class BenchmarkEngine:
    """
    Downloads benchmark price data concurrently for all tickers defined in a master CSV.
    Pushes progress tuples of (message, data_or_None, progress_float) to status_queue.
    """

    def __init__(
        self,
        df_m: pl.DataFrame,
        status_queue: queue.Queue,
        start_date=None,
        end_date=None,
        max_workers: int = 8,
        target_db_base_path: str | None = None,
        current_db_path: str | None = None,
    ):
        self.df_m = df_m
        self.status_queue = status_queue
        self.start_date = start_date
        self.end_date = end_date
        self.max_workers = max_workers
        self.target_db_base_path = target_db_base_path
        self.current_db_path = current_db_path

    def _get_cached_benchmark_data(self):
        """Scans the target DB base path for the most recent DB and loads f_Investment_Benchmark_Data."""
        if not self.target_db_base_path or not os.path.exists(self.target_db_base_path):
            return None

        # Search for .db files in subdirectories (outputs/FY/MM-YYYY/*.db)
        db_files = glob.glob(os.path.join(
            self.target_db_base_path, '**', '*.db'), recursive=True)
        if not db_files:
            return None

        if self.current_db_path:
            db_files = [f for f in db_files if os.path.abspath(
                f) != os.path.abspath(self.current_db_path)]

        if not db_files:
            return None

        latest_db = max(db_files, key=os.path.getmtime)
        self.status_queue.put(
            (f"Found recent cache DB: {os.path.basename(latest_db)}", None, 0.05))
        try:
            with sqlite3.connect(latest_db) as conn:
                df = pl.read_database(
                    "SELECT * FROM f_Investment_Benchmark_Data", conn)
                if not df.is_empty():
                    df = df.with_columns(pl.col("Date").cast(pl.Date))
                    return df
        except Exception as e:
            self.status_queue.put(
                (f"Warning: Failed to load cached benchmark data from {latest_db}: {e}", None, 0.05))
        return None

    def _fetch_ticker(self, row: dict, start_dt: pd.Timestamp, end_dt: pd.Timestamp,
                      fetch_start: pd.Timestamp, full_idx: pd.DatetimeIndex, cached_df: pl.DataFrame | None = None):
        """Worker function to fetch, normalize, and fill a single ticker."""
        ticker = str(row.get("yF_Ticker", "")).strip()
        if not ticker:
            return None, row, f"Warning: Skipping empty ticker row ID {row.get('ID')}"

        try:
            ticker_cached = None
            if cached_df is not None:
                ticker_cached = cached_df.filter(pl.col("yF_Ticker") == ticker)
                if not ticker_cached.is_empty():
                    max_date_val = ticker_cached.select(pl.max("Date")).item()
                    if max_date_val and pd.to_datetime(max_date_val) >= start_dt:
                        if pd.to_datetime(max_date_val) >= end_dt:
                            # Fully cached
                            df_full = ticker_cached.filter(
                                (pl.col("Date") >= start_dt.date()) & (
                                    pl.col("Date") <= end_dt.date())
                            ).to_pandas()
                            df_full["Date"] = pd.to_datetime(df_full["Date"])
                            # Ensure it aligns with full_idx
                            df_full = df_full.set_index("Date").reindex(
                                full_idx).reset_index(names=["Date"])
                            df_full["Close"] = df_full["Close"].ffill().bfill()
                            df_full["ID"] = row["ID"]
                            df_full["Benchmark_Name"] = row["Benchmark_Name"]
                            df_full["yF_Ticker"] = ticker
                            df_full["Currency"] = row["Currency"]
                            return df_full, row, f"✓ Cached {ticker}"
                        else:
                            # Partially cached, advance fetch_start
                            fetch_start = pd.to_datetime(
                                max_date_val) + pd.Timedelta(days=1)

            hist = pd.DataFrame()
            if fetch_start <= end_dt:
                for attempt in range(3):
                    try:
                        ticker_obj = yf.Ticker(ticker)
                        hist = ticker_obj.history(
                            start=fetch_start, end=end_dt + pd.Timedelta(days=1))
                        break  # Success
                    except Exception as e:
                        if attempt == 2:
                            raise e
                        time.sleep(1 + attempt * 2)  # Backoff 1s, 3s

            # If we had no cache and fetched new data, or if we fetched all new data
            if hist.empty and fetch_start <= end_dt:
                return None, row, f"Warning: No data available for {ticker}"

            df_new = pd.DataFrame()
            # Strip timezones and normalize to midnight
            if not hist.empty:
                hist.index = pd.to_datetime(
                    hist.index).tz_localize(None).normalize()

                # ffill() to cover weekends/holidays, then bfill()
                df_new = hist[["Close"]].reindex(
                    pd.date_range(start=fetch_start, end=end_dt)
                ).ffill().bfill()
                df_new = df_new.reset_index(names=["Date"])

                # Add metadata
                df_new["ID"] = row["ID"]
                df_new["Benchmark_Name"] = row["Benchmark_Name"]
                df_new["yF_Ticker"] = ticker
                df_new["Currency"] = row["Currency"]

            # Combine cache and new data if applicable
            if ticker_cached is not None and not ticker_cached.is_empty():
                df_cached_pd = ticker_cached.to_pandas()
                df_cached_pd["Date"] = pd.to_datetime(df_cached_pd["Date"])
                df_full = pd.concat([df_cached_pd, df_new], ignore_index=True)
            else:
                df_full = df_new

            # Now extract exactly the target user range
            df_full = df_full.set_index("Date").reindex(
                full_idx).reset_index(names=["Date"])
            # forward fill and backfill again across the concatenated data to ensure no NaNs in exact range
            df_full["Close"] = df_full["Close"].ffill().bfill()

            # Re-apply metadata for the new rows that were created by reindex
            df_full["ID"] = row["ID"]
            df_full["Benchmark_Name"] = row["Benchmark_Name"]
            df_full["yF_Ticker"] = ticker
            df_full["Currency"] = row["Currency"]

            # Anomaly check: detect huge 1-day drops that might be unadjusted splits
            warn_msg = None
            if not hist.empty:
                pct_drops = hist["Close"].pct_change()
                # greater than 40% drop
                huge_drops = pct_drops[pct_drops < -0.4]
                if not huge_drops.empty:
                    drop_dts = pd.to_datetime(
                        huge_drops.index).strftime("%Y-%m-%d").tolist()
                    warn_msg = f"⚠ Anomalous drops (>40%) in {ticker} on {', '.join(drop_dts)} (Unadjusted split?)"

            msg = f"✓ Fetched {ticker}" if not warn_msg else f"✓ Fetched {ticker}. {warn_msg}"
            return df_full, row, msg

        except Exception as e:
            return None, row, f"Error on {ticker}: {str(e)}"

    def run(self):
        try:
            self.status_queue.put(("Loading Benchmark Master...", None, 0.05))
            df_m = self.df_m

            required_cols = ["ID", "Benchmark_Name", "yF_Ticker", "Currency"]
            missing_cols = [c for c in required_cols if c not in df_m.columns]
            if missing_cols:
                self.status_queue.put((
                    f"Error: Missing columns in Benchmark Master: {missing_cols}",
                    None, 0.0,
                ))
                return pl.DataFrame()

            tickers_df = df_m.to_dicts()
            total = len(tickers_df)

            if not self.start_date or not self.end_date:
                self.status_queue.put((
                    "Error: Start Date and End Date are required for the Downloader.",
                    None, 0.0,
                ))
                return pl.DataFrame()

            start_dt = pd.to_datetime(self.start_date)
            end_dt = pd.to_datetime(self.end_date)

            # GET CACHE
            cached_df = self._get_cached_benchmark_data()
            if cached_df is not None:
                self.status_queue.put(
                    ("Validating cached benchmark data...", None, 0.08))

            # Give a 15-day buffer back to prime ffill logic
            base_fetch_start = start_dt - pd.Timedelta(days=15)
            full_idx = pd.date_range(start=start_dt, end=end_dt, freq="D")

            all_dfs = []

            self.status_queue.put(
                (f"Starting concurrent download for {total} tickers...", None, 0.1))

            processed = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                futures = {
                    executor.submit(
                        self._fetch_ticker,
                        row, start_dt, end_dt, base_fetch_start, full_idx, cached_df
                    ): row
                    for row in tickers_df
                }

                # Process results as they complete
                for future in concurrent.futures.as_completed(futures):
                    processed += 1
                    prog = 0.1 + 0.85 * (processed / total)

                    try:
                        df_pd, row, msg = future.result()
                        # Update UI
                        self.status_queue.put((msg, None, prog))

                        if df_pd is not None:
                            all_dfs.append(df_pd)
                    except Exception as e:
                        # Catch catastrophic thread failures
                        ticker = futures[future].get("yF_Ticker", "Unknown")
                        self.status_queue.put(
                            (f"Error: Critical thread failure on {ticker}: {str(e)}", None, prog))

            self.status_queue.put(("Consolidating data...", None, 0.98))

            if all_dfs:
                final_pd = pd.concat(all_dfs, ignore_index=True)
                final_df = pl.from_pandas(final_pd)
                final_df = final_df.select(
                    ["Date", "ID", "Benchmark_Name", "yF_Ticker", "Currency", "Close"])
                final_df = final_df.with_columns(pl.col("Date").cast(pl.Date))
                self.status_queue.put(("Processing Complete!", final_df, 1.0))
                return final_df
            else:
                empty_df = pl.DataFrame()
                self.status_queue.put((
                    "No data retrieved for the specified tickers in range.",
                    empty_df, 1.0,
                ))
                return empty_df

        except Exception as e:
            self.status_queue.put((f"Error: {str(e)}", None, 0.0))
