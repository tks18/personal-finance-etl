"""Investment quantitative analytics application service.

Owns
----
- InvestmentQuantEngine: Orchestrates the end-to-end investment pipeline:
  1. Ingests raw inputs into RunContext via AnalyticsContextManager.
  2. Runs concurrent per-ISIN processing and lot accounting via IsinPipeline.
  3. Executes multi-asset portfolio aggregation and post-processing via PostProcessingPipeline.
- QuantService: Canonical alias for InvestmentQuantEngine.

Does not own
-------------
- Chronological per-ISIN daily simulation (owned by application.investments.isin_service).
- Post-processing aggregation logic (owned by application.investments.aggregation_service).
- Ingestion extraction adapters (owned by application.investments.input_adapter).
"""

from __future__ import annotations

import logging
import tempfile

import polars as pl

from personal_finance_etl.application.investments.aggregation_service import (
    PostProcessingPipeline,
)
from personal_finance_etl.application.investments.context import (
    AnalyticsContextManager,
    QuantDataFrames,
    QuantRunOptions,
)
from personal_finance_etl.application.investments.isin_service import (
    IsinPipeline,
)
from personal_finance_etl.application.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.logging import StatusQueue
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    EventOutcome,
    PresentationKind,
)

__all__ = ["InvestmentQuantEngine", "QuantService"]

logger = logging.getLogger(__name__)


class InvestmentQuantEngine:
    """Orchestrates the multi-process investment quantitative calculations."""

    def __init__(
        self,
        data: QuantDataFrames,
        options: QuantRunOptions,
        status_queue: StatusQueue | None = None,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        """Initialize InvestmentQuantEngine with structured typed parameter bundles.

        Parameters
        ----------
        data : QuantDataFrames
            Bundle of DataFrames for analysis.
        options : QuantRunOptions
            Execution options and boundaries.
        status_queue : StatusQueue | None, optional
            Queue for streaming engine progress events.
        emitter : ObservabilityEmitter | None, optional
            Observability emitter for canonical structured events.
        """
        self.data = data
        self.options = options
        self.status_queue = status_queue
        self.emitter = emitter or get_global_emitter()

    def run(self) -> dict[str, pl.DataFrame]:
        """Execute the quantitative analysis engine.

        Returns
        -------
        dict[str, pl.DataFrame]
            Dictionary of 13 aggregated analytical tables.
        """
        try:
            return self._run()
        except Exception as e:
            self.emitter.emit_event(
                event_code=EventCode.RUN_FAILED,
                message=f"Quant Engine failed: {e}",
                severity=DiagnosticSeverity.ERROR,
                outcome=EventOutcome.FAILED,
                presentation_kind=PresentationKind.FAILURE,
                stage=EngineStage.ANALYZING,
            )
            raise e

    def _run(self) -> dict[str, pl.DataFrame]:
        context_manager = AnalyticsContextManager(self.status_queue)
        ctx, isins = context_manager.initialize(data=self.data, options=self.options)

        min_market = ctx.df_m.select(pl.min("Date")).item() if not ctx.df_m.is_empty() else None
        max_market = ctx.df_m.select(pl.max("Date")).item() if not ctx.df_m.is_empty() else None
        logger.info(
            f"  -> Quant Engine initialized context spanning market dates {min_market} to {max_market} for {len(isins)} unique ISINs."
        )
        self.emitter.emit_event(
            event_code=EventCode.QUANT_ENGINE_START,
            message=(
                f"Quant Engine initialized context spanning market dates {min_market} to "
                f"{max_market} for {len(isins)} unique ISINs."
            ),
            presentation_kind=PresentationKind.STEP,
            rows=len(isins),
            stage=EngineStage.ANALYZING,
        )

        if not isins:
            empty_df = pl.DataFrame()
            self.emitter.emit_event(
                event_code=EventCode.QUANT_POOL_COMPLETED,
                message="Processing Complete! (no valid ISINs found)",
                presentation_kind=PresentationKind.SUCCESS,
                stage=EngineStage.ANALYZING,
            )
            return {"df_f_investment_analytics_lot": empty_df}

        with tempfile.TemporaryDirectory() as tmp_dir:
            isin_pipeline = IsinPipeline(
                ctx, isins, tmp_dir, self.status_queue, emitter=self.emitter
            )
            pipeline_res = isin_pipeline.process_all()
            has_data = pipeline_res.has_data

            if not has_data:
                empty_df = pl.DataFrame()
                self.emitter.emit_event(
                    event_code=EventCode.QUANT_POOL_COMPLETED,
                    message="Processing Complete! (no output rows)",
                    presentation_kind=PresentationKind.SUCCESS,
                    stage=EngineStage.ANALYZING,
                )
                return {"df_f_investment_analytics_lot": empty_df}

            post_pipeline = PostProcessingPipeline(ctx, tmp_dir, self.status_queue)
            final_dfs = post_pipeline.run(pipeline_res)

            self.emitter.emit_event(
                event_code=EventCode.QUANT_POOL_COMPLETED,
                message=f"Processing Complete — generated {len(final_dfs)} analytics tables",
                presentation_kind=PresentationKind.SUCCESS,
                rows=len(final_dfs),
                stage=EngineStage.ANALYZING,
            )

            return final_dfs


QuantService = InvestmentQuantEngine
