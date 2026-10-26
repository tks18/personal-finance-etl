"""Common utility routines for external Yahoo Finance market data providers.

Owns
----
- calculate_market_fetch_window: Date boundary calculation for delta fetching with buffer window.
- download_yfinance_history: Resilient ticker history download with exponential backoff and retry policy.
- vault_parquet_chunks: Serializing combined Polars DataFrame by year and vaulting into Control Plane Raw Store.

Does not own
-------------
- Provider-specific spine generation or column schema mappings (owned by benchmark.py, us_market.py, currency.py).
- Bronze table database upsert operations (owned by infrastructure.warehouse.bronze).
"""

from __future__ import annotations

import io
import logging
import time
import uuid
from datetime import date, timedelta
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import polars as pl

# Exception TYP-002 [THIRD_PARTY_TYPING_GAP]: yfinance lacks py.typed marker and complete stubs
import yfinance as yf  # type: ignore[import-untyped]

from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane

__all__ = [
    "calculate_market_fetch_window",
    "download_yfinance_history",
    "vault_parquet_chunks",
]

logger = logging.getLogger(__name__)


def calculate_market_fetch_window(
    start_dt: date,
    end_dt: date,
    max_cached_date: date | None,
    buffer_days: int = 15,
) -> tuple[date, bool]:
    """Calculate the adjusted fetch start date considering existing cache and buffer.

    Parameters
    ----------
    start_dt : date
        Global requested start date.
    end_dt : date
        Global requested end date.
    max_cached_date : date | None
        Latest observation date currently cached in the Bronze layer, if any.
    buffer_days : int, optional
        Overlap buffer in days to prevent weekend / holiday gaps (default: 15).

    Returns
    -------
    tuple[date, bool]
        Tuple of (effective_fetch_start_date, is_fully_cached).
        If is_fully_cached is True, the entity requires no external API call.
    """
    fetch_start = start_dt - timedelta(days=buffer_days)
    if max_cached_date and max_cached_date >= fetch_start:
        fetch_start = max_cached_date + timedelta(days=1)

    is_cached = fetch_start > end_dt
    return fetch_start, is_cached


def download_yfinance_history(
    ticker: str,
    fetch_start: date,
    end_dt: date,
    max_attempts: int = 3,
    label: str = "Market Extractor",
) -> tuple[pd.DataFrame | None, int, Exception | None]:
    """Download historical price observations from Yahoo Finance with exponential backoff.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker symbol.
    fetch_start : date
        Start date boundary for historical price series.
    end_dt : date
        End date boundary for historical price series.
    max_attempts : int, optional
        Maximum retry attempts before failing (default: 3).
    label : str, optional
        Extractor identifier prefix for logging (default: 'Market Extractor').

    Returns
    -------
    tuple[pd.DataFrame | None, int, Exception | None]
        Tuple of (result_dataframe, attempts_performed, last_exception).
        If successful, last_exception is None and result_dataframe is populated.
    """
    logger.debug("API fetching %s (%s) from %s to %s", ticker, label, fetch_start, end_dt)
    attempts_done = 0
    last_err: Exception | None = None
    hist_pd: pd.DataFrame | None = None

    for attempt in range(max_attempts):
        attempts_done = attempt + 1
        try:
            ticker_obj: Any = yf.Ticker(ticker)
            raw_hist: Any = ticker_obj.history(start=fetch_start, end=end_dt + timedelta(days=1))
            if raw_hist is not None and not raw_hist.empty:
                # Strip timezone and normalize timestamps to calendar dates
                raw_hist.index = raw_hist.index.tz_localize(None).normalize()
                hist_pd = raw_hist
            else:
                hist_pd = raw_hist
            return hist_pd, attempts_done, None
        except Exception as e:
            last_err = e
            logger.warning(
                "Attempt %d/%d failed for %s (%s): %s",
                attempts_done,
                max_attempts,
                ticker,
                label,
                e,
            )
            if attempt < max_attempts - 1:
                time.sleep(1 + attempt * 2)

    return None, attempts_done, last_err


def vault_parquet_chunks(
    cp: ControlPlane,
    df_combined: pl.DataFrame,
    file_prefix: str,
    category: str,
) -> tuple[list[pl.DataFrame], list[str]]:
    """Partition combined market DataFrame by calendar year and inject into Raw Store.

    Parameters
    ----------
    cp : ControlPlane
        Control plane facade managing virtual artifact vaulting.
    df_combined : pl.DataFrame
        Combined multi-ticker market observations.
    file_prefix : str
        Base prefix for vaulted files (e.g., 'benchmark_delta', 'us_stock_delta').
    category : str
        Artifact category identifier (e.g., 'benchmark_history', 'us_stock_history').

    Returns
    -------
    tuple[list[pl.DataFrame], list[str]]
        Tuple of (chunk_frames_with_metadata, list_of_injected_virtual_paths).
    """
    if df_combined.is_empty():
        return [], []

    df_with_year = df_combined.with_columns(pl.col("Date").dt.year().alias("Year"))
    years = df_with_year["Year"].unique().to_list()
    injected_files: list[str] = []
    df_final_chunks: list[pl.DataFrame] = []

    for year in sorted(years):
        df_year = df_with_year.filter(pl.col("Year") == year).drop("Year")

        buf = io.BytesIO()
        df_year.write_parquet(buf)
        raw_bytes = buf.getvalue()

        run_uuid = str(uuid.uuid4())[:8]
        filename = f"{file_prefix}_{year}_{run_uuid}.parquet"
        virtual_path = cp.artifacts.inject_virtual_file(
            filename=filename, category=category, raw_bytes=raw_bytes
        )
        injected_files.append(virtual_path)

        df_final_chunks.append(
            df_year.with_columns(
                pl.lit(filename).alias("__file_name__"),
                pl.lit(virtual_path).alias("__folder_path__"),
            )
        )

    logger.info(
        "Injected %d Parquet chunks into Raw Store for %s.", len(injected_files), file_prefix
    )
    return df_final_chunks, injected_files
