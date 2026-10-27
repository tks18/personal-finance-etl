"""Application execution and cross-process message contracts.

Owns
----
- Dedicated tabular result transport contract (EngineDataTransport).
- EngineStage categorical workflow stages.
- EngineExecutionResult high-level pipeline outcome.

Does not own
-------------
- Orchestration execution logic (owned by application.pipeline).
- Presentation rendering (owned by presentation).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

import polars as pl

from personal_finance_etl.contracts.lifecycle import CommitState, FailureDomain

__all__ = ["EngineDataTransport", "EngineExecutionResult", "EngineStage"]


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


def _empty_metadata() -> dict[str, str | int | float | bool]:
    """Provide a default empty metadata dictionary for pipeline status events.

    Returns
    -------
    dict[str, str | int | float | bool]
        An empty dictionary adhering to typed event metadata attributes.
    """
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
