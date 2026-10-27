"""Typed queue contracts for transporting canonical observability events."""

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
