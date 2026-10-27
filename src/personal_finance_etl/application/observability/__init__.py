"""Centralized application observability, event emission, and span coordination.

Owns
----
- Central application event dispatch and sink registration (ObservabilityEmitter).
- Automated execution span timing and error enrichment (SpanContext).
- Ambient task-local and thread-local context management (ContextVar).

Does not own
-------------
- Canonical event and context schema definitions (owned by contracts.observability).
- Concrete forensic storage, JSONL file appending, or listener threads (owned by infrastructure.observability).
- UI narrative rendering or GUI widget event handling (owned by presentation).
"""

from __future__ import annotations

from personal_finance_etl.application.observability.context import (
    get_current_context,
    reset_current_context,
    set_current_context,
)
from personal_finance_etl.application.observability.diagnostics import (
    ObservabilityDiagnostics,
    get_observability_diagnostics,
)
from personal_finance_etl.application.observability.emitter import (
    ObservabilityEmitter,
    SpanContext,
    get_global_emitter,
    set_global_emitter,
)

__all__ = [
    "ObservabilityDiagnostics",
    "ObservabilityEmitter",
    "SpanContext",
    "get_current_context",
    "get_global_emitter",
    "get_observability_diagnostics",
    "reset_current_context",
    "set_current_context",
    "set_global_emitter",
]
