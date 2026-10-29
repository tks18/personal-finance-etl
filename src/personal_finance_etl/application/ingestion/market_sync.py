"""Market data synchronization and layer publication coordination.

Owns
----
- Coordinating historical currency FX delta ingestion and Bronze/Silver publication.
- Coordinating historical benchmark index delta ingestion and Bronze/Silver publication.
- Coordinating US stock market price delta ingestion and Bronze/Silver publication.
- Logging provider extraction provenance events into the Control Plane audit log.
- Enforcing completeness assertion gates across external market feeds.

Does not own
-------------
- Low-level Yahoo Finance HTTP/API communication (owned by infrastructure.providers.market).
- Currency normalization formulas or valuation logic (owned by domain.market and domain.investments).
- Parquet storage files or DuckDB transaction commit mechanics (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import os
from datetime import date

import polars as pl

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.extraction import (
    ExtractionBatchResult,
    ExtractorEntityStatus,
)
from personal_finance_etl.contracts.observability import (
    EventCode,
    PresentationKind,
)
from personal_finance_etl.domain.investments.valuation.market_state import (
    transform_us_market_data,
)
from personal_finance_etl.domain.market.benchmarks import (
    BenchmarkTransformer,
)
from personal_finance_etl.domain.market.fx import (
    transform_currency_fx_rates,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.providers.market.benchmark import (
    BenchmarkExtractor,
)
from personal_finance_etl.infrastructure.providers.market.currency import (
    CurrencyExtractor,
)
from personal_finance_etl.infrastructure.providers.market.us_market import (
    USMarketExtractor,
)
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer

__all__ = [
    "BenchmarkPipeline",
    "CurrencyPipeline",
    "USMarketPipeline",
    "emit_market_sync_completed",
    "log_provider_requests_and_assert",
    "upsert_market_delta_and_register",
]

diagnostics = get_observability_diagnostics(__name__)

CURRENCY_BRONZE_SCHEMA: dict[str, type[pl.DataType] | pl.DataType] = {
    "Date": pl.Date,
    "Currency_ID": pl.String,
    "Currency_Code": pl.String,
    "Target_Currency_Code": pl.String,
    "yF_Ticker": pl.String,
    "FX_Rate": pl.Float64,
    "Data_Provider": pl.String,
    "Extraction_Time": pl.String,
    "Requested_Start": pl.Date,
    "Requested_End": pl.Date,
    "Is_Closure_Gap": pl.Boolean,
}

US_MARKET_BRONZE_SCHEMA: dict[str, type[pl.DataType] | pl.DataType] = {
    "Date": pl.Date,
    "ISIN": pl.String,
    "yF_Ticker": pl.String,
    "Closing_Price_Local": pl.Float64,
    "Data_Provider": pl.String,
    "Extraction_Time": pl.String,
    "Requested_Start": pl.Date,
    "Requested_End": pl.Date,
    "Is_Closure_Gap": pl.Boolean,
}


def upsert_market_delta_and_register(
    bronze: BronzeLayer,
    df_delta: pl.DataFrame,
    table_name: str,
    new_files: list[str],
    meta_file_type: str,
) -> None:
    """Upsert delta market Parquet chunks to Bronze, mark artifacts synced, and register metadata.

    Parameters
    ----------
    bronze : BronzeLayer
        Active Bronze lakehouse persistence layer.
    df_delta : pl.DataFrame
        Delta observations to append into the lakehouse table.
    table_name : str
        Target Bronze lakehouse physical table name.
    new_files : list[str]
        List of newly generated chunk file paths.
    meta_file_type : str
        Metadata classification string for file registry.
    """
    if not df_delta.is_empty():
        diagnostics.debug("Upserting new Parquet chunks to Bronze...")
        row_counts = bronze.upsert_table(
            df=df_delta,
            table_name=table_name,
            actionable_files=new_files,
            full_replace=False,
        )
        for filepath in new_files:
            filename = os.path.basename(filepath)
            count = row_counts.get(filename, 0)
            bronze.cp.artifacts.mark_synced([filepath])
            bronze.meta_layer.register_file(filepath, meta_file_type, count, bronze.cp)


def log_provider_requests_and_assert(
    cp: ControlPlane,
    batch_res: ExtractionBatchResult,
    extractor_name: str,
) -> None:
    """Log external provider request provenance to control plane and assert completeness.

    Parameters
    ----------
    cp : ControlPlane
        Active ControlPlane instance.
    batch_res : ExtractionBatchResult
        Aggregated extractor batch result containing provider requests and entity outcomes.
    extractor_name : str
        Descriptive extractor name for assertion error reporting.
    """
    if cp.active_run_id:
        cp.runs.log_provider_requests(cp.active_run_id, batch_res.to_provider_requests())
    batch_res.assert_complete(extractor_name)


def emit_market_sync_completed(
    emitter: ObservabilityEmitter,
    batch_res: ExtractionBatchResult,
    pipeline_name: str,
    total_quotes: int,
    entity_noun: str = "ticker(s)",
) -> None:
    """Emit standardized MARKET_SYNC_COMPLETED observability milestone event.

    Parameters
    ----------
    emitter : ObservabilityEmitter
        Active observability event emitter.
    batch_res : ExtractionBatchResult
        Completed batch result.
    pipeline_name : str
        Human-readable name of the completed pipeline.
    total_quotes : int
        Total number of quote rows produced in Silver layer.
    entity_noun : str, default='ticker(s)'
        Entity noun for diagnostic reporting.
    """
    cached_cnt = sum(
        1 for e in batch_res.entity_results if e.status == ExtractorEntityStatus.CACHED
    )
    fetched_cnt = len(batch_res.entity_results) - cached_cnt
    emitter.emit_event(
        event_code=EventCode.MARKET_SYNC_COMPLETED,
        message=(
            f"{pipeline_name} Completed — {len(batch_res.entity_results)} {entity_noun} "
            f"({cached_cnt} cached, {fetched_cnt} fetched, {total_quotes:,} quotes)"
        ),
        presentation_kind=PresentationKind.SUCCESS,
        progress=1.0,
        rows=total_quotes,
        stage=EngineStage.TRANSFORMING,
    )


class CurrencyPipeline:
    """Synchronizes external daily Currency FX rates into Bronze and Silver layers."""

    def __init__(
        self,
        cp: ControlPlane,
        bronze: BronzeLayer,
        status_queue: EventQueue,
        max_workers: int = 8,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self.cp = cp
        self.bronze = bronze
        self.status_queue = status_queue
        self.max_workers = max_workers
        self.emitter = emitter or get_global_emitter()

    def _load_cached_bronze_currency(self) -> pl.DataFrame:
        """Load existing Bronze currency FX observations or initialize empty schema.

        Returns
        -------
        pl.DataFrame
            Cached currency observation DataFrame or empty initialized schema.
        """
        df_bronze_cached = self.bronze.get_table("r_Currency_FX_Data")
        if df_bronze_cached.is_empty():
            diagnostics.debug(
                "Bronze Cache: EMPTY. A full historical extraction will be performed."
            )
            return pl.DataFrame(schema=CURRENCY_BRONZE_SCHEMA)
        cached_min = df_bronze_cached.select(pl.min("Date")).item()
        cached_max = df_bronze_cached.select(pl.max("Date")).item()
        diagnostics.debug(
            f"Bronze Cache: FOUND {df_bronze_cached.height} rows ({cached_min} to {cached_max})."
        )
        return df_bronze_cached

    def _upsert_currency_delta(self, df_delta: pl.DataFrame, new_files: list[str]) -> pl.LazyFrame:
        """Persist delta Parquet chunks into Bronze lakehouse and return full LazyFrame.

        Parameters
        ----------
        df_delta : pl.DataFrame
            Newly extracted currency observation rows.
        new_files : list[str]
            Newly generated chunk filenames.

        Returns
        -------
        pl.LazyFrame
            Complete updated Bronze currency FX LazyFrame.
        """
        upsert_market_delta_and_register(
            bronze=self.bronze,
            df_delta=df_delta,
            table_name="bronze.r_Currency_FX_Data",
            new_files=new_files,
            meta_file_type="currency_history",
        )
        df_bronze_full = self.bronze.get_table("r_Currency_FX_Data")
        if df_bronze_full.is_empty():
            return pl.LazyFrame(schema=CURRENCY_BRONZE_SCHEMA)
        return df_bronze_full.lazy()

    def run(
        self,
        df_currency: pl.DataFrame,
        global_start_date: date,
        global_end_date: date,
    ) -> pl.DataFrame:
        """Run the Currency FX pipeline.

        Parameters
        ----------
        df_currency : pl.DataFrame
            Currency dimension reference table.
        global_start_date : date
            Earliest required date for exchange rate continuous history.
        global_end_date : date
            Latest required date for exchange rate continuous history.

        Returns
        -------
        pl.DataFrame
            Continuous Silver currency FX rates DataFrame.
        """
        self.emitter.emit_event(
            event_code=EventCode.MARKET_FETCH_START,
            message=f"Starting Currency FX Pipeline ({global_start_date} to {global_end_date})...",
            presentation_kind=PresentationKind.STEP,
            progress=0.05,
            stage=EngineStage.TRANSFORMING,
        )

        df_bronze_cached = self._load_cached_bronze_currency()
        extractor = CurrencyExtractor(
            self.cp, self.status_queue, self.max_workers, emitter=self.emitter
        )
        batch_res = extractor.extract_currency_delta(
            df_currency, global_start_date, global_end_date, df_bronze_cached
        )
        log_provider_requests_and_assert(self.cp, batch_res, "Currency Extractor")

        self.emitter.emit_event(
            event_code=EventCode.BRONZE_UPSERT,
            message="Upserting Delta into Bronze Currency Lake...",
            presentation_kind=PresentationKind.PROGRESS,
            progress=0.6,
            stage=EngineStage.TRANSFORMING,
        )

        df_bronze_full_lazy = self._upsert_currency_delta(
            batch_res.combined_frame, batch_res.injected_files
        )

        self.emitter.emit_event(
            event_code=EventCode.TRANSFORMATION_STAGE,
            message="Transforming continuous Currency FX series...",
            presentation_kind=PresentationKind.PROGRESS,
            progress=0.8,
            stage=EngineStage.TRANSFORMING,
        )

        df_silver_lazy = transform_currency_fx_rates(
            df_bronze_full_lazy, df_currency.lazy(), global_start_date, global_end_date
        )
        # Materialization Boundary: PUBLICATION_BOUNDARY
        # Materialize final continuous currency FX observations for pipeline publication and warehouse
        df_silver = df_silver_lazy.collect(engine="streaming")

        emit_market_sync_completed(
            emitter=self.emitter,
            batch_res=batch_res,
            pipeline_name="Currency FX Pipeline",
            total_quotes=df_silver.height,
            entity_noun="ticker(s)",
        )
        return df_silver


class BenchmarkPipeline:
    """Synchronizes external daily Benchmark index series into Bronze and Silver layers."""

    def __init__(
        self,
        cp: ControlPlane,
        bronze: BronzeLayer,
        status_queue: EventQueue,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self.cp = cp
        self.bronze = bronze
        self.status_queue = status_queue
        self.emitter = emitter or get_global_emitter()

    @staticmethod
    def _resolve_benchmark_date_range(
        df_market: pl.DataFrame | None, df_purchase: pl.DataFrame | None
    ) -> tuple[date, date]:
        """Infer target historical extraction date boundaries from existing market transactions.

        Parameters
        ----------
        df_market : pl.DataFrame | None
            Existing market data table if available.
        df_purchase : pl.DataFrame | None
            Trade purchase table if available.

        Returns
        -------
        tuple[date, date]
            (start_date, end_date) bounding interval.
        """
        min_market, max_market, min_purch = None, None, None
        if df_market is not None and not df_market.is_empty():
            market_dates = df_market.select(pl.col("Date").drop_nulls())
            if not market_dates.is_empty():
                min_market = market_dates.select(pl.min("Date")).item()
                max_market = market_dates.select(pl.max("Date")).item()

        if df_purchase is not None and not df_purchase.is_empty():
            purch_dates = df_purchase.select(pl.col("Date").drop_nulls())
            if not purch_dates.is_empty():
                min_purch = purch_dates.select(pl.min("Date")).item()

        valid_starts = [d for d in [min_market, min_purch] if d is not None]
        start_date = min(valid_starts) if valid_starts else date(2000, 1, 1)
        end_date = max_market if max_market else date.today()

        if isinstance(start_date, str):
            start_date = date.fromisoformat(start_date)
        if isinstance(end_date, str):
            end_date = date.fromisoformat(end_date)
        return start_date, end_date

    def _load_cached_bronze_benchmark(self) -> pl.DataFrame:
        """Fetch cached benchmark observation table from Bronze layer.

        Returns
        -------
        pl.DataFrame
            Cached benchmark observations.
        """
        df_bronze_cached = self.bronze.get_table("r_Benchmark_Data")
        if df_bronze_cached.is_empty():
            diagnostics.debug(
                "Bronze Cache: EMPTY. A full historical extraction will be performed."
            )
        else:
            cached_min = df_bronze_cached.select(pl.min("Date")).item()
            cached_max = df_bronze_cached.select(pl.max("Date")).item()
            diagnostics.debug(
                f"Bronze Cache: FOUND {df_bronze_cached.height} rows ({cached_min} to {cached_max})."
            )
        return df_bronze_cached

    def _upsert_benchmark_delta(
        self, df_new_raw: pl.DataFrame, virtual_files: list[str]
    ) -> pl.DataFrame:
        """Persist delta benchmark Parquet chunks to Bronze and re-fetch updated cache.

        Parameters
        ----------
        df_new_raw : pl.DataFrame
            Newly extracted raw benchmark observations.
        virtual_files : list[str]
            Newly generated virtual artifact filenames.

        Returns
        -------
        pl.DataFrame
            Complete updated Bronze benchmark table.
        """
        upsert_market_delta_and_register(
            bronze=self.bronze,
            df_delta=df_new_raw,
            table_name="bronze.r_Benchmark_Data",
            new_files=virtual_files,
            meta_file_type="benchmark_history",
        )
        return self.bronze.get_table("r_Benchmark_Data")

    def process(
        self,
        df_market: pl.DataFrame | None,
        df_purchase: pl.DataFrame | None,
        df_master: pl.DataFrame,
    ) -> pl.DataFrame:
        """Extract missing benchmark index rates and produce continuous Silver benchmark table.

        Parameters
        ----------
        df_market : pl.DataFrame | None
            Combined market observations for bounds calculation.
        df_purchase : pl.DataFrame | None
            Trade purchase table for earliest investment bounds calculation.
        df_master : pl.DataFrame
            Instrument master reference table containing benchmark identifiers.

        Returns
        -------
        pl.DataFrame
            Continuous Silver benchmark price observation table.
        """
        start_date, end_date = self._resolve_benchmark_date_range(df_market, df_purchase)
        self.emitter.emit_event(
            event_code=EventCode.MARKET_FETCH_START,
            message=f"Phase 3.5: Dynamic Benchmark Extraction & Transformation ({start_date} to {end_date})...",
            presentation_kind=PresentationKind.STEP,
            stage=EngineStage.TRANSFORMING,
        )

        df_bronze_cached = self._load_cached_bronze_benchmark()
        extractor = BenchmarkExtractor(self.cp, self.status_queue, emitter=self.emitter)
        batch_res = extractor.extract_benchmark_delta(
            df_m=df_master,
            global_start_date=start_date,
            global_end_date=end_date,
            df_bronze_cached=df_bronze_cached,
        )
        log_provider_requests_and_assert(self.cp, batch_res, "Benchmark Extractor")

        self.emitter.emit_event(
            event_code=EventCode.BRONZE_UPSERT,
            message="Upserting Delta into Bronze Benchmark Lake...",
            presentation_kind=PresentationKind.PROGRESS,
            progress=0.6,
            stage=EngineStage.TRANSFORMING,
        )

        df_bronze_cached = self._upsert_benchmark_delta(
            batch_res.combined_frame, batch_res.injected_files
        )

        self.emitter.emit_event(
            event_code=EventCode.TRANSFORMATION_STAGE,
            message=f"Transforming Bronze Benchmark Data into Silver ({start_date} to {end_date})...",
            presentation_kind=PresentationKind.PROGRESS,
            progress=0.8,
            stage=EngineStage.TRANSFORMING,
        )

        transformer = BenchmarkTransformer()
        df_silver = transformer.transform(df_bronze_cached, start_date, end_date)
        diagnostics.debug(
            f"Transformation Complete: Silver Benchmark table has {df_silver.height} market periods."
        )

        emit_market_sync_completed(
            emitter=self.emitter,
            batch_res=batch_res,
            pipeline_name="Benchmark Pipeline",
            total_quotes=df_silver.height,
            entity_noun="indices",
        )
        return df_silver


class USMarketPipeline:
    """Synchronizes external daily US stock market prices into Bronze and Silver layers."""

    def __init__(
        self,
        cp: ControlPlane,
        bronze: BronzeLayer,
        status_queue: EventQueue,
        max_workers: int = 8,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self.cp = cp
        self.bronze = bronze
        self.status_queue = status_queue
        self.max_workers = max_workers
        self.emitter = emitter or get_global_emitter()

    def _load_cached_bronze_us_market(self) -> pl.DataFrame:
        """Fetch cached US market prices from Bronze layer or initialize empty schema.

        Returns
        -------
        pl.DataFrame
            Cached US stock price table or empty initialized schema.
        """
        df_bronze_cached = self.bronze.get_table("r_US_Stock_Prices")
        if df_bronze_cached.is_empty():
            diagnostics.debug(
                "Bronze Cache: EMPTY. A full historical extraction will be performed."
            )
            return pl.DataFrame(schema=US_MARKET_BRONZE_SCHEMA)
        return df_bronze_cached

    def _upsert_us_market_delta(self, df_delta: pl.DataFrame, new_files: list[str]) -> pl.LazyFrame:
        """Persist US market delta Parquet chunks into Bronze layer and return full LazyFrame.

        Parameters
        ----------
        df_delta : pl.DataFrame
            Newly extracted US stock price rows.
        new_files : list[str]
            Newly generated chunk filenames.

        Returns
        -------
        pl.LazyFrame
            Complete updated Bronze US market LazyFrame.
        """
        upsert_market_delta_and_register(
            bronze=self.bronze,
            df_delta=df_delta,
            table_name="bronze.r_US_Stock_Prices",
            new_files=new_files,
            meta_file_type="us_stock_market",
        )
        df_bronze_full = self.bronze.get_table("r_US_Stock_Prices")
        if df_bronze_full.is_empty():
            return pl.LazyFrame(schema=US_MARKET_BRONZE_SCHEMA)
        return df_bronze_full.lazy()

    def run(
        self,
        df_purchase: pl.DataFrame,
        df_sale: pl.DataFrame,
        df_master: pl.DataFrame,
        df_fx: pl.DataFrame,
        global_start_date: date,
        global_end_date: date,
    ) -> pl.DataFrame:
        """Run the US Market Data pipeline.

        Parameters
        ----------
        df_purchase : pl.DataFrame
            Trade purchase observations.
        df_sale : pl.DataFrame
            Trade sale observations.
        df_master : pl.DataFrame
            Instrument reference master table.
        df_fx : pl.DataFrame
            Continuous Currency FX exchange rate table.
        global_start_date : date
            Earliest required date for US stock quotes.
        global_end_date : date
            Latest required date for US stock quotes.

        Returns
        -------
        pl.DataFrame
            Harmonized Silver US market price observations.
        """
        if df_purchase.is_empty():
            return pl.DataFrame()

        us_purchases = df_purchase.filter(pl.col("__file_category__") == "US Stocks")
        if us_purchases.is_empty():
            return pl.DataFrame()

        active_isins = us_purchases["ISIN"].unique().to_list()
        master_dict = dict(zip(df_master["ISIN"], df_master["YAHOO_TICKER"], strict=False))

        isin_ticker_map: dict[str, str] = {}
        for isin in active_isins:
            name = str(master_dict.get(isin, ""))
            if name:
                isin_ticker_map[str(isin)] = name

        self.emitter.emit_event(
            event_code=EventCode.MARKET_FETCH_START,
            message=f"Starting US Market Data Pipeline ({global_start_date} to {global_end_date})...",
            presentation_kind=PresentationKind.STEP,
            progress=0.05,
            stage=EngineStage.TRANSFORMING,
        )

        df_bronze_cached = self._load_cached_bronze_us_market()
        extractor = USMarketExtractor(
            self.cp, self.status_queue, self.max_workers, emitter=self.emitter
        )
        batch_res = extractor.extract_us_market_delta(
            isin_ticker_map, global_start_date, global_end_date, df_bronze_cached
        )
        log_provider_requests_and_assert(self.cp, batch_res, "US Market Extractor")

        self.emitter.emit_event(
            event_code=EventCode.BRONZE_UPSERT,
            message="Upserting Delta into Bronze US Market Lake...",
            presentation_kind=PresentationKind.PROGRESS,
            progress=0.6,
            stage=EngineStage.TRANSFORMING,
        )

        df_bronze_full_lazy = self._upsert_us_market_delta(
            batch_res.combined_frame, batch_res.injected_files
        )

        self.emitter.emit_event(
            event_code=EventCode.TRANSFORMATION_STAGE,
            message="Transforming continuous US Market series...",
            presentation_kind=PresentationKind.PROGRESS,
            progress=0.8,
            stage=EngineStage.TRANSFORMING,
        )

        df_silver_lazy = transform_us_market_data(
            df_bronze_prices_lazy=df_bronze_full_lazy,
            df_purchase_lazy=df_purchase.lazy(),
            df_sale_lazy=df_sale.lazy(),
            df_fx_lazy=df_fx.lazy(),
            global_start_date=global_start_date,
            global_end_date=global_end_date,
        )
        # Materialization Boundary: PUBLICATION_BOUNDARY
        # Materialize final continuous US market valuation dataset for pipeline publication and warehouse
        df_silver = df_silver_lazy.collect(engine="streaming")

        emit_market_sync_completed(
            emitter=self.emitter,
            batch_res=batch_res,
            pipeline_name="US Market Pipeline",
            total_quotes=df_silver.height,
            entity_noun="tickers",
        )
        return df_silver
