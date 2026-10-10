import gc
import multiprocessing
import os
import sys
import time
import traceback
import zlib
from datetime import date
from typing import Any, cast

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.config.settings import Settings
from personal_finance_etl.backend.engines.analytics import InvestmentQuantEngine
from personal_finance_etl.backend.engines.presentation.wealth_engine import WealthPresentationEngine
from personal_finance_etl.backend.engines.tax.tax_engine import TaxEngine
from personal_finance_etl.backend.extract.sqlite_extractor import SQLiteExtractor
from personal_finance_etl.backend.extract.statement_locator import categorize_statement_files
from personal_finance_etl.backend.load.bronze import BronzeLayer
from personal_finance_etl.backend.load.control_plane import ControlPlane
from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.load.gold import GoldLayer
from personal_finance_etl.backend.load.metadata import MetaLayer
from personal_finance_etl.backend.load.registry import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
    validate_registry,
)
from personal_finance_etl.backend.load.silver import SilverLayer
from personal_finance_etl.backend.pipeline.benchmark_pipeline import BenchmarkPipeline
from personal_finance_etl.backend.pipeline.core.extractor import DataExtractor
from personal_finance_etl.backend.pipeline.core.transformer import TransformationDAG
from personal_finance_etl.backend.pipeline.currency_pipeline import CurrencyPipeline
from personal_finance_etl.backend.pipeline.us_market_pipeline import USMarketPipeline
from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import (
    add_file_handler,
    add_queue_handler,
    logger,
    remove_file_handlers,
    stop_worker_listener,
)
from personal_finance_etl.backend.utils.models import EngineStatus, ExtractionResult, LogLevel


