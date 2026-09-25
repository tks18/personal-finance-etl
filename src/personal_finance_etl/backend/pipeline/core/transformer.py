import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.config.settings import Settings
from personal_finance_etl.backend.pipeline.strategies import (
    AssetPipeline,
    MutualFundPipeline,
    StockPipeline,
)
from personal_finance_etl.backend.transform.calendar import (
    get_stg_calendar_ref,
    transform_d_calendar,
)
from personal_finance_etl.backend.transform.dimensions import (
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
from personal_finance_etl.backend.transform.facts import (
    get_base_transactions,
    transform_f_expense_transactions,
    transform_f_income_transactions,
    transform_f_opening_balances,
    transform_f_transfer_transactions,
)
from personal_finance_etl.backend.transform.investments import (
    get_d_investment_master,
    get_f_tf_investment_purchase_data,
    get_f_tf_investment_sale_data,
    transform_stg_investment_market_data,
)
from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import (
    AssetPipelineResult,
    EngineStatus,
    ExtractionResult,
    LogLevel,
)


class TransformationDAG:
    def __init__(self, cfg: Settings, status_queue: ILogger, rules: "FinancialRules | None" = None):
        self.cfg = cfg
        self.status_queue = status_queue
        self.rules = rules

    def run(self, extracted: ExtractionResult) -> dict[str, pl.DataFrame]:
        assert self.rules is not None, "FinancialRules must be provided to TransformationDAG"
        logger.debug("Transforming Base Dimensions...")
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
            extracted.assetgroup, mappings["asset_group"], self.rules
        )
        d_asset_subcategory_lazy = transform_d_asset_subcategory(
            extracted.assets, mappings["assets"], self.rules
        )
        d_currency_lazy = transform_d_currency(extracted.currency, mappings["currency"])

        # Load mapping dependencies
        logger.debug("Transforming Macro Parameters and Opening Balances...")
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
            logger.debug("Empty incremental frames detected. Skipping AssetPipelines...")
            stg_investment_market_data_lazy = pl.LazyFrame()
            f_tf_inv_purchase_data_lazy = pl.LazyFrame()
            f_tf_inv_sale_data_lazy = pl.LazyFrame()
            d_tf_investment_master_lazy = pl.LazyFrame()
        else:
            asset_pipelines: list[AssetPipeline] = [MutualFundPipeline(), StockPipeline()]

            asset_results: list[AssetPipelineResult] = []
            for pipeline in asset_pipelines:
                asset_results.append(
                    pipeline.process(extracted, d_asset_subcategory_lazy, self.rules, logger)
                )

            market_data_ref_lazy_list = [res.market_data_ref for res in asset_results]
            purchase_ref_lazy_list = [res.purchase_ref for res in asset_results]
            sale_ref_lazy_list = [res.sale_ref for res in asset_results]
            master_ref_lazy_list = [res.master_ref for res in asset_results]

            stg_investment_market_data_lazy = transform_stg_investment_market_data(
                market_data_ref_lazy_list
            )
            f_tf_inv_purchase_data_lazy = get_f_tf_investment_purchase_data(
                purchase_ref_lazy_list, self.rules.DEFAULT_CURRENCY_ID
            )
            f_tf_inv_sale_data_lazy = get_f_tf_investment_sale_data(
                sale_ref_lazy_list, self.rules.DEFAULT_CURRENCY_ID
            )

            logger.debug("Building Investment Master...")
            d_tf_investment_master_lazy = get_d_investment_master(
                master_ref_lazy_list, extracted.stg_benchmark_mapping
            )

        logger.debug("Generating Master Calendar...")
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

        compact_cal = d_calendar_lazy.explain().replace("\n", " | ")
        logger.debug(f"[DAG:OPTIMIZER] Physical Plan for Master Calendar: {compact_cal}")

        logger.debug("Executing Base Transformation DAG in Parallel...")
        self.status_queue.put(
            EngineStatus(
                msg="",
                data=None,
                progress=0.2,
                level=LogLevel.STEP,
            )
        )
        dag_nodes = {
            "df_d_income_category": d_income_category_lazy,
            "df_d_income_subcategory": d_income_subcategory_lazy,
            "df_d_expense_category": d_expense_category_lazy,
            "df_d_expense_subcategory": d_expense_subcategory_lazy,
            "df_d_asset_category": d_asset_category_lazy,
            "df_d_asset_subcategory": d_asset_subcategory_lazy,
            "df_d_currency": d_currency_lazy,
            "df_d_benchmark_master": d_benchmark_master_lazy,
            "df_d_macro_parameters": d_macro_parameters_lazy,
            "df_f_income_transactions": f_income_transactions_lazy,
            "df_f_expense_transactions": f_expense_transactions_lazy,
            "df_f_transfer_transactions": f_transfer_transactions_lazy,
            "df_f_opening_balances": f_opening_balances_lazy,
            "df_f_investment_market_data": stg_investment_market_data_lazy,
            "df_f_tf_inv_purchase": f_tf_inv_purchase_data_lazy,
            "df_f_tf_inv_sale": f_tf_inv_sale_data_lazy,
            "df_d_investment_master": d_tf_investment_master_lazy,
        }

        for name, node in dag_nodes.items():
            compact_plan = node.explain().replace("\n", " | ")
            logger.debug(f"[DAG:OPTIMIZER] Physical Plan for Silver '{name}': {compact_plan}")

        results = pl.collect_all(list(dag_nodes.values()), engine="streaming")

        logger.debug(
            f"  -> Base Transformation DAG successfully mapped {len(results)} core tables."
        )

        final_dfs: dict[str, pl.DataFrame] = {}
        for (name, _), df in zip(dag_nodes.items(), results, strict=True):
            logger.debug(
                f"[DAG:TRACE] Node '{name}': Output materialized -> ({df.height} rows, {df.width} cols)"
            )
            final_dfs[name] = df

        logger.debug("Executing Calendar Generation DAG...")
        calendar_result = d_calendar_lazy.collect(engine="streaming")
        logger.debug(f"  -> Generated {calendar_result.height} rows for Master Calendar.")
        final_dfs["df_d_calendar"] = calendar_result

        return final_dfs
