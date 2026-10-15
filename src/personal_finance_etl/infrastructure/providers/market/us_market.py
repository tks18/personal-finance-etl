# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportMissingImports=false, reportAttributeAccessIssue=false
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
import io
import time
import uuid
from datetime import date, datetime, timedelta

import polars as pl
import yfinance as yf  # type: ignore[import-untyped]

from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.extraction import (
    ExtractionBatchResult,
    ExtractorEntityResult,
    ExtractorEntityStatus,
)
from personal_finance_etl.contracts.logging import LogLevel, StatusQueue
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.logging import logger

__all__ = ["USMarketExtractor"]


class USMarketExtractor:
    """Extracts daily US stock prices from yfinance with delta fetching and chunking."""

    def __init__(
        self,
        cp: ControlPlane,
        status_queue: StatusQueue,
        max_workers: int = 8,
    ) -> None:
        self.cp = cp
        self.status_queue = status_queue
        self.max_workers = max_workers

    def _fetch_ticker_delta(
        self, isin: str, ticker: str, start_dt: date, end_dt: date, max_cached_date: date | None
    ) -> ExtractorEntityResult:
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

        fetch_start = start_dt - timedelta(days=15)
        if max_cached_date and max_cached_date >= fetch_start:
            fetch_start = max_cached_date + timedelta(days=1)

        if fetch_start > end_dt:
            logger.debug(
                f"[US Market Extractor] {ticker} fully cached up to {end_dt}. Skipping API fetch."
            )
            return ExtractorEntityResult(
                entity=entity_label,
                status=ExtractorEntityStatus.CACHED,
                message=f"✓ {ticker} fully cached up to {end_dt}",
                attempt_count=0,
                requested_start=fetch_start,
                requested_end=end_dt,
            )

        logger.debug(f"[US Market Extractor] API Fetching {ticker} from {fetch_start} to {end_dt}")
        hist_pd = None
        attempts_done = 0
        for attempt in range(3):
            attempts_done = attempt + 1
            try:
                ticker_obj = yf.Ticker(ticker)
                hist_pd = ticker_obj.history(  # pyright: ignore[reportUnknownMemberType]
                    start=fetch_start, end=end_dt + timedelta(days=1)
                )
                break
            except Exception as e:
                logger.warning(
                    f"[US Market Extractor] Attempt {attempt + 1}/3 failed for {ticker}: {e}"
                )
                if attempt == 2:
                    return ExtractorEntityResult(
                        entity=entity_label,
                        status=ExtractorEntityStatus.RETRY_EXHAUSTED,
                        message=f"Error on {ticker}: {str(e)}",
                        attempt_count=attempts_done,
                        requested_start=fetch_start,
                        requested_end=end_dt,
                        failure_class=type(e).__name__,
                        final_error=str(e),
                    )
                time.sleep(1 + attempt * 2)

        if hist_pd is None or hist_pd.empty:
            logger.debug(f"[US Market Extractor] No data returned from API for {ticker}.")
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

        hist_pd.index = hist_pd.index.tz_localize(None).normalize()  # pyright: ignore[reportUnknownMemberType]
        hist_pl = pl.from_pandas(hist_pd.reset_index())

        if "Date" not in hist_pl.columns:
            hist_pl = hist_pl.rename({"index": "Date"})

        df_api = hist_pl.select([pl.col("Date").cast(pl.Date), pl.col("Close").cast(pl.Float64)])

        # Create a continuous spine to handle closures (weekends/holidays) without re-fetching
        df_spine = pl.DataFrame(
            {"Date": pl.date_range(start=fetch_start, end=end_dt, interval="1d", eager=True)}
        )

        df_new = df_spine.join(df_api, on="Date", how="left")

        df_new = df_new.with_columns(
            pl.lit(isin).alias("ISIN"),
            pl.lit(ticker).alias("yF_Ticker"),
            pl.col("Close").alias("Closing_Price_Local"),
            pl.lit("Yahoo Finance").alias("Data_Provider"),
            pl.lit(datetime.now().isoformat()).alias("Extraction_Time"),
            pl.lit(fetch_start).alias("Requested_Start"),
            pl.lit(end_dt).alias("Requested_End"),
            pl.col("Close").is_null().alias("Is_Closure_Gap"),
        ).drop("Close")

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

    def extract_us_market_delta(
        self,
        isin_ticker_map: dict[str, str],
        global_start_date: date,
        global_end_date: date,
        df_bronze_cached: pl.DataFrame,
    ) -> ExtractionBatchResult:
        total = len(isin_ticker_map)
        all_new_data: list[pl.DataFrame] = []

        batch_result = ExtractionBatchResult(
            provider="Yahoo Finance",
            start_date=global_start_date,
            end_date=global_end_date,
        )
        batch_result.requested_entities = [ticker for ticker in isin_ticker_map.values() if ticker]

        cache_map: dict[str, date] = {}
        if not df_bronze_cached.is_empty():
            aggs = df_bronze_cached.group_by("ISIN").agg(pl.max("Date").alias("MaxDate"))
            for r in aggs.to_dicts():
                cache_map[str(r["ISIN"])] = r["MaxDate"]

        self.status_queue.put(
            EngineStatusMessage(
                msg=f"Starting US Stock market extractor for {total} tickers...",
                data=None,
                progress=0.1,
                level=LogLevel.STEP,
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
                    batch_result.entity_results.append(res)
                    level = LogLevel.INFO
                    if res.status == ExtractorEntityStatus.SUCCESS:
                        batch_result.successful_entities.append(res.entity)
                        if not res.df.is_empty():
                            all_new_data.append(res.df)
                        level = LogLevel.INFO
                    elif res.status == ExtractorEntityStatus.CACHED:
                        batch_result.cached_entities.append(res.entity)
                        level = LogLevel.INFO
                    elif res.status in (
                        ExtractorEntityStatus.NO_NEW_DATA,
                        ExtractorEntityStatus.EMPTY_RESPONSE,
                    ):
                        batch_result.no_new_data_entities.append(res.entity)
                        level = LogLevel.WARNING
                    else:  # FAILED, RETRY_EXHAUSTED, INVALID_PAYLOAD
                        batch_result.failed_entities[res.entity] = res.message
                        level = LogLevel.ERROR

                    if res.message:
                        self.status_queue.put(
                            EngineStatusMessage(msg=res.message, data=None, progress=prog, level=level)
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
                    self.status_queue.put(
                        EngineStatusMessage(
                            msg=f"Error: Critical thread failure on {isin}: {err_msg}",
                            data=None,
                            progress=prog,
                            level=LogLevel.ERROR,
                        )
                    )

        # Enforce completeness policy before writing raw artifacts
        batch_result.assert_complete("US Market Extractor")

        if not all_new_data:
            return batch_result

        df_combined = pl.concat(all_new_data, how="diagonal_relaxed")
        df_combined = df_combined.with_columns(pl.col("Date").dt.year().alias("Year"))

        years = df_combined["Year"].unique().to_list()
        injected_files: list[str] = []
        df_final_chunks: list[pl.DataFrame] = []

        for year in years:
            df_year = df_combined.filter(pl.col("Year") == year).drop("Year")

            buf = io.BytesIO()
            df_year.write_parquet(buf)
            raw_bytes = buf.getvalue()

            run_uuid = str(uuid.uuid4())[:8]
            filename = f"us_market_raw_{year}_{run_uuid}.parquet"
            virtual_path = self.cp.artifacts.inject_virtual_file(
                filename=filename, category="us_stock_market", raw_bytes=raw_bytes
            )
            injected_files.append(virtual_path)

            df_final_chunks.append(
                df_year.with_columns(
                    pl.lit(filename).alias("__file_name__"),
                    pl.lit(virtual_path).alias("__folder_path__"),
                )
            )

        logger.info(
            f"US Market Extractor injected {len(injected_files)} Parquet chunks into Raw Store."
        )
        batch_result.frames = df_final_chunks
        batch_result.injected_files = injected_files
        return batch_result
