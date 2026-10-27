"""Ambient observability context management across asynchronous tasks and threads.

Owns
----
- Thread-safe and task-local storage for ambient ObservabilityContext via ContextVar.
- Binding utilities for run_id, stage, component, and operation propagation.

Does not own
-------------
- Canonical context data structures (owned by contracts.observability).
- Event dispatch and sink fan-out (owned by infrastructure.observability.emitter).
"""

from __future__ import annotations

import contextvars

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.observability import ObservabilityContext

__all__ = [
    "get_current_context",
    "reset_current_context",
    "set_current_context",
]

_DEFAULT_CONTEXT = ObservabilityContext(run_id="-", stage=EngineStage.INITIALIZING)
_ACTIVE_CONTEXT: contextvars.ContextVar[ObservabilityContext] = contextvars.ContextVar(
    "active_observability_context", default=_DEFAULT_CONTEXT
)


def get_current_context() -> ObservabilityContext:
    """Retrieve the currently active ambient ObservabilityContext.

    Returns
    -------
    ObservabilityContext
        The active contextual envelope.
    """
    return _ACTIVE_CONTEXT.get()


def set_current_context(
    context: ObservabilityContext,
) -> contextvars.Token[ObservabilityContext]:
    """Set the active ambient ObservabilityContext, returning a reset token.

    Parameters
    ----------
    context : ObservabilityContext
        The new context to activate in the current task/thread.

    Returns
    -------
    contextvars.Token[ObservabilityContext]
        Token used to restore previous context via reset_current_context.
    """
    return _ACTIVE_CONTEXT.set(context)


def reset_current_context(token: contextvars.Token[ObservabilityContext]) -> None:
    """Reset the active ObservabilityContext using a previously acquired token.

    Parameters
    ----------
    token : contextvars.Token[ObservabilityContext]
        The context token returned by set_current_context.
    """
    _ACTIVE_CONTEXT.reset(token)
