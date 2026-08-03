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
from src.engines.benchmark.cache import BenchmarkCacheManager
from src.engines.presentation.wealth_engine import WealthPresentationEngine
from src.load.database import DuckDBLoader, DuckDBManager
from src.pipeline.core.extractor import DataExtractor
from src.pipeline.core.transformer import TransformationDAG
from src.utils.interfaces import IDatabaseLoader, ILogger
from src.utils.logger import add_queue_handler, logger
from src.utils.models import EngineStatus, ExtractionResult, LogLevel


class ETLOrchestrator:
    def __init__(self, cfg: Settings, status_queue: ILogger, rules: "FinancialRules | None" = None):
        if cfg is None:
            raise ValueError("Configuration settings (cfg) cannot be None")
        self.cfg = cfg
        self.rules = rules
        self.status_queue = status_queue
        self.db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH)
        self.dfs: dict[str, pl.DataFrame] = {}

    def _extract(self) -> ExtractionResult:
        extractor = DataExtractor(self.cfg, self.status_queue)
        return extractor.run()

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
            target_db_base_path=self.cfg.TARGET_DB_BASE_PATH,
            current_db_path=self.db_manager.db_path,
        )
        self.dfs["df_f_investment_benchmark_data"] = bm_engine.run(
            df_market=self.dfs.get("df_stg_investment_market_data"),
            df_purchase=self.dfs.get("df_f_tf_inv_purchase"),
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
        logger.info(
            f"  -> Quant Engine mapped {analytics_results.get('df_f_tf_inv_tax_harvesting', pl.DataFrame()).height} open tax lots and "
            f"{analytics_results.get('df_f_tf_inv_tax_realized', pl.DataFrame()).height} realized gain events."
        )

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

    def _load(self) -> None:
        loader: IDatabaseLoader = DuckDBLoader(self.db_manager, self.status_queue)
        loader.run(self.dfs)

    def run(self) -> None:
        self.cfg.validate_config()

        start_time = time.time()
        add_queue_handler(cast(multiprocessing.Queue, self.status_queue))
        logger.info("Initializing Quantitative Master Engine...")
        self.status_queue.put(EngineStatus(msg="", data=None, progress=0.0))

        logger.info(f"Target Database: {self.cfg.TARGET_DB_BASE_PATH}")
        logger.info(f"Source Extractor Folder: {self.cfg.STATEMENTS_FOLDER}")

        BenchmarkCacheManager.rescue_benchmark_cache(self.db_manager.db_path)
        self.db_manager.setup_schema()

        try:
            # Extraction Phase
            t_ext_start = time.time()
            logger.info("Phase 1/4: Extracting base rules and raw statements...")
            extracted_data = self._extract()
            logger.info(f"Phase 1 Complete [{time.time() - t_ext_start:.2f}s] - Data streams loaded into memory.")

            # Transformation Phase
            t_trans_start = time.time()
            logger.info("Phase 2/4: Transforming and harmonizing data streams...")
            self._transform(extracted_data)
            logger.info(f"Phase 2 Complete [{time.time() - t_trans_start:.2f}s] - DAG mapped {len(self.dfs)} base tables.")

            # Analytics Phase
            t_eng_start = time.time()
            logger.info("Phase 3/4: Executing Advanced Analytics & Monte Carlo engines...")
            self._run_engines()
            logger.info(f"Phase 3 Complete [{time.time() - t_eng_start:.2f}s] - Presentation logic built {len(self.dfs)} total tables.")

            # Load Phase
            t_load_start = time.time()
            logger.info("Phase 4/4: Flushing materialized tables to DuckDB...")
            self._load()
            logger.info(f"Phase 4 Complete [{time.time() - t_load_start:.2f}s] - Disk synchronization successful.")

            self.status_queue.put(EngineStatus(msg="", data=None, progress=1.0))
            total_time = time.time() - start_time
            logger.info(
                f"✅ Pipeline Execution Successful in {total_time:.2f} seconds. Total Nodes: {len(self.dfs)}"
            )
            logger.info("Finalizing database commit...")
            self.db_manager.commit()
        finally:
            logger.info("Cleaning up database connections and WAL sidecars...")
            self.db_manager.cleanup()
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
