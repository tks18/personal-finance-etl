import gc
import multiprocessing
import sys
import time
import traceback
from typing import Any, cast

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.config.settings import Settings
from personal_finance_etl.backend.engines.analytics import InvestmentQuantEngine
from personal_finance_etl.backend.engines.presentation.wealth_engine import WealthPresentationEngine
from personal_finance_etl.backend.extract.sqlite_extractor import SQLiteExtractor
from personal_finance_etl.backend.extract.statement_locator import categorize_statement_files
from personal_finance_etl.backend.load.bronze import BronzeLayer
from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.load.file_tracker import FileTracker
from personal_finance_etl.backend.load.gold import GoldLayer
from personal_finance_etl.backend.load.metadata import MetaLayer
from personal_finance_etl.backend.load.raw import RawDocumentStore
from personal_finance_etl.backend.load.silver import SilverLayer
from personal_finance_etl.backend.pipeline.benchmark_pipeline import BenchmarkPipeline
from personal_finance_etl.backend.pipeline.core.extractor import DataExtractor
from personal_finance_etl.backend.pipeline.core.transformer import TransformationDAG
from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import add_file_handler, add_queue_handler, logger
from personal_finance_etl.backend.utils.models import EngineStatus, ExtractionResult, LogLevel


class ETLOrchestrator:
    def __init__(self, cfg: Settings, status_queue: ILogger, rules: "FinancialRules | None" = None):

        self.cfg = cfg
        self.rules = rules
        self.status_queue = status_queue
        self.db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)
        self.dfs: dict[str, pl.DataFrame] = {}

    def _extract(
        self, raw_store: RawDocumentStore, actionable_files: dict[str, list[str]] | None = None
    ) -> ExtractionResult:
        extractor = DataExtractor(self.cfg, self.status_queue, raw_store)
        return extractor.run(actionable_files)

    def _transform(self, extracted_data: ExtractionResult) -> None:
        transformer = TransformationDAG(self.cfg, self.status_queue, self.rules)
        self.dfs = transformer.run(extracted_data)

    def _process_benchmark(self, raw_store: RawDocumentStore, bronze: BronzeLayer) -> None:
        pipeline = BenchmarkPipeline(raw_store, bronze, self.status_queue)
        self.dfs["df_f_investment_benchmark_data"] = pipeline.process(
            df_market=self.dfs.get("df_f_investment_market_data"),
            df_purchase=self.dfs.get("df_f_tf_inv_purchase"),
            df_master=self.dfs["df_d_benchmark_master"],
        )

    def _run_engines(self) -> None:

        logger.info("Starting Investment Quant Engine...")
        self.status_queue.put(EngineStatus(msg="", data=None, progress=0.6, level=LogLevel.STEP))

        quant_engine = InvestmentQuantEngine(
            df_p=self.dfs["df_f_tf_inv_purchase"],
            df_s=self.dfs["df_f_tf_inv_sale"],
            df_m=self.dfs["df_f_investment_market_data"],
            df_i=self.dfs["df_d_investment_master"],
            df_b=self.dfs["df_f_investment_benchmark_data"],
            df_t=self.dfs["df_d_macro_parameters"],
            status_queue=self.status_queue,
            rules=self.rules,
            start_date=None,
            end_date=None,
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

        logger.info("Starting Presentation Layer Engines...")
        self.status_queue.put(EngineStatus(msg="", data=None, progress=0.8, level=LogLevel.STEP))

        if self.rules is None:
            raise ValueError("FinancialRules must be provided to ETL pipeline")

        wealth_engine = WealthPresentationEngine(rules=self.rules)
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

    def run(self) -> None:
        self.cfg.validate_config()

        start_time = time.time()

        add_queue_handler(cast("multiprocessing.Queue[Any]", self.status_queue))

        log_file_path = self.db_manager.db_path.replace(".duckdb", ".log")
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

        raw_store = RawDocumentStore(self.cfg.TARGET_DB_BASE_PATH, self.cfg.RAW_DOCUMENT_STORE_NAME)
        raw_store.open()
        raw_store.ensure_schema()

        file_tracker = FileTracker(self.db_manager.conn, self.cfg.FILE_HASH_POLICY, raw_store)
        run_id = file_tracker.start_run()

        try:
            # Start ACID Transaction for the entire ETL run
            self.db_manager.conn.execute("BEGIN TRANSACTION")
            raw_store.begin_transaction()

            t_ext_start = time.time()
            if not self.cfg.DISABLE_FILE_DISCOVERER:
                logger.info("Phase 1/5: Discovering files and detecting changes...")

                discovered_files = categorize_statement_files(
                    self.cfg.STATEMENTS_FOLDER, strict=True
                )
                discovered_files["sqlite_source"] = [
                    SQLiteExtractor(self.cfg.SOURCE_DB_FOLDER).get_latest_sqlite_backup()
                ]
                discovered_files["mf_isin"] = [self.cfg.MF_ISIN_CSV_PATH]
                discovered_files["benchmark_mapping"] = [self.cfg.BENCHMARK_MAPPING_CSV_PATH]
                discovered_files["opening_balances"] = [self.cfg.OPENING_BALANCE_CSV_PATH]
                discovered_files["benchmark_master"] = [self.cfg.BENCHMARK_MASTER_CSV_PATH]
                discovered_files["macro_parameters"] = [self.cfg.MACRO_PARAMETERS_CSV_PATH]
                discovered_files["column_master"] = [self.cfg.COLUMN_MASTER_PATH]

                new_files, changed_files = file_tracker.get_actionable_files(discovered_files)

                logger.info("File Tracker Discovery Breakdown:")
                for category in discovered_files.keys():
                    n_new = len(new_files.get(category, []))
                    n_mod = len(changed_files.get(category, []))
                    if n_new == 0 and n_mod == 0:
                        logger.info(
                            f"  -> [{category}] 0 actionable file(s) detected. Cache intact."
                        )
                    else:
                        if n_new > 0:
                            logger.info(f"  -> [{category}] {n_new} new file(s) detected.")
                        if n_mod > 0:
                            logger.info(f"  -> [{category}] {n_mod} modified file(s) detected.")

                actionable_all = {
                    k: new_files.get(k, []) + changed_files.get(k, [])
                    for k in discovered_files.keys()
                }

                logger.info("Ingesting new/modified binary files into Raw Store...")

                # Prune obsolete files from full-replace categories to prevent SQLite bloating
                full_replace_categories = list(
                    set(cat for _, cat, _, is_full in BronzeLayer.TABLE_MAPPINGS if is_full)
                )
                for cat in full_replace_categories:
                    raw_store.delete_obsolete_files(cat, discovered_files.get(cat, []))

                raw_store.load_binaries(actionable_all)
                files_skipped = sum(len(f) for f in discovered_files.values()) - (
                    sum(len(f) for f in new_files.values())
                    + sum(len(f) for f in changed_files.values())
                )
            else:
                logger.info(
                    "Phase 1/5: Bypassing File Discoverer. Fetching pending files from Raw Store..."
                )
                new_files = {}
                changed_files = raw_store.get_pending_files()
                actionable_all = changed_files
                files_skipped = 0

            extracted_data = self._extract(raw_store, actionable_files=actionable_all)
            logger.info(
                f"Phase 1 Complete [{time.time() - t_ext_start:.2f}s] - Actionable streams loaded into memory."
            )

            # Bronze Phase
            t_bronze_start = time.time()
            logger.info("Phase 2/5: Upserting new datasets into Bronze Lakehouse...")

            bronze = BronzeLayer(self.db_manager, file_tracker)
            bronze.load(extracted_data, new_files, changed_files)
            logger.info(
                f"Phase 2 Complete [{time.time() - t_bronze_start:.2f}s] - Bronze layer synchronized."
            )

            # Full Dataset Read
            logger.info("Fetching complete dataset from Bronze Lakehouse for Transformation...")
            full_dataset = bronze.get_full_dataset(extracted_data.mappings)

            # Transformation Phase
            t_trans_start = time.time()
            logger.info("Phase 3/5: Transforming and harmonizing data streams...")
            self._transform(full_dataset)
            logger.info(
                f"Phase 3 Complete [{time.time() - t_trans_start:.2f}s] - DAG mapped {len(self.dfs)} base tables."
            )

            # Phase 3.5 Dynamic Extraction
            self._process_benchmark(raw_store, bronze)

            # Analytics Phase
            t_eng_start = time.time()
            logger.info("Phase 4/5: Executing Advanced Analytics & Monte Carlo engines...")
            self._run_engines()
            logger.info(
                f"Phase 4 Complete [{time.time() - t_eng_start:.2f}s] - Presentation logic built {len(self.dfs)} total tables."
            )

            # Load Phase (Silver & Gold)
            t_load_start = time.time()
            logger.info("Phase 5/5: Fully replacing Silver and Gold analytical layers...")
            SilverLayer(self.db_manager).load(self.dfs)
            GoldLayer(self.db_manager).load(self.dfs)
            logger.info(
                f"Phase 5 Complete [{time.time() - t_load_start:.2f}s] - Disk synchronization successful."
            )

            # Write ETL metadata to DB
            meta_layer = MetaLayer(self.db_manager, run_id, self.cfg, self.rules)
            meta_layer.load(self.dfs)

            # Commit the ACID Transaction
            self.db_manager.conn.execute("COMMIT")
            raw_store.commit()

            files_processed = sum(len(f) for f in new_files.values()) + sum(
                len(f) for f in changed_files.values()
            )
            file_tracker.finish_run(run_id, "success", files_processed, files_skipped)

            self.status_queue.put(EngineStatus(msg="", data=None, progress=1.0))
            total_time = time.time() - start_time
            logger.info(
                f"✅ Pipeline Execution Successful in {total_time:.2f} seconds. Total Nodes: {len(self.dfs)}"
            )
        except Exception as e:
            # Rollback all changes if any phase fails
            try:
                self.db_manager.conn.execute("ROLLBACK")
                logger.warning("DuckDB transaction rolled back.")
            except Exception as rollback_err:
                logger.error(f"Failed to rollback DuckDB transaction: {rollback_err}")

            try:
                raw_store.rollback()
            except Exception as rollback_err:
                logger.error(f"Failed to rollback SQLite Raw Store transaction: {rollback_err}")

            logger.warning(
                "Pipeline failed. Transactions completely rolled back to maintain ACID integrity."
            )

            file_tracker.finish_run(run_id, "failed")
            raise e
        finally:
            logger.info("Cleaning up database connections and WAL sidecars...")
            self.db_manager.close()
            raw_store.close()
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
