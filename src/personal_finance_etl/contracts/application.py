"""Application execution and cross-process message contracts.

Owns
----
- Typed cross-process worker status messages (EngineStatusMessage).
- Dedicated tabular result transport contract (EngineDataTransport).
- EngineStage categorical workflow stages.
- EngineExecutionResult high-level pipeline outcome.

Does not own
-------------
- Orchestration execution logic (owned by application.pipeline).
- Presentation rendering (owned by presentation).
"""

from collections.abc import Mapping
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

    Fully typed status message contract across process boundaries.
    Carries progress, severity, stage, and diagnostics with zero data payloads.
    """

    msg: str
    level: LogLevel = LogLevel.INFO
    progress: float | None = None
    stage: EngineStage | None = None
    failure_domain: FailureDomain | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def message(self) -> str:
        """Message content string accessor."""
        return self.msg

    @property
    def status(self) -> LogLevel:
        """Status severity level accessor."""
        return self.level


def _empty_metadata() -> dict[str, str | int | float | bool]:
    return {}


@dataclass(frozen=True)
class EngineDataTransport:
    """Dedicated typed contract for UI-bound or cross-process tabular results.

    Attributes
    ----------
    channel : str
        Identifier for the dataset category (e.g. 'analytics', 'portfolio', 'tax').
    data : pl.DataFrame
        Tabular dataset payload.
    metadata : Mapping[str, str | int | float | bool]
        Bounded descriptive metadata.
    timestamp : datetime
        Creation timestamp.
    """

    channel: str
    data: pl.DataFrame
    metadata: Mapping[str, str | int | float | bool] = field(default_factory=_empty_metadata)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class EngineExecutionResult:
    """High-level application pipeline execution outcome."""

    is_success: bool
    run_id: str
    commit_state: CommitState
    duration_seconds: float
    error_message: str | None = None
    failure_domain: FailureDomain | None = None
