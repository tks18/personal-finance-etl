# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingImports=false
# pyright: reportAttributeAccessIssue=false
"""Currency FX rates provider adapter (Yahoo Finance).

Owns
----
- Fetching historical daily FX rates from Yahoo Finance via yfinance.
- Delta calculation against cached Bronze lakehouse state.
- Continuous daily spine generation across market closure gaps.
- Multi-threaded batch extraction with exponential backoff and retry policy.
- Vaulting extracted Parquet chunks into the Control Plane Raw Store.

Does not own
-------------
- Currency normalization formulas (owned by domain.market.fx).
- Bronze database persistence (owned by infrastructure.warehouse.bronze).
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Mapping
from datetime import date, datetime

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

__all__ = ["CurrencyExtractor"]

diagnostics = get_observability_diagnostics(__name__)


class CurrencyExtractor:
    """Extracts daily FX rates from yfinance based on active mapping, with delta fetching and chunking."""

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
    def _build_currency_spine(
        hist_pd: pd.DataFrame,
        row: Mapping[str, object],
        ticker: str,
        fetch_start: date,
        end_dt: date,
    ) -> pl.DataFrame:
        """Construct continuous calendar spine with market closure gaps for currency FX rate.

        Parameters
        ----------
        hist_pd : pd.DataFrame
            Downloaded raw price dataframe from yfinance.
        row : Mapping[str, object]
            Metadata record from Currency reference table.
        ticker : str
            Yahoo Finance ticker symbol.
        fetch_start : date
            Effective start date boundary.
        end_dt : date
            Effective end date boundary.

        Returns
        -------
        pl.DataFrame
            Continuous observations with FX exchange rates and closure gap indicators.
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
            pl.lit(row["UID"]).alias("Currency_ID"),
            pl.lit(row["CURRENCY_NAME"]).alias("Currency_Name"),
            pl.lit(row["ISO"]).alias("Currency_Code"),
            pl.lit(row["Target_Currency_Code"]).alias("Target_Currency_Code"),
            pl.lit(ticker).alias("yF_Ticker"),
            pl.col("Close").alias("FX_Rate"),
            pl.lit("Yahoo Finance").alias("Data_Provider"),
            pl.lit(datetime.now().isoformat()).alias("Extraction_Time"),
            pl.lit(fetch_start).alias("Requested_Start"),
            pl.lit(end_dt).alias("Requested_End"),
            pl.col("Close").is_null().alias("Is_Closure_Gap"),
        ).drop("Close")

    def _fetch_ticker_delta(
        self,
        row: Mapping[str, object],
        start_dt: date,
        end_dt: date,
        max_cached_date: date | None,
    ) -> ExtractorEntityResult:
        """Fetch delta observations for a single currency FX ticker.

        Parameters
        ----------
        row : Mapping[str, object]
            Currency metadata record containing ticker and identifiers.
        start_dt : date
            Global requested start boundary.
        end_dt : date
            Global requested end boundary.
        max_cached_date : date | None
            Latest cached observation date in Bronze for this currency.

        Returns
        -------
        ExtractorEntityResult
            Result container with status, payload, and diagnostics.
        """
        ticker = str(row.get("yF_Ticker", "")).strip()
        if not ticker:
            diagnostics.debug("Currency Extractor: Skipping empty ticker %s", row.get("UID"))
            return ExtractorEntityResult(
                entity=str(row.get("UID", "Unknown")),
                status=ExtractorEntityStatus.INVALID_PAYLOAD,
                message=f"Warning: Skipping empty ticker {row.get('UID')}",
                attempt_count=0,
                requested_start=start_dt,
                requested_end=end_dt,
                failure_class="InvalidPayloadError",
                final_error=f"Skipping empty ticker {row.get('UID')}",
            )

        hist_pd, fetch_start, attempts_done, early_res = fetch_ticker_raw_history(
            ticker=ticker,
            entity_label=ticker,
            start_dt=start_dt,
            end_dt=end_dt,
            max_cached_date=max_cached_date,
            label="Currency Extractor",
        )
        if early_res is not None:
            return early_res

        assert hist_pd is not None
        df_new = self._build_currency_spine(hist_pd, row, ticker, fetch_start, end_dt)
        msg = f"✓ API Fetched {ticker} ({fetch_start} to {end_dt}) - {df_new.height} rows"

        return ExtractorEntityResult(
            entity=ticker,
            status=ExtractorEntityStatus.SUCCESS,
            message=msg,
            df=df_new,
            attempt_count=attempts_done,
            requested_start=fetch_start,
            requested_end=end_dt,
        )

    @staticmethod
    def _build_cache_map(df_bronze_cached: pl.DataFrame) -> dict[str, date]:
        """Build dictionary of latest cached observation dates per currency ticker.

        Parameters
        ----------
        df_bronze_cached : pl.DataFrame
            Cached Bronze DataFrame.

        Returns
        -------
        dict[str, date]
            Mapping of currency ticker symbol to latest cached observation date.
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

    def extract_currency_delta(
        self,
        df_currency: pl.DataFrame,
        global_start_date: date,
        global_end_date: date,
        df_bronze_cached: pl.DataFrame,
    ) -> ExtractionBatchResult:
        """Extract incremental currency foreign exchange rates via Yahoo Finance.

        Parameters
        ----------
        df_currency : pl.DataFrame
            Currency reference table containing active foreign exchange tickers.
        global_start_date : date
            Extraction window start boundary.
        global_end_date : date
            Extraction window end boundary.
        df_bronze_cached : pl.DataFrame
            Existing Bronze cache to identify latest available exchange rates.

        Returns
        -------
        ExtractionBatchResult
            Container holding combined delta observations, status, and raw files.
        """
        df_active = df_currency.filter(pl.col("Is_Active"))
        tickers_df = df_active.to_dicts()
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
                message=f"Starting Currency FX extractor for {total} tickers...",
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
            extractor_name="Currency Extractor",
            file_prefix="currency_delta",
            category="currency_history",
            concat_how="diagonal_relaxed",
        )
