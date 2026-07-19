import polars as pl
import sqlite3
import queue
import multiprocessing
import gc
import traceback
import time
from datetime import date, datetime
from typing import Any

from src.config.settings import load_config, Settings
from src.utils.logger import logger, add_queue_handler

from src.extract.sqlite_extractor import get_latest_sqlite_backup, extract_base_tables
from src.extract.excel_parser import categorize_statement_files
from src.transform.stocks import (
    get_stg_stock_market_data, get_stg_stock_market_data_ref,
    get_base_stock_transactions, transform_stg_stock_trades,
    get_stg_stock_master_ref
)
from src.transform.mutual_funds import (
    get_stg_mf_market_data, get_stg_mf_market_data_ref,
    get_base_mf_transactions, transform_stg_mf_trades,
    get_stg_mf_master_ref
)
from src.transform.core import (
    get_column_mapping, get_stg_mf_isin_mapping, get_stg_benchmark_mapping,
    get_purchase_reference, get_sale_reference,
    transform_d_income_category, transform_d_income_subcategory,
    transform_d_expense_category, transform_d_expense_subcategory,
    transform_d_asset_category, transform_d_asset_subcategory,
    transform_d_currency, transform_d_investment_benchmark_master,
    transform_d_tax_rates, get_base_transactions,
    transform_f_income_transactions, transform_f_expense_transactions,
    transform_f_transfer_transactions, transform_f_opening_balances,
    get_stg_calendar_ref, transform_d_calendar,
    transform_stg_investment_market_data, get_f_tf_investment_purchase_data,
    get_f_tf_investment_sale_data, get_d_tf_investment_master
)
from src.load.database import (
    setup_sqlite_schema, apply_indexes_and_optimize,
    generate_target_db_path, batch_write_database
)
from src.engines.tax_engine import PolarsTaxEngine
from src.engines.benchmark_engine import BenchmarkEngine


