"""Common utility routines for external Yahoo Finance market data providers.

Owns
----
- calculate_market_fetch_window: Date boundary calculation for delta fetching with buffer window.
- download_yfinance_history: Resilient ticker history download with exponential backoff and retry policy.
- fetch_ticker_raw_history: Fetch window evaluation, cache verification, and download dispatch.
- build_bronze_cache_map: Aggregating latest observation dates per ticker or ISIN from Bronze.
- record_extractor_entity_result: Routing entity extraction results into batch containers and emitting typed observability events.
- collect_extraction_futures: Concurrency future iteration, unhandled failure capture, and progress tracking.
- finalize_extraction_batch: Validating batch completion, frame concatenation, and Raw Store chunk vaulting.
- resolve_market_emitter: Canonical event emitter resolution from explicit instance or status queue.
- vault_parquet_chunks: Serializing combined Polars DataFrame by year and vaulting into Control Plane Raw Store.

Does not own
-------------
- Provider-specific spine generation or column schema mappings (owned by benchmark.py, us_market.py, currency.py).
- Bronze table database upsert operations (owned by infrastructure.warehouse.bronze).
"""

from __future__ import annotations

import concurrent.futures
import io
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

import pandas as pd  # type: ignore[import-untyped]
import polars as pl

# Exception TYP-002 [THIRD_PARTY_TYPING_GAP]: yfinance lacks py.typed marker and complete stubs
import yfinance as yf  # type: ignore[import-untyped]

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.extraction import (
    ExtractionBatchResult,
    ExtractorEntityResult,
    ExtractorEntityStatus,
)
from personal_finance_etl.contracts.lifecycle import FailureDomain
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    EventCode,
    EventEmitter,
    EventOutcome,
    ObservabilityContext,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.observability.emitter import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.infrastructure.observability.queue import ObservabilityQueueSink

ConcatMethod = Literal[
    "vertical", "vertical_relaxed", "diagonal", "diagonal_relaxed", "horizontal", "align"
]

__all__ = [
    "ConcatMethod",
    "build_bronze_cache_map",
    "calculate_market_fetch_window",
    "collect_extraction_futures",
    "download_yfinance_history",
    "fetch_ticker_raw_history",
    "finalize_extraction_batch",
    "record_extractor_entity_result",
    "resolve_market_emitter",
    "vault_parquet_chunks",
]

diagnostics = get_observability_diagnostics(__name__)


def resolve_market_emitter(
    emitter: EventEmitter | None = None,
    status_queue: EventQueue | None = None,
) -> EventEmitter:
    """Resolve an EventEmitter from explicit instance, legacy status queue, or global default.

    Parameters
    ----------
    emitter : EventEmitter | None, optional
        Explicit canonical event emitter.
    status_queue : EventQueue | None, optional
        Legacy multiprocessing status queue for UI forwarding.

    Returns
    -------
    EventEmitter
        Resolved canonical event emitter.
    """
    if emitter is not None:
        return emitter
    if status_queue is not None:
        return ObservabilityEmitter(sinks=[ObservabilityQueueSink(status_queue)])
    return get_global_emitter()


