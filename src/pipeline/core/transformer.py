import polars as pl

from src.config.settings import Settings
from src.pipeline.strategies import AssetPipeline, MutualFundPipeline, StockPipeline
from src.transform.calendar import (
    get_stg_calendar_ref,
    transform_d_calendar,
)
from src.transform.dimensions import (
    transform_d_asset_category,
    transform_d_asset_subcategory,
    transform_d_currency,
    transform_d_expense_category,
    transform_d_expense_subcategory,
    transform_d_income_category,
    transform_d_income_subcategory,
    transform_d_investment_benchmark_master,
    transform_d_tax_rates,
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

        # Load mapping dependencies
        logger.info("Transforming Tax Rates and Opening Balances...")
        d_tax_rates_lazy = transform_d_tax_rates(extracted.raw_tax_rates)

        f_opening_balances_lazy = transform_f_opening_balances(
            extracted.raw_opening_balances, extracted.mappings["opbal"]
        )

        d_benchmark_master_lazy = transform_d_investment_benchmark_master(
            extracted.raw_benchmark_master
        )

        base_transactions_lazy = get_base_transactions(extracted.inoutcome, mappings["inoutcome"])
        f_income_transactions_lazy = transform_f_income_transactions(base_transactions_lazy)
        f_expense_transactions_lazy = transform_f_expense_transactions(base_transactions_lazy)
        f_transfer_transactions_lazy = transform_f_transfer_transactions(
            base_transactions_lazy, d_asset_subcategory_lazy, d_asset_category_lazy
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
