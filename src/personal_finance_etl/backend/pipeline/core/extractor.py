import io
import os
from collections.abc import Callable

import polars as pl

from personal_finance_etl.backend.config.settings import Settings
from personal_finance_etl.backend.extract.csv_extractor import (
    extract_benchmark_master_raw,
    extract_macro_parameters_raw,
    extract_opening_balances_raw,
    extract_stg_benchmark_mapping,
    extract_stg_mf_isin_mapping,
)
from personal_finance_etl.backend.extract.excel_extractor import (
    extract_mf_market_data_raw,
    extract_mf_transactions_raw,
    extract_stock_market_data_raw,
    extract_stock_transactions_raw,
)
from personal_finance_etl.backend.extract.sqlite_extractor import SQLiteExtractor
from personal_finance_etl.backend.load.control_plane import ControlPlane
from personal_finance_etl.backend.transform.helpers import get_column_mapping
from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import EngineStatus, ExtractionResult, LogLevel


class DataExtractor:
    def __init__(self, cfg: Settings, status_queue: ILogger, cp: "ControlPlane"):
        self.cfg = cfg
        self.status_queue = status_queue
        self.cp = cp

    def _get_bytes(self, filepath: str) -> bytes:
        """Fetches bytes from Raw Store. Raises if missing."""
        raw_bytes = self.cp.artifacts.get_file_bytes(filepath)
        if raw_bytes is None:
            raise FileNotFoundError(f"Binary payload not found in Raw Store for: {filepath}")
        return raw_bytes

    def _get_file_list_with_bytes(self, filepaths: list[str]) -> list[tuple[str, str, bytes]]:
        return [(os.path.basename(f), os.path.dirname(f), self._get_bytes(f)) for f in filepaths]

    def run(self, actionable_files: dict[str, list[str]] | None = None) -> ExtractionResult:
        logger.info("Initializing extraction from Raw Store payloads...")
        self.status_queue.put(
            EngineStatus(
                msg="",
                data=None,
                progress=0.01,
                level=LogLevel.STEP,
            )
        )

        # Determine files to process
        pending_files = actionable_files or self.cp.artifacts.get_pending_files()

        logger.info("Extracting Base Tables from SQLite...")
        # Get sqlite file
        sqlite_files = pending_files.get("sqlite_source", [])
        if sqlite_files:
            sqlite_path = sqlite_files[0]
            sqlite_bytes = self._get_bytes(sqlite_path)
            extractor = SQLiteExtractor(self.cfg.SOURCE_DB_FOLDER)
            zcategory_lazy, assetgroup_lazy, assets_lazy, currency_lazy, inoutcome_lazy = (
                extractor.extract_base_tables(
                    os.path.basename(sqlite_path), os.path.dirname(sqlite_path), sqlite_bytes
                )
            )
            logger.info(
                "  -> Successfully extracted 5 base reference tables from SQLite Source bytes."
            )
        else:
            zcategory_lazy = pl.LazyFrame()
            assetgroup_lazy = pl.LazyFrame()
            assets_lazy = pl.LazyFrame()
            currency_lazy = pl.LazyFrame()
            inoutcome_lazy = pl.LazyFrame()

        # Config files

        def get_csv_lazy(
            filepath: str, func: Callable[[str, str, bytes], pl.LazyFrame], category: str
        ) -> pl.LazyFrame:
            files = pending_files.get(category, [])
            normalized_filepath = filepath.replace("\\", "/")
            if files and normalized_filepath in files:
                return func(
                    os.path.basename(normalized_filepath),
                    os.path.dirname(normalized_filepath),
                    self._get_bytes(normalized_filepath),
                )
            return pl.LazyFrame()

        # column_master is always required to build mappings, read it directly or from bytes
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

        stg_mf_isin_mapping_lazy = get_csv_lazy(
            self.cfg.MF_ISIN_CSV_PATH, extract_stg_mf_isin_mapping, "mf_isin"
        )
        stg_benchmark_mapping_lazy = get_csv_lazy(
            self.cfg.BENCHMARK_MAPPING_CSV_PATH, extract_stg_benchmark_mapping, "benchmark_mapping"
        )
        raw_opening_balances = get_csv_lazy(
            self.cfg.OPENING_BALANCE_CSV_PATH, extract_opening_balances_raw, "opening_balances"
        )
        raw_benchmark_master = get_csv_lazy(
            self.cfg.BENCHMARK_MASTER_CSV_PATH, extract_benchmark_master_raw, "benchmark_master"
        )
        raw_macro_parameters = get_csv_lazy(
            self.cfg.MACRO_PARAMETERS_CSV_PATH, extract_macro_parameters_raw, "macro_parameters"
        )

        mf_holdings = pending_files.get("mf_holdings", [])
        mf_orders = pending_files.get("mf_orders", [])
        stock_pl = pending_files.get("stock_pl", [])
        stock_orders = pending_files.get("stock_orders", [])

        total_files = len(mf_holdings) + len(mf_orders) + len(stock_pl) + len(stock_orders)

        if total_files > 0:
            logger.info(f"Extracting {total_files} Excel Binaries from Raw Store...")
            mf_market_data_raw = extract_mf_market_data_raw(
                self._get_file_list_with_bytes(mf_holdings)
            )
            mf_transactions_raw = extract_mf_transactions_raw(
                self._get_file_list_with_bytes(mf_orders)
            )
            stock_market_data_raw = extract_stock_market_data_raw(
                self._get_file_list_with_bytes(stock_pl)
            )
            stock_transactions_raw = extract_stock_transactions_raw(
                self._get_file_list_with_bytes(stock_orders)
            )
            logger.info(f"  -> Successfully parsed {total_files} raw Excel payloads.")
        else:
            mf_market_data_raw = pl.LazyFrame()
            mf_transactions_raw = pl.LazyFrame()
            stock_market_data_raw = pl.LazyFrame()
            stock_transactions_raw = pl.LazyFrame()

        result = ExtractionResult(
            zcategory=zcategory_lazy,
            assetgroup=assetgroup_lazy,
            assets=assets_lazy,
            currency=currency_lazy,
            inoutcome=inoutcome_lazy,
            mappings=mappings,
            stg_mf_isin_mapping=stg_mf_isin_mapping_lazy,
            stg_benchmark_mapping=stg_benchmark_mapping_lazy,
            mf_market_data_raw=mf_market_data_raw,
            mf_transactions_raw=mf_transactions_raw,
            stock_market_data_raw=stock_market_data_raw,
            stock_transactions_raw=stock_transactions_raw,
            raw_opening_balances=raw_opening_balances,
            raw_benchmark_master=raw_benchmark_master,
            raw_macro_parameters=raw_macro_parameters,
            column_master=df_column_master,
        )

        logger.info("Running Gatekeeper Schema Validation...")
        self.status_queue.put(
            EngineStatus(
                msg="",
                data=None,
                progress=0.15,
                level=LogLevel.STEP,
            )
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
        ]

        try:
            pl.collect_all([lf.head(1) for lf in validation_frames])
        except Exception as e:
            self.status_queue.put(
                EngineStatus(
                    msg=f"Gatekeeper Validation Failed: {e}",
                    data=None,
                    progress=0,
                    level=LogLevel.ERROR,
                )
            )
            raise RuntimeError(f"Corrupted source data detected during extraction: {e}") from e

        return result
