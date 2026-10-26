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

from personal_finance_etl.application.observability import get_global_emitter
from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.logging import ILogger, LogLevel
from personal_finance_etl.contracts.observability import ObservabilityEvent
from personal_finance_etl.infrastructure.observability import (
    EventQueue,
    ObservabilityQueueSink,
)

__all__ = ["QueueStream", "WorkerPoolCoordinator", "infer_log_level", "process_wrapper"]


def infer_log_level(msg: str, is_error: bool = False) -> LogLevel:
    """Map execution error status directly to LogLevel severity."""
    del msg  # String parsing replaced by explicit boolean flag
    return LogLevel.ERROR if is_error else LogLevel.INFO


class QueueStream:
    """Stream wrapper redirecting stdout and stderr lines without string-based severity inference."""

    def __init__(self, target_queue: ILogger, is_error: bool = False) -> None:
        self.queue = target_queue
        self.buffer = ""
        self.is_error = is_error

    def write(self, msg: str) -> None:
        """Buffer and forward raw streaming text output without semantic guessing."""
        self.buffer += msg
        if "\n" in self.buffer:
            lines = self.buffer.split("\n")
            level = LogLevel.ERROR if self.is_error else LogLevel.INFO
            for line in lines[:-1]:
                stripped = line.strip()
                if stripped:
                    self.queue.put(
                        EngineStatusMessage(
                            msg=stripped,
                            progress=None,
                            level=level,
                        )
                    )
            self.buffer = lines[-1]

    def flush(self) -> None:
        """Flush remaining buffered text as raw output without semantic inference."""
        stripped = self.buffer.strip()
        if stripped:
            level = LogLevel.ERROR if self.is_error else LogLevel.INFO
            self.queue.put(
                EngineStatusMessage(
                    msg=stripped,
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

    emitter = get_global_emitter()
    queue_sink = ObservabilityQueueSink(cast(EventQueue, status_queue))
    emitter.register_sink(queue_sink)

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
                progress=0.0,
                level=LogLevel.ERROR,
            )
        )
        time.sleep(0.5)
        raise e
    finally:
        emitter.unregister_sink(queue_sink)


class WorkerPoolCoordinator:
    """Supervises isolated worker execution and streams telemetry back to caller callbacks."""

    @staticmethod
    def spawn_process(
        status_queue: multiprocessing.Queue[EngineStatusMessage | ObservabilityEvent],
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
    def _parse_queue_item(item: object) -> EngineStatusMessage | ObservabilityEvent:
        """Parse raw tuple or status queue payload into structured status or canonical event."""
        if isinstance(item, ObservabilityEvent):
            return item
        if not isinstance(item, tuple):
            return cast(EngineStatusMessage, item)
        t_item = cast("tuple[object, ...]", item)
        t_msg = str(t_item[0]) if len(t_item) > 0 and t_item[0] else ""
        t_prog = (
            float(t_item[2]) if len(t_item) > 2 and isinstance(t_item[2], (int, float)) else None
        )
        return EngineStatusMessage(
            msg=t_msg,
            progress=t_prog,
            level=LogLevel.INFO,
        )

    @staticmethod
    def _emit_exit_status(
        process: multiprocessing.Process,
        on_status: Callable[[EngineStatusMessage | ObservabilityEvent], None],
    ) -> None:
        """Emit clean completion or abnormal exit status based on worker exit code."""
        if process.exitcode is None:
            return
        if process.exitcode != 0:
            on_status(
                EngineStatusMessage(
                    msg="Process exited abnormally.",
                    progress=0.0,
                    level=LogLevel.ERROR,
                )
            )
        else:
            on_status(
                EngineStatusMessage(
                    msg="Process completed cleanly.",
                    progress=1.0,
                    level=LogLevel.SUCCESS,
                )
            )

    @staticmethod
    def monitor_queue(
        process: multiprocessing.Process,
        status_queue: multiprocessing.Queue[EngineStatusMessage | ObservabilityEvent],
        on_status: Callable[[EngineStatusMessage | ObservabilityEvent], None],
    ) -> threading.Thread:
        """Start a daemon thread monitoring status_queue until the child process terminates."""

        def _monitor() -> None:
            while process.is_alive() or not status_queue.empty():
                try:
                    item = status_queue.get(timeout=0.1)
                    on_status(WorkerPoolCoordinator._parse_queue_item(item))
                except queue.Empty:
                    continue
                except Exception:
                    break

            WorkerPoolCoordinator._emit_exit_status(process, on_status)

        thread = threading.Thread(target=_monitor, daemon=True)
        thread.start()
        return thread