def build_bronze_cache_map(
    df_bronze_cached: pl.DataFrame,
    key_column: str = "yF_Ticker",
) -> dict[str, date]:
    """Build dictionary of latest cached observation dates per entity identifier.

    Parameters
    ----------
    df_bronze_cached : pl.DataFrame
        Cached Bronze DataFrame.
    key_column : str, default='yF_Ticker'
        Column name to group by for extracting maximum cached date.

    Returns
    -------
    dict[str, date]
        Mapping of entity identifier string to latest cached observation date.
    """
    cache_map: dict[str, date] = {}
    if not df_bronze_cached.is_empty() and key_column in df_bronze_cached.columns:
        aggs = df_bronze_cached.group_by(key_column).agg(pl.max("Date").alias("MaxDate"))
        for r in aggs.to_dicts():
            cache_map[str(r[key_column])] = r["MaxDate"]
    return cache_map


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
    diagnostics.debug("API fetching %s (%s) from %s to %s", ticker, label, fetch_start, end_dt)
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
            diagnostics.warning(
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


def fetch_ticker_raw_history(
    ticker: str,
    entity_label: str,
    start_dt: date,
    end_dt: date,
    max_cached_date: date | None,
    buffer_days: int = 15,
    max_attempts: int = 3,
    label: str = "Market Extractor",
) -> tuple[pd.DataFrame | None, date, int, ExtractorEntityResult | None]:
    """Calculate fetch window, check cache, and download yfinance history with retries.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker symbol.
    entity_label : str
        Human-readable entity label for reporting and logging.
    start_dt : date
        Global requested start boundary.
    end_dt : date
        Global requested end boundary.
    max_cached_date : date | None
        Latest cached observation date in Bronze.
    buffer_days : int, default=15
        Lookback buffer in days to prevent holiday/weekend gap issues.
    max_attempts : int, default=3
        Maximum download attempts with exponential backoff.
    label : str, default='Market Extractor'
        Context label for diagnostics.

    Returns
    -------
    tuple[pd.DataFrame | None, date, int, ExtractorEntityResult | None]
        Tuple of (hist_pd, fetch_start, attempts_done, early_result).
        If early_result is not None, the entity was cached, empty, or failed,
        and early_result should be returned immediately by the caller.
    """
    fetch_start, is_cached = calculate_market_fetch_window(
        start_dt=start_dt,
        end_dt=end_dt,
        max_cached_date=max_cached_date,
        buffer_days=buffer_days,
    )

    if is_cached:
        diagnostics.debug(
            "%s: %s fully cached up to %s. Skipping API fetch.", label, entity_label, end_dt
        )
        return (
            None,
            fetch_start,
            0,
            ExtractorEntityResult(
                entity=entity_label,
                status=ExtractorEntityStatus.CACHED,
                message=f"{entity_label} fully cached up to {end_dt}",
                attempt_count=0,
                requested_start=fetch_start,
                requested_end=end_dt,
            ),
        )

    hist_pd, attempts_done, err = download_yfinance_history(
        ticker=ticker,
        fetch_start=fetch_start,
        end_dt=end_dt,
        max_attempts=max_attempts,
        label=label,
    )

    if err is not None:
        err_msg = f"Error on {ticker}: {err}"
        diagnostics.error("%s: %s", label, err_msg)
        return (
            None,
            fetch_start,
            attempts_done,
            ExtractorEntityResult(
                entity=entity_label,
                status=ExtractorEntityStatus.RETRY_EXHAUSTED,
                message=err_msg,
                attempt_count=attempts_done,
                requested_start=fetch_start,
                requested_end=end_dt,
                failure_class=type(err).__name__,
                final_error=str(err),
            ),
        )

    if hist_pd is None or hist_pd.empty:
        diagnostics.debug("%s: No data returned from API for %s.", label, ticker)
        return (
            None,
            fetch_start,
            attempts_done,
            ExtractorEntityResult(
                entity=entity_label,
                status=ExtractorEntityStatus.EMPTY_RESPONSE,
                message=f"⚠ No new data fetched for {ticker}",
                attempt_count=attempts_done,
                requested_start=fetch_start,
                requested_end=end_dt,
                failure_class="EmptyResponse",
                final_error=f"No new data fetched for {ticker}",
            ),
        )

    return hist_pd, fetch_start, attempts_done, None


def record_extractor_entity_result(
    res: ExtractorEntityResult,
    batch_result: ExtractionBatchResult,
    all_new_data: list[pl.DataFrame],
    progress: float,
    emitter: EventEmitter,
) -> None:
    """Process and route entity extraction result into the batch container and emit typed events.

    Parameters
    ----------
    res : ExtractorEntityResult
        Single entity extraction result.
    batch_result : ExtractionBatchResult
        Container aggregating all entity results for the batch.
    all_new_data : list[pl.DataFrame]
        Accumulator list for non-empty newly extracted DataFrames.
    progress : float
        Overall batch progress fraction between 0.0 and 1.0.
    emitter : EventEmitter
        Canonical observability event emitter.
    """
    batch_result.entity_results.append(res)

    if res.status == ExtractorEntityStatus.SUCCESS:
        batch_result.successful_entities.append(res.entity)
        if not res.df.is_empty():
            all_new_data.append(res.df)
        emitter.emit(
            ObservabilityEvent(
                timestamp=datetime.now(UTC),
                event_code=EventCode.MARKET_TICKER_SUCCESS,
                severity=DiagnosticSeverity.INFO,
                presentation_kind=PresentationKind.SUCCESS,
                outcome=EventOutcome.COMPLETED,
                context=ObservabilityContext(
                    stage=EngineStage.TRANSFORMING,
                    provider="YahooFinance",
                    entity_type="Ticker",
                    entity_id=res.entity,
                    attempt=res.attempt_count,
                    rows=res.df.height if not res.df.is_empty() else None,
                ),
                message=res.message,
                progress=progress,
            )
        )
    elif res.status == ExtractorEntityStatus.CACHED:
        batch_result.cached_entities.append(res.entity)
        emitter.emit(
            ObservabilityEvent(
                timestamp=datetime.now(UTC),
                event_code=EventCode.MARKET_TICKER_CACHE_HIT,
                severity=DiagnosticSeverity.INFO,
                presentation_kind=PresentationKind.STEP,
                outcome=EventOutcome.COMPLETED,
                context=ObservabilityContext(
                    stage=EngineStage.TRANSFORMING,
                    provider="YahooFinance",
                    entity_type="Ticker",
                    entity_id=res.entity,
                    cache_hit=True,
                ),
                message=f"{res.entity} fully cached up to {res.requested_end}",
                progress=progress,
            )
        )
    elif res.status in (
        ExtractorEntityStatus.NO_NEW_DATA,
        ExtractorEntityStatus.EMPTY_RESPONSE,
    ):
        batch_result.no_new_data_entities.append(res.entity)
        emitter.emit(
            ObservabilityEvent(
                timestamp=datetime.now(UTC),
                event_code=EventCode.MARKET_TICKER_SUCCESS,
                severity=DiagnosticSeverity.WARNING,
                presentation_kind=PresentationKind.WARNING,
                outcome=EventOutcome.COMPLETED,
                context=ObservabilityContext(
                    stage=EngineStage.TRANSFORMING,
                    provider="YahooFinance",
                    entity_type="Ticker",
                    entity_id=res.entity,
                    attempt=res.attempt_count,
                ),
                message=res.message,
                progress=progress,
            )
        )
    else:
        batch_result.failed_entities[res.entity] = res.message
        err_details = ErrorDetails(
            exception_type=res.failure_class or "MarketTickerFetchError",
            exception_message=res.final_error or res.message,
            failure_domain=FailureDomain.EXTERNAL_PROVIDER,
            traceback_summary="",
            retryable=False,
        )
        emitter.emit(
            ObservabilityEvent(
                timestamp=datetime.now(UTC),
                event_code=EventCode.MARKET_TICKER_FAILED,
                severity=DiagnosticSeverity.ERROR,
                presentation_kind=PresentationKind.FAILURE,
                outcome=EventOutcome.FAILED,
                error=err_details,
                context=ObservabilityContext(
                    stage=EngineStage.TRANSFORMING,
                    provider="YahooFinance",
                    entity_type="Ticker",
                    entity_id=res.entity,
                    attempt=res.attempt_count,
                ),
                message=res.message,
                progress=progress,
            )
        )


def collect_extraction_futures(
    futures: Mapping[concurrent.futures.Future[ExtractorEntityResult], str],
    batch_result: ExtractionBatchResult,
    all_new_data: list[pl.DataFrame],
    emitter: EventEmitter,
    global_start_date: date,
    global_end_date: date,
    total: int,
    base_progress: float = 0.1,
    progress_scale: float = 0.4,
) -> None:
    """Iterate completed extractor futures, record results, and handle unhandled thread exceptions.

    Parameters
    ----------
    futures : Mapping[concurrent.futures.Future[ExtractorEntityResult], str]
        Mapping of submitted futures to their entity identifier label.
    batch_result : ExtractionBatchResult
        Container tracking all entity results, statuses, and failures.
    all_new_data : list[pl.DataFrame]
        List accumulating non-empty DataFrames from successful extractions.
    emitter : EventEmitter
        Canonical observability event emitter.
    global_start_date : date
        Start boundary of requested batch extraction.
    global_end_date : date
        End boundary of requested batch extraction.
    total : int
        Total number of entities in the batch.
    base_progress : float, default=0.1
        Base progress offset for the batch stage.
    progress_scale : float, default=0.4
        Scale factor for per-entity progress fraction.
    """
    processed = 0
    for future in concurrent.futures.as_completed(futures):
        processed += 1
        prog = base_progress + progress_scale * (processed / total) if total > 0 else 0.5
        entity_label = futures[future]
        try:
            res = future.result()
            record_extractor_entity_result(
                res=res,
                batch_result=batch_result,
                all_new_data=all_new_data,
                progress=prog,
                emitter=emitter,
            )
        except Exception as e:
            err_msg = str(e)
            batch_result.failed_entities[entity_label] = err_msg
            batch_result.entity_results.append(
                ExtractorEntityResult(
                    entity=entity_label,
                    status=ExtractorEntityStatus.FAILED,
                    message=err_msg,
                    attempt_count=1,
                    requested_start=global_start_date,
                    requested_end=global_end_date,
                    failure_class=type(e).__name__,
                    final_error=err_msg,
                )
            )
            emitter.emit(
                ObservabilityEvent.create(
                    event_code=EventCode.MARKET_TICKER_FAILED,
                    message=f"Error: Critical thread failure on {entity_label}: {err_msg}",
                    progress=prog,
                    severity=DiagnosticSeverity.ERROR,
                    outcome=EventOutcome.FAILED,
                    presentation_kind=PresentationKind.FAILURE,
                    stage=EngineStage.TRANSFORMING,
                )
            )


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

    diagnostics.info(
        "Injected %d Parquet chunks into Raw Store for %s.", len(injected_files), file_prefix
    )
    return df_final_chunks, injected_files


def finalize_extraction_batch(
    cp: ControlPlane,
    batch_result: ExtractionBatchResult,
    all_new_data: list[pl.DataFrame],
    extractor_name: str,
    file_prefix: str,
    category: str,
    concat_how: ConcatMethod = "diagonal_relaxed",
) -> ExtractionBatchResult:
    """Assert batch completeness, concatenate newly extracted frames, and vault parquet chunks.

    Parameters
    ----------
    cp : ControlPlane
        Control plane facade for vaulting artifacts.
    batch_result : ExtractionBatchResult
        Extraction batch tracking container.
    all_new_data : list[pl.DataFrame]
        List of newly extracted DataFrames.
    extractor_name : str
        Human-readable extractor name for assertions (e.g., 'Benchmark Extractor').
    file_prefix : str
        Prefix for vaulted parquet files.
    category : str
        Artifact store category.
    concat_how : ConcatMethod, default='diagonal_relaxed'
        Polars concatenation strategy.

    Returns
    -------
    ExtractionBatchResult
        Updated batch result with populated frames and injected virtual files.
    """
    batch_result.assert_complete(extractor_name)
    if not all_new_data:
        return batch_result

    df_combined = pl.concat(all_new_data, how=concat_how)
    batch_result.frames, batch_result.injected_files = vault_parquet_chunks(
        cp, df_combined, file_prefix, category
    )
    return batch_result
