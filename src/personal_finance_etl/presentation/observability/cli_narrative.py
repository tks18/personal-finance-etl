"""Rich-based console renderer for beautiful human-facing execution narratives.

Owns
----
- RichNarrativeSink: Console event projection rendering concise narrative lines.
- Formatting presentation tokens, timing badges, entity markers, and error summaries.
- Filtering internal implementation noise and forensic-only trace telemetry.

Does not own
-------------
- Raw JSONL event serialization or file I/O (owned by infrastructure.observability).
- Control plane SQLite persistence (owned by infrastructure.control_plane).
- Core pipeline orchestration (owned by application.pipeline).
"""

from __future__ import annotations

from typing import Final

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import Progress, TaskID

from personal_finance_etl.contracts.observability import (
    ObservabilityEvent,
    ObservabilitySink,
    PresentationKind,
)

__all__ = ["RichNarrativeSink"]

_KIND_PREFIX_MAP: Final[dict[PresentationKind, str]] = {
    PresentationKind.STEP: "[bold cyan]>>[/bold cyan]",
    PresentationKind.PROGRESS: "[bold blue]•[/bold blue]",
    PresentationKind.SUCCESS: "[bold green]✓[/bold green]",
    PresentationKind.SKIP: "[bold yellow]↷[/bold yellow]",
    PresentationKind.WARNING: "[bold yellow]![/bold yellow]",
    PresentationKind.FAILURE: "[bold red]✗ FAILURE:[/bold red]",
    PresentationKind.RECOVERY: "[bold magenta]♻ RECOVERY:[/bold magenta]",
}


class RichNarrativeSink(ObservabilitySink):
    """Rich console renderer projecting canonical events into a clean narrative.

    Normal successful runs render roughly 20-40 scannable narrative lines without
    implementation chatter, tracebacks, or raw database internals.
    """

    def __init__(
        self,
        console: Console | None = None,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
        show_timestamps: bool = True,
        time_format: str = "%H:%M:%S",
    ) -> None:
        self._console: Console = console if console is not None else Console()
        self._progress: Progress | None = progress
        self._task_id: TaskID | None = task_id
        self._show_timestamps: bool = show_timestamps
        self._time_format: str = time_format
        self._rendered_count: int = 0

    @property
    def rendered_count(self) -> int:
        """Return the number of user-facing events rendered during this session."""
        return self._rendered_count

    def emit(self, event: ObservabilityEvent) -> None:
        """Render a single canonical ObservabilityEvent to the console.

        Parameters
        ----------
        event : ObservabilityEvent
            The canonical event to project.
        """
        # Enterprise rule: internal implementation chatter is dropped from UI log
        if event.presentation_kind == PresentationKind.INTERNAL:
            return

        # Update progress bar if associated with a Rich progress task
        if event.progress is not None and self._progress is not None and self._task_id is not None:
            self._progress.update(self._task_id, completed=event.progress * 100.0)

        # Pure progress bar updates without narrative prose should not print empty log lines
        if not event.message.strip():
            return

        # Build formatted narrative line
        prefix = _KIND_PREFIX_MAP.get(event.presentation_kind, "[dim]•[/dim]")
        safe_msg = escape(event.message)

        metadata_parts: list[str] = []

        # Entity identification badge
        if event.context.entity_type and event.context.entity_id:
            badge = escape(f"[{event.context.entity_type}:{event.context.entity_id}]")
            metadata_parts.append(f"[cyan]{badge}[/cyan]")
        elif event.context.entity_id:
            badge = escape(f"[{event.context.entity_id}]")
            metadata_parts.append(f"[cyan]{badge}[/cyan]")

        # Row / item count
        if event.context.rows is not None:
            metadata_parts.append(f"[dim]({event.context.rows:,} items)[/dim]")

        # Cache state
        if event.context.cache_hit is True:
            metadata_parts.append("[dim](cache hit)[/dim]")

        # Elapsed execution duration
        if event.context.duration_ms is not None:
            if event.context.duration_ms >= 1000.0:
                duration_str = f"{event.context.duration_ms / 1000.0:.2f}s"
            else:
                duration_str = f"{event.context.duration_ms:.1f}ms"
            metadata_parts.append(f"[dim]({duration_str})[/dim]")

        meta_suffix = f" {' '.join(metadata_parts)}" if metadata_parts else ""
        content = f"{prefix} {safe_msg}{meta_suffix}"

        if self._show_timestamps:
            ts_str = event.timestamp.astimezone().strftime(self._time_format)
            line = f"[dim][{ts_str}][/dim] {content}"
        else:
            line = content

        self._print_line(line)
        self._rendered_count += 1

        # On failure: display actionable summary panel without dumping stack traces
        if event.presentation_kind == PresentationKind.FAILURE:
            self._render_failure_panel(event)

    def flush(self) -> None:
        """Flush output to the underlying console."""
        # Rich Console auto-flushes on print

    def _print_line(self, line: str) -> None:
        """Print a formatted line respecting active progress bars."""
        if self._progress is not None:
            self._progress.console.print(line)
        else:
            self._console.print(line)

    def _render_failure_panel(self, event: ObservabilityEvent) -> None:
        """Render an actionable error diagnostics panel.

        Parameters
        ----------
        event : ObservabilityEvent
            Failed event containing error telemetry.
        """
        details: list[str] = []
        if event.error is not None:
            details.append(f"[bold]Domain:[/bold] {event.error.failure_domain.value}")
            details.append(
                f"[bold]Exception:[/bold] {escape(event.error.exception_type)}: "
                f"{escape(event.error.exception_message)}"
            )
            if event.error.retryable:
                details.append(
                    "[bold yellow]Status: Transient failure eligible for automatic retry.[/bold yellow]"
                )
        details.append(
            f"[bold]Diagnostics:[/bold] Inspect forensic log for run "
            f"[bold cyan]{event.context.run_id}[/bold cyan] in logs directory."
        )

        panel = Panel(
            "\n".join(details),
            title="[bold red]Actionable Diagnostics[/bold red]",
            border_style="red",
            expand=False,
        )
        if self._progress is not None:
            self._progress.console.print(panel)
        else:
            self._console.print(panel)
