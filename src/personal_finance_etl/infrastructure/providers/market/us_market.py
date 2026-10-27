# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingImports=false
# pyright: reportAttributeAccessIssue=false
"""US Market stock price provider adapter (Yahoo Finance).

Owns
----
- Fetching historical daily US stock closing prices from Yahoo Finance via yfinance.
- Delta calculation against cached Bronze lakehouse state per ISIN.
- Continuous daily spine generation across market closure gaps.
- Multi-threaded batch extraction with exponential backoff and retry policy.
- Vaulting extracted Parquet chunks into the Control Plane Raw Store.

Does not own
-------------
- US stock portfolio transactions or tax lot logic (owned by domain.investments).
- Bronze database persistence (owned by infrastructure.warehouse.bronze).
"""

from __future__ import annotations

import concurrent.futures
from datetime import UTC, date, datetime

import pandas as pd  # type: ignore[import-untyped]
import polars as pl

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
from personal_finance_etl.infrastructure.providers.market.common import (
    calculate_market_fetch_window,
    download_yfinance_history,
    vault_parquet_chunks,
)

__all__ = ["USMarketExtractor"]

diagnostics = get_observability_diagnostics(__name__)


class USMarketExtractor:
    """Extracts daily US stock prices from yfinance with delta fetching and chunking."""

    def __init__(
        self,
        cp: ControlPlane,
        status_queue: EventQueue | None = None,
        max_workers: int = 8,
        emitter: EventEmitter | None = None,
    ) -> None:
        self.cp = cp
        self.status_queue = status_queue
        self.max_workers = max_workers
        if emitter is not None:
            self.emitter = emitter
        elif status_queue is not None:
            self.emitter = ObservabilityEmitter(sinks=[ObservabilityQueueSink(status_queue)])
        else:
            self.emitter = get_global_emitter()

    def _emit_event(self, event: ObservabilityEvent) -> None:
        """Route event through canonical observability emitter."""
        self.emitter.emit(event)

    @staticmethod
    def _build_us_market_spine(
        hist_pd: pd.DataFrame,
        isin: str,
        ticker: str,
        fetch_start: date,
        end_dt: date,
    ) -> pl.DataFrame:
        """Construct continuous calendar spine with market closure gaps for a US ticker.

        Parameters
        ----------
        hist_pd : pd.DataFrame
            Downloaded raw price dataframe from yfinance.
        isin : str
            Unique security ISIN identifier.
        ticker : str
            Yahoo Finance ticker symbol.
        fetch_start : date
            Effective start date boundary.
        end_dt : date
            Effective end date boundary.

        Returns
        -------
        pl.DataFrame
            Continuous observations with closing prices and closure indicators.
        """
        hist_pl = pl.from_pandas(hist_pd.reset_index())
        if "Date" not in hist_pl.columns:
            hist_pl = hist_pl.rename({"index": "Date"})

        df_api = hist_pl.select([pl.col("Date").cast(pl.Date), pl.col("Close").cast(pl.Float64)])
        df_spine = pl.DataFrame(
            {"Date": pl.date_range(start=fetch_start, end=end_dt, interval="1d", eager=True)}
        )
        df_new = df_spine.join(df_api, on="Date", how="left")

        return df_new.with_columns(
            pl.lit(isin).alias("ISIN"),
            pl.lit(ticker).alias("yF_Ticker"),
            pl.col("Close").alias("Closing_Price_Local"),
            pl.lit("Yahoo Finance").alias("Data_Provider"),
            pl.lit(datetime.now().isoformat()).alias("Extraction_Time"),
            pl.lit(fetch_start).alias("Requested_Start"),
            pl.lit(end_dt).alias("Requested_End"),
            pl.col("Close").is_null().alias("Is_Closure_Gap"),
        ).drop("Close")

    def _fetch_ticker_delta(
        self, isin: str, ticker: str, start_dt: date, end_dt: date, max_cached_date: date | None
    ) -> ExtractorEntityResult:
        """Fetch delta observations for a single US stock ticker.

        Parameters
        ----------
        isin : str
            Unique security ISIN identifier.
        ticker : str
            Yahoo Finance ticker symbol.
        start_dt : date
            Global requested start boundary.
        end_dt : date
            Global requested end boundary.
        max_cached_date : date | None
            Latest cached observation date in Bronze for this ISIN.

        Returns
        -------
        ExtractorEntityResult
            Result container with status, payload, and diagnostics.
        """
        entity_label = f"{ticker} ({isin})" if ticker else isin
        if not ticker:
            return ExtractorEntityResult(
                entity=entity_label,
                status=ExtractorEntityStatus.INVALID_PAYLOAD,
                message=f"Warning: Skipping empty ticker for ISIN {isin}",
                attempt_count=0,
                requested_start=start_dt,
                requested_end=end_dt,
                failure_class="InvalidPayloadError",
                final_error=f"Skipping empty ticker for ISIN {isin}",
            )

        fetch_start, is_cached = calculate_market_fetch_window(start_dt, end_dt, max_cached_date)
        if is_cached:
            diagnostics.debug(
                "US Market Extractor: %s fully cached up to %s. Skipping API fetch.",
                ticker,
                end_dt,
            )
            return ExtractorEntityResult(
                entity=entity_label,
                status=ExtractorEntityStatus.CACHED,
                message=f"{ticker} fully cached up to {end_dt}",
                attempt_count=0,
                requested_start=fetch_start,
                requested_end=end_dt,
            )

        hist_pd, attempts_done, err = download_yfinance_history(
            ticker, fetch_start, end_dt, label="US Market Extractor"
        )
        if err is not None:
            return ExtractorEntityResult(
                entity=entity_label,
                status=ExtractorEntityStatus.RETRY_EXHAUSTED,
                message=f"Error on {ticker}: {err}",
                attempt_count=attempts_done,
                requested_start=fetch_start,
                requested_end=end_dt,
                failure_class=type(err).__name__,
                final_error=str(err),
            )

        if hist_pd is None or hist_pd.empty:
            diagnostics.debug("US Market Extractor: No data returned from API for %s.", ticker)
            return ExtractorEntityResult(
                entity=entity_label,
                status=ExtractorEntityStatus.EMPTY_RESPONSE,
                message=f"⚠ No new data fetched for {ticker}",
                attempt_count=attempts_done,
                requested_start=fetch_start,
                requested_end=end_dt,
                failure_class="EmptyResponse",
                final_error=f"No new data fetched for {ticker}",
            )

        df_new = self._build_us_market_spine(hist_pd, isin, ticker, fetch_start, end_dt)
        msg = f"✓ API Fetched {ticker} ({fetch_start} to {end_dt}) - {df_new.height} rows"

        return ExtractorEntityResult(
            entity=entity_label,
            status=ExtractorEntityStatus.SUCCESS,
            message=msg,
            df=df_new,
            attempt_count=attempts_done,
            requested_start=fetch_start,
            requested_end=end_dt,
        )

    @staticmethod
    def _build_cache_map(df_bronze_cached: pl.DataFrame) -> dict[str, date]:
        """Build dictionary of latest cached observation dates per ISIN."""
        cache_map: dict[str, date] = {}
        if not df_bronze_cached.is_empty():
            aggs = df_bronze_cached.group_by("ISIN").agg(pl.max("Date").alias("MaxDate"))
            for r in aggs.to_dicts():
                cache_map[str(r["ISIN"])] = r["MaxDate"]
        return cache_map

    def _record_future_result(
        self,
        res: ExtractorEntityResult,
        batch_result: ExtractionBatchResult,
        all_new_data: list[pl.DataFrame],
        prog: float,
    ) -> None:
        """Process and route entity extraction result into the batch result container."""
        batch_result.entity_results.append(res)

        if res.status == ExtractorEntityStatus.SUCCESS:
            batch_result.successful_entities.append(res.entity)
            if not res.df.is_empty():
                all_new_data.append(res.df)
            self._emit_event(
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
                    progress=prog,
                )
            )
        elif res.status == ExtractorEntityStatus.CACHED:
            batch_result.cached_entities.append(res.entity)
            self._emit_event(
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
                    progress=prog,
                )
            )
        elif res.status in (
            ExtractorEntityStatus.NO_NEW_DATA,
            ExtractorEntityStatus.EMPTY_RESPONSE,
        ):
            batch_result.no_new_data_entities.append(res.entity)
            self._emit_event(
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
                    progress=prog,
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
            self._emit_event(
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
                    progress=prog,
                )
            )

    def extract_us_market_delta(
        self,
        isin_ticker_map: dict[str, str],
        global_start_date: date,
        global_end_date: date,
        df_bronze_cached: pl.DataFrame,
    ) -> ExtractionBatchResult:
        """Extract incremental foreign/US stock market prices via Yahoo Finance.

        Parameters
        ----------
        isin_ticker_map : dict[str, str]
            Mapping of ISIN to external Yahoo Finance ticker symbols.
        global_start_date : date
            Extraction window start boundary.
        global_end_date : date
            Extraction window end boundary.
        df_bronze_cached : pl.DataFrame
            Existing Bronze cache to identify latest available prices per ISIN.

        Returns
        -------
        ExtractionBatchResult
            Container holding combined delta observations, status, and raw files.
        """
        total = len(isin_ticker_map)
        all_new_data: list[pl.DataFrame] = []

        batch_result = ExtractionBatchResult(
            provider="Yahoo Finance",
            start_date=global_start_date,
            end_date=global_end_date,
        )
        batch_result.requested_entities = [ticker for ticker in isin_ticker_map.values() if ticker]

        cache_map = self._build_cache_map(df_bronze_cached)
        self._emit_event(
            ObservabilityEvent.create(
                event_code=EventCode.MARKET_FETCH_START,
                message=f"Starting US Stock market extractor for {total} tickers...",
                progress=0.1,
                severity=DiagnosticSeverity.INFO,
                outcome=EventOutcome.COMPLETED,
                presentation_kind=PresentationKind.STEP,
                stage=EngineStage.TRANSFORMING,
            )
        )

        processed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._fetch_ticker_delta,
                    isin,
                    ticker,
                    global_start_date,
                    global_end_date,
                    cache_map.get(isin),
                ): (isin, ticker)
                for isin, ticker in isin_ticker_map.items()
            }

            for future in concurrent.futures.as_completed(futures):
                processed += 1
                prog = 0.1 + 0.4 * (processed / total)
                isin, ticker = futures[future]
                entity_label = f"{ticker} ({isin})"
                try:
                    res = future.result()
                    self._record_future_result(res, batch_result, all_new_data, prog)
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
                    self._emit_event(
                        ObservabilityEvent.create(
                            event_code=EventCode.MARKET_TICKER_FAILED,
                            message=f"Error: Critical thread failure on {isin}: {err_msg}",
                            progress=prog,
                            severity=DiagnosticSeverity.ERROR,
                            outcome=EventOutcome.FAILED,
                            presentation_kind=PresentationKind.FAILURE,
                            stage=EngineStage.TRANSFORMING,
                        )
                    )

        batch_result.assert_complete("US Market Extractor")
        if not all_new_data:
            return batch_result

        df_combined = pl.concat(all_new_data, how="diagonal_relaxed")
        batch_result.frames, batch_result.injected_files = vault_parquet_chunks(
            self.cp, df_combined, "us_market_raw", "us_stock_market"
        )
        return batch_result
