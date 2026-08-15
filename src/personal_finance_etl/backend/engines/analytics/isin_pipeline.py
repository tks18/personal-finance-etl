import concurrent.futures
import multiprocessing
import os
from datetime import date
from typing import Any

import polars as pl

from personal_finance_etl.backend.engines.analytics.pipeline.context import RunContext
from personal_finance_etl.backend.engines.analytics.pipeline.processor import IsinProcessor
from personal_finance_etl.backend.engines.analytics.pipeline.processor.benchmark import BenchmarkPriceProvider
from personal_finance_etl.backend.types.pipeline import PipelineExecutionResult
from personal_finance_etl.backend.utils.interfaces import ILogger
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import EngineStatus, LogLevel


def _process_isin_worker(
    task: tuple[
        str,
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        dict[str, Any],
        dict[date, float],
        Any,
        Any,
        Any,
        Any,
        str,
    ],
) -> tuple[
    bool, list[dict[str, Any]], dict[date, dict[str, Any]], list[dict[str, Any]], dict[str, Any]
]:
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
        tmp_dir,
    ) = task

    logger.debug(
        f"[Worker] Starting processing for ISIN: {isin} with {len(p_inst)} purchases, {len(s_inst)} sales, and {len(m_inst)} market quotes"
    )

    processor = IsinProcessor(fy_table, start_date, end_date, rules)
    try:
        res = processor.process(isin, p_inst, s_inst, m_inst, master_row, bm_map)
        if res is not None:
            df = res.df_snapshots
            isin_cf = [c.model_dump(mode="python") for c in res.cashflows]
            isin_pt = {d: pt.model_dump(mode="python") for d, pt in res.terminals.items()}
            tags = res.tags.model_dump(by_alias=True)
            isin_re = res.realized_events

            if df is not None and not df.is_empty():
                df.write_parquet(os.path.join(tmp_dir, f"{isin.replace('/', '_')}.parquet"))
                return True, isin_cf, isin_pt, isin_re, tags
            return False, isin_cf, isin_pt, isin_re, tags
        return False, [], {}, [], {}
    except Exception:
        return False, [], {}, [], {}


