"""
PolarsTaxEngine: Core investment analysis engine orchestrator.

Refactored to use a pipeline architecture with lazy Polars evaluation
and temporary parquet disk-spilling for optimal memory usage.
"""

import os
import tempfile
import traceback
from datetime import date

import polars as pl

from src.engines.pipeline.context import RunContext
from src.engines.pipeline.postprocessor import PostProcessor
from src.engines.pipeline.processor import IsinProcessor
from src.utils.interfaces import ILogger
from src.utils.models import EngineStatus, LogLevel


class PolarsTaxEngine:
    """
    Orchestrates the tax engine pipeline.
    """

    def __init__(
        self,
        df_p: pl.DataFrame,
        df_s: pl.DataFrame,
        df_m: pl.DataFrame,
        df_i: pl.DataFrame,
        df_b: pl.DataFrame | None,
        df_t: pl.DataFrame,
        status_queue: ILogger | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ):
        self.df_p = df_p
        self.df_s = df_s
        self.df_m = df_m
        self.df_i = df_i
        self.df_b = df_b if df_b is not None else pl.DataFrame()
        self.df_t = df_t
        self.status_queue = status_queue
        self.start_date = start_date
        self.end_date = end_date

    def run(self) -> pl.DataFrame:
        try:
            return self._run()
        except Exception as e:
            if self.status_queue is not None:
                if self.status_queue:
                    self.status_queue.put(
                        EngineStatus(
                            msg=f"Error: {e}\n{traceback.format_exc()}",
                            data=None,
                            progress=0.0,
                            level=LogLevel.ERROR,
                        )
                    )
            raise e

    def _run(self) -> pl.DataFrame:
        if self.status_queue:
            self.status_queue.put(
                EngineStatus("Loading DataFrame memory structures...", None, 0.01, LogLevel.STEP)
            )

        ctx = RunContext.from_dataframes(
            self.df_p,
            self.df_s,
            self.df_m,
            self.df_i,
            self.df_b,
            self.df_t,
            self.start_date,
            self.end_date,
        )

        if self.status_queue:
            self.status_queue.put(
                EngineStatus("Data loaded into Context successfully.", None, 0.05, LogLevel.INFO)
            )

        isins_p = ctx.df_p["ISIN"].unique().to_list() if "ISIN" in ctx.df_p.columns else []
        isins_s = ctx.df_s["ISIN"].unique().to_list() if "ISIN" in ctx.df_s.columns else []
        isins_m = ctx.df_m["ISIN"].unique().to_list() if "ISIN" in ctx.df_m.columns else []
        isins = sorted(set(isins_p + isins_s + isins_m))
        total_inst = len(isins)

        if total_inst == 0:
            empty_df = pl.DataFrame()
            if self.status_queue:
                self.status_queue.put(
                    EngineStatus(
                        msg="Processing Complete! (no valid ISINs found)",
                        data=empty_df,
                        progress=1.0,
                        level=LogLevel.SUCCESS,
                    )
                )
            return empty_df

        processor = IsinProcessor(ctx)
        postprocessor = PostProcessor(ctx)

        global_cashflows = []
        portfolio_terminals: dict[date, dict[str, float]] = {}
        realized_events = []

        has_data = False

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Phase 1: Process each ISIN and spill to disk
            for idx, isin in enumerate(isins):
                progress = 0.05 + 0.8 * (idx / total_inst)
                if self.status_queue:
                    self.status_queue.put(
                        EngineStatus(
                            msg=f"[{idx + 1}/{total_inst}] Processing {isin}...",
                            data=None,
                            progress=progress,
                            level=LogLevel.STEP,
                        )
                    )

                try:
                    df, isin_cf, isin_pt, isin_re = processor.process(isin)
                    if df is not None and not df.is_empty():
                        df.write_parquet(os.path.join(tmp_dir, f"{isin.replace('/', '_')}.parquet"))
                        has_data = True

                    global_cashflows.extend(isin_cf)
                    for d, vals in isin_pt.items():
                        pt = portfolio_terminals.setdefault(d, {"val": 0.0, "shadow_val": 0.0})
                        pt["val"] += vals["val"]
                        pt["shadow_val"] += vals["shadow_val"]
                    realized_events.extend(isin_re)
                except Exception as e:
                    if self.status_queue:
                        self.status_queue.put(
                            EngineStatus(
                                msg=f"Error processing {isin}: {e}",
                                data=None,
                                progress=progress,
                                level=LogLevel.ERROR,
                            )
                        )

            if not has_data:
                empty_df = pl.DataFrame()
                if self.status_queue:
                    self.status_queue.put(
                        EngineStatus(
                            msg="Processing Complete! (no output rows)",
                            data=empty_df,
                            progress=1.0,
                            level=LogLevel.SUCCESS,
                        )
                    )
                return empty_df

            if self.status_queue:
                self.status_queue.put(
                    EngineStatus(
                        msg="Post-processing: Scanning temporary parquet files...",
                        data=None,
                        progress=0.86,
                        level=LogLevel.STEP,
                    )
                )

            # Phase 2: Lazy Scan and Post-Processing
            lazy_df = pl.scan_parquet(os.path.join(tmp_dir, "*.parquet"))

            # unique dates
            # We must force execution to find unique dates for portfolio calculations
            unique_dates_df = lazy_df.select("Closing_Date").unique().collect()
            unique_dates = unique_dates_df["Closing_Date"].sort().to_list()

            if self.status_queue:
                self.status_queue.put(
                    EngineStatus(
                        msg="Post-processing: Aggregating portfolio metrics...",
                        data=None,
                        progress=0.90,
                        level=LogLevel.STEP,
                    )
                )
            lazy_df = postprocessor.run(
                lazy_df, unique_dates, global_cashflows, portfolio_terminals, realized_events
            )

            if self.status_queue:
                self.status_queue.put(
                    EngineStatus(
                        msg="Post-processing: Collecting final output...",
                        data=None,
                        progress=0.95,
                        level=LogLevel.STEP,
                    )
                )
            final_df = lazy_df.collect()

        n_rows = len(final_df)
        n_cols = len(final_df.columns)
        if self.status_queue:
            self.status_queue.put(
                EngineStatus(
                    msg=f"✅  Processing Complete — {n_rows:,} rows x {n_cols} columns.",
                    data=final_df,
                    progress=1.0,
                    level=LogLevel.SUCCESS,
                )
            )

        return final_df
