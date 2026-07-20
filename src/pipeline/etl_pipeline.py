import gc
import multiprocessing
import os
import time
import traceback
from datetime import date, datetime
from typing import cast

import polars as pl

from src.config.settings import Settings, load_config
from src.engines.benchmark_engine import BenchmarkEngine
from src.engines.tax_engine import PolarsTaxEngine
from src.extract.sqlite_extractor import ADBCSQLiteExtractor
from src.extract.statement_locator import categorize_statement_files
from src.load.database import SQLiteLoader, generate_target_db_path, setup_sqlite_schema
from src.pipeline.strategies import AssetPipeline, MutualFundPipeline, StockPipeline
from src.transform.core import (
    get_base_transactions,
    get_column_mapping,
    get_d_tf_investment_master,
    get_f_tf_investment_purchase_data,
    get_f_tf_investment_sale_data,
    get_stg_benchmark_mapping,
    get_stg_calendar_ref,
    get_stg_mf_isin_mapping,
    transform_d_asset_category,
    transform_d_asset_subcategory,
    transform_d_calendar,
    transform_d_currency,
    transform_d_expense_category,
    transform_d_expense_subcategory,
    transform_d_income_category,
    transform_d_income_subcategory,
    transform_d_investment_benchmark_master,
    transform_d_tax_rates,
    transform_f_expense_transactions,
    transform_f_income_transactions,
    transform_f_opening_balances,
    transform_f_transfer_transactions,
    transform_stg_investment_market_data,
)
from src.utils.interfaces import IDatabaseLoader, ILogger
from src.utils.logger import add_queue_handler, logger
from src.utils.models import EngineStatus, ExtractionResult, LogLevel


