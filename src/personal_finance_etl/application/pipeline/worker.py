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
from collections.abc import Callable
from typing import cast

from personal_finance_etl.application.observability import ObservabilityEmitter, get_global_emitter
from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    EventOutcome,
    ObservabilityEvent,
    PresentationKind,
)
from personal_finance_etl.infrastructure.observability import (
    ObservabilityQueueSink,
)

__all__ = ["QueueStream", "WorkerPoolCoordinator", "process_wrapper"]


class QueueStream:
    """Stream wrapper redirecting stdout and stderr lines without string-based severity inference."""

    def __init__(
        self,
        target: EventQueue | ObservabilityEmitter,
        is_error: bool = False,
    ) -> None:
        self.target = target
        self.buffer = ""
        self.is_error = is_error

    def _emit(self, message: str) -> None:
        event_code = EventCode.RAW_STDERR if self.is_error else EventCode.RAW_STDOUT
        severity = DiagnosticSeverity.ERROR if self.is_error else DiagnosticSeverity.INFO
        outcome = EventOutcome.FAILED if self.is_error else EventOutcome.COMPLETED
        if isinstance(self.target, ObservabilityEmitter):
            self.target.emit_event(
                event_code=event_code,
                message=message,
                severity=severity,
                outcome=outcome,
                presentation_kind=PresentationKind.INTERNAL,
            )
            return
        self.target.put(
            ObservabilityEvent.create(
                event_code=event_code,
                message=message,
                severity=severity,
                outcome=outcome,
                presentation_kind=PresentationKind.INTERNAL,
            )
        )

    def write(self, msg: str) -> None:
        """Buffer and forward raw streaming text output without semantic guessing."""
        self.buffer += msg
        if "\n" in self.buffer:
            lines = self.buffer.split("\n")
            for line in lines[:-1]:
                stripped = line.strip()
                if stripped:
                    self._emit(stripped)
            self.buffer = lines[-1]

    def flush(self) -> None:
        """Flush remaining buffered text as raw output without semantic inference."""
        stripped = self.buffer.strip()
        if stripped:
            self._emit(stripped)
            self.buffer = ""


def process_wrapper(
    status_queue: EventQueue | None = None,
    config_path: str = "config.toml",
    rules_path: str = "",
) -> None:
    """Multiprocessing entry point for isolated pipeline execution.

    Parameters
    ----------
    status_queue : EventQueue | None
        Inter-process status communication queue.
    config_path : str
        Path to TOML configuration settings.
    rules_path : str
        Path to TOML financial rules policy.
    """
    if status_queue is None:
        status_queue = cast(EventQueue, multiprocessing.Queue())

    emitter = get_global_emitter()
    queue_sink = ObservabilityQueueSink(cast(EventQueue, status_queue))
    emitter.register_sink(queue_sink)

    sys.stdout = QueueStream(emitter, is_error=False)
    sys.stderr = QueueStream(emitter, is_error=True)

    try:
        cfg = Settings.from_toml(config_path) if config_path else Settings()
        rules = FinancialRules.from_toml(rules_path) if rules_path else None

        orchestrator = ETLOrchestrator(cfg, status_queue, rules)
        orchestrator.run()

    finally:
        emitter.unregister_sink(queue_sink)


class WorkerPoolCoordinator:
    """Supervises isolated worker execution and streams telemetry back to caller callbacks."""

    @staticmethod
    def spawn_process(
        status_queue: multiprocessing.Queue[ObservabilityEvent],
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
    def _parse_queue_item(item: object) -> ObservabilityEvent:
        """Parse status queue item into canonical ObservabilityEvent.

        Parameters
        ----------
        item : object
            Status queue item.

        Returns
        -------
        ObservabilityEvent
            Canonical observability event instance.
        """
        if isinstance(item, ObservabilityEvent):
            return item
        return ObservabilityEvent.create(
            event_code=EventCode.GENERIC_DIAGNOSTIC,
            message=str(item),
            severity=DiagnosticSeverity.INFO,
            outcome=EventOutcome.COMPLETED,
            presentation_kind=PresentationKind.PROGRESS,
        )

    @staticmethod
    def _emit_exit_status(
        process: multiprocessing.Process,
        on_status: Callable[[ObservabilityEvent], None],
        terminal_seen: bool = False,
    ) -> None:
        """Emit clean completion or abnormal exit status based on worker exit code."""
        if terminal_seen or process.exitcode is None:
            return
        if process.exitcode != 0:
            on_status(
                ObservabilityEvent.create(
                    event_code=EventCode.RUN_FAILED,
                    message="Process exited abnormally.",
                    severity=DiagnosticSeverity.ERROR,
                    outcome=EventOutcome.FAILED,
                    progress=0.0,
                    presentation_kind=PresentationKind.FAILURE,
                )
            )
        else:
            on_status(
                ObservabilityEvent.create(
                    event_code=EventCode.RUN_COMPLETED,
                    message="Process completed cleanly.",
                    severity=DiagnosticSeverity.INFO,
                    outcome=EventOutcome.COMPLETED,
                    progress=1.0,
                    presentation_kind=PresentationKind.PROGRESS,
                )
            )

    @staticmethod
    def monitor_queue(
        process: multiprocessing.Process,
        status_queue: multiprocessing.Queue[ObservabilityEvent],
        on_status: Callable[[ObservabilityEvent], None],
    ) -> threading.Thread:
        """Start a daemon thread monitoring status_queue until the child process terminates."""

        def _monitor() -> None:
            terminal_seen = False
            while process.is_alive() or not status_queue.empty():
                try:
                    item = status_queue.get(timeout=0.1)
                    event = WorkerPoolCoordinator._parse_queue_item(item)
                    if event.event_code in (
                        EventCode.RUN_COMPLETED,
                        EventCode.RUN_FAILED,
                        EventCode.RUN_ABORTED,
                    ):
                        terminal_seen = True
                    on_status(event)
                except queue.Empty:
                    continue
                except Exception:
                    break

            if not terminal_seen:
                WorkerPoolCoordinator._emit_exit_status(
                    process,
                    on_status,
                    terminal_seen=terminal_seen,
                )

        thread = threading.Thread(target=_monitor, daemon=True)
        thread.start()
        return thread
