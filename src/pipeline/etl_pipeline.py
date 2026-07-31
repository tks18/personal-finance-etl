import gc
import multiprocessing
import time
import traceback
from typing import cast

import polars as pl

from src.config.settings import Settings
from src.engines.analytics import InvestmentAnalyticsEngine
from src.engines.benchmark import BenchmarkEngine
from src.engines.presentation.wealth_engine import WealthPresentationEngine
from src.load.database import DuckDBLoader, DuckDBManager
from src.pipeline.core.extractor import DataExtractor
from src.pipeline.core.transformer import TransformationDAG
from src.utils.interfaces import IDatabaseLoader, ILogger
from src.utils.logger import add_queue_handler, logger
from src.utils.models import EngineStatus, ExtractionResult, LogLevel


class ETLOrchestrator:
    def __init__(self, cfg: Settings, status_queue: ILogger):
        if cfg is None:
            raise ValueError("Configuration settings (cfg) cannot be None")
        self.cfg = cfg
        self.status_queue = status_queue
        self.db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH)
        self.dfs: dict[str, pl.DataFrame] = {}

    def _extract(self) -> ExtractionResult:
        extractor = DataExtractor(self.cfg, self.status_queue)
        return extractor.run()

    def _transform(self, extracted_data: ExtractionResult) -> None:
        transformer = TransformationDAG(self.cfg, self.status_queue)
        self.dfs = transformer.run(extracted_data)

    def _run_engines(self) -> None:
        self.status_queue.put(
            EngineStatus(
                msg="Detecting date range & Starting Benchmark Engine...",
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

        self.status_queue.put(
            EngineStatus(
                msg="Starting Polars Tax Engine...", data=None, progress=0.6, level=LogLevel.STEP
            )
        )
        tax_engine = InvestmentAnalyticsEngine(
            df_p=self.dfs["df_f_tf_inv_purchase"],
            df_s=self.dfs["df_f_tf_inv_sale"],
            df_m=self.dfs["df_stg_investment_market_data"],
            df_i=self.dfs["df_d_tf_investment_master"],
            df_b=self.dfs["df_f_investment_benchmark_data"]
            if self.dfs["df_f_investment_benchmark_data"] is not None
            else pl.DataFrame(),
            df_t=self.dfs["df_d_tax_rates"],
            status_queue=self.status_queue,
            start_date=None,
            end_date=None,
        )
        self.dfs["df_f_investment_market_data"] = tax_engine.run()

        self.status_queue.put(
            EngineStatus(
                msg="Starting Presentation Engines...", data=None, progress=0.8, level=LogLevel.STEP
            )
        )
        wealth_engine = WealthPresentationEngine()
        wealth_lazy = wealth_engine.run(self.dfs)

        presentation_lazy = wealth_lazy
        if presentation_lazy:
            self.status_queue.put(
                EngineStatus(
                    msg="Executing Presentation DAG in Parallel...",
                    data=None,
                    progress=0.9,
                    level=LogLevel.STEP,
                )
            )
            keys = list(presentation_lazy.keys())
            lazy_frames = [presentation_lazy[k] for k in keys]
            results = pl.collect_all(lazy_frames, engine="streaming")
            for k, res in zip(keys, results, strict=True):
                self.dfs[k] = res

    def _load(self) -> None:
        loader: IDatabaseLoader = DuckDBLoader(self.db_manager, self.status_queue)
        loader.run(self.dfs)

    def run(self) -> None:
        self.cfg.validate()

        start_time = time.time()
        add_queue_handler(cast(multiprocessing.Queue, self.status_queue))
        logger.info("Starting ETL Pipeline")
        self.status_queue.put(EngineStatus(msg="", data=None, progress=0.0))

        logger.info(f"Setting up Target DB at {self.db_manager.db_path}")

        # Rescue Benchmark Data before schema wipe
        from src.engines.benchmark.cache import BenchmarkCacheManager

        BenchmarkCacheManager.rescue_benchmark_cache(self.db_manager.db_path)

        self.db_manager.setup_schema()

        try:
            extracted_data = self._extract()
            self._transform(extracted_data)

            self._run_engines()
            self._load()

            self.status_queue.put(EngineStatus(msg="", data=None, progress=1.0))
            total_time = time.time() - start_time
            logger.info(
                f"ETL complete in {total_time:.2f} seconds. All tables generated successfully."
            )
        finally:
            logger.info("Cleaning up database connections and WAL sidecars...")
            self.db_manager.cleanup()
            gc.collect()


def process_wrapper(status_queue: ILogger | None = None, config_path: str = "config.toml") -> None:
    """Wrapper to catch exceptions inside the child process and send them back to the UI."""
    try:
        cfg = Settings()
        if config_path:
            cfg = Settings.from_toml(config_path)

        if status_queue is None:
            from typing import cast

            status_queue = cast(ILogger, multiprocessing.Queue())

        orchestrator = ETLOrchestrator(cfg, status_queue)
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
