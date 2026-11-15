"""Evidence extraction outcome contracts.

Owns
----
- ExtractorEntityStatus categorical outcomes.
- ExtractorEntityResult structured outcome for single-entity workers.
- ExtractionBatchResult aggregated outcomes across concurrent extraction workers.
- ExtractionCompletenessError raised on missing required market evidence.
- ExtractionResult legacy consolidated raw extracted evidence stream container.
- EXTRACTION_ATTRIBUTE_TO_DATASET_ID mapping from ExtractionResult attributes to DatasetIds.
- DATASET_ID_TO_EXTRACTION_ATTRIBUTE inverse mapping from DatasetIds to ExtractionResult attributes.

Does not own
-------------
- Provider implementation details (owned by infrastructure.providers).
- Bronze warehouse persistence (owned by infrastructure.warehouse.bronze).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import TypedDict

import polars as pl

from personal_finance_etl.contracts.dataset_collection import DatasetCollection
from personal_finance_etl.contracts.datasets import DatasetId


class ExtractorEntityStatus(StrEnum):
    """Categorical status for single-entity extraction outcomes."""

    SUCCESS = "SUCCESS"
    CACHED = "CACHED"
    NO_NEW_DATA = "NO_NEW_DATA"
    PARTIAL = "PARTIAL"
    EMPTY_RESPONSE = "EMPTY_RESPONSE"
    FAILED = "FAILED"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    INVALID_PAYLOAD = "INVALID_PAYLOAD"


class ExtractionCompletenessError(RuntimeError):
    """Raised when required market evidence extraction fails to meet completeness policy."""

    def __init__(
        self,
        message: str,
        *,
        failed_entities: dict[str, str],
        requested_interval: tuple[date, date] | None = None,
        provider: str = "Yahoo Finance",
    ) -> None:
        super().__init__(
            f"{message} [failed={failed_entities}, interval={requested_interval}, provider={provider}]"
        )
        self.failed_entities = failed_entities
        self.requested_interval = requested_interval
        self.provider = provider


class ExtractionProviderRequest(TypedDict, total=False):
    """Normalized provider request audit log record for control plane."""

    provider: str
    entity: str
    requested_start: date | None
    requested_end: date | None
    attempt_count: int
    status: str
    failure_class: str | None
    final_error: str | None


@dataclass
class ExtractorEntityResult:
    """Structured extraction outcome for a single entity returned by worker tasks."""

    entity: str
    status: ExtractorEntityStatus
    message: str
    df: pl.DataFrame = field(default_factory=lambda: pl.DataFrame())
    context: dict[str, object] = field(default_factory=lambda: dict[str, object]())
    attempt_count: int = 1
    requested_start: date | None = None
    requested_end: date | None = None
    failure_class: str | None = None
    final_error: str | None = None


@dataclass
class ExtractionBatchResult:
    """Structured extraction outcome across concurrent entity workers."""

    requested_entities: list[str] = field(default_factory=lambda: list[str]())
    successful_entities: list[str] = field(default_factory=lambda: list[str]())
    cached_entities: list[str] = field(default_factory=lambda: list[str]())
    no_new_data_entities: list[str] = field(default_factory=lambda: list[str]())
    failed_entities: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    frames: list[pl.DataFrame] = field(default_factory=lambda: list[pl.DataFrame]())
    injected_files: list[str] = field(default_factory=lambda: list[str]())
    provider: str = "Yahoo Finance"
    start_date: date | None = None
    end_date: date | None = None
    entity_results: list[ExtractorEntityResult] = field(
        default_factory=lambda: list[ExtractorEntityResult]()
    )

    @property
    def is_complete(self) -> bool:
        """Return True if every requested entity succeeded, was cached, or returned valid empty data."""
        return len(self.failed_entities) == 0

    @property
    def combined_frame(self) -> pl.DataFrame:
        """Combine all entity frames into a single concatenated DataFrame."""
        if not self.frames:
            return pl.DataFrame()
        return pl.concat(self.frames, how="diagonal_relaxed")

    def assert_complete(self, extractor_name: str = "Extractor") -> None:
        """Raise ExtractionCompletenessError if any required entity failed."""
        if not self.is_complete:
            interval = (
                (self.start_date, self.end_date) if self.start_date and self.end_date else None
            )
            raise ExtractionCompletenessError(
                f"{extractor_name} batch extraction failed completeness policy: "
                f"{len(self.failed_entities)} required entity/entities failed",
                failed_entities=self.failed_entities,
                requested_interval=interval,
                provider=self.provider,
            )

    def to_provider_requests(self) -> list[ExtractionProviderRequest]:
        """Format entity outcomes into structured records for cp_external_provider_requests."""
        records: list[ExtractionProviderRequest] = []
        for res in self.entity_results:
            records.append(
                {
                    "provider": self.provider,
                    "entity": res.entity,
                    "requested_start": res.requested_start or self.start_date,
                    "requested_end": res.requested_end or self.end_date,
                    "attempt_count": res.attempt_count,
                    "status": res.status.value,
                    "failure_class": res.failure_class,
                    "final_error": res.final_error
                    or (
                        res.message
                        if res.status
                        in (
                            ExtractorEntityStatus.FAILED,
                            ExtractorEntityStatus.RETRY_EXHAUSTED,
                            ExtractorEntityStatus.INVALID_PAYLOAD,
                        )
                        else None
                    ),
                }
            )
        return records

    def __iter__(self) -> Iterator[pl.DataFrame | list[str]]:
        """Iterate over (combined_frame, injected_files) pair."""
        return iter((self.combined_frame, self.injected_files))


@dataclass
class ExtractionResult:
    """Consolidated raw extracted evidence streams across all ingestion sources.

    Notes
    -----
    DEPRECATION TARGET: Phase 027.
    Use contracts.dataset_collection.DatasetCollection for new development.
    """

    zcategory: pl.LazyFrame
    assetgroup: pl.LazyFrame
    assets: pl.LazyFrame
    currency: pl.LazyFrame
    inoutcome: pl.LazyFrame
    mappings: dict[str, dict[str, str]]
    stg_mf_isin_mapping: pl.LazyFrame
    stg_benchmark_mapping: pl.LazyFrame
    mf_market_data_raw: pl.LazyFrame
    mf_transactions_raw: pl.LazyFrame
    stock_market_data_raw: pl.LazyFrame
    stock_transactions_raw: pl.LazyFrame
    raw_opening_balances: pl.LazyFrame
    raw_benchmark_master: pl.LazyFrame
    raw_macro_parameters: pl.LazyFrame
    column_master: pl.DataFrame | pl.LazyFrame
    us_stock_transactions_raw: pl.LazyFrame
    currency_mapping_raw: pl.LazyFrame

    def to_dataset_collection(self) -> DatasetCollection:
        """Convert this ExtractionResult into an immutable typed DatasetCollection.

        Returns
        -------
        DatasetCollection
            DatasetCollection containing all 17 dataset frames indexed by DatasetId.
        """
        frames: dict[DatasetId, pl.LazyFrame | pl.DataFrame] = {
            DatasetId.HOUSEHOLD_ZCATEGORY: self.zcategory,
            DatasetId.HOUSEHOLD_ASSET_GROUP: self.assetgroup,
            DatasetId.HOUSEHOLD_ASSETS: self.assets,
            DatasetId.HOUSEHOLD_CURRENCY: self.currency,
            DatasetId.HOUSEHOLD_INOUTCOME: self.inoutcome,
            DatasetId.INVESTMENT_MF_ISIN_MAPPING: self.stg_mf_isin_mapping,
            DatasetId.INVESTMENT_BENCHMARK_MAPPING: self.stg_benchmark_mapping,
            DatasetId.MARKET_MF_HOLDINGS: self.mf_market_data_raw,
            DatasetId.INVESTMENT_MF_ORDERS: self.mf_transactions_raw,
            DatasetId.MARKET_STOCK_HOLDINGS: self.stock_market_data_raw,
            DatasetId.INVESTMENT_STOCK_ORDERS: self.stock_transactions_raw,
            DatasetId.HOUSEHOLD_OPENING_BALANCES: self.raw_opening_balances,
            DatasetId.INVESTMENT_BENCHMARK_MASTER: self.raw_benchmark_master,
            DatasetId.INVESTMENT_MACRO_PARAMETERS: self.raw_macro_parameters,
            DatasetId.COMMON_COLUMN_MASTER: self.column_master,
            DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS: self.us_stock_transactions_raw,
            DatasetId.MARKET_CURRENCY_MAPPING: self.currency_mapping_raw,
        }
        return DatasetCollection(frames=frames)

    @classmethod
    def from_dataset_collection(
        cls,
        collection: DatasetCollection,
        mappings: dict[str, dict[str, str]] | None = None,
    ) -> ExtractionResult:
        """Construct an ExtractionResult from a DatasetCollection for backward compatibility.

        Parameters
        ----------
        collection : DatasetCollection
            Source dataset collection.
        mappings : dict[str, dict[str, str]] | None, default=None
            Optional mappings dictionary to attach to ExtractionResult.

        Returns
        -------
        ExtractionResult
            Populated ExtractionResult instance.
        """

        def _get_lf(ds_id: DatasetId) -> pl.LazyFrame:
            frame = collection.get(ds_id)
            if frame is None:
                return pl.LazyFrame()
            return frame if isinstance(frame, pl.LazyFrame) else frame.lazy()

        def _get_cm() -> pl.DataFrame | pl.LazyFrame:
            frame = collection.get(DatasetId.COMMON_COLUMN_MASTER)
            if frame is None:
                return pl.DataFrame()
            return frame

        return cls(
            zcategory=_get_lf(DatasetId.HOUSEHOLD_ZCATEGORY),
            assetgroup=_get_lf(DatasetId.HOUSEHOLD_ASSET_GROUP),
            assets=_get_lf(DatasetId.HOUSEHOLD_ASSETS),
            currency=_get_lf(DatasetId.HOUSEHOLD_CURRENCY),
            inoutcome=_get_lf(DatasetId.HOUSEHOLD_INOUTCOME),
            mappings=mappings if mappings is not None else {},
            stg_mf_isin_mapping=_get_lf(DatasetId.INVESTMENT_MF_ISIN_MAPPING),
            stg_benchmark_mapping=_get_lf(DatasetId.INVESTMENT_BENCHMARK_MAPPING),
            mf_market_data_raw=_get_lf(DatasetId.MARKET_MF_HOLDINGS),
            mf_transactions_raw=_get_lf(DatasetId.INVESTMENT_MF_ORDERS),
            stock_market_data_raw=_get_lf(DatasetId.MARKET_STOCK_HOLDINGS),
            stock_transactions_raw=_get_lf(DatasetId.INVESTMENT_STOCK_ORDERS),
            raw_opening_balances=_get_lf(DatasetId.HOUSEHOLD_OPENING_BALANCES),
            raw_benchmark_master=_get_lf(DatasetId.INVESTMENT_BENCHMARK_MASTER),
            raw_macro_parameters=_get_lf(DatasetId.INVESTMENT_MACRO_PARAMETERS),
            column_master=_get_cm(),
            us_stock_transactions_raw=_get_lf(DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS),
            currency_mapping_raw=_get_lf(DatasetId.MARKET_CURRENCY_MAPPING),
        )


EXTRACTION_ATTRIBUTE_TO_DATASET_ID: dict[str, DatasetId] = {
    "zcategory": DatasetId.HOUSEHOLD_ZCATEGORY,
    "assetgroup": DatasetId.HOUSEHOLD_ASSET_GROUP,
    "assets": DatasetId.HOUSEHOLD_ASSETS,
    "currency": DatasetId.HOUSEHOLD_CURRENCY,
    "inoutcome": DatasetId.HOUSEHOLD_INOUTCOME,
    "stg_mf_isin_mapping": DatasetId.INVESTMENT_MF_ISIN_MAPPING,
    "stg_benchmark_mapping": DatasetId.INVESTMENT_BENCHMARK_MAPPING,
    "mf_market_data_raw": DatasetId.MARKET_MF_HOLDINGS,
    "mf_transactions_raw": DatasetId.INVESTMENT_MF_ORDERS,
    "stock_market_data_raw": DatasetId.MARKET_STOCK_HOLDINGS,
    "stock_transactions_raw": DatasetId.INVESTMENT_STOCK_ORDERS,
    "raw_opening_balances": DatasetId.HOUSEHOLD_OPENING_BALANCES,
    "raw_benchmark_master": DatasetId.INVESTMENT_BENCHMARK_MASTER,
    "raw_macro_parameters": DatasetId.INVESTMENT_MACRO_PARAMETERS,
    "column_master": DatasetId.COMMON_COLUMN_MASTER,
    "us_stock_transactions_raw": DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS,
    "currency_mapping_raw": DatasetId.MARKET_CURRENCY_MAPPING,
}

DATASET_ID_TO_EXTRACTION_ATTRIBUTE: dict[DatasetId, str] = {
    v: k for k, v in EXTRACTION_ATTRIBUTE_TO_DATASET_ID.items()
}

# Invariant check: Assert that every frame field on ExtractionResult is mapped
_FRAME_FIELDS_ON_EXTRACTION_RESULT = {
    f.name for f in dataclasses.fields(ExtractionResult) if f.name != "mappings"
}
assert set(EXTRACTION_ATTRIBUTE_TO_DATASET_ID.keys()) == _FRAME_FIELDS_ON_EXTRACTION_RESULT, (
    f"Mismatch in ExtractionResult adapter mapping: "
    f"unmapped={_FRAME_FIELDS_ON_EXTRACTION_RESULT - set(EXTRACTION_ATTRIBUTE_TO_DATASET_ID.keys())}, "
    f"extra={set(EXTRACTION_ATTRIBUTE_TO_DATASET_ID.keys()) - _FRAME_FIELDS_ON_EXTRACTION_RESULT}"
)


@dataclass
class AssetPipelineResult:
    """Standardized outcome for individual asset class extraction pipelines."""

    market_data: pl.LazyFrame
    market_data_ref: pl.LazyFrame
    purchase_ref: pl.LazyFrame
    sale_ref: pl.LazyFrame
    master_ref: pl.LazyFrame
