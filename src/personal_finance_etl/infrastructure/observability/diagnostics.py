"""Canonical diagnostic facade backed exclusively by observability events.

Owns
----
- ObservabilityDiagnostics: Severity-oriented diagnostic facade mirroring familiar logging semantics.
- get_observability_diagnostics: Factory function for component-scoped diagnostic facades.
- Zero-drift translation of diagnostic messages into canonical ObservabilityEvent records.

Does not own
-------------
- Canonical event schema and error models (owned by contracts.observability).
- Concrete sink file I/O or terminal rendering (owned by infrastructure.observability and presentation).
- Domain calculation mathematics (owned by domain).
"""

from __future__ import annotations

import traceback
from collections.abc import Mapping
from typing import cast

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.lifecycle import FailureDomain
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    EventCode,
    EventEmitter,
    PresentationKind,
)
from personal_finance_etl.infrastructure.observability.emitter import (
    ObservabilityEmitter,
    get_global_emitter,
)

__all__ = ["ObservabilityDiagnostics", "get_observability_diagnostics"]


class ObservabilityDiagnostics:
    """Emit internal diagnostics through the canonical observability pipeline.

    Provides familiar severity-oriented helper methods (debug, info, warning, error,
    critical, exception) while ensuring every diagnostic call constructs and dispatches
    a canonical typed ObservabilityEvent to registered sinks.
    """

    def __init__(
        self,
        component: str,
        emitter: ObservabilityEmitter | EventEmitter | None = None,
    ) -> None:
        """Initialize the diagnostic facade for a specific component.

        Parameters
        ----------
        component : str
            The component or module name generating diagnostics.
        emitter : ObservabilityEmitter | EventEmitter | None, default=None
            The event emitter to dispatch through; defaults to the process-global emitter.
        """
        self.component = component
        self._emitter = emitter

    @property
    def emitter(self) -> ObservabilityEmitter:
        """Resolve the active ObservabilityEmitter at call time.

        Returns
        -------
        ObservabilityEmitter
            The configured emitter or process-global default emitter instance.
        """
        resolved = self._emitter or get_global_emitter()
        if isinstance(resolved, ObservabilityEmitter):
            return resolved
        return get_global_emitter()

    @staticmethod
    def _format(message: object, args: tuple[object, ...]) -> str:
        """Format message with positional arguments safely.

        Parameters
        ----------
        message : object
            Format string or raw message object.
        args : tuple[object, ...]
            Format parameters.

        Returns
        -------
        str
            Formatted message string.
        """
        text = str(message)
        if not args:
            return text
        try:
            return text % args
        except (TypeError, ValueError):
            return " ".join((text, *(str(arg) for arg in args)))

    @staticmethod
    def _extract_extra(kwargs: Mapping[str, object]) -> Mapping[str, object] | None:
        """Extract and validate the optional 'extra' metadata mapping.

        Parameters
        ----------
        kwargs : Mapping[str, object]
            Keyword arguments passed to logging method.

        Returns
        -------
        Mapping[str, object] | None
            The extra mapping if present and valid, else None.
        """
        extra = kwargs.get("extra")
        if isinstance(extra, Mapping):
            return cast(Mapping[str, object], extra)
        return None

    def _emit(
        self,
        severity: DiagnosticSeverity,
        message: object,
        *args: object,
        extra: Mapping[str, object] | None = None,
        capture_exception: bool = False,
    ) -> None:
        """Construct and emit a canonical ObservabilityEvent for a diagnostic entry.

        Parameters
        ----------
        severity : DiagnosticSeverity
            Diagnostic severity level.
        message : object
            Message text or format template.
        *args : object
            Positional format arguments.
        extra : Mapping[str, object] | None, default=None
            Structured metadata dictionary (e.g. isin, stage).
        capture_exception : bool, default=False
            Whether to inspect and attach active exception traceback details.
        """
        metadata = extra or {}
        entity_id = metadata.get("isin")
        stage_value = metadata.get("stage")
        stage = stage_value if isinstance(stage_value, EngineStage) else None
        error = None
        if capture_exception:
            summary = traceback.format_exc()
            error = ErrorDetails(
                exception_type="DiagnosticException",
                exception_message=self._format(message, args),
                traceback_summary=summary if summary != "NoneType: None\n" else "",
                failure_domain=FailureDomain.UNKNOWN,
                retryable=False,
            )

        self.emitter.emit_event(
            event_code=EventCode.GENERIC_DIAGNOSTIC,
            message=self._format(message, args),
            severity=severity,
            presentation_kind=PresentationKind.INTERNAL,
            component=self.component,
            stage=stage,
            entity_type="ISIN" if entity_id is not None else None,
            entity_id=str(entity_id) if entity_id is not None else None,
            error=error,
        )

    def debug(self, message: object, *args: object, **kwargs: object) -> None:
        """Emit a DEBUG-level diagnostic event.

        Parameters
        ----------
        message : object
            Diagnostic message or format string.
        *args : object
            Positional format arguments for message.
        **kwargs : object
            Optional keyword arguments including 'extra' mapping.
        """
        self._emit(DiagnosticSeverity.DEBUG, message, *args, extra=self._extract_extra(kwargs))

    def info(self, message: object, *args: object, **kwargs: object) -> None:
        """Emit an INFO-level diagnostic event.

        Parameters
        ----------
        message : object
            Diagnostic message or format string.
        *args : object
            Positional format arguments for message.
        **kwargs : object
            Optional keyword arguments including 'extra' mapping.
        """
        self._emit(DiagnosticSeverity.INFO, message, *args, extra=self._extract_extra(kwargs))

    def warning(self, message: object, *args: object, **kwargs: object) -> None:
        """Emit a WARNING-level diagnostic event.

        Parameters
        ----------
        message : object
            Diagnostic message or format string.
        *args : object
            Positional format arguments for message.
        **kwargs : object
            Optional keyword arguments including 'extra' mapping.
        """
        self._emit(DiagnosticSeverity.WARNING, message, *args, extra=self._extract_extra(kwargs))

    def error(self, message: object, *args: object, **kwargs: object) -> None:
        """Emit an ERROR-level diagnostic event.

        Parameters
        ----------
        message : object
            Diagnostic message or format string.
        *args : object
            Positional format arguments for message.
        **kwargs : object
            Optional keyword arguments including 'extra' mapping.
        """
        self._emit(DiagnosticSeverity.ERROR, message, *args, extra=self._extract_extra(kwargs))

    def critical(self, message: object, *args: object, **kwargs: object) -> None:
        """Emit a CRITICAL-level diagnostic event.

        Parameters
        ----------
        message : object
            Diagnostic message or format string.
        *args : object
            Positional format arguments for message.
        **kwargs : object
            Optional keyword arguments including 'extra' mapping.
        """
        self._emit(DiagnosticSeverity.CRITICAL, message, *args, extra=self._extract_extra(kwargs))

    def exception(self, message: object, *args: object, **kwargs: object) -> None:
        """Emit an ERROR-level diagnostic event capturing the current active exception.

        Parameters
        ----------
        message : object
            Diagnostic message or format string.
        *args : object
            Positional format arguments for message.
        **kwargs : object
            Optional keyword arguments including 'extra' mapping.
        """
        self._emit(
            DiagnosticSeverity.ERROR,
            message,
            *args,
            extra=self._extract_extra(kwargs),
            capture_exception=True,
        )

    def emit(
        self,
        severity: DiagnosticSeverity,
        message: object,
        *args: object,
        **kwargs: object,
    ) -> None:
        """Emit a diagnostic event with an explicitly specified severity level.

        Parameters
        ----------
        severity : DiagnosticSeverity
            The explicit diagnostic severity.
        message : object
            Diagnostic message or format string.
        *args : object
            Positional format arguments for message.
        **kwargs : object
            Optional keyword arguments including 'extra' mapping.
        """
        self._emit(severity, message, *args, extra=self._extract_extra(kwargs))


def get_observability_diagnostics(
    component: str,
    emitter: ObservabilityEmitter | EventEmitter | None = None,
) -> ObservabilityDiagnostics:
    """Create a component-scoped canonical diagnostic facade.

    Parameters
    ----------
    component : str
        Name of the component or module producing diagnostics.
    emitter : ObservabilityEmitter | EventEmitter | None, default=None
        Custom emitter instance; if None, binds to global emitter.

    Returns
    -------
    ObservabilityDiagnostics
        The configured component-scoped diagnostic helper.
    """
    return ObservabilityDiagnostics(component=component, emitter=emitter)
