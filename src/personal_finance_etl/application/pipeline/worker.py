"""Multiprocessing worker coordination and status queue stream capture.

Owns
----
- QueueStream: Intercepts stdout/stderr in child processes and routes lines to status_queue.
- process_wrapper: Child process entry point for multiprocessing pipeline execution.
- WorkerPoolCoordinator: Spawns the multiprocessing ETL worker and monitors the status queue in a background thread.

Does not own
-------------
- Pipeline orchestration or stage sequencing (owned by application.pipeline.orchestrator).
- Transaction commit or rollback logic (owned by application.pipeline.lifecycle).
- Direct UI widget manipulation (owned by presentation).
"""

from __future__ import annotations

import multiprocessing
import queue
import sys
import threading
import time
import traceback
from collections.abc import Callable
from typing import cast

import polars as pl

from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.logging import ILogger, LogLevel

__all__ = ["QueueStream", "WorkerPoolCoordinator", "infer_log_level", "process_wrapper"]


def infer_log_level(msg: str, is_error: bool = False) -> LogLevel:
    """Infer LogLevel from message contents or stream error flag."""
    if not msg:
        return LogLevel.WARNING if is_error else LogLevel.INFO
    lw = msg.lower()
    if "error" in lw or msg.startswith("Error"):
        return LogLevel.ERROR
    if any(token in lw for token in ("✅", "complete", "success", "✓", "exported")):
        return LogLevel.SUCCESS
    if "warning" in lw or is_error:
        return LogLevel.WARNING
    if any(token in lw for token in ("fetching", "loading", "post-processing")) or msg.startswith(
        "["
    ):
        return LogLevel.STEP
    return LogLevel.INFO


class QueueStream:
    """Stream wrapper redirecting stdout and stderr lines to the multiprocessing status queue."""

    def __init__(self, target_queue: ILogger, is_error: bool = False) -> None:
        self.queue = target_queue
        self.buffer = ""
        self.is_error = is_error

    def write(self, msg: str) -> None:
        """Buffer and parse streaming text output into structured status messages."""
        self.buffer += msg
        if "\n" in self.buffer:
            lines = self.buffer.split("\n")
            for line in lines[:-1]:
                if line.strip():
                    level = infer_log_level(line.strip(), is_error=self.is_error)
                    self.queue.put(
                        EngineStatusMessage(
                            msg=line.strip(),
                            data=None,
                            progress=None,
                            level=level,
                        )
                    )
            self.buffer = lines[-1]

    def flush(self) -> None:
        """Flush remaining buffered text as a status message."""
        if self.buffer.strip():
            level = infer_log_level(self.buffer.strip(), is_error=self.is_error)
            self.queue.put(
                EngineStatusMessage(
                    msg=self.buffer.strip(),
                    data=None,
                    progress=None,
                    level=level,
                )
            )
            self.buffer = ""


def process_wrapper(
    status_queue: ILogger | None = None,
    config_path: str = "config.toml",
    rules_path: str = "",
) -> None:
    """Multiprocessing entry point for isolated pipeline execution.

    Parameters
    ----------
    status_queue : ILogger | None
        Inter-process status communication queue.
    config_path : str
        Path to TOML configuration settings.
    rules_path : str
        Path to TOML financial rules policy.
    """
    if status_queue is None:
        status_queue = cast(ILogger, multiprocessing.Queue())

    sys.stdout = QueueStream(status_queue, is_error=False)
    sys.stderr = QueueStream(status_queue, is_error=True)

    try:
        cfg = Settings.from_toml(config_path) if config_path else Settings()
        rules = FinancialRules.from_toml(rules_path) if rules_path else None

        orchestrator = ETLOrchestrator(cfg, status_queue, rules)
        orchestrator.run()

    except Exception as e:
        status_queue.put(
            EngineStatusMessage(
                msg=f"Critical Pipeline Failure: {e}\n{traceback.format_exc()}",
                data=None,
                progress=0.0,
                level=LogLevel.ERROR,
            )
        )
        time.sleep(0.5)
        raise e


class WorkerPoolCoordinator:
    """Supervises isolated worker execution and streams telemetry back to caller callbacks."""

    @staticmethod
    def spawn_process(
        status_queue: multiprocessing.Queue[EngineStatusMessage],
        config_path: str,
        rules_path: str,
    ) -> multiprocessing.Process:
        """Spawn the multiprocessing pipeline child process."""
        process = multiprocessing.Process(
            target=process_wrapper,
            args=(status_queue, config_path, rules_path),
            daemon=True,
        )
        process.start()
        return process

    @staticmethod
    def monitor_queue(
        process: multiprocessing.Process,
        status_queue: multiprocessing.Queue[EngineStatusMessage],
        on_status: Callable[[EngineStatusMessage], None],
    ) -> threading.Thread:
        """Start a daemon thread monitoring status_queue until the child process terminates."""

        def _monitor() -> None:
            while process.is_alive() or not status_queue.empty():
                try:
                    item = status_queue.get(timeout=0.1)

                    if isinstance(item, tuple):
                        t_item = cast("tuple[object, ...]", item)
                        t_msg = str(t_item[0]) if len(t_item) > 0 and t_item[0] else ""
                        t_data = (
                            t_item[1]
                            if len(t_item) > 1 and isinstance(t_item[1], pl.DataFrame)
                            else None
                        )
                        t_prog = (
                            float(t_item[2])
                            if len(t_item) > 2 and isinstance(t_item[2], (int, float))
                            else None
                        )
                        status = EngineStatusMessage(
                            msg=t_msg,
                            data=t_data,
                            progress=t_prog,
                            level=infer_log_level(t_msg),
                        )
                    else:
                        status = item

                    on_status(status)
                except queue.Empty:
                    continue
                except Exception:
                    break

            if process.exitcode is not None:
                if process.exitcode != 0:
                    on_status(
                        EngineStatusMessage(
                            msg="Process exited abnormally.",
                            data=None,
                            progress=0.0,
                            level=LogLevel.ERROR,
                        )
                    )
                else:
                    on_status(
                        EngineStatusMessage(
                            msg="Process completed cleanly.",
                            data=None,
                            progress=1.0,
                            level=LogLevel.SUCCESS,
                        )
                    )

        thread = threading.Thread(target=_monitor, daemon=True)
        thread.start()
        return thread
