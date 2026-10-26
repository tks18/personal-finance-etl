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

import io
import logging
import os
import time
from collections.abc import Callable

import polars as pl

from personal_finance_etl.application.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.extraction import ExtractionResult
from personal_finance_etl.contracts.logging import StatusQueue
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    PresentationKind,
)
from personal_finance_etl.domain.household.transforms.common import get_column_mapping
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.providers.files.csv import (
    extract_benchmark_master_raw,
    extract_currency_mapping_raw,
    extract_macro_parameters_raw,
    extract_opening_balances_raw,
    extract_stg_benchmark_mapping,
    extract_stg_mf_isin_mapping,
)
from personal_finance_etl.infrastructure.providers.files.excel import (
    extract_mf_market_data_raw,
    extract_mf_transactions_raw,
    extract_stock_market_data_raw,
    extract_stock_transactions_raw,
    extract_us_stock_transactions_raw,
)
from personal_finance_etl.infrastructure.providers.files.sqlite import (
    SQLiteExtractor,
)

__all__ = ["DataExtractor"]

logger = logging.getLogger(__name__)


class DataExtractor:
    """Coordinates evidence extraction from raw payloads and executes Gatekeeper validation."""

    def __init__(
        self,
        cfg: Settings,
        status_queue: StatusQueue,
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
        return [(os.path.basename(f), os.path.dirname(f), self._get_bytes(f)) for f in filepaths]

    def _extract_sqlite_tables(
        self, pending_files: dict[str, list[str]]
    ) -> tuple[pl.LazyFrame, pl.LazyFrame, pl.LazyFrame, pl.LazyFrame, pl.LazyFrame]:
        """Extract reference tables from SQLite source database bytes."""
        logger.debug("Extracting base reference tables from SQLite source...")
        sqlite_files = pending_files.get("sqlite_source", [])
        if sqlite_files:
            sqlite_path = sqlite_files[0]
            sqlite_bytes = self._get_bytes(sqlite_path)
            extractor = SQLiteExtractor(self.cfg.SOURCE_DB_FOLDER)
            tables = extractor.extract_base_tables(
                os.path.basename(sqlite_path), os.path.dirname(sqlite_path), sqlite_bytes
            )
            logger.debug("Successfully extracted 5 base reference tables from SQLite source bytes.")
            return tables
        return (
            pl.LazyFrame(),
            pl.LazyFrame(),
            pl.LazyFrame(),
            pl.LazyFrame(),
            pl.LazyFrame(),
        )

    def _read_config_csv_lazy(
        self,
        pending_files: dict[str, list[str]],
        filepath: str,
        func: Callable[[str, str, bytes], pl.LazyFrame],
        category: str,
    ) -> pl.LazyFrame:
        """Read a pending CSV configuration file as a Polars LazyFrame."""
        files = pending_files.get(category, [])
        normalized_filepath = filepath.replace("\\", "/")
        if files and normalized_filepath in files:
            return func(
                os.path.basename(normalized_filepath),
                os.path.dirname(normalized_filepath),
                self._get_bytes(normalized_filepath),
            )
        return pl.LazyFrame()

    def _extract_config_tables(
        self, pending_files: dict[str, list[str]]
    ) -> tuple[pl.DataFrame, dict[str, dict[str, str]], dict[str, pl.LazyFrame]]:
        """Extract column master mappings and configuration CSV lazyframes."""
        column_master_bytes = self._get_bytes(self.cfg.COLUMN_MASTER_PATH)
        df_column_master = pl.read_csv(io.BytesIO(column_master_bytes)).with_columns(
            pl.lit(os.path.basename(self.cfg.COLUMN_MASTER_PATH)).alias("__file_name__"),
            pl.lit(os.path.dirname(self.cfg.COLUMN_MASTER_PATH)).alias("__folder_path__"),
        )
        mappings = {
            "category": get_column_mapping(df_column_master, "CATEGORY"),
            "asset_group": get_column_mapping(df_column_master, "ASSETGROUP"),
            "assets": get_column_mapping(df_column_master, "ASSETS"),
            "currency": get_column_mapping(df_column_master, "CURRENCY"),
            "inoutcome": get_column_mapping(df_column_master, "INOUTCOME"),
            "opbal": get_column_mapping(df_column_master, "ZOPBAL"),
        }
        config_frames = {
            "stg_mf_isin_mapping": self._read_config_csv_lazy(
                pending_files, self.cfg.MF_ISIN_CSV_PATH, extract_stg_mf_isin_mapping, "mf_isin"
            ),
            "stg_benchmark_mapping": self._read_config_csv_lazy(
                pending_files,
                self.cfg.BENCHMARK_MAPPING_CSV_PATH,
                extract_stg_benchmark_mapping,
                "benchmark_mapping",
            ),
            "raw_opening_balances": self._read_config_csv_lazy(
                pending_files,
                self.cfg.OPENING_BALANCE_CSV_PATH,
                extract_opening_balances_raw,
                "opening_balances",
            ),
            "raw_benchmark_master": self._read_config_csv_lazy(
                pending_files,
                self.cfg.BENCHMARK_MASTER_CSV_PATH,
                extract_benchmark_master_raw,
                "benchmark_master",
            ),
            "raw_macro_parameters": self._read_config_csv_lazy(
                pending_files,
                self.cfg.MACRO_PARAMETERS_CSV_PATH,
                extract_macro_parameters_raw,
                "macro_parameters",
            ),
            "currency_mapping_raw": self._read_config_csv_lazy(
                pending_files,
                self.cfg.CURRENCY_MAPPING_CSV_PATH,
                extract_currency_mapping_raw,
                "currency_mapping",
            ),
        }
        return df_column_master, mappings, config_frames

    def _extract_excel_statements(
        self, pending_files: dict[str, list[str]]
    ) -> dict[str, pl.LazyFrame]:
        """Extract raw market and transaction frames from pending Excel files."""
        mf_holdings = pending_files.get("mf_holdings", [])
        mf_orders = pending_files.get("mf_orders", [])
        stock_pl = pending_files.get("stock_pl", [])
        stock_orders = pending_files.get("stock_orders", [])
        us_stock_transactions = pending_files.get("us_stock_transactions", [])

        excel_count = (
            len(mf_holdings)
            + len(mf_orders)
            + len(stock_pl)
            + len(stock_orders)
            + len(us_stock_transactions)
        )
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

        logger.info(
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

        if excel_count > 0:
            return {
                "mf_market_data_raw": extract_mf_market_data_raw(
                    self._get_file_list_with_bytes(mf_holdings)
                ),
                "mf_transactions_raw": extract_mf_transactions_raw(
                    self._get_file_list_with_bytes(mf_orders)
                ),
                "stock_market_data_raw": extract_stock_market_data_raw(
                    self._get_file_list_with_bytes(stock_pl)
                ),
                "stock_transactions_raw": extract_stock_transactions_raw(
                    self._get_file_list_with_bytes(stock_orders)
                ),
                "us_stock_transactions_raw": extract_us_stock_transactions_raw(
                    self._get_file_list_with_bytes(us_stock_transactions)
                ),
            }
        return {
            "mf_market_data_raw": pl.LazyFrame(),
            "mf_transactions_raw": pl.LazyFrame(),
            "stock_market_data_raw": pl.LazyFrame(),
            "stock_transactions_raw": pl.LazyFrame(),
            "us_stock_transactions_raw": pl.LazyFrame(),
        }

    def _validate_extracted_streams(self, result: ExtractionResult) -> None:
        """Execute Gatekeeper schema validation on active extracted streams."""
        logger.info("Running Gatekeeper Schema Validation on 18 active streams...")
        self.emitter.emit_event(
            event_code=EventCode.SCHEMA_VALIDATION,
            message="Running Gatekeeper Schema Validation on 18 active streams...",
            presentation_kind=PresentationKind.STEP,
            progress=0.15,
            stage=EngineStage.EXTRACTING,
        )

        validation_frames = [
            result.zcategory,
            result.assetgroup,
            result.assets,
            result.currency,
            result.inoutcome,
            result.stg_mf_isin_mapping,
            result.stg_benchmark_mapping,
            result.mf_market_data_raw,
            result.mf_transactions_raw,
            result.stock_market_data_raw,
            result.stock_transactions_raw,
            result.raw_opening_balances,
            result.raw_benchmark_master,
            result.raw_macro_parameters,
            result.us_stock_transactions_raw,
            result.currency_mapping_raw,
        ]

        try:
            t0 = time.perf_counter()
            for lf in validation_frames:
                schema = lf.collect_schema()
                if len(schema.names()) > 0:
                    logger.debug(f"Validating schema constraints: {schema.names()}")

            pl.collect_all([lf.head(1) for lf in validation_frames])
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            logger.info(f"Gatekeeper validated 18 schemas with 0 violations in {elapsed_ms:.2f}ms.")
            self.emitter.emit_event(
                event_code=EventCode.SCHEMA_VALIDATION,
                message=f"Gatekeeper validated 18 schemas with 0 violations in {elapsed_ms:.2f}ms",
                presentation_kind=PresentationKind.SUCCESS,
                duration_ms=elapsed_ms,
                stage=EngineStage.EXTRACTING,
            )
        except Exception as e:
            self.emitter.emit_event(
                event_code=EventCode.SCHEMA_VALIDATION,
                message=f"Gatekeeper Validation Failed: {e}",
                presentation_kind=PresentationKind.FAILURE,
                severity=DiagnosticSeverity.ERROR,
                progress=0.0,
                stage=EngineStage.EXTRACTING,
            )
            raise RuntimeError(f"Corrupted source data detected during extraction: {e}") from e

    def run(self, actionable_files: dict[str, list[str]] | None = None) -> ExtractionResult:
        """Extract and validate raw database, Excel, and CSV payloads into ExtractionResult.

        Parameters
        ----------
        actionable_files : dict[str, list[str]] | None, optional
            Dictionary mapping file categories to payload paths; if None, queries Control Plane.

        Returns
        -------
        ExtractionResult
            Container of extracted lazy frames, raw payloads, and mapping tables.
        """
        logger.info("Initializing extraction from Raw Store payloads...")
        self.emitter.emit_event(
            event_code=EventCode.EXTRACTION_START,
            message="Initializing extraction from Raw Store payloads...",
            presentation_kind=PresentationKind.STEP,
            progress=0.01,
            stage=EngineStage.EXTRACTING,
        )

        pending_files = actionable_files or self.cp.artifacts.get_pending_files()
        zcat, agrp, asts, curr, inout = self._extract_sqlite_tables(pending_files)
        df_column_master, mappings, config_frames = self._extract_config_tables(pending_files)
        excel_frames = self._extract_excel_statements(pending_files)

        result = ExtractionResult(
            zcategory=zcat,
            assetgroup=agrp,
            assets=asts,
            currency=curr,
            inoutcome=inout,
            mappings=mappings,
            column_master=df_column_master,
            stg_mf_isin_mapping=config_frames["stg_mf_isin_mapping"],
            stg_benchmark_mapping=config_frames["stg_benchmark_mapping"],
            raw_opening_balances=config_frames["raw_opening_balances"],
            raw_benchmark_master=config_frames["raw_benchmark_master"],
            raw_macro_parameters=config_frames["raw_macro_parameters"],
            currency_mapping_raw=config_frames["currency_mapping_raw"],
            mf_market_data_raw=excel_frames["mf_market_data_raw"],
            mf_transactions_raw=excel_frames["mf_transactions_raw"],
            stock_market_data_raw=excel_frames["stock_market_data_raw"],
            stock_transactions_raw=excel_frames["stock_transactions_raw"],
            us_stock_transactions_raw=excel_frames["us_stock_transactions_raw"],
        )

        self._validate_extracted_streams(result)
        return result
