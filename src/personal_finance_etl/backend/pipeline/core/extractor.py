import os

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
from personal_finance_etl.backend.extract.sqlite_extractor import ADBCSQLiteExtractor
from personal_finance_etl.backend.extract.statement_locator import categorize_statement_files
from personal_finance_etl.backend.transform.helpers import get_column_mapping
from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import EngineStatus, ExtractionResult, LogLevel


class DataExtractor:
    def __init__(self, cfg: Settings, status_queue: ILogger):
        self.cfg = cfg
        self.status_queue = status_queue

    def run(self, actionable_files: dict[str, list[str]] | None = None) -> ExtractionResult:
        logger.info("Validating input configuration files...")
        self.status_queue.put(
            EngineStatus(
                msg="",
                data=None,
                progress=0.01,
                level=LogLevel.STEP,
            )
        )
        required_files = [
            self.cfg.COLUMN_MASTER_PATH,
            self.cfg.MF_ISIN_CSV_PATH,
            self.cfg.BENCHMARK_MAPPING_CSV_PATH,
            self.cfg.BENCHMARK_MASTER_CSV_PATH,
            self.cfg.MACRO_PARAMETERS_CSV_PATH,
            self.cfg.OPENING_BALANCE_CSV_PATH,
        ]
        for filepath in required_files:
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Missing required configuration file: {filepath}")

        extractor = ADBCSQLiteExtractor(self.cfg.SOURCE_DB_FOLDER)
        logger.info("Extracting Base Tables from SQLite...")
        zcategory_lazy, assetgroup_lazy, assets_lazy, currency_lazy, inoutcome_lazy = (
            extractor.extract_base_tables()
        )
        logger.info("  -> Successfully extracted 5 base reference tables from SQLite Source.")

        df_column_master = pl.read_csv(self.cfg.COLUMN_MASTER_PATH).with_columns(
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

        stg_mf_isin_mapping_lazy = (
            extract_stg_mf_isin_mapping(self.cfg.MF_ISIN_CSV_PATH)
            if (not actionable_files or actionable_files.get("mf_isin"))
            else pl.LazyFrame()
        )
        stg_benchmark_mapping_lazy = (
            extract_stg_benchmark_mapping(self.cfg.BENCHMARK_MAPPING_CSV_PATH)
            if (not actionable_files or actionable_files.get("benchmark_mapping"))
            else pl.LazyFrame()
        )
        raw_opening_balances = (
            extract_opening_balances_raw(self.cfg.OPENING_BALANCE_CSV_PATH)
            if (not actionable_files or actionable_files.get("opening_balances"))
            else pl.LazyFrame()
        )
        raw_benchmark_master = (
            extract_benchmark_master_raw(self.cfg.BENCHMARK_MASTER_CSV_PATH)
            if (not actionable_files or actionable_files.get("benchmark_master"))
            else pl.LazyFrame()
        )
        raw_macro_parameters = (
            extract_macro_parameters_raw(self.cfg.MACRO_PARAMETERS_CSV_PATH)
            if (not actionable_files or actionable_files.get("macro_parameters"))
            else pl.LazyFrame()
        )

        logger.info("Categorizing Statement Files from FULL Statements Folder...")
        if not self.cfg.STATEMENTS_FOLDER or not os.path.isdir(self.cfg.STATEMENTS_FOLDER):
            raise FileNotFoundError("Statements folder not found.")

        statement_files = categorize_statement_files(self.cfg.STATEMENTS_FOLDER, strict=True)
        if actionable_files is not None:
            for k in statement_files:
                statement_files[k] = [
                    f for f in statement_files[k] if f in actionable_files.get(k, [])
                ]

        total_files = sum(len(f) for f in statement_files.values())

        if total_files > 0:
            logger.info(f"Extracting {total_files} FULL Excel Binaries...")
            mf_market_data_raw = extract_mf_market_data_raw(statement_files["mf_holdings"])
            mf_transactions_raw = extract_mf_transactions_raw(statement_files["mf_orders"])
            stock_market_data_raw = extract_stock_market_data_raw(statement_files["stock_pl"])
            stock_transactions_raw = extract_stock_transactions_raw(statement_files["stock_orders"])
            logger.info(f"  -> Successfully parsed {total_files} raw Excel files.")
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
        # Fail-fast by attempting to collect the first row of all extract lazy frames.
        # This will trigger Polars to aggressively evaluate schema_overrides and cast(strict=True)
        # instantly, preventing OOM or compute waste down the DAG if source files are corrupted.
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
