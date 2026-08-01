import concurrent.futures
import os
from datetime import date

from src.engines.analytics.pipeline.context import RunContext
from src.engines.analytics.pipeline.processor import IsinProcessor
from src.utils.interfaces import ILogger
from src.utils.logger import logger
from src.utils.models import EngineStatus, LogLevel


class IsinPipeline:
    """Handles processing individual ISINs and spilling results to disk."""

    def __init__(
        self, ctx: RunContext, isins: list[str], tmp_dir: str, status_queue: ILogger | None = None
    ):
        self.ctx = ctx
        self.isins = isins
        self.tmp_dir = tmp_dir
        self.status_queue = status_queue
        self.processor = IsinProcessor(ctx)

    def process_all(self):
        global_cashflows = []
        portfolio_terminals: dict[date, dict[str, float]] = {}
        realized_events = []

        class_cf: dict[str, list[dict]] = {}
        class_pt: dict[str, dict[date, dict[str, float]]] = {}
        class_re: dict[str, list[dict]] = {}

        subtype_cf: dict[str, list[dict]] = {}
        subtype_pt: dict[str, dict[date, dict[str, float]]] = {}
        subtype_re: dict[str, list[dict]] = {}

        has_data = False
        total_inst = len(self.isins)

        def _process_single(isin: str, idx: int) -> tuple[bool, list, dict, list, dict]:
            if self.status_queue:
                logger.debug(f"[{idx + 1}/{total_inst}] Processing {isin}...")
                self.status_queue.put(
                    EngineStatus(
                        msg="",
                        data=None,
                        progress=0.05 + 0.8 * (idx / total_inst),
                        level=LogLevel.STEP,
                    )
                )

            try:
                df, isin_cf, isin_pt, isin_re, tags = self.processor.process(isin)
                if df is not None and not df.is_empty():
                    df.write_parquet(
                        os.path.join(self.tmp_dir, f"{isin.replace('/', '_')}.parquet")
                    )
                    return True, isin_cf, isin_pt, isin_re, tags
                return False, isin_cf, isin_pt, isin_re, tags
            except Exception as e:
                if self.status_queue:
                    self.status_queue.put(
                        EngineStatus(
                            msg=f"Error processing {isin}: {e}",
                            data=None,
                            progress=0.05 + 0.8 * (idx / total_inst),
                            level=LogLevel.ERROR,
                        )
                    )
                return False, [], {}, [], {}

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(32, (os.cpu_count() or 1) * 2)
        ) as executor:
            futures = [
                executor.submit(_process_single, isin, idx) for idx, isin in enumerate(self.isins)
            ]
            for future in concurrent.futures.as_completed(futures):
                success, isin_cf, isin_pt, isin_re, tags = future.result()
                if success:
                    has_data = True

                global_cashflows.extend(isin_cf)
                for d, vals in isin_pt.items():
                    pt = portfolio_terminals.setdefault(d, {"val": 0.0, "shadow_val": 0.0})
                    pt["val"] += vals["val"]
                    pt["shadow_val"] += vals["shadow_val"]
                realized_events.extend(isin_re)

                if not tags:
                    continue

                cls = tags.get("class", "Unknown")
                sub = tags.get("subtype", "Unknown")

                class_cf.setdefault(cls, []).extend(isin_cf)
                class_re.setdefault(cls, []).extend(isin_re)
                cp = class_pt.setdefault(cls, {})
                for d, vals in isin_pt.items():
                    pt = cp.setdefault(d, {"val": 0.0, "shadow_val": 0.0})
                    pt["val"] += vals["val"]
                    pt["shadow_val"] += vals["shadow_val"]

                sub_key = f"{cls}___{sub}"
                subtype_cf.setdefault(sub_key, []).extend(isin_cf)
                subtype_re.setdefault(sub_key, []).extend(isin_re)
                sp = subtype_pt.setdefault(sub_key, {})
                for d, vals in isin_pt.items():
                    pt = sp.setdefault(d, {"val": 0.0, "shadow_val": 0.0})
                    pt["val"] += vals["val"]
                    pt["shadow_val"] += vals["shadow_val"]

        return {
            "has_data": has_data,
            "global_cf": global_cashflows,
            "global_pt": portfolio_terminals,
            "global_re": realized_events,
            "class_cf": class_cf,
            "class_pt": class_pt,
            "class_re": class_re,
            "subtype_cf": subtype_cf,
            "subtype_pt": subtype_pt,
            "subtype_re": subtype_re,
        }