class ETLOrchestrator:
    def __init__(self, cfg: Settings, status_queue: ILogger, rules: "FinancialRules | None" = None):

        self.cfg = cfg
        self.rules = rules
        self.status_queue = status_queue
        self.db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)
        self.dfs: dict[str, pl.DataFrame] = {}

    def _extract(
        self,
        cp: ControlPlane,
        actionable_files: dict[str, list[str]] | None = None,
    ) -> ExtractionResult:
        extractor = DataExtractor(self.cfg, self.status_queue, cp)
        return extractor.run(actionable_files)

    def _transform(self, extracted_data: ExtractionResult) -> None:
        transformer = TransformationDAG(self.cfg, self.status_queue, self.rules)
        self.dfs = transformer.run(extracted_data)

    def _process_benchmark(self, cp: ControlPlane, bronze: BronzeLayer) -> None:
        pipeline = BenchmarkPipeline(cp, bronze, self.status_queue)
        self.dfs["df_f_investment_benchmark_data"] = pipeline.process(
            df_market=self.dfs.get("df_f_investment_market_data"),
            df_purchase=self.dfs.get("df_f_tf_inv_purchase"),
            df_master=self.dfs["df_d_benchmark_master"],
        )

    def _process_currency(self, cp: ControlPlane, bronze: BronzeLayer) -> None:
        pipeline = CurrencyPipeline(cp, bronze, self.status_queue, max_workers=8)

        # Start Date: Earliest date in Calendar
        cal_pd = self.dfs["df_d_calendar"]
        if cal_pd.is_empty():
            global_start_date = date.today()
        else:
            sd = cal_pd.select(pl.min("Date")).item()
            global_start_date = sd if sd is not None else date.today()

        # End Date: Max date of Indian Market Data
        df_market = self.dfs.get("df_f_investment_market_data")
        global_end_date = date.today()
        if df_market is not None and not df_market.is_empty():
            ed = df_market.select(pl.col("Date").drop_nulls().max()).item()
            if ed is not None:
                global_end_date = ed

        self.dfs["df_f_currency_fx_rates"] = pipeline.run(
            df_currency=self.dfs["df_d_currency"],
            global_start_date=global_start_date,
            global_end_date=global_end_date,
        )

    def _process_us_market_data(self, cp: ControlPlane, bronze: BronzeLayer) -> None:
        pipeline = USMarketPipeline(cp, bronze, self.status_queue, max_workers=8)

        # Start Date: Earliest US Stock transaction
        df_purchase = self.dfs.get("df_f_tf_inv_purchase")
        df_sale = self.dfs.get("df_f_tf_inv_sale")

        valid_starts: list[date] = []
        if df_purchase is not None and not df_purchase.is_empty():
            us_p = df_purchase.filter(pl.col("__file_category__") == "US Stocks")
            if not us_p.is_empty():
                d = us_p.select(pl.col("Date").drop_nulls().min()).item()
                if isinstance(d, date):
                    valid_starts.append(d)

        if df_sale is not None and not df_sale.is_empty():
            us_s = df_sale.filter(pl.col("__file_category__") == "US Stocks")
            if not us_s.is_empty():
                d = us_s.select(pl.col("Date").drop_nulls().min()).item()
                if isinstance(d, date):
                    valid_starts.append(d)
        global_start_date = min(valid_starts) if valid_starts else date.today()

        # End Date: Max date of Indian Market Data
        df_market = self.dfs.get("df_f_investment_market_data")
        global_end_date = date.today()
        if df_market is not None and not df_market.is_empty():
            ed = df_market.select(pl.col("Date").drop_nulls().max()).item()
            if ed is not None:
                global_end_date = ed

        df_us_market = pipeline.run(
            df_purchase=self.dfs["df_f_tf_inv_purchase"],
            df_sale=self.dfs["df_f_tf_inv_sale"],
            df_master=self.dfs["df_d_investment_master"],
            df_fx=self.dfs["df_f_currency_fx_rates"],
            global_start_date=global_start_date,
            global_end_date=global_end_date,
        )

        if not df_us_market.is_empty():
            # Union into f_Investment_Market_Data
            df_market_existing = self.dfs.get("df_f_investment_market_data")
            if df_market_existing is not None and not df_market_existing.is_empty():
                df_combined = pl.concat([df_market_existing, df_us_market], how="diagonal_relaxed")
                self.dfs["df_f_investment_market_data"] = df_combined
            else:
                self.dfs["df_f_investment_market_data"] = df_us_market

    def _run_engines(self, cp: "ControlPlane | None", run_id: str) -> None:

        logger.info("Starting Investment Quant Engine...")
        self.status_queue.put(EngineStatus(msg="", data=None, progress=0.6, level=LogLevel.STEP))

        quant_engine = InvestmentQuantEngine(
            df_p=self.dfs["df_f_tf_inv_purchase"],
            df_s=self.dfs["df_f_tf_inv_sale"],
            df_m=self.dfs["df_f_investment_market_data"],
            df_i=self.dfs["df_d_investment_master"],
            df_b=self.dfs["df_f_investment_benchmark_data"],
            df_t=self.dfs["df_d_macro_parameters"],
            df_fx=self.dfs.get("df_f_currency_fx_rates"),
            status_queue=self.status_queue,
            rules=self.rules,
            start_date=None,
            end_date=None,
            run_id=run_id,
        )
        analytics_results = quant_engine.run()
        self.dfs.update(analytics_results)
        lot_df = analytics_results.get("df_f_investment_analytics_lot", pl.DataFrame())
        if (
            not lot_df.is_empty()
            and "Quantity" in lot_df.columns
            and "Closing_Date" in lot_df.columns
        ):
            max_date = lot_df.select(pl.col("Closing_Date").max()).item()
            open_lots = lot_df.filter(
                (pl.col("Closing_Date") == max_date) & (pl.col("Quantity") > 0)
            ).height
        else:
            open_lots = 0

        logger.info(f"  -> Quant Engine mapped {open_lots} open tax lots across portfolio.")

        # Fetch Rules Snapshot ID — needed by TaxEngine as an input and by log_simulation_run.
        # Placed here so it's available before Tax runs.
        rules_snapshot_id = "UNKNOWN"
        settings_snapshot_id = None
        if cp and self.rules:
            metadata = cp.runs.get_run_metadata(run_id)
            settings_snapshot_id = metadata.get("settings_snapshot_id")
            rules_snapshot_id = metadata.get("rules_snapshot_id") or "UNKNOWN"

        # Tax Engine — runs AFTER Quant (needs df_f_investment_realized_events produced by FIFO)
        # and BEFORE Presentation so that tax outputs land in self.dfs and are available to
        # WealthPresentationEngine for any current or future tax-aware presentation tables.
        logger.info("Executing Tax Engine...")
        tax_engine = TaxEngine(
            df_income=self.dfs["df_f_income_transactions"],
            df_realized_events=self.dfs["df_f_investment_realized_events"],
            df_subcategory=self.dfs["df_d_income_subcategory"],
            df_market=self.dfs.get("df_f_investment_market_data", pl.DataFrame()),
            df_analytics_lot=self.dfs.get("df_f_investment_analytics_lot", pl.DataFrame()),
            df_macro=self.dfs.get("df_d_macro_parameters", pl.DataFrame()),
            rules=self.rules,
            rules_snapshot_id=rules_snapshot_id,
        )
        tax_results = tax_engine.run()
        self.dfs.update(tax_results)

        logger.info("Starting Presentation Layer Engines...")
        self.status_queue.put(EngineStatus(msg="", data=None, progress=0.8, level=LogLevel.STEP))

        if self.rules is None:
            raise ValueError("FinancialRules must be provided to ETL pipeline")

        wealth_engine = WealthPresentationEngine(rules=self.rules, root_seed=run_id)
        wealth_lazy = wealth_engine.run(self.dfs)

        presentation_lazy = wealth_lazy
        if presentation_lazy:
            logger.info("Executing Presentation DAG in Parallel...")
            self.status_queue.put(
                EngineStatus(
                    msg="",
                    data=None,
                    progress=0.9,
                    level=LogLevel.STEP,
                )
            )
            keys = list(presentation_lazy.keys())
            logger.info(f"  -> Spawning {len(keys)} concurrent Polars streaming graphs...")
            lazy_frames = [presentation_lazy[k] for k in keys]
            results = pl.collect_all(lazy_frames, engine="streaming")
            for k, res in zip(keys, results, strict=True):
                self.dfs[k] = res

        if cp and self.rules:
            cp.runs.log_simulation_run(
                run_id=str(run_id),
                root_seed=str(run_id),
                rules=self.rules,
                input_df=self.dfs.get("df_p_tf_wealth_risk_analytics_inputs"),
                settings_snapshot_id=settings_snapshot_id,
                rules_snapshot_id=rules_snapshot_id if rules_snapshot_id != "UNKNOWN" else None,
            )

        if "df_p_tf_wealth_risk_analytics_inputs" in self.dfs:
            self.dfs.pop("df_p_tf_wealth_risk_analytics_inputs")

    def run(self) -> None:
        self.cfg.validate_config()

        validate_registry()

        start_time = time.perf_counter()

        run_id = None
        cp = None
        log_file_path = self.db_manager.db_path.replace(".duckdb", ".log")

        try:
            add_queue_handler(cast("multiprocessing.Queue[Any]", self.status_queue))
            add_file_handler(log_file_path)

            logger.debug("=== ETL CONFIGURATION DUMP ===")
            if hasattr(self.cfg, "model_dump_json"):
                logger.debug(self.cfg.model_dump_json(indent=2))
            else:
                logger.debug(str(self.cfg))

            logger.debug("=== FINANCIAL RULES DUMP ===")
            if self.rules is not None and hasattr(self.rules, "model_dump_json"):
                logger.debug(self.rules.model_dump_json(indent=2))
            else:
                logger.debug(str(self.rules))
            logger.debug("==============================")

            logger.info("Initializing Quantitative Master Engine...")
            self.status_queue.put(EngineStatus(msg="", data=None, progress=0.0))

            logger.info(f"Target Database: {self.cfg.TARGET_DB_BASE_PATH}")
            logger.info(f"Source Extractor Folder: {self.cfg.STATEMENTS_FOLDER}")

            self.db_manager.open()
            self.db_manager.ensure_schemas()

            cp = ControlPlane(self.cfg.TARGET_DB_BASE_PATH, self.cfg.RAW_DOCUMENT_STORE_NAME)
            cp.open()
            cp.ensure_schema()

            # 1. Authoritative SQLite State
            run_id = cp.runs.start_run(
                cfg_json=self.cfg.model_dump_json(),
                rules_json=self.rules.model_dump_json() if self.rules else None,
            )
            cp.active_run_id = run_id
            cp.artifacts.active_run_id = run_id
            cp.file_sync.active_run_id = run_id

            # 2. Mirror to DuckDB Analytics
            meta_layer = MetaLayer(self.db_manager, self.cfg, self.rules)
            meta_layer.heal_duckdb_registry(cp)

            # Start ACID Transaction for the entire ETL run
            logger.debug("[DATABASE:DUCKDB] BEGIN TRANSACTION")
            self.db_manager.conn.execute("BEGIN TRANSACTION")
            cp.begin_transaction()

            cp.runs.update_run_status(run_id, "RUNNING")

            t_ext_start = time.perf_counter()
            renames: list[tuple[str, str, str]] = []
            if not self.cfg.DISABLE_FILE_DISCOVERER:
                logger.info("[PHASE] --- 1/5: Discovery & Sync ---")

                discovered_files = categorize_statement_files(
                    self.cfg.STATEMENTS_FOLDER, strict=True
                )
                discovered_files["sqlite_source"] = [
                    SQLiteExtractor(self.cfg.SOURCE_DB_FOLDER)
                    .get_latest_sqlite_backup()
                    .replace("\\", "/")
                ]
                discovered_files["mf_isin"] = [self.cfg.MF_ISIN_CSV_PATH.replace("\\", "/")]
                discovered_files["benchmark_mapping"] = [
                    self.cfg.BENCHMARK_MAPPING_CSV_PATH.replace("\\", "/")
                ]
                discovered_files["opening_balances"] = [
                    self.cfg.OPENING_BALANCE_CSV_PATH.replace("\\", "/")
                ]
                discovered_files["benchmark_master"] = [
                    self.cfg.BENCHMARK_MASTER_CSV_PATH.replace("\\", "/")
                ]
                discovered_files["macro_parameters"] = [
                    self.cfg.MACRO_PARAMETERS_CSV_PATH.replace("\\", "/")
                ]
                discovered_files["currency_mapping"] = [
                    self.cfg.CURRENCY_MAPPING_CSV_PATH.replace("\\", "/")
                ]
                discovered_files["column_master"] = [self.cfg.COLUMN_MASTER_PATH.replace("\\", "/")]
                logger.info(
                    "[DISCOV] Injected 8 dynamic configuration assets (7 CSV, 1 SQLite DB)."
                )

                full_replace_categories = list(
                    set(
                        contract.sync_category
                        for contract in BRONZE_CONTRACT_REGISTRY
                        if contract.is_full_replace
                    )
                )
                new_files, changed_files, _, renames = cp.file_sync.sync_with_disk(
                    discovered_files, self.cfg.FILE_HASH_POLICY, full_replace_categories
                )

                pending_files = cp.artifacts.get_pending_files()
                actionable_all = {}
                all_keys = set(discovered_files.keys()).union(pending_files.keys())
                for k in all_keys:
                    paths = (
                        new_files.get(k, []) + changed_files.get(k, []) + pending_files.get(k, [])
                    )

                    if paths:
                        # Normalize slashes to ensure set() deduplicates absolute vs relative variations properly
                        normalized_paths = {p.replace("\\", "/") for p in paths}
                        actionable_all[k] = list(normalized_paths)
            else:
                logger.info(
                    "Phase 1/5: Bypassing File Discoverer. Fetching pending files from Raw Store..."
                )
                actionable_all = cp.artifacts.get_pending_files()

            extracted_data = self._extract(cp, actionable_files=actionable_all)
            logger.info(
                f"Phase 1 Complete [{time.perf_counter() - t_ext_start:.2f}s] - Actionable streams loaded into memory."
            )

            t_bronze_start = time.perf_counter()
            logger.info("[PHASE] --- 2/5: Upserting new datasets into Bronze Lakehouse ---")

            bronze = BronzeLayer(self.db_manager, cp, meta_layer)
            if renames:
                bronze.migrate_identity(renames)
                meta_layer.migrate_identity(renames)

            bronze.load(extracted_data, actionable_all)
            logger.info(
                f"Phase 2 Complete [{time.perf_counter() - t_bronze_start:.2f}s] - Bronze layer synchronized."
            )

            logger.debug(
                "[ENGINE:READ] Fetching complete dataset from Bronze Lakehouse for Transformation..."
            )
            full_dataset = bronze.get_full_dataset(extracted_data.mappings)

            t_trans_start = time.perf_counter()
            logger.info("[PHASE] --- 3/5: Transforming and harmonizing data streams ---")
            self._transform(full_dataset)
            logger.info(
                f"[PHASE] 3/5 Complete [{time.perf_counter() - t_trans_start:.2f}s] - DAG mapped {len(self.dfs)} base tables."
            )

            self._process_currency(cp, bronze)
            self._process_us_market_data(cp, bronze)
            self._process_benchmark(cp, bronze)

            t_eng_start = time.perf_counter()
            logger.info("[PHASE] --- 4/5: Executing Advanced Analytics & Monte Carlo engines ---")
            self._run_engines(cp, str(run_id))

            # Strict DataContract Validation

            registered_contracts = {c.contract_id for c in DATA_CONTRACT_REGISTRY}
            for df_key in self.dfs.keys():
                if df_key not in registered_contracts:
                    raise RuntimeError(
                        f"Engine produced unregistered table '{df_key}'. All analytical tables must be defined in DATA_CONTRACT_REGISTRY."
                    )

            missing_contracts = registered_contracts - set(self.dfs.keys())
            if missing_contracts:
                raise RuntimeError(f"Engine failed to produce required tables: {missing_contracts}")

            logger.info(
                f"[PHASE] 4/5 Complete [{time.perf_counter() - t_eng_start:.2f}s] - Presentation logic built {len(self.dfs)} total tables."
            )

            # Load Phase (Silver & Gold)
            t_load_start = time.perf_counter()
            logger.info("[PHASE] --- 5/5: Fully replacing Silver and Gold analytical layers ---")
            SilverLayer(self.db_manager).load(self.dfs)
            GoldLayer(self.db_manager).load(self.dfs)
            logger.info(
                f"[PHASE] 5/5 Complete [{time.perf_counter() - t_load_start:.2f}s] - Disk synchronization successful."
            )

            # Write ETL metadata to DB
            meta_layer = MetaLayer(self.db_manager, self.cfg, self.rules)
            meta_layer.load(self.dfs, cp=cp)

            cp.runs.update_run_status(run_id, "COMMITTING")

            # Commit the ACID Transaction
            try:
                logger.debug("[DATABASE:DUCKDB] COMMIT")
                self.db_manager.conn.execute("COMMIT")
            except Exception as duckdb_commit_err:
                raise RuntimeError(
                    f"DuckDB Commit Failed: {duckdb_commit_err}"
                ) from duckdb_commit_err

            try:
                cp.commit()
            except Exception as sqlite_commit_err:
                # DuckDB committed, but SQLite failed. The next run will rely on idempotency
                # and Bronze self-healing to resolve this state mismatch.
                raise RuntimeError(
                    f"SQLite Commit Failed after DuckDB committed: {sqlite_commit_err}"
                ) from sqlite_commit_err

            cp.runs.finish_run(run_id, "SUCCESS")

            self.status_queue.put(EngineStatus(msg="", data=None, progress=1.0))
            total_time = time.perf_counter() - start_time
            logger.info(
                f"✅ Pipeline Execution Successful in {total_time:.2f} seconds. Total Nodes: {len(self.dfs)}"
            )
        except Exception as e:
            logger.exception("CRITICAL PIPELINE FAILURE:")
            # Rollback all changes if any phase fails
            try:
                logger.debug("[DATABASE:DUCKDB] ROLLBACK")
                self.db_manager.conn.execute("ROLLBACK")
                logger.warning("DuckDB transaction rolled back.")
            except Exception as rollback_err:
                logger.error(f"Failed to rollback DuckDB transaction: {rollback_err}")

            try:
                if cp is not None:
                    cp.rollback()
            except Exception as rollback_err:
                logger.error(f"Failed to rollback SQLite Raw Store transaction: {rollback_err}")

            logger.warning(
                "Pipeline failed. Transactions completely rolled back to maintain ACID integrity."
            )

            # Persist failure details
            try:
                if cp is not None and run_id is not None:
                    if "ISIN_FAILURE" in str(e):
                        parts = str(e).split("|")
                        if len(parts) >= 3:
                            failed_isin = parts[1]
                            error_msg = parts[2]
                            cp.runs.log_run_failure(
                                run_id=run_id,
                                failed_isin=failed_isin,
                                stage="InvestmentQuantEngine",
                                error_type="RuntimeError",
                                error_message=error_msg,
                                traceback_log=traceback.format_exc(),
                            )
                    else:
                        cp.runs.log_run_failure(
                            run_id=run_id,
                            failed_isin=None,
                            stage="Pipeline",
                            error_type=type(e).__name__,
                            error_message=str(e),
                            traceback_log=traceback.format_exc(),
                        )
            except Exception as failure_log_err:
                logger.error(f"Failed to log run_failure to Control Plane: {failure_log_err}")

            if cp is not None and run_id is not None:
                cp.runs.finish_run(run_id, "FAILED")

            raise e
        finally:
            logger.info("Cleaning up database connections and WAL sidecars...")
            stop_worker_listener()
            remove_file_handlers()
            try:
                if cp is not None and run_id is not None and os.path.exists(log_file_path):
                    with open(log_file_path, "rb") as f:
                        log_bytes = f.read()
                    compressed_log = zlib.compress(log_bytes, level=9)
                    cp.runs.save_execution_log(run_id, compressed_log)
            except Exception as log_err:
                logger.error(f"Failed to save compressed execution log to Raw Store: {log_err}")

            try:
                self.db_manager.close()
            finally:
                if cp is not None:
                    cp.close()
                gc.collect()