class DataExtractor:
    def __init__(self, cfg: Settings, status_queue: ILogger):
        self.cfg = cfg
        self.status_queue = status_queue

    def run(self) -> ExtractionResult:
        self.status_queue.put(
            EngineStatus(
                msg="Validating input configuration files...",
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

        stg_mf_isin_mapping_lazy = get_stg_mf_isin_mapping(self.cfg.MF_ISIN_CSV_PATH)
        stg_benchmark_mapping_lazy = get_stg_benchmark_mapping(self.cfg.BENCHMARK_MAPPING_CSV_PATH)

        logger.info("Categorizing Statement Files...")
        statement_files = categorize_statement_files(self.cfg.STATEMENTS_FOLDER)

        return ExtractionResult(
            zcategory=zcategory_lazy,
            assetgroup=assetgroup_lazy,
            assets=assets_lazy,
            currency=currency_lazy,
            inoutcome=inoutcome_lazy,
            mappings=mappings,
            stg_mf_isin_mapping=stg_mf_isin_mapping_lazy,
            stg_benchmark_mapping=stg_benchmark_mapping_lazy,
            statement_files=statement_files,
        )


class TransformationDAG:
    def __init__(self, cfg: Settings, status_queue: ILogger):
        self.cfg = cfg
        self.status_queue = status_queue

    def run(self, extracted: ExtractionResult) -> dict[str, pl.DataFrame]:
        logger.info("Transforming Base Dimensions...")
        mappings = extracted.mappings
        d_income_category_lazy = transform_d_income_category(
            extracted.zcategory, mappings["category"]
        )
        d_income_subcategory_lazy = transform_d_income_subcategory(
            extracted.zcategory, mappings["category"], d_income_category_lazy
        )
        d_expense_category_lazy = transform_d_expense_category(
            extracted.zcategory, mappings["category"]
        )
        d_expense_subcategory_lazy = transform_d_expense_subcategory(
            extracted.zcategory, mappings["category"]
        )
        d_asset_category_lazy = transform_d_asset_category(
            extracted.assetgroup, mappings["asset_group"]
        )
        d_asset_subcategory_lazy = transform_d_asset_subcategory(
            extracted.assets, mappings["assets"]
        )
        d_currency_lazy = transform_d_currency(extracted.currency, mappings["currency"])
        d_benchmark_master_lazy = transform_d_investment_benchmark_master(
            self.cfg.BENCHMARK_MASTER_CSV_PATH
        )
        d_tax_rates_lazy = transform_d_tax_rates(self.cfg.TAX_RATES_CSV_PATH)

        base_transactions_lazy = get_base_transactions(extracted.inoutcome, mappings["inoutcome"])
        f_income_transactions_lazy = transform_f_income_transactions(base_transactions_lazy)
        f_expense_transactions_lazy = transform_f_expense_transactions(base_transactions_lazy)
        f_transfer_transactions_lazy = transform_f_transfer_transactions(
            base_transactions_lazy, d_asset_subcategory_lazy, d_asset_category_lazy
        )
        f_opening_balances_lazy = transform_f_opening_balances(
            self.cfg.OPENING_BALANCE_CSV_PATH, mappings["opbal"]
        )

        asset_pipelines: list[AssetPipeline] = [MutualFundPipeline(), StockPipeline()]

        asset_results = []
        for pipeline in asset_pipelines:
            asset_results.append(pipeline.process(extracted, d_asset_subcategory_lazy, logger))

        [res.market_data for res in asset_results]
        market_data_ref_lazy_list = [res.market_data_ref for res in asset_results]
        purchase_ref_lazy_list = [res.purchase_ref for res in asset_results]
        sale_ref_lazy_list = [res.sale_ref for res in asset_results]
        master_ref_lazy_list = [res.master_ref for res in asset_results]

        stg_investment_market_data_lazy = transform_stg_investment_market_data(
            market_data_ref_lazy_list
        )
        f_tf_inv_purchase_data_lazy = get_f_tf_investment_purchase_data(purchase_ref_lazy_list)
        f_tf_inv_sale_data_lazy = get_f_tf_investment_sale_data(sale_ref_lazy_list)

        logger.info("Building Investment Master...")
        d_tf_investment_master_lazy = get_d_tf_investment_master(
            master_ref_lazy_list, extracted.stg_benchmark_mapping
        )

        logger.info("Generating Master Calendar...")
        # Get first market_data to seed calendar (simplified since they're processed downstream anyway)
        min_date, max_date = get_stg_calendar_ref(
            f_income_transactions_lazy,
            f_expense_transactions_lazy,
            f_transfer_transactions_lazy,
            f_opening_balances_lazy,
            stg_investment_market_data_lazy,
            f_tf_inv_purchase_data_lazy,
            f_tf_inv_sale_data_lazy,
        )
        d_calendar_lazy = transform_d_calendar(min_date, max_date)

        self.status_queue.put(
            EngineStatus(
                msg="Executing Base Transformation DAG in Parallel...",
                data=None,
                progress=0.2,
                level=LogLevel.STEP,
            )
        )
        logger.info("Executing Base Transformation DAG in Parallel...")
        results = pl.collect_all(
            [
                d_income_category_lazy,
                d_income_subcategory_lazy,
                d_expense_category_lazy,
                d_expense_subcategory_lazy,
                d_asset_category_lazy,
                d_asset_subcategory_lazy,
                d_currency_lazy,
                d_benchmark_master_lazy,
                d_tax_rates_lazy,
                f_income_transactions_lazy,
                f_expense_transactions_lazy,
                f_transfer_transactions_lazy,
                f_opening_balances_lazy,
                stg_investment_market_data_lazy,
                f_tf_inv_purchase_data_lazy,
                f_tf_inv_sale_data_lazy,
                d_tf_investment_master_lazy,
                d_calendar_lazy,
            ],
            engine="streaming",
        )

        return {
            "df_d_income_category": results[0],
            "df_d_income_subcategory": results[1],
            "df_d_expense_category": results[2],
            "df_d_expense_subcategory": results[3],
            "df_d_asset_category": results[4],
            "df_d_asset_subcategory": results[5],
            "df_d_currency": results[6],
            "df_d_benchmark_master": results[7],
            "df_d_tax_rates": results[8],
            "df_f_income_transactions": results[9],
            "df_f_expense_transactions": results[10],
            "df_f_transfer_transactions": results[11],
            "df_f_opening_balances": results[12],
            "df_stg_investment_market_data": results[13],
            "df_f_tf_inv_purchase": results[14],
            "df_f_tf_inv_sale": results[15],
            "df_d_tf_investment_master": results[16],
            "df_d_calendar": results[17],
        }


def run_pipeline(status_queue: ILogger, cfg: Settings) -> None:
    start_time = time.time()

    if cfg is None:
        raise ValueError("Configuration settings (cfg) cannot be None")

    add_queue_handler(cast(multiprocessing.Queue, status_queue))
    logger.info("Starting ETL Pipeline")
    status_queue.put(EngineStatus(msg="", data=None, progress=0.0))
    target_db_path = generate_target_db_path(cfg.TARGET_DB_BASE_PATH)
    logger.info(f"Setting up Target DB at {target_db_path}")
    setup_sqlite_schema(target_db_path)

    # 1. Extraction
    extractor = DataExtractor(cfg, status_queue)
    extracted_data = extractor.run()

    # 2. Transformation
    transformer = TransformationDAG(cfg, status_queue)
    dfs = transformer.run(extracted_data)

    # 3. Detect date range for benchmarks
    status_queue.put(
        EngineStatus(
            msg="Detecting date range for Benchmarks...",
            data=None,
            progress=0.35,
            level=LogLevel.STEP,
        )
    )
    market_dates = dfs["df_stg_investment_market_data"].select(pl.col("Date").drop_nulls())
    purchase_dates = dfs["df_f_tf_inv_purchase"].select(pl.col("Date").drop_nulls())

    min_market_date = (
        market_dates.select(pl.min("Date")).item() if not market_dates.is_empty() else None
    )
    max_market_date = (
        market_dates.select(pl.max("Date")).item() if not market_dates.is_empty() else None
    )
    min_purchase_date = (
        purchase_dates.select(pl.min("Date")).item() if not purchase_dates.is_empty() else None
    )

    valid_start_dates = [d for d in [min_market_date, min_purchase_date] if d is not None]
    if valid_start_dates:
        start_date = min(valid_start_dates)
        end_date = max_market_date or date.today()
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
    else:
        start_date = date(2000, 1, 1)
        end_date = date.today()

    # 4. Engine Processing
    status_queue.put(
        EngineStatus(
            msg="Starting Benchmark Engine...", data=None, progress=0.4, level=LogLevel.STEP
        )
    )
    bm_engine = BenchmarkEngine(
        df_m=dfs["df_d_benchmark_master"],
        status_queue=status_queue,
        start_date=start_date,
        end_date=end_date,
        target_db_base_path=cfg.TARGET_DB_BASE_PATH,
        current_db_path=target_db_path,
    )
    dfs["df_f_investment_benchmark_data"] = bm_engine.run()

    status_queue.put(
        EngineStatus(
            msg="Starting Polars Tax Engine...", data=None, progress=0.6, level=LogLevel.STEP
        )
    )
    tax_engine = PolarsTaxEngine(
        df_p=dfs["df_f_tf_inv_purchase"],
        df_s=dfs["df_f_tf_inv_sale"],
        df_m=dfs["df_stg_investment_market_data"],
        df_i=dfs["df_d_tf_investment_master"],
        df_b=dfs["df_f_investment_benchmark_data"]
        if dfs["df_f_investment_benchmark_data"] is not None
        else pl.DataFrame(),
        df_t=dfs["df_d_tax_rates"],
        status_queue=status_queue,
        start_date=None,
        end_date=None,
    )
    dfs["df_f_investment_market_data"] = tax_engine.run()

    # 5. Load Data
    loader: IDatabaseLoader = SQLiteLoader(target_db_path, status_queue)
    loader.run(dfs)

    status_queue.put(EngineStatus(msg="", data=None, progress=1.0))
    total_time = time.time() - start_time
    logger.info(f"ETL complete in {total_time:.2f} seconds. All tables generated successfully.")
    gc.collect()


def process_wrapper(status_queue: ILogger | None = None, config_path: str = "config.toml") -> None:
    """Wrapper to catch exceptions inside the child process and send them back to the UI."""
    try:
        cfg = Settings()
        if config_path:
            cfg = load_config(config_path)

        if status_queue is None:
            # Type ignore because Queue duck-types as ILogger but mypy can't verify Protocol without explicit wrapper
            from typing import cast

            run_pipeline(cast(ILogger, multiprocessing.Queue()), cfg)
        else:
            run_pipeline(status_queue, cfg)
    except Exception as e:
        if status_queue is not None:
            status_queue.put(
                EngineStatus(
                    msg=f"Critical Pipeline Failure: {e}\n{traceback.format_exc()}",
                    data=None,
                    progress=0.0,
                    level=LogLevel.ERROR,
                )
            )
        # Brief pause to ensure the queue message flushes before process destruction
        time.sleep(0.5)
