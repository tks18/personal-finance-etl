"""Pipeline stage execution engine across Bronze, Silver, and Gold transformations.

Owns
----
- PipelineExecutor: Coordinates data extraction, base transformations, market integrations, and analytics engines.
- External market data ingestion (Currency FX, US market prices, and benchmark indices).
- Parallel execution of WealthPresentationEngine streaming Polars graphs.
- Strict DataContract validation against DATA_CONTRACT_REGISTRY.
- Persistence into Silver, Gold, and Meta warehouse layers.

Does not own
-------------
- Transaction boundary management, rollbacks, or split-commit recovery (owned by application.pipeline.lifecycle).
- Process isolation or child process wrappers (owned by application.pipeline.worker).
- High-level orchestrator lifecycle control (owned by application.pipeline.orchestrator).
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any, cast

import polars as pl

from personal_finance_etl.application.ingestion.coordinator import DataExtractor
from personal_finance_etl.application.ingestion.market_sync import (
    BenchmarkPipeline,
    CurrencyPipeline,
    USMarketPipeline,
)
from personal_finance_etl.application.investments.quant_service import InvestmentQuantEngine
from personal_finance_etl.application.tax.tax_service import TaxEngine
from personal_finance_etl.application.wealth.wealth_service import WealthPresentationEngine
from personal_finance_etl.backend.pipeline.core.transformer import TransformationDAG
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.extraction import ExtractionResult
from personal_finance_etl.contracts.logging import ILogger, LogLevel
from personal_finance_etl.infrastructure.control_plane import ControlPlane
from personal_finance_etl.infrastructure.logging.setup import logger
from personal_finance_etl.infrastructure.providers.files.locator import (
    categorize_statement_files,
)
from personal_finance_etl.infrastructure.providers.files.sqlite import SQLiteExtractor
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.gold import GoldLayer
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.registry import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
    validate_registry,
)
from personal_finance_etl.infrastructure.warehouse.silver import SilverLayer

__all__ = ["PipelineExecutor"]


class PipelineExecutor:
    """Executes the quantitative ETL phases from discovery through analytical presentation."""

    def __init__(
        self,
        cfg: Settings,
        status_queue: ILogger,
        db_manager: DuckDBManager,
        rules: FinancialRules | None = None,
    ) -> None:
        self.cfg = cfg
        self.status_queue = status_queue
        self.db_manager = db_manager
        self.rules = rules
        self.dfs: dict[str, pl.DataFrame] = {}

    def extract(
        self,
        cp: ControlPlane,
        actionable_files: dict[str, list[str]] | None = None,
    ) -> ExtractionResult:
        """Extract evidence from local files or raw payloads via DataExtractor."""
        extractor = DataExtractor(self.cfg, self.status_queue, cp)
        return extractor.run(actionable_files)

    def transform(self, extracted_data: ExtractionResult) -> None:
        """Transform raw extracted data into base dimension and fact tables."""
        transformer = TransformationDAG(self.cfg, self.status_queue, self.rules)
        self.dfs = transformer.run(extracted_data)

    def process_benchmark(self, cp: ControlPlane, bronze: BronzeLayer) -> None:
        """Fetch and align benchmark history against investment portfolio holdings."""
        pipeline = BenchmarkPipeline(cp, bronze, self.status_queue)
        self.dfs["df_f_investment_benchmark_data"] = pipeline.process(
            df_market=self.dfs.get("df_f_investment_market_data"),
            df_purchase=self.dfs.get("df_f_tf_inv_purchase"),
            df_master=self.dfs["df_d_benchmark_master"],
        )

    def process_currency(self, cp: ControlPlane, bronze: BronzeLayer) -> None:
        """Fetch and synchronize continuous historical currency exchange rates."""
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

    def process_us_market_data(self, cp: ControlPlane, bronze: BronzeLayer) -> None:
        """Fetch and synchronize continuous historical US stock prices."""
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
            df_market_existing = self.dfs.get("df_f_investment_market_data")
            if df_market_existing is not None and not df_market_existing.is_empty():
                df_combined = pl.concat([df_market_existing, df_us_market], how="diagonal_relaxed")
                self.dfs["df_f_investment_market_data"] = df_combined
            else:
                self.dfs["df_f_investment_market_data"] = df_us_market

    def run_engines(self, cp: ControlPlane | None, run_id: str) -> None:
        """Run Quant, Tax, and Wealth Presentation engines with contract verification."""
        logger.info("Starting Investment Quant Engine...")
        self.status_queue.put(
            cast(
                Any,
                EngineStatusMessage(
                    msg="",
                    progress=0.6,
                    level=LogLevel.STEP,
                ),
            )
        )

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

        rules_snapshot_id = "UNKNOWN"
        settings_snapshot_id = None
        if cp and self.rules:
            metadata = cp.runs.get_run_metadata(run_id)
            settings_snapshot_id = metadata.get("settings_snapshot_id")
            rules_snapshot_id = metadata.get("rules_snapshot_id") or "UNKNOWN"

        logger.info("Executing Tax Engine...")
        tax_engine = TaxEngine(
            df_income=self.dfs["df_f_income_transactions"],
            df_realized_events=self.dfs["df_f_investment_realized_events"],
            df_subcategory=self.dfs["df_d_income_subcategory"],
            rules=self.rules,
            df_macro_parameters=self.dfs.get("df_d_macro_parameters"),
        )
        tax_results = tax_engine.run()
        self.dfs.update(tax_results)

        logger.info("Starting Presentation Layer Engines...")
        self.status_queue.put(
            cast(
                Any,
                EngineStatusMessage(
                    msg="",
                    progress=0.8,
                    level=LogLevel.STEP,
                ),
            )
        )

        if self.rules is None:
            raise ValueError("FinancialRules must be provided to ETL pipeline")

        wealth_engine = WealthPresentationEngine(rules=self.rules, root_seed=run_id)
        wealth_lazy = wealth_engine.run(self.dfs)

        presentation_lazy = wealth_lazy
        if presentation_lazy:
            logger.info("Executing Presentation DAG in Parallel...")
            self.status_queue.put(
                cast(
                    Any,
                    EngineStatusMessage(
                        msg="",
                        progress=0.9,
                        level=LogLevel.STEP,
                    ),
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
                result_df=self.dfs.get("df_p_tf_wealth_risk_analytics"),
                settings_snapshot_id=settings_snapshot_id,
                rules_snapshot_id=rules_snapshot_id if rules_snapshot_id != "UNKNOWN" else None,
            )

        if "df_p_tf_wealth_risk_analytics_inputs" in self.dfs:
            self.dfs.pop("df_p_tf_wealth_risk_analytics_inputs")

    def execute_phases(self, cp: ControlPlane, run_id: str) -> None:
        """Execute all five sequential ETL pipeline phases."""
        self.cfg.validate_config()
        validate_registry()

        logger.info(f"Target Database: {self.cfg.TARGET_DB_BASE_PATH}")
        logger.info(f"Source Extractor Folder: {self.cfg.STATEMENTS_FOLDER}")

        # Phase 1: Discovery & Sync
        t_ext_start = time.perf_counter()
        renames: list[tuple[str, str, str]] = []
        if not self.cfg.DISABLE_FILE_DISCOVERER:
            logger.info("[PHASE] --- 1/5: Discovery & Sync ---")

            discovered_files = categorize_statement_files(self.cfg.STATEMENTS_FOLDER, strict=True)
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
            logger.info("[DISCOV] Injected 8 dynamic configuration assets (7 CSV, 1 SQLite DB).")

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
                paths = new_files.get(k, []) + changed_files.get(k, []) + pending_files.get(k, [])
                if paths:
                    normalized_paths = {p.replace("\\", "/") for p in paths}
                    actionable_all[k] = list(normalized_paths)
        else:
            logger.info(
                "Phase 1/5: Bypassing File Discoverer. Fetching pending files from Raw Store..."
            )
            actionable_all = cp.artifacts.get_pending_files()

        extracted_data = self.extract(cp, actionable_files=actionable_all)
        logger.info(
            f"Phase 1 Complete [{time.perf_counter() - t_ext_start:.2f}s] - Actionable streams loaded into memory."
        )

        # Phase 2: Upserting new datasets into Bronze Lakehouse
        t_bronze_start = time.perf_counter()
        logger.info("[PHASE] --- 2/5: Upserting new datasets into Bronze Lakehouse ---")

        meta_layer = MetaLayer(self.db_manager, self.cfg, self.rules)
        bronze = BronzeLayer(self.db_manager, cp, meta_layer)
        if renames:
            bronze.migrate_identity(renames)
            meta_layer.migrate_identity(renames)

        bronze.load(extracted_data, actionable_all)
        logger.info(
            f"Phase 2 Complete [{time.perf_counter() - t_bronze_start:.2f}s] - Bronze layer synchronized."
        )

        # Record run-level artifact synchronization completeness
        actionable_paths = [p for paths in actionable_all.values() for p in paths]
        actionable_cnt = len(actionable_paths)
        if actionable_cnt == 0:
            sync_summary = {
                "actionable_count": 0,
                "synced_count": 0,
                "healed_count": 0,
                "failed_count": 0,
                "deferred_count": 0,
                "sync_status": "NOT_REQUIRED",
            }
        else:
            norm_actionable = {p.replace("\\", "/") for p in actionable_paths}
            reg_with_status = cp.artifacts.get_registry_with_status()
            synced_cnt = sum(
                1
                for p in norm_actionable
                if reg_with_status.get(p, (None, None, None))[2] == "SYNCED"
            )
            healed_cnt = cp.db.conn.execute(
                "SELECT COUNT(*) FROM cp_artifact_run_events WHERE run_id = ? AND event_type = 'HEALED'",
                (run_id,),
            ).fetchone()[0]
            failed_cnt = actionable_cnt - synced_cnt
            status_str = (
                "COMPLETE" if failed_cnt == 0 else ("PARTIAL" if synced_cnt > 0 else "FAILED")
            )
            sync_summary = {
                "actionable_count": actionable_cnt,
                "synced_count": synced_cnt,
                "healed_count": healed_cnt,
                "failed_count": failed_cnt,
                "deferred_count": 0,
                "sync_status": status_str,
            }
        cp.runs.log_sync_summary(run_id, sync_summary)

        logger.debug(
            "[ENGINE:READ] Fetching complete dataset from Bronze Lakehouse for Transformation..."
        )
        full_dataset = bronze.get_full_dataset(extracted_data.mappings)

        # Phase 3: Transforming and harmonizing data streams
        t_trans_start = time.perf_counter()
        logger.info("[PHASE] --- 3/5: Transforming and harmonizing data streams ---")
        self.transform(full_dataset)
        logger.info(
            f"[PHASE] 3/5 Complete [{time.perf_counter() - t_trans_start:.2f}s] - DAG mapped {len(self.dfs)} base tables."
        )

        self.process_currency(cp, bronze)
        self.process_us_market_data(cp, bronze)
        self.process_benchmark(cp, bronze)

        # Phase 4: Executing Advanced Analytics & Monte Carlo engines
        t_eng_start = time.perf_counter()
        logger.info("[PHASE] --- 4/5: Executing Advanced Analytics & Monte Carlo engines ---")
        self.run_engines(cp, str(run_id))

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

        # Phase 5: Fully replacing Silver and Gold analytical layers
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
