# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingImports=false
# pyright: reportAttributeAccessIssue=false
"""Benchmark series provider adapter (Yahoo Finance).

Owns
----
- Fetching historical daily benchmark index series from Yahoo Finance via yfinance.
- Delta calculation against cached Bronze lakehouse state.
- Continuous daily spine generation across market closure gaps.
- Anomalous drop detection heuristics (>40% single-day change).
- Multi-threaded batch extraction with exponential backoff and retry policy.
- Vaulting extracted Parquet chunks into the Control Plane Raw Store.

Does not own
-------------
- Benchmark normalization transformations (owned by domain.market).
- Bronze database persistence (owned by infrastructure.warehouse.bronze).
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import polars as pl

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.extraction import (
    ExtractionBatchResult,
    ExtractorEntityResult,
    ExtractorEntityStatus,
)
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    EventEmitter,
    EventOutcome,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.providers.market.common import (
    build_bronze_cache_map,
    collect_extraction_futures,
    fetch_ticker_raw_history,
    finalize_extraction_batch,
    record_extractor_entity_result,
    resolve_market_emitter,
)

__all__ = ["BenchmarkExtractor"]

diagnostics = get_observability_diagnostics(__name__)


class BenchmarkExtractor:
    """Fetches missing benchmark delta from yfinance, chunks by year, and injects into Raw Store."""

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
        self.emitter = resolve_market_emitter(emitter, status_queue)

    def _emit_event(self, event: ObservabilityEvent) -> None:
        """Route event through canonical observability emitter."""
        self.emitter.emit(event)

    @staticmethod
    def _check_anomalous_drops(ticker: str, hist_pd: pd.DataFrame) -> tuple[list[str], str | None]:
        """Detect single-day percentage declines exceeding 40% threshold.

        Parameters
        ----------
        ticker : str
            Yahoo Finance ticker symbol.
        hist_pd : pd.DataFrame
            Historical price observations dataframe.

        Returns
        -------
        tuple[list[str], str | None]
            List of anomalous drop dates and optional warning message string.
        """
        pct_drops: Any = hist_pd["Close"].pct_change()
        huge_drops: Any = pct_drops[pct_drops < -0.4]
        if not huge_drops.empty:
            drop_dts = [d.strftime("%Y-%m-%d") for d in huge_drops.index]
            warn_msg = f"⚠ Anomalous drops (>40%) in {ticker} on {', '.join(drop_dts)}"
            diagnostics.warning("Benchmark Extractor: %s", warn_msg)
            return drop_dts, warn_msg
        return [], None

    @staticmethod
    def _build_benchmark_spine(
        hist_pd: pd.DataFrame,
        row: Mapping[str, object],
        ticker: str,
        fetch_start: date,
        end_dt: date,
    ) -> pl.DataFrame:
        """Construct continuous daily calendar spine joined against API observations.

        Parameters
        ----------
        hist_pd : pd.DataFrame
            Downloaded raw price dataframe from yfinance.
        row : Mapping[str, object]
            Metadata record from Benchmark Master reference table.
        ticker : str
            Yahoo Finance ticker symbol.
        fetch_start : date
            Effective start date boundary.
        end_dt : date
            Effective end date boundary.

        Returns
        -------
        pl.DataFrame
            Continuous daily observations table with closure gap indicators.
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
            pl.lit(row["ID"]).alias("ID"),
            pl.lit(row["Benchmark_Name"]).alias("Benchmark_Name"),
            pl.lit(ticker).alias("yF_Ticker"),
            pl.lit(row["CURRENCY_ID"]).alias("CURRENCY_ID"),
            pl.col("Close").alias("Close"),
            pl.lit("Yahoo Finance").alias("Data_Provider"),
            pl.lit(datetime.now().isoformat()).alias("Extraction_Time"),
            pl.lit(fetch_start).alias("Requested_Start"),
            pl.lit(end_dt).alias("Requested_End"),
            pl.col("Close").is_null().alias("Is_Closure_Gap"),
        )

    def _fetch_ticker_delta(
        self,
        row: Mapping[str, object],
        start_dt: date,
        end_dt: date,
        max_cached_date: date | None,
    ) -> ExtractorEntityResult:
        """Fetch delta observations for a single benchmark ticker.

        Parameters
        ----------
        row : Mapping[str, object]
            Benchmark metadata row containing ticker and identifier.
        start_dt : date
            Global requested start boundary.
        end_dt : date
            Global requested end boundary.
        max_cached_date : date | None
            Latest cached date in Bronze for this ticker.

        Returns
        -------
        ExtractorEntityResult
            Result container with status, payload, and diagnostics.
        """
        ticker = str(row.get("yF_Ticker", "")).strip()
        if not ticker:
            diagnostics.debug("Benchmark Extractor: Skipping empty ticker %s", row.get("ID"))
            return ExtractorEntityResult(
                entity=str(row.get("ID", "Unknown")),
                status=ExtractorEntityStatus.INVALID_PAYLOAD,
                message=f"Warning: Skipping empty ticker {row.get('ID')}",
                attempt_count=0,
                requested_start=start_dt,
                requested_end=end_dt,
                failure_class="InvalidPayloadError",
                final_error=f"Skipping empty ticker {row.get('ID')}",
            )

        hist_pd, fetch_start, attempts_done, early_res = fetch_ticker_raw_history(
            ticker=ticker,
            entity_label=ticker,
            start_dt=start_dt,
            end_dt=end_dt,
            max_cached_date=max_cached_date,
            label="Benchmark Extractor",
        )
        if early_res is not None:
            return early_res

        assert hist_pd is not None
        df_new = self._build_benchmark_spine(hist_pd, row, ticker, fetch_start, end_dt)
        drop_dts, warn_msg = self._check_anomalous_drops(ticker, hist_pd)

        msg = f"✓ API Fetched {ticker} ({fetch_start} to {end_dt}) - {df_new.height} rows"
        if warn_msg:
            msg += f". {warn_msg}"

        return ExtractorEntityResult(
            entity=ticker,
            status=ExtractorEntityStatus.SUCCESS,
            message=msg,
            df=df_new,
            context={"anomalous_drops": drop_dts} if drop_dts else {},
            attempt_count=attempts_done,
            requested_start=fetch_start,
            requested_end=end_dt,
        )

    @staticmethod
    def _build_cache_map(df_bronze_cached: pl.DataFrame) -> dict[str, date]:
        """Build dictionary of latest cached observation dates per ticker.

        Parameters
        ----------
        df_bronze_cached : pl.DataFrame
            Cached Bronze DataFrame.

        Returns
        -------
        dict[str, date]
            Mapping of ticker symbol to latest cached observation date.
        """
        return build_bronze_cache_map(df_bronze_cached, key_column="yF_Ticker")

    def _record_future_result(
        self,
        res: ExtractorEntityResult,
        batch_result: ExtractionBatchResult,
        all_new_data: list[pl.DataFrame],
        prog: float,
    ) -> None:
        """Process and route entity extraction result into the batch result container.

        Parameters
        ----------
        res : ExtractorEntityResult
            Single entity extraction result.
        batch_result : ExtractionBatchResult
            Container aggregating all entity results.
        all_new_data : list[pl.DataFrame]
            Accumulator list for newly extracted DataFrames.
        prog : float
            Extraction progress fraction.
        """
        record_extractor_entity_result(
            res=res,
            batch_result=batch_result,
            all_new_data=all_new_data,
            progress=prog,
            emitter=self.emitter,
        )

    def extract_benchmark_delta(
        self,
        df_m: pl.DataFrame,
        global_start_date: date,
        global_end_date: date,
        df_bronze_cached: pl.DataFrame,
    ) -> ExtractionBatchResult:
        """Extract incremental benchmark closing prices via Yahoo Finance for date window.

        Parameters
        ----------
        df_m : pl.DataFrame
            Benchmark master table containing tickers and currency identifiers.
        global_start_date : date
            Extraction window start boundary.
        global_end_date : date
            Extraction window end boundary.
        df_bronze_cached : pl.DataFrame
            Existing Bronze cache to identify latest available dates per ticker.

        Returns
        -------
        ExtractionBatchResult
            Container holding combined delta observations, status, and raw files.
        """
        required_cols = ["ID", "Benchmark_Name", "yF_Ticker", "CURRENCY_ID"]
        missing_cols = [c for c in required_cols if c not in df_m.columns]
        if missing_cols:
            raise ValueError(f"Missing columns in Benchmark Master: {missing_cols}")

        tickers_df = df_m.to_dicts()
        total = len(tickers_df)
        all_new_data: list[pl.DataFrame] = []

        batch_result = ExtractionBatchResult(
            provider="Yahoo Finance",
            start_date=global_start_date,
            end_date=global_end_date,
        )
        batch_result.requested_entities = [
            str(r.get("yF_Ticker", "")).strip()
            for r in tickers_df
            if str(r.get("yF_Ticker", "")).strip()
        ]

        cache_map = self._build_cache_map(df_bronze_cached)
        self._emit_event(
            ObservabilityEvent.create(
                event_code=EventCode.MARKET_FETCH_START,
                message=f"Starting benchmark extractor for {total} tickers...",
                progress=0.1,
                severity=DiagnosticSeverity.INFO,
                outcome=EventOutcome.COMPLETED,
                presentation_kind=PresentationKind.STEP,
                stage=EngineStage.TRANSFORMING,
            )
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(
                    self._fetch_ticker_delta,
                    row,
                    global_start_date,
                    global_end_date,
                    cache_map.get(str(row.get("yF_Ticker", "")).strip()),
                ): str(row.get("yF_Ticker", "Unknown"))
                for row in tickers_df
            }

            collect_extraction_futures(
                futures=futures,
                batch_result=batch_result,
                all_new_data=all_new_data,
                emitter=self.emitter,
                global_start_date=global_start_date,
                global_end_date=global_end_date,
                total=total,
            )

        return finalize_extraction_batch(
            cp=self.cp,
            batch_result=batch_result,
            all_new_data=all_new_data,
            extractor_name="Benchmark Extractor",
            file_prefix="benchmark_delta",
            category="benchmark_history",
            concat_how="diagonal",
        )
