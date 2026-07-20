"""
BenchmarkEngine: Downloads and processes benchmark OHLC data via yfinance.

Uses ThreadPoolExecutor for highly concurrent fetching, implements robust
request Session handling with retries, and securely cleans data via forward
and backward filling to prevent edge cases with missing dates.
Supports caching from previous ETL runs to minimize API calls.
"""

import concurrent.futures
import glob
import os
import sqlite3
import time
from datetime import date

import pandas as pd
import polars as pl
import yfinance as yf  # type: ignore[import-untyped]

from src.utils.interfaces import ILogger
from src.utils.models import EngineStatus, LogLevel


class BenchmarkEngine:
    """
    Downloads benchmark price data concurrently for all tickers defined in a master CSV.
    Pushes progress tuples of (message, data_or_None, progress_float) to status_queue.
    """

    def __init__(
        self,
        df_m: pl.DataFrame,
        status_queue: ILogger,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        max_workers: int = 8,
        target_db_base_path: str | None = None,
        current_db_path: str | None = None,
    ) -> None:
        self.df_m = df_m
        self.status_queue = status_queue
        self.start_date = start_date
        self.end_date = end_date
        self.max_workers = max_workers
        self.target_db_base_path = target_db_base_path
        self.current_db_path = current_db_path

    def _get_cached_benchmark_data(self) -> pl.DataFrame:
        """Scans the target DB base path for the most recent DB and loads f_Investment_Benchmark_Data."""
        if not self.target_db_base_path or not os.path.exists(self.target_db_base_path):
            return pl.DataFrame()

        # Search for .db files in subdirectories (outputs/FY/MM-YYYY/*.db)
        db_files = glob.glob(os.path.join(self.target_db_base_path, "**", "*.db"), recursive=True)
        if not db_files:
            return pl.DataFrame()

        if self.current_db_path:
            db_files = [
                f for f in db_files if os.path.abspath(f) != os.path.abspath(self.current_db_path)
            ]

        if not db_files:
            return pl.DataFrame()

        latest_db = max(db_files, key=os.path.getmtime)
        self.status_queue.put(
            EngineStatus(
                msg=f"Found recent cache DB: {os.path.basename(latest_db)}",
                data=None,
                progress=0.05,
                level=LogLevel.STEP,
            )
        )
        try:
            with sqlite3.connect(latest_db) as conn:
                df = pl.read_database("SELECT * FROM f_Investment_Benchmark_Data", conn)
                if not df.is_empty():
                    df = df.with_columns(pl.col("Date").cast(pl.Date))
                    return df
        except Exception as e:
            self.status_queue.put(
                EngineStatus(
                    msg=f"Warning: Failed to load cached benchmark data from {latest_db}: {e}",
                    data=None,
                    progress=0.05,
                    level=LogLevel.WARNING,
                )
            )
        return pl.DataFrame()

    def _fetch_ticker(
        self,
        row: dict[str, str],
        start_dt: pd.Timestamp,
        end_dt: pd.Timestamp,
        fetch_start: pd.Timestamp,
        full_idx: pd.DatetimeIndex,
        cached_df: pl.DataFrame | None = None,
    ) -> tuple[pd.DataFrame, dict[str, str], str | None]:
        """Worker function to fetch, normalize, and fill a single ticker."""
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
                            # Fully cached
                            df_full = ticker_cached.filter(
                                (pl.col("Date") >= start_dt.date())
                                & (pl.col("Date") <= end_dt.date())
                            ).to_pandas()
                            df_full["Date"] = pd.to_datetime(df_full["Date"])
                            # Ensure it aligns with full_idx
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
                            # Partially cached, advance fetch_start
                            fetch_start = pd.to_datetime(max_date_val) + pd.Timedelta(days=1)

            hist = pd.DataFrame()
            if fetch_start <= end_dt:
                for attempt in range(3):
                    try:
                        ticker_obj = yf.Ticker(ticker)
                        hist = ticker_obj.history(
                            start=fetch_start, end=end_dt + pd.Timedelta(days=1)
                        )
                        break  # Success
                    except Exception as e:
                        if attempt == 2:
                            raise e
                        time.sleep(1 + attempt * 2)  # Backoff 1s, 3s

            # If we had no cache and fetched new data, or if we fetched all new data
            if hist.empty and fetch_start <= end_dt:
                return pd.DataFrame(), row, f"Warning: No data available for {ticker}"

            df_new = pd.DataFrame()
            # Strip timezones and normalize to midnight
            if not hist.empty:
                hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()

                # ffill() to cover weekends/holidays, then bfill()
                df_new = (
                    hist[["Close"]]
                    .reindex(pd.date_range(start=fetch_start, end=end_dt))
                    .ffill()
                    .bfill()
                )
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
            df_full = df_full.set_index("Date").reindex(full_idx).reset_index(names=["Date"])
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
                    drop_dts = pd.to_datetime(huge_drops.index).strftime("%Y-%m-%d").tolist()
                    warn_msg = f"⚠ Anomalous drops (>40%) in {ticker} on {', '.join(drop_dts)} (Unadjusted split?)"

            msg = f"✓ Fetched {ticker}" if not warn_msg else f"✓ Fetched {ticker}. {warn_msg}"
            return df_full, row, msg

        except Exception as e:
            return pd.DataFrame(), row, f"Error on {ticker}: {str(e)}"

    def run(self) -> pl.DataFrame:
        try:
            self.status_queue.put(
                EngineStatus(
                    msg="Loading Benchmark Master...", data=None, progress=0.05, level=LogLevel.STEP
                )
            )
            df_m = self.df_m

            required_cols = ["ID", "Benchmark_Name", "yF_Ticker", "Currency"]
            missing_cols = [c for c in required_cols if c not in df_m.columns]
            if missing_cols:
                self.status_queue.put(
                    EngineStatus(
                        msg=f"Error: Missing columns in Benchmark Master: {missing_cols}",
                        data=None,
                        progress=0.0,
                        level=LogLevel.ERROR,
                    )
                )
                return pl.DataFrame()

            tickers_df = df_m.to_dicts()
            total = len(tickers_df)

            if not self.start_date or not self.end_date:
                self.status_queue.put(
                    EngineStatus(
                        msg="Error: Start Date and End Date are required for the Downloader.",
                        data=None,
                        progress=0.0,
                        level=LogLevel.ERROR,
                    )
                )
                return pl.DataFrame()

            start_dt = pd.to_datetime(self.start_date)
            end_dt = pd.to_datetime(self.end_date)

            # GET CACHE
            cached_df = self._get_cached_benchmark_data()
            if cached_df is not None:
                self.status_queue.put(
                    EngineStatus(
                        msg="Validating cached benchmark data...",
                        data=None,
                        progress=0.08,
                        level=LogLevel.STEP,
                    )
                )

            # Give a 15-day buffer back to prime ffill logic
            base_fetch_start = start_dt - pd.Timedelta(days=15)
            full_idx = pd.date_range(start=start_dt, end=end_dt, freq="D")

            all_dfs = []

            self.status_queue.put(
                EngineStatus(
                    msg=f"Starting concurrent download for {total} tickers...",
                    data=None,
                    progress=0.1,
                    level=LogLevel.STEP,
                )
            )

            processed = 0
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                futures = {
                    executor.submit(
                        self._fetch_ticker,
                        row,
                        start_dt,
                        end_dt,
                        base_fetch_start,
                        full_idx,
                        cached_df,
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
                        level = (
                            LogLevel.WARNING
                            if "Warning" in (msg or "") or "⚠" in (msg or "")
                            else LogLevel.INFO
                        )
                        self.status_queue.put(
                            EngineStatus(msg=msg or "", data=None, progress=prog, level=level)
                        )

                        if df_pd is not None and not df_pd.empty:
                            all_dfs.append(df_pd)
                    except Exception as e:
                        # Catch catastrophic thread failures
                        ticker = futures[future].get("yF_Ticker", "Unknown")
                        self.status_queue.put(
                            EngineStatus(
                                msg=f"Error: Critical thread failure on {ticker}: {str(e)}",
                                data=None,
                                progress=prog,
                                level=LogLevel.ERROR,
                            )
                        )

            self.status_queue.put(
                EngineStatus(
                    msg="Consolidating data...", data=None, progress=0.98, level=LogLevel.STEP
                )
            )

            if all_dfs:
                final_pd = pd.concat(all_dfs, ignore_index=True)
                final_df = pl.from_pandas(final_pd)
                final_df = final_df.select(
                    ["Date", "ID", "Benchmark_Name", "yF_Ticker", "Currency", "Close"]
                )
                final_df = final_df.with_columns(pl.col("Date").cast(pl.Date))
                self.status_queue.put(
                    EngineStatus(
                        msg="Processing Complete!",
                        data=final_df,
                        progress=1.0,
                        level=LogLevel.SUCCESS,
                    )
                )
                return final_df
            else:
                empty_df = pl.DataFrame()
                self.status_queue.put(
                    EngineStatus(
                        msg="No data retrieved for the specified tickers in range.",
                        data=empty_df,
                        progress=1.0,
                        level=LogLevel.WARNING,
                    )
                )
                return empty_df

        except Exception as e:
            self.status_queue.put(
                EngineStatus(msg=f"Error: {str(e)}", data=None, progress=0.0, level=LogLevel.ERROR)
            )
            return pl.DataFrame()
