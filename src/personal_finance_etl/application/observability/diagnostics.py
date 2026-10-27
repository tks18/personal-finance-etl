"""Canonical diagnostic facade backed exclusively by observability events.

This module provides concise severity-oriented helpers for low-level diagnostic
sites.  It deliberately mirrors the small formatting surface historically used
by Python logging while routing every message through ``ObservabilityEmitter``.
It is not a second logging system: the produced value is always a typed
``ObservabilityEvent`` and therefore reaches the same registered sinks as every
other application event.
"""

from __future__ import annotations

import traceback
from collections.abc import Mapping
from typing import Any

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.lifecycle import FailureDomain
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    ErrorDetails,
    EventCode,
    PresentationKind,
)

from .emitter import ObservabilityEmitter, get_global_emitter

__all__ = ["ObservabilityDiagnostics", "get_observability_diagnostics"]


class ObservabilityDiagnostics:
    """Emit internal diagnostics through the canonical observability pipeline."""

    def __init__(
        self,
        component: str,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self.component = component
        self._emitter = emitter

    @property
    def emitter(self) -> ObservabilityEmitter:
        """Resolve the process-global emitter at call time.

        Late resolution is important during bootstrap and in tests because the
        global emitter can be replaced after modules have been imported.
        """
        return self._emitter or get_global_emitter()

    @staticmethod
    def _format(message: object, args: tuple[object, ...]) -> str:
        text = str(message)
        if not args:
            return text
        try:
            return text % args
        except (TypeError, ValueError):
            return " ".join((text, *(str(arg) for arg in args)))

    def _emit(
        self,
        severity: DiagnosticSeverity,
        message: object,
        *args: object,
        extra: Mapping[str, Any] | None = None,
        capture_exception: bool = False,
    ) -> None:
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

    def debug(self, message: object, *args: object, **kwargs: Any) -> None:
        self._emit(DiagnosticSeverity.DEBUG, message, *args, extra=kwargs.get("extra"))

    def info(self, message: object, *args: object, **kwargs: Any) -> None:
        self._emit(DiagnosticSeverity.INFO, message, *args, extra=kwargs.get("extra"))

    def warning(self, message: object, *args: object, **kwargs: Any) -> None:
        self._emit(DiagnosticSeverity.WARNING, message, *args, extra=kwargs.get("extra"))

    def error(self, message: object, *args: object, **kwargs: Any) -> None:
        self._emit(DiagnosticSeverity.ERROR, message, *args, extra=kwargs.get("extra"))

    def critical(self, message: object, *args: object, **kwargs: Any) -> None:
        self._emit(DiagnosticSeverity.CRITICAL, message, *args, extra=kwargs.get("extra"))

    def exception(self, message: object, *args: object, **kwargs: Any) -> None:
        self._emit(
            DiagnosticSeverity.ERROR,
            message,
            *args,
            extra=kwargs.get("extra"),
            capture_exception=True,
        )

    def emit(
        self,
        severity: DiagnosticSeverity,
        message: object,
        *args: object,
        **kwargs: Any,
    ) -> None:
        """Emit a diagnostic with an explicitly selected canonical severity."""
        self._emit(severity, message, *args, extra=kwargs.get("extra"))


def get_observability_diagnostics(
    component: str,
    emitter: ObservabilityEmitter | None = None,
) -> ObservabilityDiagnostics:
    """Create a module-scoped canonical diagnostic emitter."""
    return ObservabilityDiagnostics(component=component, emitter=emitter)
