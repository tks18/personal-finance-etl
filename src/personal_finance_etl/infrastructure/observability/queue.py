"""Asynchronous multi-process observability queue sinks and background listeners.

Owns
----
- EventQueue: Protocol unifying thread and multiprocessing event queues.
- ObservabilityQueueSink: Non-blocking sink enqueuing events to a background buffer.
- AsyncObservabilityListener: Background daemon thread pulling queued events and writing to sinks.

Does not own
-------------
- Concrete JSONL formatting or disk appending (owned by infrastructure.observability.forensic_sink).
- Event creation and context management (owned by application.observability).
- Terminal rendering or GUI widget dispatch (owned by presentation).
"""

from __future__ import annotations

import queue
import threading
from types import TracebackType
from typing import Protocol

from personal_finance_etl.contracts.observability import (
    ObservabilityEvent,
    ObservabilitySink,
)

__all__ = [
    "AsyncObservabilityListener",
    "EventQueue",
    "ObservabilityQueueSink",
]


class EventQueue(Protocol):
    """Protocol for cross-thread or cross-process queues transporting events."""

    def put(
        self,
        item: ObservabilityEvent | None,
        /,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        """Put an item onto the queue."""
        ...

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
                # Logging queue must not compromise execution stability
                pass

    def flush(self) -> None:
        """Flush operation is handled asynchronously by the listener thread."""


class AsyncObservabilityListener:
    """Dedicated background listener thread draining queue events and routing to sinks.

    Owns synchronous disk I/O and ensures single-writer file integrity.
    """

    def __init__(
        self,
        inbound_queue: EventQueue,
        sinks: list[ObservabilitySink],
    ) -> None:
        self.inbound_queue = inbound_queue
        self.sinks = list(sinks)
        self._thread: threading.Thread | None = None
        self._stop_requested = threading.Event()

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

    def _dispatch(self, event: ObservabilityEvent) -> None:
        """Safely fan-out one event to all listener-owned sinks."""
        for sink in self.sinks:
            try:
                sink.emit(event)
            except Exception:
                pass

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
        for sink in self.sinks:
            try:
                sink.flush()
            except Exception:
                pass

    def stop(self, timeout: float = 3.0) -> None:
        """Stop the background listener thread and flush all sinks.

        Parameters
        ----------
        timeout : float, default=3.0
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
