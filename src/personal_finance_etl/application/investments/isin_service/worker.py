"""Multiprocessing child process worker function for isolated ISIN simulation.

Owns
----
- IsinTaskPayload: Typed contract for parameters dispatched to isolated worker child process.
- IsinResultPayload: Typed contract for simulation results returned by worker process.
- Top-level picklable process worker entrypoint (_process_isin_worker).
- Per-ISIN calculation execution and temporary parquet spilling.

Does not own
-------------
- ProcessPoolExecutor lifecycle (owned by application.investments.isin_pipeline).
- Aggregation of results (owned by application.investments.aggregation_service).
"""

from __future__ import annotations

import os
import traceback
from datetime import date
from typing import NamedTuple, cast

from personal_finance_etl.application.investments.isin_service.processor import IsinProcessor
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.investments.contracts import (
    CashflowDict,
    IsinMasterRecord,
    RealizedEventDict,
    ReconciliationEventDict,
    TerminalValueDict,
    TradeRecord,
)
from personal_finance_etl.domain.market.fx import FXRateProvider
from personal_finance_etl.domain.market.macro import FYMacroParametersTable

__all__ = ["IsinResultPayload", "IsinTaskPayload", "_process_isin_worker"]


class IsinTaskPayload(NamedTuple):
    """Task parameters dispatched to an isolated ISIN simulation worker process.

    Parameters
    ----------
    isin : str
        Unique security ISIN code.
    p_inst : list[TradeRecord]
        List of historical purchase transactions for this ISIN.
    s_inst : list[TradeRecord]
        List of historical sale transactions for this ISIN.
    m_inst : list[TradeRecord]
        Aggregated market quote and value records for this ISIN.
    master_row : IsinMasterRecord
        Security metadata including classification tags and benchmark mappings.
    bm_map : dict[date, float]
        Date-to-price lookup map for the mapped benchmark index.
    fy_table : FYMacroParametersTable
        Financial year macroeconomic parameters table.
    start_date : date | None
        Analysis window start boundary.
    end_date : date | None
        Analysis window end boundary.
    rules : FinancialRules
        System financial calculation rules and currency standards.
    fx_provider : FXRateProvider | None
        Foreign exchange rate provider for multi-currency securities.
    tmp_dir : str
        Temporary directory path for spilling calculated snapshot parquet partitions.
    """

    isin: str
    p_inst: list[TradeRecord]
    s_inst: list[TradeRecord]
    m_inst: list[TradeRecord]
    master_row: IsinMasterRecord
    bm_map: dict[date, float]
    fy_table: FYMacroParametersTable
    start_date: date | None
    end_date: date | None
    rules: FinancialRules
    fx_provider: FXRateProvider | None
    tmp_dir: str


class IsinResultPayload(NamedTuple):
    """Result bundle returned by an isolated ISIN simulation worker process.

    Parameters
    ----------
    success : bool
        Flag indicating whether a non-empty parquet partition was spilled.
    cashflows : list[CashflowDict]
        Calculated chronological cashflow records for the instrument.
    terminals : dict[date, TerminalValueDict]
        Daily valuation terminals for the instrument.
    realized_events : list[RealizedEventDict]
        Chronological capital gains realized events.
    recon_events : list[ReconciliationEventDict]
        Reconciliation and quantity adjustment audit events.
    tags : dict[str, str]
        Asset classification tags for multi-dimensional aggregation.
    error_info : dict[str, str] | None
        Captured exception and traceback summary if calculation failed in child process.
    """

    success: bool
    cashflows: list[CashflowDict]
    terminals: dict[date, TerminalValueDict]
    realized_events: list[RealizedEventDict]
    recon_events: list[ReconciliationEventDict]
    tags: dict[str, str]
    error_info: dict[str, str] | None


def _process_isin_worker(
    task: IsinTaskPayload
    | tuple[
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
    ],
) -> IsinResultPayload:
    """Execute chronological simulation for a single ISIN inside ProcessPoolExecutor child process.

    Parameters
    ----------
    task : IsinTaskPayload | tuple
        Task bundle consisting of ISIN, purchase/sale/market inputs, master tags,
        macro tables, bounds, rules, fx provider, and temporary spill directory.

    Returns
    -------
    IsinResultPayload
        Structured named tuple of (success, cashflows, terminals, realized_events,
        recon_events, tags, error_info).
    """
    (
        isin,
        p_inst,
        s_inst,
        m_inst,
        master_row,
        bm_map,
        fy_table,
        start_date,
        end_date,
        rules,
        fx_provider,
        tmp_dir,
    ) = task

    processor = IsinProcessor(fy_table, start_date, end_date, rules, fx_provider)
    try:
        res = processor.process(isin, p_inst, s_inst, m_inst, master_row, bm_map)

        if res is not None:
            df = res.df_snapshots
            isin_cf = cast(
                "list[CashflowDict]", [c.model_dump(mode="python") for c in res.cashflows]
            )
            isin_pt = cast(
                "dict[date, TerminalValueDict]",
                {d: pt.model_dump(mode="python") for d, pt in res.terminals.items()},
            )
            tags = cast("dict[str, str]", res.tags.model_dump(by_alias=True))
            isin_re = cast(
                "list[RealizedEventDict]",
                [
                    r if isinstance(r, dict) else r.model_dump(by_alias=True)
                    for r in res.realized_events
                ],
            )
            isin_recon = cast(
                "list[ReconciliationEventDict]",
                [
                    r if isinstance(r, dict) else r.model_dump(by_alias=True)
                    for r in res.recon_events
                ],
            )

            if df is not None and not df.is_empty():
                df.write_parquet(os.path.join(tmp_dir, f"{isin.replace('/', '_')}.parquet"))
                return IsinResultPayload(
                    success=True,
                    cashflows=isin_cf,
                    terminals=isin_pt,
                    realized_events=isin_re,
                    recon_events=isin_recon,
                    tags=tags,
                    error_info=None,
                )
            return IsinResultPayload(
                success=False,
                cashflows=isin_cf,
                terminals=isin_pt,
                realized_events=isin_re,
                recon_events=isin_recon,
                tags=tags,
                error_info=None,
            )
        return IsinResultPayload(
            success=False,
            cashflows=[],
            terminals={},
            realized_events=[],
            recon_events=[],
            tags={},
            error_info=None,
        )
    except Exception as e:
        tb = traceback.format_exc()
        return IsinResultPayload(
            success=False,
            cashflows=[],
            terminals={},
            realized_events=[],
            recon_events=[],
            tags={},
            error_info={"isin": isin, "error": str(e), "traceback": tb},
        )
