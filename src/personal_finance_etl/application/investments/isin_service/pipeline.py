"""Orchestrates ISIN worker task execution across ProcessPoolExecutor.

Owns
----
- IsinPipeline: Coordinates multiprocessing pool submission and collection.
- _PipelineAccumulator: Collects cashflows, terminals, and realized events across multi-dimensional groups.
- _DimensionAccumulator: Encapsulates cashflow, terminal, and event maps for a dimension.

Does not own
-------------
- Chronological simulation logic (owned by application.investments.isin_processor).
- Multiprocessing child process work (owned by application.investments.isin_worker).
- Lakehouse Parquet post-processing (owned by application.investments.aggregation_service).
"""

from __future__ import annotations

import concurrent.futures
import multiprocessing
import os
import traceback
from datetime import date
from typing import cast

import polars as pl

from personal_finance_etl.application.investments.context import RunContext
from personal_finance_etl.application.investments.isin_service.worker import _process_isin_worker
from personal_finance_etl.application.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.application.observability.diagnostics import get_observability_diagnostics
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.lifecycle import FailureDomain
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    EventCode,
    EventOutcome,
    PresentationKind,
)
from personal_finance_etl.domain.investments.contracts import (
    CashflowDict,
    IsinMasterRecord,
    PipelineExecutionResult,
    RealizedEventDict,
    ReconciliationEventDict,
    TerminalValueDict,
    TradeRecord,
)
from personal_finance_etl.domain.investments.valuation.benchmark import BenchmarkPriceProvider
from personal_finance_etl.domain.market.fx import FXRateProvider
from personal_finance_etl.domain.market.macro import FYMacroParametersTable

__all__ = ["IsinPipeline"]

diagnostics = get_observability_diagnostics(__name__)


class _DimensionAccumulator:
    """Container for dimensional cashflows, terminals, and realized events."""

    def __init__(self) -> None:
        self.cf: dict[str, list[CashflowDict]] = {}
        self.pt: dict[str, dict[date, dict[str, float]]] = {}
        self.re: dict[str, list[RealizedEventDict]] = {}


