import gc
import multiprocessing
import time
import traceback
from typing import cast

import polars as pl

from src.config.financial_rules import FinancialRules
from src.config.settings import Settings
from src.engines.analytics import InvestmentQuantEngine
from src.engines.benchmark import BenchmarkEngine
from src.engines.presentation.wealth_engine import WealthPresentationEngine
from src.extract.sqlite_extractor import ADBCSQLiteExtractor
from src.extract.statement_locator import categorize_statement_files
from src.load.bronze import BronzeLayer
from src.load.database import DuckDBManager
from src.load.file_tracker import FileTracker
from src.load.gold import GoldLayer
from src.load.metadata import MetaLayer
from src.load.silver import SilverLayer
from src.pipeline.core.extractor import DataExtractor
from src.pipeline.core.transformer import TransformationDAG
from src.utils.interfaces import ILogger
from src.utils.logger import add_file_handler, add_queue_handler, logger
from src.utils.models import EngineStatus, ExtractionResult, LogLevel


class ETLOrchestrator:
    def __init__(self, cfg: Settings, status_queue: ILogger, rules: "FinancialRules | None" = None):
        if cfg is None:
            raise ValueError("Configuration settings (cfg) cannot be None")
        self.cfg = cfg
        self.rules = rules
        self.status_queue = status_queue
        self.db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)
        self.dfs: dict[str, pl.DataFrame] = {}

    def _extract(self, actionable_files: dict[str, list[str]] | None = None) -> ExtractionResult:
        extractor = DataExtractor(self.cfg, self.status_queue)
        return extractor.run(actionable_files)

    def _transform(self, extracted_data: ExtractionResult) -> None:
        transformer = TransformationDAG(self.cfg, self.status_queue, self.rules)
        self.dfs = transformer.run(extracted_data)

    def _run_engines(self) -> None:
        logger.info("Detecting date range & Starting Benchmark Engine...")
        self.status_queue.put(
            EngineStatus(
                msg="",
                data=None,
                progress=0.4,
                level=LogLevel.STEP,
            )
        )
        bm_engine = BenchmarkEngine(
            df_m=self.dfs["df_d_benchmark_master"],
            status_queue=self.status_queue,
        )

        # Read the cache directly from the active DuckDB transaction before the Silver layer is wiped
        try:
            cached_benchmark_df = self.db_manager.conn.execute(
                "SELECT * FROM silver.f_Investment_Benchmark_Data"
            ).pl()
        except Exception:
            cached_benchmark_df = pl.DataFrame()

        self.dfs["df_f_investment_benchmark_data"] = bm_engine.run(
            df_market=self.dfs.get("df_stg_investment_market_data"),
            df_purchase=self.dfs.get("df_f_tf_inv_purchase"),
            df_cached=cached_benchmark_df,
        )
        logger.info(
            f"  -> Benchmark Engine computed tracking deviations for {self.dfs['df_f_investment_benchmark_data'].height} market periods."
        )

        logger.info("Starting Investment Quant Engine...")
        self.status_queue.put(EngineStatus(msg="", data=None, progress=0.6, level=LogLevel.STEP))
        quant_engine = InvestmentQuantEngine(
            df_p=self.dfs["df_f_tf_inv_purchase"],
            df_s=self.dfs["df_f_tf_inv_sale"],
            df_m=self.dfs["df_stg_investment_market_data"],
            df_i=self.dfs["df_d_tf_investment_master"],
            df_b=self.dfs["df_f_investment_benchmark_data"]
            if self.dfs["df_f_investment_benchmark_data"] is not None
            else pl.DataFrame(),
            df_t=self.dfs["df_d_macro_parameters"],
            status_queue=self.status_queue,
            rules=self.rules,
            start_date=None,
            end_date=None,
        )
        analytics_results = quant_engine.run()
        self.dfs.update(analytics_results)
        lot_df = analytics_results.get("df_f_tf_investment_analytics_lot", pl.DataFrame())
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

    # _load() removed since loading is handled per layer

    def run(self) -> None:
        self.cfg.validate_config()

        start_time = time.time()

        add_queue_handler(cast(multiprocessing.Queue, self.status_queue))

        log_file_path = self.db_manager.db_path.replace(".duckdb", ".log")
        add_file_handler(log_file_path)

        logger.debug("=== ETL CONFIGURATION DUMP ===")
        if hasattr(self.cfg, "model_dump_json"):
            logger.debug(self.cfg.model_dump_json(indent=2))
        else:
            logger.debug(str(self.cfg))

        logger.debug("=== FINANCIAL RULES DUMP ===")
        if self.rules is not None and hasattr(self.rules, "model_dump_json"):
            logger.debug(self.rules.model_dump_json(indent=2))  # type: ignore
        else:
            logger.debug(str(self.rules))
        logger.debug("==============================")

        logger.info("Initializing Quantitative Master Engine...")
        self.status_queue.put(EngineStatus(msg="", data=None, progress=0.0))

        logger.info(f"Target Database: {self.cfg.TARGET_DB_BASE_PATH}")
        logger.info(f"Source Extractor Folder: {self.cfg.STATEMENTS_FOLDER}")

        self.db_manager.open()
        self.db_manager.ensure_schemas()

        file_tracker = FileTracker(self.db_manager.conn, self.cfg.FILE_HASH_POLICY)
        run_id = file_tracker.start_run()

        try:
            # Start ACID Transaction for the entire ETL run
            self.db_manager.conn.execute("BEGIN TRANSACTION")

            # Pre-Extraction File Discovery
            t_ext_start = time.time()
            logger.info("Phase 1/5: Discovering files and detecting changes...")

            discovered_files = categorize_statement_files(self.cfg.STATEMENTS_FOLDER, strict=True)
            discovered_files["sqlite_source"] = [
                ADBCSQLiteExtractor(self.cfg.SOURCE_DB_FOLDER)._get_latest_sqlite_backup()
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
                    logger.info(f"  -> [{category}] 0 actionable file(s) detected. Cache intact.")
                else:
                    if n_new > 0:
                        logger.info(f"  -> [{category}] {n_new} new file(s) detected.")
                    if n_mod > 0:
                        logger.info(f"  -> [{category}] {n_mod} modified file(s) detected.")

            # Actionable Extraction
            extracted_data = self._extract(
                actionable_files={
                    k: new_files.get(k, []) + changed_files.get(k, [])
                    for k in discovered_files.keys()
                }
            )
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

            files_processed = sum(len(f) for f in new_files.values()) + sum(
                len(f) for f in changed_files.values()
            )
            files_skipped = sum(len(f) for f in discovered_files.values()) - files_processed
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
                logger.warning(
                    "Pipeline failed. Transaction completely rolled back to maintain ACID integrity."
                )
            except Exception as rollback_err:
                logger.error(f"Failed to rollback transaction: {rollback_err}")

            file_tracker.finish_run(run_id, "failed")
            raise e
        finally:
            logger.info("Cleaning up database connections and WAL sidecars...")
            self.db_manager.close()
            gc.collect()


def process_wrapper(
    status_queue: ILogger | None = None, config_path: str = "config.toml", rules_path: str = ""
) -> None:
    """Wrapper to catch exceptions inside the child process and send them back to the UI."""
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
