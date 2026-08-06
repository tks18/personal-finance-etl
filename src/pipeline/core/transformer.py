import polars as pl

from src.config.financial_rules import FinancialRules
from src.config.settings import Settings
from src.pipeline.strategies import AssetPipeline, MutualFundPipeline, StockPipeline
from src.transform.calendar import (
    get_stg_calendar_ref,
    transform_d_calendar,
)
from src.pipeline.core.cache import DatabaseCacheManager
from src.transform.dimensions import (
    transform_d_asset_category,
    transform_d_asset_subcategory,
    transform_d_currency,
    transform_d_expense_category,
    transform_d_expense_subcategory,
    transform_d_income_category,
    transform_d_income_subcategory,
    transform_d_investment_benchmark_master,
    transform_d_macro_parameters,
)
from src.transform.facts import (
    get_base_transactions,
    transform_f_expense_transactions,
    transform_f_income_transactions,
    transform_f_opening_balances,
    transform_f_transfer_transactions,
)
from src.transform.investments import (
    get_d_tf_investment_master,
    get_f_tf_investment_purchase_data,
    get_f_tf_investment_sale_data,
    transform_stg_investment_market_data,
)
from src.utils.interfaces import ILogger
from src.utils.logger import logger
from src.utils.models import EngineStatus, ExtractionResult, LogLevel


