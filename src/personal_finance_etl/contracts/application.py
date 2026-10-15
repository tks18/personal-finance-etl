"""Application execution and cross-process message contracts.

Owns
----
- Typed cross-process worker status messages (EngineStatusMessage).
- EngineStage categorical workflow stages.
- EngineExecutionResult high-level pipeline outcome.

Does not own
-------------
- Orchestration execution logic (owned by application.pipeline).
- Presentation rendering (owned by presentation).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

import polars as pl

from personal_finance_etl.contracts.lifecycle import CommitState, FailureDomain
from personal_finance_etl.contracts.logging import LogLevel


class EngineStage(StrEnum):
    """Categorical stages of pipeline execution."""

    INITIALIZING = "INITIALIZING"
    DISCOVERING = "DISCOVERING"
    EXTRACTING = "EXTRACTING"
    TRANSFORMING = "TRANSFORMING"
    ANALYZING = "ANALYZING"
    PUBLISHING = "PUBLISHING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RECOVERY = "RECOVERY"


@dataclass
class EngineStatusMessage:
    """Structured message for the UI and worker status queue.

    Replaces legacy anonymous tuples (tuple[str, Any | None, float | None])
    with a fully typed, extensible contract across process boundaries.
    """

    msg: str
    level: LogLevel = LogLevel.INFO
    progress: float | None = None
    data: pl.DataFrame | None = None
    stage: EngineStage | None = None
    failure_domain: FailureDomain | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def message(self) -> str:
        """Alias for msg for backward compatibility."""
        return self.msg

    @property
    def status(self) -> LogLevel:
        """Alias for level for backward compatibility."""
        return self.level


@dataclass(frozen=True)
class EngineExecutionResult:
    """High-level application pipeline execution outcome."""

    is_success: bool
    run_id: str
    commit_state: CommitState
    duration_seconds: float
    error_message: str | None = None
    failure_domain: FailureDomain | None = None
