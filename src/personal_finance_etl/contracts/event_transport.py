"""Typed queue contracts for transporting canonical observability events across boundaries.

Owns
----
- EventQueue protocol defining the structural contract for inter-process and in-memory event queues.
- NullEventQueue providing a typed no-op null object for headless or non-subscribed execution paths.
- Typed event-transport boundary abstraction between producers and asynchronous consumers.

Does not own
-------------
- Event dispatch, filtering, or fan-out emission (owned by infrastructure.observability.emitter).
- Sink persistence, JSONL formatting, or disk writing (owned by infrastructure.observability.forensic_sink).
- Presentation rendering, UI log formatting, or desktop widgets (owned by presentation).
"""

from __future__ import annotations

from typing import Protocol

from personal_finance_etl.contracts.observability import ObservabilityEvent

__all__ = ["EventQueue", "NullEventQueue"]


class EventQueue(Protocol):
    """Structural protocol for a canonical event transport queue."""

    def put(
        self,
        event: ObservabilityEvent | None,
        /,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        """Enqueue a canonical observability event."""
        ...


class NullEventQueue:
    """No-op event transport used when no external consumer is attached."""

    def put(
        self,
        event: ObservabilityEvent | None,
        /,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        """Discard an event intentionally."""
        del event, block, timeout