class _PipelineAccumulator:
    """Accumulates worker ISIN simulation outputs into multi-dimensional aggregation containers.

    Parameters
    ----------
    default_curr : str
        Base portfolio currency.
    """

    def __init__(self, default_curr: str) -> None:
        self.default_curr = default_curr
        self.global_cashflows: list[CashflowDict] = []
        self.portfolio_terminals: dict[date, dict[str, float]] = {}
        self.realized_events: list[RealizedEventDict] = []
        self.global_recon_events: list[ReconciliationEventDict] = []
        self.isin_cashflows: dict[str, list[CashflowDict]] = {}
        self.isin_terminals: dict[str, dict[date, TerminalValueDict]] = {}

        self.dim_class = _DimensionAccumulator()
        self.dim_subtype = _DimensionAccumulator()
        self.dim_instrument_type = _DimensionAccumulator()
        self.dim_sector = _DimensionAccumulator()
        self.dim_industry = _DimensionAccumulator()
        self.dim_geo = _DimensionAccumulator()
        self.dim_country = _DimensionAccumulator()
        self.dim_currency = _DimensionAccumulator()

    @staticmethod
    def _accumulate_group(
        key: str,
        target_cf: dict[str, list[CashflowDict]],
        target_pt: dict[str, dict[date, dict[str, float]]],
        isin_cf: list[CashflowDict],
        isin_pt: dict[date, TerminalValueDict],
    ) -> None:
        """Merge cashflows and terminals into a targeted dimension dictionary."""
        target_cf.setdefault(key, []).extend(isin_cf)
        pt_dict = target_pt.setdefault(key, {})
        for d, vals in isin_pt.items():
            entry = pt_dict.setdefault(
                d,
                {
                    "val": 0.0,
                    "shadow_val": 0.0,
                    "after_tax_val": 0.0,
                    "val_local": 0.0,
                    "shadow_val_local": 0.0,
                },
            )
            entry["val"] += vals.get("val", 0.0)
            entry["shadow_val"] += vals.get("shadow_val", 0.0)
            entry["after_tax_val"] += vals.get("after_tax_val", 0.0)
            entry["val_local"] += vals.get("val_local", 0.0)
            entry["shadow_val_local"] += vals.get("shadow_val_local", 0.0)

    def ingest_isin_result(
        self,
        isin: str,
        isin_cf: list[CashflowDict],
        isin_pt: dict[date, TerminalValueDict],
        isin_re: list[RealizedEventDict],
        isin_recon: list[ReconciliationEventDict],
        tags: dict[str, str],
    ) -> None:
        """Ingest individual ISIN worker result into global and group containers.

        Parameters
        ----------
        isin : str
            Instrument ISIN code.
        isin_cf : list[CashflowDict]
            Instrument cashflows.
        isin_pt : dict[date, TerminalValueDict]
            Daily terminals for the instrument.
        isin_re : list[RealizedEventDict]
            Realized capital gain events.
        isin_recon : list[ReconciliationEventDict]
            Quantity/cost-basis reconciliation events.
        tags : dict[str, str]
            Classification tags.
        """
        if isin_cf or isin_pt:
            self.isin_cashflows[isin] = isin_cf
            self.isin_terminals[isin] = isin_pt

        self.global_cashflows.extend(isin_cf)
        for d, vals in isin_pt.items():
            pt = self.portfolio_terminals.setdefault(
                d,
                {
                    "val": 0.0,
                    "shadow_val": 0.0,
                    "after_tax_val": 0.0,
                    "val_local": 0.0,
                    "shadow_val_local": 0.0,
                },
            )
            pt["val"] += vals.get("val", 0.0)
            pt["shadow_val"] += vals.get("shadow_val", 0.0)
            pt["after_tax_val"] += vals.get("after_tax_val", 0.0)
            pt["val_local"] += vals.get("val_local", 0.0)
            pt["shadow_val_local"] += vals.get("shadow_val_local", 0.0)

        self.realized_events.extend(isin_re)
        self.global_recon_events.extend(isin_recon)

        if not tags:
            return

        cls = tags.get("class", "Unknown")
        sub = tags.get("subtype", "Unknown")
        inst_type = tags.get("instrument_type", "Unknown")
        sector = tags.get("sector", "Unknown")
        industry = tags.get("industry", "Unknown")
        geo = tags.get("geo", "Unknown")
        country = tags.get("country", "Unknown")
        currency = tags.get("currency", self.default_curr)

        self.dim_class.re.setdefault(cls, []).extend(isin_re)
        self._accumulate_group(cls, self.dim_class.cf, self.dim_class.pt, isin_cf, isin_pt)

        sub_key = f"{cls}___{sub}"
        self.dim_subtype.re.setdefault(sub_key, []).extend(isin_re)
        self._accumulate_group(sub_key, self.dim_subtype.cf, self.dim_subtype.pt, isin_cf, isin_pt)

        self._accumulate_group(
            inst_type, self.dim_instrument_type.cf, self.dim_instrument_type.pt, isin_cf, isin_pt
        )
        self._accumulate_group(sector, self.dim_sector.cf, self.dim_sector.pt, isin_cf, isin_pt)
        self._accumulate_group(
            industry, self.dim_industry.cf, self.dim_industry.pt, isin_cf, isin_pt
        )
        self._accumulate_group(geo, self.dim_geo.cf, self.dim_geo.pt, isin_cf, isin_pt)
        self._accumulate_group(country, self.dim_country.cf, self.dim_country.pt, isin_cf, isin_pt)

        self.dim_currency.re.setdefault(currency, []).extend(isin_re)
        self._accumulate_group(
            currency, self.dim_currency.cf, self.dim_currency.pt, isin_cf, isin_pt
        )

    def to_result(self, has_data: bool) -> PipelineExecutionResult:
        """Construct the immutable PipelineExecutionResult structure.

        Parameters
        ----------
        has_data : bool
            Flag indicating whether any non-empty parquet partition was written.

        Returns
        -------
        PipelineExecutionResult
            Aggregated pipeline result contract.
        """
        return PipelineExecutionResult(
            has_data=has_data,
            global_cf=self.global_cashflows,
            global_pt=self.portfolio_terminals,
            global_re=self.realized_events,
            global_recon_events=self.global_recon_events,
            isin_cf=self.isin_cashflows,
            isin_pt=self.isin_terminals,
            class_cf=self.dim_class.cf,
            class_pt=self.dim_class.pt,
            class_re=self.dim_class.re,
            subtype_cf=self.dim_subtype.cf,
            subtype_pt=self.dim_subtype.pt,
            subtype_re=self.dim_subtype.re,
            instrument_type_cf=self.dim_instrument_type.cf,
            instrument_type_pt=self.dim_instrument_type.pt,
            sector_cf=self.dim_sector.cf,
            sector_pt=self.dim_sector.pt,
            industry_cf=self.dim_industry.cf,
            industry_pt=self.dim_industry.pt,
            geo_cf=self.dim_geo.cf,
            geo_pt=self.dim_geo.pt,
            country_cf=self.dim_country.cf,
            country_pt=self.dim_country.pt,
            currency_cf=self.dim_currency.cf,
            currency_pt=self.dim_currency.pt,
            currency_re=self.dim_currency.re,
        )