def run_pipeline(
    status_queue: Any = None,
    cfg: Settings | None = None
):
    start_time = time.time()
    if status_queue is None:
        status_queue = multiprocessing.Queue()  # type: ignore

    if cfg is None:
        raise ValueError("Configuration settings (cfg) cannot be None")

    add_queue_handler(status_queue)

    logger.info("Starting ETL Pipeline")
    status_queue.put(("", None, 0.0))
    logger.info("Starting Base ETL Extraction...")
    target_db_path = generate_target_db_path(cfg.TARGET_DB_BASE_PATH)

    # 1. Setup Target DB
    logger.info(f"Setting up Target DB at {target_db_path}")
    setup_sqlite_schema(target_db_path)

    # 2. Extract Data
    latest_backup = get_latest_sqlite_backup(cfg.SOURCE_DB_FOLDER)

    logger.info("Extracting Base Tables from SQLite...")
    zcategory_lazy, assetgroup_lazy, assets_lazy, currency_lazy, inoutcome_lazy = extract_base_tables(
        latest_backup)

    # Load mappings once
    df_column_master = pl.read_csv(cfg.COLUMN_MASTER_PATH)
    category_mapping = get_column_mapping(df_column_master, "CATEGORY")
    asset_group_mapping = get_column_mapping(df_column_master, "ASSETGROUP")
    assets_mapping = get_column_mapping(df_column_master, "ASSETS")
    currency_mapping = get_column_mapping(df_column_master, "CURRENCY")
    inoutcome_mapping = get_column_mapping(df_column_master, "INOUTCOME")
    opbal_mapping = get_column_mapping(df_column_master, "ZOPBAL")

    # Staging Tables for Downstream Processing
    stg_mf_isin_mapping_lazy = get_stg_mf_isin_mapping(cfg.MF_ISIN_CSV_PATH)
    stg_benchmark_mapping_lazy = get_stg_benchmark_mapping(
        cfg.BENCHMARK_MAPPING_CSV_PATH)

    logger.info("Categorizing Statement Files...")
    statement_files = categorize_statement_files(cfg.STATEMENTS_FOLDER)

    logger.info("Parsing unstructured Stock Excel files...")
    stg_stock_market_data_lazy = get_stg_stock_market_data(
        statement_files["stock_pl"])

    logger.info("Parsing unstructured Mutual Fund Excel files...")
    stg_mf_market_data_lazy = get_stg_mf_market_data(
        statement_files["mf_holdings"],
        stg_mf_isin_mapping_lazy
    )

    stg_stock_market_data_ref_lazy = get_stg_stock_market_data_ref(
        stg_stock_market_data_lazy)
    stg_mf_market_data_ref_lazy = get_stg_mf_market_data_ref(
        stg_mf_market_data_lazy)

    logger.info("Parsing Stock Trade Orders...")
    base_stock_orders_lazy = get_base_stock_transactions(
        statement_files["stock_orders"])

    stg_stock_purchase_transactions_lazy = transform_stg_stock_trades(
        base_stock_orders_lazy, trade_type="BUY")
    stg_stock_sale_transactions_lazy = transform_stg_stock_trades(
        base_stock_orders_lazy, trade_type="SELL")

    logger.info("Parsing Mutual Fund Trade Orders...")
    base_mf_orders_lazy = get_base_mf_transactions(
        statement_files["mf_orders"])

    stg_mf_purchase_transactions_lazy = transform_stg_mf_trades(
        base_mf_orders_lazy, stg_mf_isin_mapping_lazy, trade_type="PURCHASE"
    )
    stg_mf_sale_transactions_lazy = transform_stg_mf_trades(
        base_mf_orders_lazy, stg_mf_isin_mapping_lazy, trade_type="REDEEM"
    )

    logger.info("Aggregating Investment Purchases...")
    mf_purchase_ref_lazy = get_purchase_reference(
        stg_mf_purchase_transactions_lazy, "Final Scheme Name", "Date", "NAV", "Units"
    )
    stock_purchase_ref_lazy = get_purchase_reference(
        stg_stock_purchase_transactions_lazy, "Stock name", "Execution date and time", "Price", "Quantity"
    )

    logger.info(
        "Processing Investment Sales and Rolling Buy-Price Aggregations...")
    mf_sale_ref_lazy = get_sale_reference(
        stg_mf_sale_transactions_lazy, mf_purchase_ref_lazy,
        "Final Scheme Name", "Date", "NAV", "Units"
    )
    stock_sale_ref_lazy = get_sale_reference(
        stg_stock_sale_transactions_lazy, stock_purchase_ref_lazy,
        "Stock name", "Execution date and time", "Price", "Quantity"
    )

    # 3. Transform Data
    logger.info("Transforming Data...")
    d_income_category_lazy = transform_d_income_category(
        zcategory_lazy, category_mapping)
    d_income_subcategory_lazy = transform_d_income_subcategory(
        zcategory_lazy, category_mapping, d_income_category_lazy)
    d_expense_category_lazy = transform_d_expense_category(
        zcategory_lazy, category_mapping)
    d_expense_subcategory_lazy = transform_d_expense_subcategory(
        zcategory_lazy, category_mapping)
    d_asset_category_lazy = transform_d_asset_category(
        assetgroup_lazy, asset_group_mapping)
    d_asset_subcategory_lazy = transform_d_asset_subcategory(
        assets_lazy, assets_mapping)
    d_currency_lazy = transform_d_currency(currency_lazy, currency_mapping)
    d_benchmark_master_lazy = transform_d_investment_benchmark_master(
        cfg.BENCHMARK_MASTER_CSV_PATH)
    d_tax_rates_lazy = transform_d_tax_rates(cfg.TAX_RATES_CSV_PATH)

    base_transactions_lazy = get_base_transactions(
        inoutcome_lazy, inoutcome_mapping)
    f_income_transactions_lazy = transform_f_income_transactions(
        base_transactions_lazy)
    f_expense_transactions_lazy = transform_f_expense_transactions(
        base_transactions_lazy)
    f_transfer_transactions_lazy = transform_f_transfer_transactions(
        base_transactions_lazy, d_asset_subcategory_lazy, d_asset_category_lazy)
    f_opening_balances_lazy = transform_f_opening_balances(
        cfg.OPENING_BALANCE_CSV_PATH, opbal_mapping)

    stg_investment_market_data_lazy = transform_stg_investment_market_data(
        stg_stock_market_data_ref_lazy, stg_mf_market_data_ref_lazy)
    f_tf_inv_purchase_data_lazy = get_f_tf_investment_purchase_data(
        stock_purchase_ref_lazy, mf_purchase_ref_lazy)
    f_tf_inv_sale_data_lazy = get_f_tf_investment_sale_data(
        stock_sale_ref_lazy, mf_sale_ref_lazy)

    # Remove the manual scripts.benchmark_gen call
    # The Benchmark Engine will handle it in the next phase

    logger.info("Building Investment Master...")
    stg_stock_master_ref_lazy = get_stg_stock_master_ref(
        stg_stock_market_data_lazy, d_asset_subcategory_lazy)
    stg_mf_master_ref_lazy = get_stg_mf_master_ref(
        stg_mf_market_data_lazy, stg_mf_purchase_transactions_lazy, stg_mf_sale_transactions_lazy, d_asset_subcategory_lazy)

    d_tf_investment_master_lazy = get_d_tf_investment_master(
        stg_stock_master_ref_lazy, stg_mf_master_ref_lazy, stg_benchmark_mapping_lazy)

    logger.info("Generating Master Calendar...")
    min_date, max_date = get_stg_calendar_ref(
        f_income_transactions_lazy, f_expense_transactions_lazy, f_transfer_transactions_lazy,
        f_opening_balances_lazy, stg_investment_market_data_lazy, f_tf_inv_purchase_data_lazy, f_tf_inv_sale_data_lazy
    )
    d_calendar_lazy = transform_d_calendar(min_date, max_date)

    status_queue.put(
        ("Executing Base Transformation DAG in Parallel...", None, 0.2))
    logger.info("Executing Base Transformation DAG in Parallel...")
    (
        df_d_income_category, df_d_income_subcategory, df_d_expense_category, df_d_expense_subcategory,
        df_d_asset_category, df_d_asset_subcategory, df_d_currency, df_d_benchmark_master, df_d_tax_rates,
        df_f_income_transactions, df_f_expense_transactions, df_f_transfer_transactions, df_f_opening_balances,
        df_stg_investment_market_data, df_f_tf_inv_purchase, df_f_tf_inv_sale, df_d_tf_investment_master, df_d_calendar
    ) = pl.collect_all([
        d_income_category_lazy, d_income_subcategory_lazy, d_expense_category_lazy, d_expense_subcategory_lazy,
        d_asset_category_lazy, d_asset_subcategory_lazy, d_currency_lazy, d_benchmark_master_lazy, d_tax_rates_lazy,
        f_income_transactions_lazy, f_expense_transactions_lazy, f_transfer_transactions_lazy, f_opening_balances_lazy,
        stg_investment_market_data_lazy, f_tf_inv_purchase_data_lazy, f_tf_inv_sale_data_lazy, d_tf_investment_master_lazy, d_calendar_lazy
    ], engine="streaming")

    # Compute start and end dates from Market Data and Purchase Data
    status_queue.put(("Detecting date range for Benchmarks...", None, 0.35))
    market_dates = df_stg_investment_market_data.select(
        pl.col("Date").drop_nulls())
    purchase_dates = df_f_tf_inv_purchase.select(pl.col("Date").drop_nulls())

    min_market_date = market_dates.select(
        pl.min("Date")).item() if not market_dates.is_empty() else None
    max_market_date = market_dates.select(
        pl.max("Date")).item() if not market_dates.is_empty() else None
    min_purchase_date = purchase_dates.select(
        pl.min("Date")).item() if not purchase_dates.is_empty() else None

    valid_start_dates = [d for d in [
        min_market_date, min_purchase_date] if d is not None]

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
    status_queue.put(("Starting Benchmark Engine...", None, 0.4))
    bm_engine = BenchmarkEngine(
        df_m=df_d_benchmark_master,
        status_queue=status_queue,
        start_date=start_date,
        end_date=end_date,
        target_db_base_path=cfg.TARGET_DB_BASE_PATH,
        current_db_path=target_db_path
    )
    df_f_investment_benchmark_data = bm_engine.run()

    status_queue.put(("Starting Polars Tax Engine...", None, 0.6))

    # Setup PolarsTaxEngine
    df_p = df_f_tf_inv_purchase
    df_s = df_f_tf_inv_sale

    tax_engine = PolarsTaxEngine(
        df_p=df_p,
        df_s=df_s,
        df_m=df_stg_investment_market_data,
        df_i=df_d_tf_investment_master,
        df_b=df_f_investment_benchmark_data if df_f_investment_benchmark_data is not None else pl.DataFrame(),
        df_t=df_d_tax_rates,
        status_queue=status_queue,
        start_date=None,
        end_date=None
    )
    df_f_investment_market_data = tax_engine.run()

    # 5. Load Data into Target SQLite
    logger.info("Writing tables to SQLite in batches...")
    batch_write_database(df_d_calendar, "d_Calendar", target_db_path)
    batch_write_database(df_d_income_category,
                         "d_Income_Category", target_db_path)
    batch_write_database(df_d_income_subcategory,
                         "d_Income_Subcategory", target_db_path)
    batch_write_database(df_d_expense_category,
                         "d_Expense_Category", target_db_path)
    batch_write_database(df_d_expense_subcategory,
                         "d_Expense_Subcategory", target_db_path)
    batch_write_database(df_d_asset_category,
                         "d_Asset_Category", target_db_path)
    batch_write_database(df_d_asset_subcategory,
                         "d_Asset_SubCategory", target_db_path)
    batch_write_database(df_d_currency, "d_Currency", target_db_path)
    batch_write_database(df_d_benchmark_master,
                         "d_Investment_Benchmark_Master", target_db_path)
    batch_write_database(df_d_tf_investment_master,
                         "d_tf_Investment_Master", target_db_path)
    batch_write_database(df_d_tax_rates, "d_Tax_Rates", target_db_path)
    batch_write_database(df_f_income_transactions,
                         "f_Income_Transactions", target_db_path)
    batch_write_database(df_f_expense_transactions,
                         "f_Expense_Transactions", target_db_path)
    batch_write_database(df_f_transfer_transactions,
                         "f_Transfer_Transactions", target_db_path)
    batch_write_database(df_f_opening_balances,
                         "f_Opening_Balances", target_db_path)
    batch_write_database(df_stg_investment_market_data,
                         "stg_Investment_Market_Data", target_db_path)
    batch_write_database(df_f_tf_inv_purchase,
                         "f_tf_Investment_Purchase_Data", target_db_path)
    batch_write_database(
        df_f_tf_inv_sale, "f_tf_Investment_Sale_Data", target_db_path)
    batch_write_database(df_f_investment_benchmark_data,
                         "f_Investment_Benchmark_Data", target_db_path)
    batch_write_database(df_f_investment_market_data,
                         "f_Investment_Market_Data", target_db_path)

    status_queue.put(("", None, 0.9))
    logger.info("Applying indexes and optimizing database...")
    apply_indexes_and_optimize(target_db_path)

    with sqlite3.connect(target_db_path) as conn:
        conn.cursor().execute("PRAGMA optimize;")
        conn.cursor().execute("PRAGMA wal_checkpoint(TRUNCATE);")

    status_queue.put(("", None, 1.0))
    total_time = time.time() - start_time
    logger.info(
        f"ETL complete in {total_time:.2f} seconds. All tables generated successfully.")

    # Force garbage collection to destroy ADBC driver objects and release SQLite WAL file locks
    gc.collect()


def process_wrapper(status_queue: Any = None, config_path: str = "config.toml"):
    """Wrapper to catch exceptions inside the child process and send them back to the UI."""
    try:
        cfg = Settings()
        if config_path:
            cfg = load_config(config_path)
        run_pipeline(status_queue, cfg)
    except Exception as e:
        if status_queue is not None:
            status_queue.put(
                (f"Critical Pipeline Failure: {e}\n{traceback.format_exc()}", None, 0.0))
        # Brief pause to ensure the queue message flushes before process destruction
        time.sleep(0.5)
