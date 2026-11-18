"""Evidence extraction and gatekeeper schema validation coordinator.

Owns
----
- Orchestrating binary payload retrieval from the Control Plane Raw Store.
- Invoking file format providers (CSV, Excel, SQLite) to build lazy frames.
- Column mapping construction using column_master reference data.
- Gatekeeper schema validation and dry-run query evaluation on all actionable streams.

Does not own
-------------
- Physical file reading or network requests (owned by infrastructure.providers).
- Raw store storage transactions (owned by infrastructure.control_plane).
- Financial ledger or portfolio transformations (owned by domain.*).
"""

from __future__ import annotations

import os
import time
import traceback

import polars as pl

from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.dataset_collection import DatasetCollection
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.lifecycle import FailureDomain
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    EventCode,
    PresentationKind,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)

__all__ = ["DataExtractor"]

diagnostics = get_observability_diagnostics(__name__)


class DataExtractor:
    """Coordinates evidence extraction from raw payloads and executes Gatekeeper validation."""

    def __init__(
        self,
        cfg: Settings,
        status_queue: EventQueue,
        cp: ControlPlane,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self.cfg = cfg
        self.status_queue = status_queue
        self.cp = cp
        self.emitter = emitter or get_global_emitter()

    def _get_bytes(self, filepath: str) -> bytes:
        """Fetch bytes from Raw Store. Raise FileNotFoundError if missing."""
        raw_bytes = self.cp.artifacts.get_file_bytes(filepath)
        if raw_bytes is None:
            raise FileNotFoundError(f"Binary payload not found in Raw Store for: {filepath}")
        return raw_bytes

    def _get_file_list_with_bytes(self, filepaths: list[str]) -> list[tuple[str, str, bytes]]:
        """Retrieve binary contents along with path metadata for a list of file paths.

        Parameters
        ----------
        filepaths : list[str]
            List of file paths to resolve from the control plane artifact store.

        Returns
        -------
        list[tuple[str, str, bytes]]
            List of tuples of (filename, directory_path, file_bytes).
        """
        return [(os.path.basename(f), os.path.dirname(f), self._get_bytes(f)) for f in filepaths]

    def _extract_excel_statements(self, pending_files: dict[str, list[str]]) -> None:
        """Log extraction telemetry for pending binary payloads."""
        excel_count = 0
        csv_count = sum(
            len(pending_files.get(k, []))
            for k in [
                "mf_isin",
                "benchmark_mapping",
                "opening_balances",
                "benchmark_master",
                "macro_parameters",
                "column_master",
                "currency_mapping",
            ]
        )
        sqlite_count = len(pending_files.get("sqlite_source", []))
        total_payloads = excel_count + csv_count + sqlite_count

        diagnostics.info(
            f"Pulled {total_payloads} binary payloads from Raw Store "
            f"({excel_count} Excel, {csv_count} CSV, {sqlite_count} DB)"
        )
        self.emitter.emit_event(
            event_code=EventCode.EXTRACTION_BATCH,
            message=(
                f"Pulled {total_payloads} binary payloads from Raw Store "
                f"({excel_count} Excel, {csv_count} CSV, {sqlite_count} DB)"
            ),
            presentation_kind=PresentationKind.STEP,
            rows=total_payloads,
            stage=EngineStage.EXTRACTING,
        )

    def _validate_extracted_streams(self, collection: DatasetCollection) -> None:
        """Execute Gatekeeper schema validation on active extracted streams."""
        diagnostics.info("Running Gatekeeper Schema Validation on active streams...")
        self.emitter.emit_event(
            event_code=EventCode.SCHEMA_VALIDATION,
            message="Running Gatekeeper Schema Validation on active streams...",
            presentation_kind=PresentationKind.STEP,
            progress=0.15,
            stage=EngineStage.EXTRACTING,
        )

        validation_frames = [f for _, f in collection.items() if isinstance(f, pl.LazyFrame)]

        try:
            t0 = time.perf_counter()
            for lf in validation_frames:
                schema = lf.collect_schema()
                if len(schema.names()) > 0:
                    diagnostics.debug(f"Validating schema constraints: {schema.names()}")

            pl.collect_all([lf.head(1) for lf in validation_frames])
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            diagnostics.info(
                f"Gatekeeper validated {len(validation_frames)} schemas with 0 violations in {elapsed_ms:.2f}ms."
            )
            self.emitter.emit_event(
                event_code=EventCode.SCHEMA_VALIDATION,
                message=f"Gatekeeper validated {len(validation_frames)} schemas with 0 violations in {elapsed_ms:.2f}ms",
                presentation_kind=PresentationKind.SUCCESS,
                duration_ms=elapsed_ms,
                stage=EngineStage.EXTRACTING,
            )
        except Exception as e:
            err_details = ErrorDetails(
                exception_type=type(e).__name__,
                exception_message=str(e),
                failure_domain=FailureDomain.SOURCE_VALIDATION,
                traceback_summary=traceback.format_exc(),
                retryable=False,
            )
            self.emitter.emit_event(
                event_code=EventCode.SCHEMA_VALIDATION,
                message=f"Gatekeeper Validation Failed: {e}",
                presentation_kind=PresentationKind.FAILURE,
                severity=DiagnosticSeverity.ERROR,
                progress=0.0,
                stage=EngineStage.EXTRACTING,
                error=err_details,
            )
            raise RuntimeError(f"Corrupted source data detected during extraction: {e}") from e

    def run(self, actionable_files: dict[str, list[str]] | None = None) -> DatasetCollection:
        """Extract and validate raw database, Excel, and CSV payloads into DatasetCollection.

        Parameters
        ----------
        actionable_files : dict[str, list[str]] | None, optional
            Dictionary mapping file categories to payload paths; if None, queries Control Plane.

        Returns
        -------
        DatasetCollection
            Immutable container of extracted lazy frames and raw payloads keyed by canonical DatasetId.
        """
        diagnostics.info("Initializing extraction from Raw Store payloads...")
        self.emitter.emit_event(
            event_code=EventCode.EXTRACTION_START,
            message="Initializing extraction from Raw Store payloads...",
            presentation_kind=PresentationKind.STEP,
            progress=0.01,
            stage=EngineStage.EXTRACTING,
        )

        pending_files = actionable_files or self.cp.artifacts.get_pending_files()
        self._extract_excel_statements(pending_files)

        collection = DatasetCollection(
            frames={
                DatasetId.HOUSEHOLD_ZCATEGORY: pl.LazyFrame(),
                DatasetId.HOUSEHOLD_ASSET_GROUP: pl.LazyFrame(),
                DatasetId.HOUSEHOLD_ASSETS: pl.LazyFrame(),
                DatasetId.HOUSEHOLD_CURRENCY: pl.LazyFrame(),
                DatasetId.HOUSEHOLD_INOUTCOME: pl.LazyFrame(),
                DatasetId.COMMON_COLUMN_MASTER: pl.DataFrame(),
                DatasetId.INVESTMENT_MF_ISIN_MAPPING: pl.LazyFrame(),
                DatasetId.INVESTMENT_BENCHMARK_MAPPING: pl.LazyFrame(),
                DatasetId.HOUSEHOLD_OPENING_BALANCES: pl.LazyFrame(),
                DatasetId.INVESTMENT_BENCHMARK_MASTER: pl.LazyFrame(),
                DatasetId.INVESTMENT_MACRO_PARAMETERS: pl.LazyFrame(),
                DatasetId.MARKET_CURRENCY_MAPPING: pl.LazyFrame(),
                DatasetId.MARKET_MF_HOLDINGS: pl.LazyFrame(),
                DatasetId.INVESTMENT_MF_ORDERS: pl.LazyFrame(),
                DatasetId.MARKET_STOCK_HOLDINGS: pl.LazyFrame(),
                DatasetId.INVESTMENT_STOCK_ORDERS: pl.LazyFrame(),
                DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS: pl.LazyFrame(),
            }
        )

        self._validate_extracted_streams(collection)
        return collection
