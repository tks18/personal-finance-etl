"""Observability presentation projections for CLI terminal and Desktop GUI.

Owns
----
- RichNarrativeSink: Rich console renderer emitting beautiful human narratives.
- DesktopNarrativeSink: CustomTkinter GUI adapter and thread-safe event dispatcher.
- Formatters for human-facing event lines and actionable error dialogs.

Does not own
-------------
- Forensic JSONL file persistence (owned by infrastructure.observability).
- Central emitter and span management (owned by infrastructure.observability).
- Canonical contracts and data types (owned by contracts.observability).
"""

from __future__ import annotations

from personal_finance_etl.presentation.observability.cli_narrative import (
    RichNarrativeSink,
)
from personal_finance_etl.presentation.observability.desktop_sink import (
    DesktopNarrativeSink,
    format_event_narrative,
    format_failure_summary,
)

__all__ = [
    "DesktopNarrativeSink",
    "RichNarrativeSink",
    "format_event_narrative",
    "format_failure_summary",
]
