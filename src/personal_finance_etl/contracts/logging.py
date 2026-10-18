"""Logging level and tag contracts.

Owns
----
- LogLevel enumeration used across process boundaries and UI queues.
- StatusQueue protocol for cross-process status sinks (with ILogger backward-compatibility alias).

Does not own
-------------
- Concrete logging handler configuration (owned by infrastructure.logging).
- Desktop GUI log viewer widgets (owned by presentation.desktop).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

__all__ = ["ILogger", "LogLevel", "NullStatusQueue", "StatusQueue"]


class LogLevel(StrEnum):
    """Categorical logging levels for the application status sink."""

    INFO = "info"
    STEP = "step"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class StatusQueue(Protocol):
    """Protocol for cross-process status queue sinks."""

    def put(
        self,
        status: object,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        """Put a status item onto the queue."""
        ...


class NullStatusQueue:
    """No-op status queue sink used when no external status queue is attached."""

    def put(
        self,
        status: object,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        """Discard status message."""


# Architectural alias for legacy ILogger protocol
ILogger = StatusQueue
