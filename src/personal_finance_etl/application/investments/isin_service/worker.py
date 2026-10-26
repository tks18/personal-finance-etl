"""Multiprocessing child process worker function for isolated ISIN simulation.

Owns
----
- Top-level picklable process worker entrypoint (_process_isin_worker).
- Per-ISIN calculation execution and temporary parquet spilling.

Does not own
-------------
- ProcessPoolExecutor lifecycle (owned by application.investments.isin_pipeline).
- Aggregation of results (owned by application.investments.aggregation_service).
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import time
import traceback
from datetime import date
from typing import cast

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

__all__ = ["_process_isin_worker"]

logger = logging.getLogger(__name__)


def _process_isin_worker(
    task: tuple[
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
) -> tuple[
    bool,
    list[CashflowDict],
    dict[date, TerminalValueDict],
    list[RealizedEventDict],
    list[ReconciliationEventDict],
    dict[str, str],
    dict[str, str] | None,
]:
    """Execute chronological simulation for a single ISIN inside ProcessPoolExecutor child process.

    Parameters
    ----------
    task : tuple
        Task bundle consisting of:
        - isin (str)
        - p_inst (list[TradeRecord])
        - s_inst (list[TradeRecord])
        - m_inst (list[TradeRecord])
        - master_row (IsinMasterRecord)
        - bm_map (dict[date, float])
        - fy_table (FYMacroParametersTable)
        - start_date (date | None)
        - end_date (date | None)
        - rules (FinancialRules)
        - fx_provider (FXRateProvider | None)
        - tmp_dir (str)

    Returns
    -------
    tuple
        Tuple of (written_flag, cashflows, terminals, realized_events, recon_events, tags, error_info).
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

    logger.debug(
        f"Starting processing for ISIN: {isin} with {len(p_inst)} purchases, "
        f"{len(s_inst)} sales, and {len(m_inst)} market quotes",
        extra={"isin": isin, "stage": "QuantWorker"},
    )

    processor = IsinProcessor(fy_table, start_date, end_date, rules, fx_provider)
    try:
        worker_id = multiprocessing.current_process().name
        logger.debug(
            f"{worker_id} started processing ISIN '{isin}'",
            extra={"isin": isin, "stage": "QuantWorker"},
        )
        t0 = time.perf_counter()

        res = processor.process(isin, p_inst, s_inst, m_inst, master_row, bm_map)

        logger.debug(
            f"{worker_id} finished ISIN '{isin}' in {(time.perf_counter() - t0) * 1000:.2f}ms",
            extra={"isin": isin, "stage": "QuantWorker"},
        )

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
                return True, isin_cf, isin_pt, isin_re, isin_recon, tags, None
            return False, isin_cf, isin_pt, isin_re, isin_recon, tags, None
        return False, [], {}, [], [], {}, None
    except Exception as e:
        tb = traceback.format_exc()
        return False, [], {}, [], [], {}, {"isin": isin, "error": str(e), "traceback": tb}
