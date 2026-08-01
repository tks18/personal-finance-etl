import os

import polars as pl

from src.config.settings import Settings
from src.extract.csv_extractor import (
    extract_benchmark_master_raw,
    extract_inflation_rates_raw,
    extract_opening_balances_raw,
    extract_stg_benchmark_mapping,
    extract_stg_mf_isin_mapping,
    extract_tax_rates_raw,
)
from src.extract.excel_extractor import (
    extract_mf_market_data_raw,
    extract_mf_transactions_raw,
    extract_stock_market_data_raw,
    extract_stock_transactions_raw,
)
from src.extract.sqlite_extractor import ADBCSQLiteExtractor
from src.extract.statement_locator import categorize_statement_files
from src.transform.helpers import get_column_mapping
from src.utils.interfaces import ILogger
from src.utils.logger import logger
from src.utils.models import EngineStatus, ExtractionResult, LogLevel


class DataExtractor:
    def __init__(self, cfg: Settings, status_queue: ILogger):
        self.cfg = cfg
        self.status_queue = status_queue

    def run(self) -> ExtractionResult:
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
            self.cfg.TAX_RATES_CSV_PATH,
            self.cfg.OPENING_BALANCE_CSV_PATH,
            self.cfg.INFLATION_RATES_CSV_PATH,
        ]
        for filepath in required_files:
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"Missing required configuration file: {filepath}")

        extractor = ADBCSQLiteExtractor(self.cfg.SOURCE_DB_FOLDER)
        logger.info("Extracting Base Tables from SQLite...")
        zcategory_lazy, assetgroup_lazy, assets_lazy, currency_lazy, inoutcome_lazy = (
            extractor.extract_base_tables()
        )

        df_column_master = pl.read_csv(self.cfg.COLUMN_MASTER_PATH)
        mappings = {
            "category": get_column_mapping(df_column_master, "CATEGORY"),
            "asset_group": get_column_mapping(df_column_master, "ASSETGROUP"),
            "assets": get_column_mapping(df_column_master, "ASSETS"),
            "currency": get_column_mapping(df_column_master, "CURRENCY"),
            "inoutcome": get_column_mapping(df_column_master, "INOUTCOME"),
            "opbal": get_column_mapping(df_column_master, "ZOPBAL"),
        }

        stg_mf_isin_mapping_lazy = extract_stg_mf_isin_mapping(self.cfg.MF_ISIN_CSV_PATH)
        stg_benchmark_mapping_lazy = extract_stg_benchmark_mapping(
            self.cfg.BENCHMARK_MAPPING_CSV_PATH
        )
        raw_opening_balances = extract_opening_balances_raw(self.cfg.OPENING_BALANCE_CSV_PATH)
        raw_benchmark_master = extract_benchmark_master_raw(self.cfg.BENCHMARK_MASTER_CSV_PATH)
        raw_tax_rates = extract_tax_rates_raw(self.cfg.TAX_RATES_CSV_PATH)
        raw_inflation_rates = extract_inflation_rates_raw(self.cfg.INFLATION_RATES_CSV_PATH)

        logger.info("Categorizing Statement Files...")
        statement_files = categorize_statement_files(self.cfg.STATEMENTS_FOLDER)

        logger.info("Extracting Unstructured Excel Binaries...")
        mf_market_data_raw = extract_mf_market_data_raw(statement_files["mf_holdings"])
        mf_transactions_raw = extract_mf_transactions_raw(statement_files["mf_orders"])
        stock_market_data_raw = extract_stock_market_data_raw(statement_files["stock_pl"])
        stock_transactions_raw = extract_stock_transactions_raw(statement_files["stock_orders"])

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
            raw_tax_rates=raw_tax_rates,
            raw_inflation_rates=raw_inflation_rates,
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
            result.raw_tax_rates,
            result.raw_inflation_rates,
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
