import os
from datetime import date
from src.engines.analytics.pipeline.context import RunContext
from src.engines.analytics.pipeline.processor import IsinProcessor
from src.utils.interfaces import ILogger
from src.utils.models import EngineStatus, LogLevel


class IsinPipeline:
    """Handles processing individual ISINs and spilling results to disk."""
    def __init__(self, ctx: RunContext, isins: list[str], tmp_dir: str, status_queue: ILogger | None = None):
        self.ctx = ctx
        self.isins = isins
        self.tmp_dir = tmp_dir
        self.status_queue = status_queue
        self.processor = IsinProcessor(ctx)

    def process_all(self) -> tuple[bool, list[dict], dict[date, dict[str, float]], list[dict]]:
        global_cashflows = []
        portfolio_terminals: dict[date, dict[str, float]] = {}
        realized_events = []
        has_data = False
        total_inst = len(self.isins)

        for idx, isin in enumerate(self.isins):
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
                df, isin_cf, isin_pt, isin_re = self.processor.process(isin)
                if df is not None and not df.is_empty():
                    df.write_parquet(os.path.join(self.tmp_dir, f"{isin.replace('/', '_')}.parquet"))
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

        return has_data, global_cashflows, portfolio_terminals, realized_events