class TransformationDAG:
    def __init__(self, cfg: Settings, status_queue: ILogger, rules: "FinancialRules | None" = None):
        self.cfg = cfg
        self.status_queue = status_queue
        self.rules = rules

    def run(self, extracted: ExtractionResult) -> dict[str, pl.DataFrame]:
        logger.info("Transforming Base Dimensions...")
        mappings = extracted.mappings
        d_income_category_lazy = transform_d_income_category(
            extracted.zcategory, mappings["category"]
        )
        d_income_subcategory_lazy = transform_d_income_subcategory(
            extracted.zcategory, mappings["category"], d_income_category_lazy, self.rules
        )
        d_expense_category_lazy = transform_d_expense_category(
            extracted.zcategory, mappings["category"]
        )
        d_expense_subcategory_lazy = transform_d_expense_subcategory(
            extracted.zcategory, mappings["category"], self.rules
        )
        d_asset_category_lazy = transform_d_asset_category(
            extracted.assetgroup, mappings["asset_group"]
        )
        d_asset_subcategory_lazy = transform_d_asset_subcategory(
            extracted.assets, mappings["assets"], self.rules
        )
        d_currency_lazy = transform_d_currency(extracted.currency, mappings["currency"])

        # Load mapping dependencies
        logger.info("Transforming Macro Parameters and Opening Balances...")
        d_macro_parameters_lazy = transform_d_macro_parameters(extracted.raw_macro_parameters)

        f_opening_balances_lazy = transform_f_opening_balances(
            extracted.raw_opening_balances, extracted.mappings["opbal"]
        )

        d_benchmark_master_lazy = transform_d_investment_benchmark_master(
            extracted.raw_benchmark_master
        )

        base_transactions_lazy = get_base_transactions(extracted.inoutcome, mappings["inoutcome"])
        f_income_transactions_lazy = transform_f_income_transactions(
            base_transactions_lazy, self.rules, d_income_subcategory_lazy
        )
        f_expense_transactions_lazy = transform_f_expense_transactions(
            base_transactions_lazy, self.rules, d_expense_subcategory_lazy
        )
        f_transfer_transactions_lazy = transform_f_transfer_transactions(
            base_transactions_lazy, d_asset_subcategory_lazy, d_asset_category_lazy
        )

        if len(extracted.mf_market_data_raw.collect_schema().names()) == 0:
            logger.info("Empty incremental frames detected. Skipping AssetPipelines...")
            stg_investment_market_data_lazy = pl.LazyFrame()
            f_tf_inv_purchase_data_lazy = pl.LazyFrame()
            f_tf_inv_sale_data_lazy = pl.LazyFrame()
            d_tf_investment_master_lazy = pl.LazyFrame()
        else:
            asset_pipelines: list[AssetPipeline] = [MutualFundPipeline(), StockPipeline()]
    
            asset_results = []
            for pipeline in asset_pipelines:
                asset_results.append(
                    pipeline.process(extracted, d_asset_subcategory_lazy, self.cfg, logger)
                )
    
            market_data_ref_lazy_list = [res.market_data_ref for res in asset_results]
            purchase_ref_lazy_list = [res.purchase_ref for res in asset_results]
            sale_ref_lazy_list = [res.sale_ref for res in asset_results]
            master_ref_lazy_list = [res.master_ref for res in asset_results]
    
            stg_investment_market_data_lazy = transform_stg_investment_market_data(
                market_data_ref_lazy_list
            )
            f_tf_inv_purchase_data_lazy = get_f_tf_investment_purchase_data(
                purchase_ref_lazy_list, self.cfg.DEFAULT_CURRENCY_ID
            )
            f_tf_inv_sale_data_lazy = get_f_tf_investment_sale_data(
                sale_ref_lazy_list, self.cfg.DEFAULT_CURRENCY_ID
            )
    
            logger.info("Building Investment Master...")
            d_tf_investment_master_lazy = get_d_tf_investment_master(
                master_ref_lazy_list, extracted.stg_benchmark_mapping
            )

        if not self.cfg.FULL_REFRESH:
            logger.info("FULL_REFRESH=False. Merging historical Silver tables from previous DuckDB...")
            cache_manager = DatabaseCacheManager(self.cfg.TARGET_DB_BASE_PATH)
            
            hist_market = cache_manager.get_historical_silver_table("stg_Investment_Market_Data")
            if hist_market is not None:
                if len(stg_investment_market_data_lazy.collect_schema().names()) == 0:
                    stg_investment_market_data_lazy = hist_market
                else:
                    stg_investment_market_data_lazy = pl.concat([hist_market, stg_investment_market_data_lazy]).unique()
                    
            hist_purchase = cache_manager.get_historical_silver_table("f_tf_Investment_Purchase_Data")
            if hist_purchase is not None:
                if len(f_tf_inv_purchase_data_lazy.collect_schema().names()) == 0:
                    f_tf_inv_purchase_data_lazy = hist_purchase
                else:
                    f_tf_inv_purchase_data_lazy = pl.concat([hist_purchase, f_tf_inv_purchase_data_lazy]).unique()
                    
            hist_sale = cache_manager.get_historical_silver_table("f_tf_Investment_Sale_Data")
            if hist_sale is not None:
                if len(f_tf_inv_sale_data_lazy.collect_schema().names()) == 0:
                    f_tf_inv_sale_data_lazy = hist_sale
                else:
                    f_tf_inv_sale_data_lazy = pl.concat([hist_sale, f_tf_inv_sale_data_lazy]).unique()
                    
            hist_master = cache_manager.get_historical_silver_table("d_tf_Investment_Master")
            if hist_master is not None:
                if len(d_tf_investment_master_lazy.collect_schema().names()) == 0:
                    d_tf_investment_master_lazy = hist_master
                else:
                    d_tf_investment_master_lazy = pl.concat([hist_master, d_tf_investment_master_lazy]).unique()

        logger.info("Generating Master Calendar...")
        # Get first market_data to seed calendar (simplified since they're processed downstream anyway)
        df_bounds_lazy = get_stg_calendar_ref(
            f_income_transactions_lazy,
            f_expense_transactions_lazy,
            f_transfer_transactions_lazy,
            f_opening_balances_lazy,
            stg_investment_market_data_lazy,
            f_tf_inv_purchase_data_lazy,
            f_tf_inv_sale_data_lazy,
        )
        d_calendar_lazy = transform_d_calendar(df_bounds_lazy)

        logger.info("Executing Base Transformation DAG in Parallel...")
        self.status_queue.put(
            EngineStatus(
                msg="",
                data=None,
                progress=0.2,
                level=LogLevel.STEP,
            )
        )
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
                d_macro_parameters_lazy,
                f_income_transactions_lazy,
                f_expense_transactions_lazy,
                f_transfer_transactions_lazy,
                f_opening_balances_lazy,
                stg_investment_market_data_lazy,
                f_tf_inv_purchase_data_lazy,
                f_tf_inv_sale_data_lazy,
                d_tf_investment_master_lazy,
            ],
            engine="streaming",
        )

        logger.info(f"  -> Base Transformation DAG successfully mapped {len(results)} core tables.")
        
        if not self.cfg.FULL_REFRESH:
            logger.info(
                f"  -> Incremental Merge Summary (New + Historical): "
                f"Master: {results[16].height} rows | "
                f"Market: {results[13].height} rows | "
                f"Purchase: {results[14].height} rows | "
                f"Sale: {results[15].height} rows."
            )

        logger.info("Executing Calendar Generation DAG...")
        calendar_result = d_calendar_lazy.collect(engine="streaming")
        logger.info(f"  -> Generated {calendar_result.height} rows for Master Calendar.")

        rules_records = []
        if self.rules:
            rules_records = self.rules.export_to_db_records()
        if not rules_records:
            rules_records = [
                {
                    "Rule_Domain": "None",
                    "Rule_Type": "None",
                    "Target_Level": "None",
                    "Target_ID": "None",
                }
            ]
        df_rules_lazy = pl.LazyFrame(rules_records).with_columns(
            pl.col("Rule_Domain").cast(pl.String),
            pl.col("Rule_Type").cast(pl.String),
            pl.col("Target_Level").cast(pl.String),
            pl.col("Target_ID").cast(pl.String),
        )
        rules_result = df_rules_lazy.collect()

        return {
            "df_d_income_category": results[0],
            "df_d_income_subcategory": results[1],
            "df_d_expense_category": results[2],
            "df_d_expense_subcategory": results[3],
            "df_d_asset_category": results[4],
            "df_d_asset_subcategory": results[5],
            "df_d_currency": results[6],
            "df_d_benchmark_master": results[7],
            "df_d_macro_parameters": results[8],
            "df_f_income_transactions": results[9],
            "df_f_expense_transactions": results[10],
            "df_f_transfer_transactions": results[11],
            "df_f_opening_balances": results[12],
            "df_stg_investment_market_data": results[13],
            "df_f_tf_inv_purchase": results[14],
            "df_f_tf_inv_sale": results[15],
            "df_d_tf_investment_master": results[16],
            "df_d_calendar": calendar_result,
            "_ETL_Metadata_Financial_Rules": rules_result,
        }
