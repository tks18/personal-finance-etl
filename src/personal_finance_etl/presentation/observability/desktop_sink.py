"""CustomTkinter desktop GUI event dispatcher for real-time user narratives.

Owns
----
- DesktopNarrativeSink: ObservabilitySink adapter routing canonical events to Desktop GUI.
- Mapping presentation kinds to syntax color tags and progress updates.
- Formatting human-facing narrative text and actionable error notifications.
- Filtering internal diagnostic chatter from graphical display.

Does not own
-------------
- Terminal Rich console formatting (owned by cli_narrative.py).
- Raw JSONL event serialization or file I/O (owned by infrastructure.observability).
- Concrete Tkinter widget hierarchies (owned by presentation.desktop.base_tab).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from personal_finance_etl.contracts.observability import (
    ObservabilityEvent,
    ObservabilitySink,
    PresentationKind,
)

__all__ = ["DesktopNarrativeSink", "format_event_narrative", "format_failure_summary"]

_KIND_TAG_MAP: Final[dict[PresentationKind, str]] = {
    PresentationKind.STEP: "step",
    PresentationKind.PROGRESS: "info",
    PresentationKind.SUCCESS: "success",
    PresentationKind.SKIP: "skip",
    PresentationKind.WARNING: "warning",
    PresentationKind.FAILURE: "error",
    PresentationKind.RECOVERY: "recovery",
}

_KIND_PREFIX_MAP: Final[dict[PresentationKind, str]] = {
    PresentationKind.STEP: ">>",
    PresentationKind.PROGRESS: "•",
    PresentationKind.SUCCESS: "✓",
    PresentationKind.SKIP: "↷",
    PresentationKind.WARNING: "!",
    PresentationKind.FAILURE: "✗ FAILURE:",
    PresentationKind.RECOVERY: "♻ RECOVERY:",
}


def format_event_narrative(event: ObservabilityEvent) -> str:
    """Format canonical event into human-readable desktop log text.

    Parameters
    ----------
    event : ObservabilityEvent
        Event containing message and contextual metadata.

    Returns
    -------
    str
        Formatted narrative line.
    """
    prefix = _KIND_PREFIX_MAP.get(event.presentation_kind, "•")
    parts: list[str] = [f"{prefix} {event.message}"]

    if event.context.entity_type and event.context.entity_id:
        parts.append(f"[{event.context.entity_type}: {event.context.entity_id}]")
    elif event.context.entity_id:
        parts.append(f"[{event.context.entity_id}]")

    if event.context.rows is not None:
        parts.append(f"({event.context.rows:,} items)")

    if event.context.cache_hit is True:
        parts.append("(cached)")

    if event.context.duration_ms is not None:
        if event.context.duration_ms >= 1000.0:
            parts.append(f"({event.context.duration_ms / 1000.0:.2f}s)")
        else:
            parts.append(f"({event.context.duration_ms:.1f}ms)")

    return " ".join(parts)


def format_failure_summary(event: ObservabilityEvent) -> str:
    """Format an actionable failure summary without raw tracebacks.

    Parameters
    ----------
    event : ObservabilityEvent
        Event representing an operational or critical failure.

    Returns
    -------
    str
        Multi-line actionable error diagnostic summary.
    """
    if event.error is None:
        return f"{event.message}\n\nRun ID: {event.context.run_id}"

    lines: list[str] = [
        f"Domain: {event.error.failure_domain.value}",
        f"Error: {event.error.exception_type} - {event.error.exception_message}",
        "",
        f"Run ID: {event.context.run_id}",
        "Inspect forensic log for complete diagnostic details.",
    ]
    if event.error.retryable:
        lines.append("Status: Transient failure eligible for automatic retry.")
    return "\n".join(lines)


class DesktopNarrativeSink(ObservabilitySink):
    """Observability sink projecting events to Desktop GUI controls and callbacks."""

    def __init__(
        self,
        status_consumer: Callable[[ObservabilityEvent], None] | None = None,
        log_callback: Callable[[str, str], None] | None = None,
        progress_callback: Callable[[float], None] | None = None,
        error_callback: Callable[[str, str], None] | None = None,
    ) -> None:
        self._status_consumer = status_consumer
        self._log_callback = log_callback
        self._progress_callback = progress_callback
        self._error_callback = error_callback
        self._emitted_count: int = 0

    @property
    def emitted_count(self) -> int:
        """Return total count of visible events processed by this sink."""
        return self._emitted_count

    def emit(self, event: ObservabilityEvent) -> None:
        """Process and dispatch a canonical ObservabilityEvent to the desktop interface.

        Parameters
        ----------
        event : ObservabilityEvent
            Canonical structured event.
        """
        # Drop internal diagnostic chatter from human-facing presentation
        if event.presentation_kind == PresentationKind.INTERNAL:
            return

        self._emitted_count += 1

        # Direct delegation to consumer if present (e.g., BaseEngineTab.handle_status)
        if self._status_consumer is not None:
            self._status_consumer(event)
            return

        # Discrete callback delegation mode
        if self._progress_callback is not None and event.progress is not None:
            self._progress_callback(float(event.progress))

        if self._log_callback is not None:
            tag = _KIND_TAG_MAP.get(event.presentation_kind, "info")
            line = format_event_narrative(event)
            self._log_callback(line, tag)

        if event.presentation_kind == PresentationKind.FAILURE and self._error_callback is not None:
            summary = format_failure_summary(event)
            self._error_callback("Execution Failure", summary)

    def flush(self) -> None:
        """Flush buffered status updates."""
        # No buffering required for GUI callbacks