class IsinPipeline:
    """Handles processing individual ISINs and spilling results to disk.

    Parameters
    ----------
    ctx : RunContext
        Run context with DataFrames and financial configuration.
    isins : list[str]
        List of actionable instrument ISIN codes.
    tmp_dir : str
        Directory to spill intermediate per-ISIN Parquet files.
    status_queue : EventQueue | None, optional
        Status queue for reporting execution progress.
    """

    def __init__(
        self,
        ctx: RunContext,
        isins: list[str],
        tmp_dir: str,
        status_queue: EventQueue | None = None,
        emitter: ObservabilityEmitter | None = None,
    ):
        self.ctx = ctx
        self.isins = isins
        self.tmp_dir = tmp_dir
        self.status_queue = status_queue
        self.emitter = emitter or get_global_emitter()

    def _report_step(self, progress: float) -> None:
        """Emit incremental progress through the canonical emitter."""
        self.emitter.emit_event(
            event_code=EventCode.QUANT_ISIN_PROCESSED,
            message="",
            progress=progress,
            severity=DiagnosticSeverity.INFO,
            outcome=EventOutcome.COMPLETED,
            presentation_kind=PresentationKind.PROGRESS,
            stage=EngineStage.ANALYZING,
        )

    def _build_worker_tasks(
        self,
    ) -> list[
        tuple[
            str,
            list[TradeRecord],
            list[TradeRecord],
            list[TradeRecord],
            IsinMasterRecord,
            dict[date, float],
            FYMacroParametersTable,
            date | None,
            date | None,
            FinancialRules,
            FXRateProvider | None,
            str,
        ]
    ]:
        """Partition input trade frames and build task payloads for multiprocessing worker pool.

        Returns
        -------
        list[tuple]
            List of worker task tuples ready for ProcessPoolExecutor execution.
        """
        p_dict_pl: dict[tuple[object, ...] | str, pl.DataFrame] = (
            cast(
                dict[tuple[object, ...] | str, pl.DataFrame],
                self.ctx.df_p.partition_by("ISIN", as_dict=True),
            )
            if not self.ctx.df_p.is_empty()
            else {}
        )
        s_dict_pl: dict[tuple[object, ...] | str, pl.DataFrame] = (
            cast(
                dict[tuple[object, ...] | str, pl.DataFrame],
                self.ctx.df_s.partition_by("ISIN", as_dict=True),
            )
            if not self.ctx.df_s.is_empty()
            else {}
        )

        m_grouped = (
            (
                self.ctx.df_m.sort(["ISIN", "Date"])
                .group_by(["ISIN", "Date"], maintain_order=True)
                .agg(
                    [
                        pl.col("Quantity").sum().alias("Quantity"),
                        pl.col("Closing_Price").last().alias("Closing_Price"),
                        pl.col("Buy_Value").sum().alias("Buy_Value"),
                        (
                            pl.col("Buy_Value_Local").sum().alias("Buy_Value_Local")
                            if "Buy_Value_Local" in self.ctx.df_m.columns
                            else pl.lit(None).cast(pl.Float64).alias("Buy_Value_Local")
                        ),
                    ]
                )
            )
            if not self.ctx.df_m.is_empty()
            else pl.DataFrame()
        )

        m_dict_pl: dict[tuple[object, ...] | str, pl.DataFrame] = (
            cast(
                dict[tuple[object, ...] | str, pl.DataFrame],
                m_grouped.partition_by("ISIN", as_dict=True),
            )
            if not m_grouped.is_empty()
            else {}
        )

        bm_maps: dict[str, dict[date, float]] = {}
        for _isin, row in self.ctx.isin_master.items():
            b_id = str(row.get("BENCHMARK_ID", ""))
            if b_id and b_id not in bm_maps:
                bm_maps[b_id] = BenchmarkPriceProvider(b_id, self.ctx.df_b).bm_price_map

        tasks: list[
            tuple[
                str,
                list[TradeRecord],
                list[TradeRecord],
                list[TradeRecord],
                IsinMasterRecord,
                dict[date, float],
                FYMacroParametersTable,
                date | None,
                date | None,
                FinancialRules,
                FXRateProvider | None,
                str,
            ]
        ] = []
        for isin in self.isins:
            p_df = p_dict_pl.get((isin,)) if (isin,) in p_dict_pl else p_dict_pl.get(isin)
            p_inst = cast(
                "list[TradeRecord]",
                p_df.sort("Date").to_dicts() if p_df is not None and not p_df.is_empty() else [],
            )

            s_df = s_dict_pl.get((isin,)) if (isin,) in s_dict_pl else s_dict_pl.get(isin)
            s_inst = cast(
                "list[TradeRecord]",
                s_df.sort("Date").to_dicts() if s_df is not None and not s_df.is_empty() else [],
            )

            m_df = m_dict_pl.get((isin,)) if (isin,) in m_dict_pl else m_dict_pl.get(isin)
            m_inst = cast(
                "list[TradeRecord]",
                m_df.to_dicts() if m_df is not None and not m_df.is_empty() else [],
            )

            master_row: IsinMasterRecord = self.ctx.isin_master.get(isin, {})
            b_id = str(master_row.get("BENCHMARK_ID", ""))
            bm_map = bm_maps.get(b_id, {})

            tasks.append(
                (
                    isin,
                    p_inst,
                    s_inst,
                    m_inst,
                    master_row,
                    bm_map,
                    self.ctx.fy_table,
                    self.ctx.start_date,
                    self.ctx.end_date,
                    self.ctx.rules,
                    self.ctx.fx_provider,
                    self.tmp_dir,
                )
            )
        return tasks

    def process_all(self) -> PipelineExecutionResult:
        """Execute parallel multi-process simulation across all configured ISIN instruments.

        Returns
        -------
        PipelineExecutionResult
            Consolidated simulation results across all ISINs.
        """
        acc = _PipelineAccumulator(self.ctx.rules.DEFAULT_CURRENCY_ID)
        has_data = False
        total_inst = len(self.isins)
        tasks = self._build_worker_tasks()

        current_process = multiprocessing.current_process()
        is_daemon = current_process.daemon
        current_process.daemon = False
        try:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=min(4, os.cpu_count() or 1),
            ) as executor:
                future_to_isin = {
                    executor.submit(_process_isin_worker, task): task[0] for task in tasks
                }

                for i, future in enumerate(concurrent.futures.as_completed(future_to_isin)):
                    isin = future_to_isin[future]
                    self._report_step(0.05 + 0.8 * (i / total_inst))

                    try:
                        success, isin_cf, isin_pt, isin_re, isin_recon, tags, error_info = (
                            future.result()
                        )
                    except Exception as e:
                        error_msg = f"Process-boundary failure: {type(e).__name__} - {str(e)}"
                        diagnostics.error(
                            f"ISIN Processing Failed for {isin}: {error_msg}\n{traceback.format_exc()}"
                        )
                        err_details = ErrorDetails(
                            exception_type=type(e).__name__,
                            exception_message=str(e),
                            failure_domain=FailureDomain.WORKER,
                            traceback_summary=traceback.format_exc(),
                            retryable=False,
                        )
                        self.emitter.emit_event(
                            event_code=EventCode.QUANT_ISIN_PROCESSED,
                            message=f"ISIN Processing Failed for {isin}: {error_msg}",
                            presentation_kind=PresentationKind.FAILURE,
                            severity=DiagnosticSeverity.ERROR,
                            outcome=EventOutcome.FAILED,
                            stage=EngineStage.ANALYZING,
                            entity_type="ISIN",
                            entity_id=isin,
                            error=err_details,
                        )
                        raise RuntimeError(f"ISIN_FAILURE|{isin}|{error_msg}") from e

                    if error_info is not None:
                        failed_isin = error_info.get("isin", isin)
                        error_msg = error_info.get("error", "Unknown Error")
                        tb = error_info.get("traceback", "")
                        diagnostics.error(
                            f"ISIN Processing Failed for {failed_isin}: {error_msg}\n{tb}"
                        )
                        err_details = ErrorDetails(
                            exception_type="ISINCalculationError",
                            exception_message=error_msg,
                            failure_domain=FailureDomain.WORKER,
                            traceback_summary=tb,
                            retryable=False,
                        )
                        self.emitter.emit_event(
                            event_code=EventCode.QUANT_ISIN_PROCESSED,
                            message=f"ISIN Processing Failed for {failed_isin}: {error_msg}",
                            presentation_kind=PresentationKind.FAILURE,
                            severity=DiagnosticSeverity.ERROR,
                            outcome=EventOutcome.FAILED,
                            stage=EngineStage.ANALYZING,
                            entity_type="ISIN",
                            entity_id=failed_isin,
                            error=err_details,
                        )
                        raise RuntimeError(f"ISIN_FAILURE|{failed_isin}|{error_msg}")

                    if success:
                        has_data = True
                    acc.ingest_isin_result(isin, isin_cf, isin_pt, isin_re, isin_recon, tags)
                    self.emitter.emit_event(
                        event_code=EventCode.QUANT_ISIN_PROCESSED,
                        message=f"Calculated quant lots and cashflows for ISIN {isin}",
                        presentation_kind=PresentationKind.INTERNAL,
                        severity=DiagnosticSeverity.DEBUG,
                        stage=EngineStage.ANALYZING,
                        entity_type="ISIN",
                        entity_id=isin,
                        rows=len(isin_cf),
                    )
        finally:
            current_process.daemon = is_daemon

        diagnostics.info(
            f"  -> Quant Engine successfully processed {len(self.isins)} ISIN workloads across Process Pool."
        )
        return acc.to_result(has_data)
