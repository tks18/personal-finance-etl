"""Asynchronous multi-process observability queue sinks and background listeners.

Owns
----
- BufferedEventQueue: Read/write queue used by the asynchronous listener.
- ObservabilityQueueSink: Non-blocking sink enqueuing events to a background buffer.
- AsyncObservabilityListener: Background daemon thread pulling queued events and writing to sinks.
- create_forensic_pipeline: Assembles asynchronous queue, listener, and JSONL forensic sink.

Does not own
-------------
- Concrete JSONL formatting or disk appending (owned by infrastructure.observability.forensic_sink).
- Event creation and context management (owned by infrastructure.observability).
- Terminal rendering or GUI widget dispatch (owned by presentation).
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Mapping
from pathlib import Path
from types import TracebackType
from typing import Protocol

from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventOutcome,
    ObservabilityEvent,
    ObservabilitySink,
)
from personal_finance_etl.infrastructure.observability.forensic_sink import (
    JsonlForensicSink,
)
from personal_finance_etl.infrastructure.observability.redaction import (
    RedactionPolicy,
)

__all__ = [
    "AsyncObservabilityListener",
    "BufferedEventQueue",
    "ObservabilityQueueSink",
    "create_forensic_pipeline",
]


class BufferedEventQueue(EventQueue, Protocol):
    """Readable event queue owned by an asynchronous consumer."""

    def get(
        self,
        block: bool = True,
        timeout: float | None = None,
    ) -> ObservabilityEvent | None:
        """Retrieve an item from the queue."""
        ...

    def get_nowait(self) -> ObservabilityEvent | None:
        """Retrieve an item without blocking."""
        ...

    def empty(self) -> bool:
        """Return True if the queue is empty."""
        ...


class ObservabilityQueueSink(ObservabilitySink):
    """Non-blocking sink that routes events to a background queue.

    Ensures application and worker execution paths remain non-blocking.
    """

    def __init__(self, target_queue: EventQueue) -> None:
        """Initialize queue sink forwarding events to an asynchronous buffer.

        Parameters
        ----------
        target_queue : EventQueue
            Target IPC or background queue receiving events.
        """
        self.queue = target_queue

    def emit(self, event: ObservabilityEvent) -> None:
        """Put an ObservabilityEvent onto the queue with non-blocking fallback.

        Parameters
        ----------
        event : ObservabilityEvent
            The canonical event to forward to the listener.
        """
        try:
            self.queue.put(event, block=False)
        except (queue.Full, OSError):
            try:
                self.queue.put(event, block=True, timeout=0.05)
            except Exception:
                # Observability transport must not compromise execution stability.
                pass

    def flush(self) -> None:
        """Flush operation is handled asynchronously by the listener thread."""


class AsyncObservabilityListener:
    """Dedicated background listener thread draining queue events and routing to sinks.

    Owns synchronous disk I/O and ensures single-writer file integrity.
    """

    def __init__(
        self,
        inbound_queue: BufferedEventQueue,
        sinks: list[ObservabilitySink],
    ) -> None:
        """Initialize asynchronous listener background worker thread.

        Parameters
        ----------
        inbound_queue : BufferedEventQueue
            Inbound queue providing serialized events.
        sinks : list[ObservabilitySink]
            Target sinks receiving dequeued events.
        """
        self.inbound_queue = inbound_queue
        self.sinks = list(sinks)
        self._thread: threading.Thread | None = None
        self._stop_requested = threading.Event()

    def is_alive(self) -> bool:
        """Return True if background consumer thread is actively running.

        Returns
        -------
        bool
            True if the thread is started and alive, False otherwise.
        """
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the background consumer thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_requested.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="ObservabilityListenerThread",
            daemon=True,
        )
        self._thread.start()

    def flush(self) -> None:
        """Flush all attached sinks synchronously.

        Silently suppresses individual sink failures to maintain listener stability.
        """
        for sink in self.sinks:
            try:
                sink.flush()
            except Exception:
                pass

    def _dispatch(self, event: ObservabilityEvent) -> None:
        """Safely fan-out one event to all listener-owned sinks.

        Parameters
        ----------
        event : ObservabilityEvent
            The canonical structured event to forward to attached sinks.
        """
        for sink in self.sinks:
            try:
                sink.emit(event)
            except Exception:
                pass

        if (
            event.severity in (DiagnosticSeverity.ERROR, DiagnosticSeverity.CRITICAL)
            or event.outcome == EventOutcome.FAILED
        ):
            self.flush()

    def _run_loop(self) -> None:
        """Execute main loop pulling events from queue until sentinel or stop signal."""
        while not self._stop_requested.is_set():
            try:
                item = self.inbound_queue.get(timeout=0.05)
            except (queue.Empty, TimeoutError, OSError):
                continue

            if item is None:
                # Sentinel received: terminate loop
                break

            self._dispatch(item)

        # Drain remaining backlog before shutting down
        while True:
            try:
                item = self.inbound_queue.get_nowait()
            except (queue.Empty, OSError):
                break

            if item is not None:
                self._dispatch(item)

        # Flush all sinks
        self.flush()

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the background listener thread, drain residual events, and flush sinks.

        Parameters
        ----------
        timeout : float, default=5.0
            Maximum duration in seconds to wait for thread join.
        """
        self._stop_requested.set()
        try:
            self.inbound_queue.put(None, block=False)
        except Exception:
            pass

        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

        # Drain any residual items directly in calling thread if queue still contains items
        while True:
            try:
                item = self.inbound_queue.get_nowait()
            except (queue.Empty, OSError):
                break

            if item is not None:
                self._dispatch(item)

        for sink in self.sinks:
            try:
                sink.flush()
                close_fn = getattr(sink, "close", None)
                if callable(close_fn):
                    close_fn()
            except Exception:
                pass

    def __enter__(self) -> AsyncObservabilityListener:
        """Enter context manager, starting the listener thread."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Exit context manager, stopping the listener thread and flushing sinks."""
        self.stop()


def create_forensic_pipeline(
    log_path: str | Path,
    buffer_size: int = 50,
    policies: Mapping[str, RedactionPolicy] | None = None,
) -> tuple[ObservabilityQueueSink, AsyncObservabilityListener, JsonlForensicSink]:
    """Create asynchronous queue, background listener, and JSONL forensic sink pipeline.

    Parameters
    ----------
    log_path : str | Path
        Filesystem path to output JSONL forensic trace.
    buffer_size : int, default=50
        Number of events to buffer before flushing file handle to physical disk.
    policies : Mapping[str, RedactionPolicy] | None, default=None
        Optional field-level redaction policies applied at forensic write boundary.

    Returns
    -------
    tuple[ObservabilityQueueSink, AsyncObservabilityListener, JsonlForensicSink]
        Tuple of queue sink for emitter registration, background listener, and forensic sink.
    """
    forensic_queue: queue.Queue[ObservabilityEvent | None] = queue.Queue()
    forensic_sink = JsonlForensicSink(log_path, buffer_size=buffer_size, policies=policies)
    listener = AsyncObservabilityListener(forensic_queue, sinks=[forensic_sink])
    queue_sink = ObservabilityQueueSink(forensic_queue)
    return queue_sink, listener, forensic_sink