class IsinPipeline:
    """Handles processing individual ISINs and spilling results to disk."""

    def __init__(
        self, ctx: RunContext, isins: list[str], tmp_dir: str, status_queue: ILogger | None = None
    ):
        self.ctx = ctx
        self.isins = isins
        self.tmp_dir = tmp_dir
        self.status_queue = status_queue

    def process_all(self) -> PipelineExecutionResult:
        global_cashflows: list[dict[str, Any]] = []
        portfolio_terminals: dict[date, dict[str, float]] = {}
        realized_events: list[dict[str, Any]] = []

        class_cf: dict[str, list[dict[str, Any]]] = {}
        class_pt: dict[str, dict[date, dict[str, float]]] = {}
        class_re: dict[str, list[dict[str, Any]]] = {}

        subtype_cf: dict[str, list[dict[str, Any]]] = {}
        subtype_pt: dict[str, dict[date, dict[str, float]]] = {}
        subtype_re: dict[str, list[dict[str, Any]]] = {}

        has_data = False
        total_inst = len(self.isins)

        # Pre-partition dataframes to avoid O(N*M) filtering inside the loop

        p_dict_pl = (
            self.ctx.df_p.partition_by("ISIN", as_dict=True) if not self.ctx.df_p.is_empty() else {}
        )
        s_dict_pl = (
            self.ctx.df_s.partition_by("ISIN", as_dict=True) if not self.ctx.df_s.is_empty() else {}
        )

        m_grouped = (
            (
                self.ctx.df_m.sort(["ISIN", "Date"])
                .group_by(["ISIN", "Date"], maintain_order=True)
                .agg(
                    [
                        pl.col("Quantity").sum().alias("Quantity"),
                        pl.col("Closing Price").last().alias("Closing Price"),
                        pl.col("Buy Value").sum().alias("Buy Value"),
                    ]
                )
            )
            if not self.ctx.df_m.is_empty()
            else pl.DataFrame()
        )

        m_dict_pl = m_grouped.partition_by("ISIN", as_dict=True) if not m_grouped.is_empty() else {}

        bm_maps: dict[str, dict[date, float]] = {}
        for _isin, row in self.ctx.isin_master.items():
            b_id = str(row.get("BENCHMARK_ID", ""))
            if b_id and b_id not in bm_maps:
                bm_maps[b_id] = BenchmarkPriceProvider(b_id, self.ctx.df_b).bm_price_map

        tasks: list[
            tuple[
                str,
                list[dict[str, Any]],
                list[dict[str, Any]],
                list[dict[str, Any]],
                dict[str, Any],
                dict[date, float],
                Any,
                Any,
                Any,
                Any,
                str,
            ]
        ] = []
        for isin in self.isins:
            p_df = p_dict_pl.get((isin,)) if (isin,) in p_dict_pl else p_dict_pl.get(isin)  # type: ignore
            p_inst = (
                p_df.sort("Date").to_dicts() if p_df is not None and not p_df.is_empty() else []
            )

            s_df = s_dict_pl.get((isin,)) if (isin,) in s_dict_pl else s_dict_pl.get(isin)  # type: ignore
            s_inst = (
                s_df.sort("Date").to_dicts() if s_df is not None and not s_df.is_empty() else []
            )

            m_df = m_dict_pl.get((isin,)) if (isin,) in m_dict_pl else m_dict_pl.get(isin)  # type: ignore
            m_inst = m_df.to_dicts() if m_df is not None and not m_df.is_empty() else []

            master_row = self.ctx.isin_master.get(isin, {})
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
                    self.tmp_dir,
                )
            )

        # Temporarily disable daemon flag to allow multiprocessing pool to spawn workers
        current_process = multiprocessing.current_process()
        is_daemon = current_process.daemon
        current_process.daemon = False

        try:
            with concurrent.futures.ProcessPoolExecutor(
                max_workers=min(4, os.cpu_count() or 1)
            ) as executor:
                futures = [executor.submit(_process_isin_worker, task) for task in tasks]

                for i, future in enumerate(concurrent.futures.as_completed(futures)):
                    if self.status_queue:
                        self.status_queue.put(
                            EngineStatus(
                                msg="",
                                data=None,
                                progress=0.05 + 0.8 * (i / total_inst),
                                level=LogLevel.STEP,
                            )
                        )

                    success, isin_cf, isin_pt, isin_re, tags = future.result()
                    if success:
                        has_data = True

                    global_cashflows.extend(isin_cf)
                    for d, vals in isin_pt.items():
                        pt = portfolio_terminals.setdefault(
                            d, {"val": 0.0, "shadow_val": 0.0, "after_tax_val": 0.0}
                        )
                        pt["val"] += vals["val"]
                        pt["shadow_val"] += vals["shadow_val"]
                        pt["after_tax_val"] += vals.get("after_tax_val", 0.0)
                    realized_events.extend(isin_re)

                    if not tags:
                        continue

                    cls = tags.get("class", "Unknown")
                    sub = tags.get("subtype", "Unknown")

                    class_cf.setdefault(cls, []).extend(isin_cf)
                    class_re.setdefault(cls, []).extend(isin_re)
                    cp = class_pt.setdefault(cls, {})
                    for d, vals in isin_pt.items():
                        pt = cp.setdefault(d, {"val": 0.0, "shadow_val": 0.0, "after_tax_val": 0.0})
                        pt["val"] += vals["val"]
                        pt["shadow_val"] += vals["shadow_val"]
                        pt["after_tax_val"] += vals.get("after_tax_val", 0.0)

                    sub_key = f"{cls}___{sub}"
                    subtype_cf.setdefault(sub_key, []).extend(isin_cf)
                    subtype_re.setdefault(sub_key, []).extend(isin_re)
                    sp = subtype_pt.setdefault(sub_key, {})
                    for d, vals in isin_pt.items():
                        pt = sp.setdefault(d, {"val": 0.0, "shadow_val": 0.0, "after_tax_val": 0.0})
                        pt["val"] += vals["val"]
                        pt["shadow_val"] += vals["shadow_val"]
                        pt["after_tax_val"] += vals.get("after_tax_val", 0.0)
        finally:
            current_process.daemon = is_daemon

        logger.info(
            f"  -> Quant Engine successfully processed {len(self.isins)} ISIN workloads across Process Pool."
        )

        return PipelineExecutionResult(
            has_data=has_data,
            global_cf=global_cashflows,
            global_pt=portfolio_terminals,
            global_re=realized_events,
            class_cf=class_cf,
            class_pt=class_pt,
            class_re=class_re,
            subtype_cf=subtype_cf,
            subtype_pt=subtype_pt,
            subtype_re=subtype_re,
        )