def process_wrapper(
    status_queue: ILogger | None = None, config_path: str = "config.toml", rules_path: str = ""
) -> None:
    """Wrapper to catch exceptions inside the child process and send them back to the UI."""

    class QueueStream:
        def __init__(self, queue: ILogger, is_error: bool = False):
            self.queue = queue
            self.buffer = ""
            self.is_error = is_error

        def write(self, msg: str) -> None:
            self.buffer += msg
            if "\n" in self.buffer:
                lines = self.buffer.split("\n")
                for line in lines[:-1]:
                    if line.strip():
                        # For warnings/errors from yfinance
                        level = LogLevel.WARNING if self.is_error else LogLevel.INFO
                        self.queue.put(
                            EngineStatus(msg=line.strip(), data=None, progress=None, level=level)
                        )
                self.buffer = lines[-1]

        def flush(self) -> None:
            pass

    sys.stdout = QueueStream(status_queue, is_error=False)  # type: ignore
    sys.stderr = QueueStream(status_queue, is_error=True)  # type: ignore

    try:
        cfg = Settings()
        if config_path:
            cfg = Settings.from_toml(config_path)

        if status_queue is None:
            status_queue = cast(ILogger, multiprocessing.Queue())

        rules = FinancialRules.from_toml(rules_path)

        orchestrator = ETLOrchestrator(cfg, status_queue, rules)
        orchestrator.run()

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
        time.sleep(0.5)
        raise e
