"""Base transformation DAG for Silver dimension and fact tables.

Owns
----
- TransformationDAG: Coordinates streaming transformation of 18 base Silver tables.
- Invoking household dimension, transaction, and investment asset pipeline transforms.
- Master calendar date boundary extraction and generation.

Does not own
-------------
- Concrete extraction of raw payloads (owned by application.ingestion.coordinator).
- Quant or tax calculation algorithms (owned by domain.investments and domain.tax).
- Warehouse persistence (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import polars as pl

from personal_finance_etl.application.ingestion.asset_strategies import (
    AssetPipeline,
    MutualFundPipeline,
    StockPipeline,
    USStockPipeline,
)
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.extraction import AssetPipelineResult, ExtractionResult
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    EventOutcome,
    PresentationKind,
)
from personal_finance_etl.domain.household.transforms.calendar import (
    get_stg_calendar_ref,
    transform_d_calendar,
)
from personal_finance_etl.domain.household.transforms.dimensions import (
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
from personal_finance_etl.domain.household.transforms.transactions import (
    get_base_transactions,
    transform_f_expense_transactions,
    transform_f_income_transactions,
    transform_f_opening_balances,
    transform_f_transfer_transactions,
)
from personal_finance_etl.domain.investments.transforms.common import (
    get_d_investment_master,
    get_f_tf_investment_purchase_data,
    get_f_tf_investment_sale_data,
    transform_stg_investment_market_data,
)
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)

__all__ = ["TransformationDAG"]

diagnostics = get_observability_diagnostics(__name__)


class TransformationDAG:
    """Orchestrates streaming transformations for 18 core Silver lakehouse tables."""

    def __init__(
        self,
        cfg: Settings,
        status_queue: EventQueue,
        rules: FinancialRules | None = None,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self.cfg = cfg
        self.status_queue = status_queue
        self.rules = rules
        self.emitter = emitter or get_global_emitter()

    def _transform_dimensions(self, extracted: ExtractionResult) -> dict[str, pl.LazyFrame]:
        """Transform base dimension LazyFrames from extracted staging records.

        Parameters
        ----------
        extracted : ExtractionResult
            Extracted source and mapping entities.

        Returns
        -------
        dict[str, pl.LazyFrame]
            Dictionary of base dimension LazyFrames.
        """
        if self.rules is None:
            raise ValueError("FinancialRules must be provided to TransformationDAG")

        diagnostics.debug("Transforming Base Dimensions...")
        mappings = extracted.mappings
        d_income_category_lazy = transform_d_income_category(
            extracted.zcategory, mappings["category"], self.rules
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
        d_currency_lazy = transform_d_currency(
            extracted.currency, mappings["currency"], extracted.currency_mapping_raw
        )

        diagnostics.debug("Transforming Macro Parameters and Opening Balances...")
        d_macro_parameters_lazy = transform_d_macro_parameters(extracted.raw_macro_parameters)
        d_benchmark_master_lazy = transform_d_investment_benchmark_master(
            extracted.raw_benchmark_master
        )

        return {
            "df_d_income_category": d_income_category_lazy,
            "df_d_income_subcategory": d_income_subcategory_lazy,
            "df_d_expense_category": d_expense_category_lazy,
            "df_d_expense_subcategory": d_expense_subcategory_lazy,
            "df_d_asset_category": d_asset_category_lazy,
            "df_d_asset_subcategory": d_asset_subcategory_lazy,
            "df_d_currency": d_currency_lazy,
            "df_d_macro_parameters": d_macro_parameters_lazy,
            "df_d_benchmark_master": d_benchmark_master_lazy,
        }

    def _transform_facts(
        self, extracted: ExtractionResult, dims: dict[str, pl.LazyFrame]
    ) -> dict[str, pl.LazyFrame]:
        """Transform core cashflow, opening balances, and transaction fact LazyFrames.

        Parameters
        ----------
        extracted : ExtractionResult
            Extracted source and mapping entities.
        dims : dict[str, pl.LazyFrame]
            Transformed dimension tables for foreign key lookups.

        Returns
        -------
        dict[str, pl.LazyFrame]
            Dictionary of core transaction fact LazyFrames.
        """
        if self.rules is None:
            raise ValueError("FinancialRules must be provided to TransformationDAG")

        mappings = extracted.mappings
        d_income_subcategory_lazy = dims["df_d_income_subcategory"]
        d_expense_subcategory_lazy = dims["df_d_expense_subcategory"]
        d_asset_category_lazy = dims["df_d_asset_category"]
        d_asset_subcategory_lazy = dims["df_d_asset_subcategory"]

        f_opening_balances_lazy = transform_f_opening_balances(
            extracted.raw_opening_balances, extracted.mappings["opbal"]
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

        return {
            "df_f_opening_balances": f_opening_balances_lazy,
            "df_f_income_transactions": f_income_transactions_lazy,
            "df_f_expense_transactions": f_expense_transactions_lazy,
            "df_f_transfer_transactions": f_transfer_transactions_lazy,
        }

    def _run_asset_pipelines(
        self, extracted: ExtractionResult, d_asset_subcategory_lazy: pl.LazyFrame
    ) -> dict[str, pl.LazyFrame]:
        """Execute investment asset pipelines for Mutual Funds, Stocks, and US Equities.

        Parameters
        ----------
        extracted : ExtractionResult
            Extracted raw statements and transaction reports.
        d_asset_subcategory_lazy : pl.LazyFrame
            Transformed asset subcategory dimension.

        Returns
        -------
        dict[str, pl.LazyFrame]
            Dictionary containing market staging, purchases, sales, and investment master.
        """
        if self.rules is None:
            raise ValueError("FinancialRules must be provided to TransformationDAG")

        if len(extracted.mf_market_data_raw.collect_schema().names()) == 0:
            diagnostics.debug("Empty incremental frames detected. Skipping AssetPipelines...")
            return {
                "df_f_investment_market_data": pl.LazyFrame(),
                "df_f_tf_inv_purchase": pl.LazyFrame(),
                "df_f_tf_inv_sale": pl.LazyFrame(),
                "df_d_investment_master": pl.LazyFrame(),
            }

        asset_pipelines: list[AssetPipeline] = [
            MutualFundPipeline(),
            StockPipeline(),
            USStockPipeline(),
        ]

        asset_results: list[AssetPipelineResult] = []
        for pipeline in asset_pipelines:
            asset_results.append(
                pipeline.process(extracted, d_asset_subcategory_lazy, self.rules, diagnostics)
            )

        market_data_ref_lazy_list = [res.market_data_ref for res in asset_results]
        purchase_ref_lazy_list = [res.purchase_ref for res in asset_results]
        sale_ref_lazy_list = [res.sale_ref for res in asset_results]
        master_ref_lazy_list = [res.master_ref for res in asset_results]

        stg_investment_market_data_lazy = transform_stg_investment_market_data(
            market_data_ref_lazy_list, self.rules.DEFAULT_CURRENCY_ID
        )
        f_tf_inv_purchase_data_lazy = get_f_tf_investment_purchase_data(
            purchase_ref_lazy_list, self.rules.DEFAULT_CURRENCY_ID
        )
        f_tf_inv_sale_data_lazy = get_f_tf_investment_sale_data(
            sale_ref_lazy_list, self.rules.DEFAULT_CURRENCY_ID
        )

        diagnostics.debug("Building Investment Master...")
        d_tf_investment_master_lazy = get_d_investment_master(
            master_ref_lazy_list,
            extracted.stg_benchmark_mapping,
            self.rules.DEFAULT_CURRENCY_ID,
        )

        return {
            "df_f_investment_market_data": stg_investment_market_data_lazy,
            "df_f_tf_inv_purchase": f_tf_inv_purchase_data_lazy,
            "df_f_tf_inv_sale": f_tf_inv_sale_data_lazy,
            "df_d_investment_master": d_tf_investment_master_lazy,
        }

    def _build_calendar_dimension(
        self,
        f_income: pl.LazyFrame,
        f_expense: pl.LazyFrame,
        f_transfer: pl.LazyFrame,
        f_opbal: pl.LazyFrame,
        stg_mkt: pl.LazyFrame,
        f_purchase: pl.LazyFrame,
        f_sale: pl.LazyFrame,
    ) -> pl.LazyFrame:
        """Extract global date bounds and compile master calendar dimension table.

        Parameters
        ----------
        f_income : pl.LazyFrame
            Income transactions stream.
        f_expense : pl.LazyFrame
            Expense transactions stream.
        f_transfer : pl.LazyFrame
            Transfer transactions stream.
        f_opbal : pl.LazyFrame
            Opening balances stream.
        stg_mkt : pl.LazyFrame
            Market data stream.
        f_purchase : pl.LazyFrame
            Investment purchases stream.
        f_sale : pl.LazyFrame
            Investment sales stream.

        Returns
        -------
        pl.LazyFrame
            Enriched calendar dimension LazyFrame.
        """
        diagnostics.debug("Generating Master Calendar...")
        df_bounds_lazy = get_stg_calendar_ref(
            f_income,
            f_expense,
            f_transfer,
            f_opbal,
            stg_mkt,
            f_purchase,
            f_sale,
        )
        d_calendar_lazy = transform_d_calendar(df_bounds_lazy)

        compact_cal = d_calendar_lazy.explain().replace("\n", " | ")
        diagnostics.debug(f"Physical Plan for Master Calendar: {compact_cal}")
        return d_calendar_lazy

    def _materialize_dag_and_emit_events(
        self,
        dag_nodes: dict[str, pl.LazyFrame],
        d_calendar_lazy: pl.LazyFrame,
    ) -> dict[str, pl.DataFrame]:
        """Execute parallel streaming collection across DAG nodes and emit audit progress.

        Parameters
        ----------
        dag_nodes : dict[str, pl.LazyFrame]
            Mapping of table names to Silver LazyFrame nodes.
        d_calendar_lazy : pl.LazyFrame
            Master calendar dimension LazyFrame.

        Returns
        -------
        dict[str, pl.DataFrame]
            Dictionary of materialized Silver DataFrames including master calendar.
        """
        diagnostics.debug("Executing Base Transformation DAG in Parallel...")
        self.emitter.emit_event(
            event_code=EventCode.TRANSFORMATION_STAGE,
            message="",
            progress=0.2,
            severity=DiagnosticSeverity.INFO,
            outcome=EventOutcome.COMPLETED,
            presentation_kind=PresentationKind.PROGRESS,
            stage=EngineStage.TRANSFORMING,
        )

        for name, node in dag_nodes.items():
            compact_plan = node.explain().replace("\n", " | ")
            diagnostics.debug(f"Physical Plan for Silver '{name}': {compact_plan}")

        results = pl.collect_all(list(dag_nodes.values()), engine="streaming")

        diagnostics.debug(
            f"  -> Base Transformation DAG successfully mapped {len(results)} core tables."
        )

        final_dfs: dict[str, pl.DataFrame] = {}
        for (name, _), df in zip(dag_nodes.items(), results, strict=True):
            diagnostics.debug(
                f"Node '{name}': Output materialized -> ({df.height} rows, {df.width} cols)"
            )
            final_dfs[name] = df
            self.emitter.emit_event(
                event_code=EventCode.TRANSFORMATION_STAGE,
                message=f"Silver node '{name}' materialized ({df.height} rows)",
                presentation_kind=PresentationKind.INTERNAL,
                severity=DiagnosticSeverity.DEBUG,
                stage=EngineStage.TRANSFORMING,
                entity_type="Table",
                entity_id=name,
                rows=df.height,
            )

        diagnostics.debug("Executing Calendar Generation DAG...")
        # Materialization Boundary: PUBLICATION_BOUNDARY
        # Materialize continuous calendar dimension into DataFrame for downstream analytical models
        calendar_result = d_calendar_lazy.collect(engine="streaming")
        diagnostics.debug(f"  -> Generated {calendar_result.height} rows for Master Calendar.")
        final_dfs["df_d_calendar"] = calendar_result
        self.emitter.emit_event(
            event_code=EventCode.TRANSFORMATION_STAGE,
            message=f"Master Calendar materialized ({calendar_result.height} rows)",
            presentation_kind=PresentationKind.INTERNAL,
            severity=DiagnosticSeverity.DEBUG,
            stage=EngineStage.TRANSFORMING,
            entity_type="Table",
            entity_id="df_d_calendar",
            rows=calendar_result.height,
        )

        return final_dfs

    def run(self, extracted: ExtractionResult) -> dict[str, pl.DataFrame]:
        """Execute parallel streaming transformation across dimensions, facts, and asset pipelines.

        Parameters
        ----------
        extracted : ExtractionResult
            Extracted source and mapping entities.

        Returns
        -------
        dict[str, pl.DataFrame]
            Dictionary of all 18 materialized Silver lakehouse DataFrames.
        """
        if self.rules is None:
            raise ValueError("FinancialRules must be provided to TransformationDAG")

        dims = self._transform_dimensions(extracted)
        facts = self._transform_facts(extracted, dims)
        assets = self._run_asset_pipelines(extracted, dims["df_d_asset_subcategory"])

        d_calendar_lazy = self._build_calendar_dimension(
            f_income=facts["df_f_income_transactions"],
            f_expense=facts["df_f_expense_transactions"],
            f_transfer=facts["df_f_transfer_transactions"],
            f_opbal=facts["df_f_opening_balances"],
            stg_mkt=assets["df_f_investment_market_data"],
            f_purchase=assets["df_f_tf_inv_purchase"],
            f_sale=assets["df_f_tf_inv_sale"],
        )

        dag_nodes: dict[str, pl.LazyFrame] = {
            "df_d_income_category": dims["df_d_income_category"],
            "df_d_income_subcategory": dims["df_d_income_subcategory"],
            "df_d_expense_category": dims["df_d_expense_category"],
            "df_d_expense_subcategory": dims["df_d_expense_subcategory"],
            "df_d_asset_category": dims["df_d_asset_category"],
            "df_d_asset_subcategory": dims["df_d_asset_subcategory"],
            "df_d_currency": dims["df_d_currency"],
            "df_d_benchmark_master": dims["df_d_benchmark_master"],
            "df_d_macro_parameters": dims["df_d_macro_parameters"],
            "df_f_income_transactions": facts["df_f_income_transactions"],
            "df_f_expense_transactions": facts["df_f_expense_transactions"],
            "df_f_transfer_transactions": facts["df_f_transfer_transactions"],
            "df_f_opening_balances": facts["df_f_opening_balances"],
            "df_f_investment_market_data": assets["df_f_investment_market_data"],
            "df_f_tf_inv_purchase": assets["df_f_tf_inv_purchase"],
            "df_f_tf_inv_sale": assets["df_f_tf_inv_sale"],
            "df_d_investment_master": assets["df_d_investment_master"],
        }

        return self._materialize_dag_and_emit_events(dag_nodes, d_calendar_lazy)
