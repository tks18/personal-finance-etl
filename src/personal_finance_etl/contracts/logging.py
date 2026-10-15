"""Logging level and tag contracts.

Owns
----
- LogLevel enumeration used across process boundaries and UI queues.

Does not own
-------------
- Concrete logging handler configuration (owned by infrastructure.logging).
- Desktop GUI log viewer widgets (owned by presentation.desktop).
"""

from enum import StrEnum


class LogLevel(StrEnum):
    """Categorical logging levels for the application status sink."""

    INFO = "info"
    STEP = "step"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"

