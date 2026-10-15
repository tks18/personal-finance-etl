"""Pipeline orchestration and execution lifecycle.

Owns
----
- Pipeline stage sequencing and worker execution.
- Transactional commit and recovery state transitions.
- Coordination of end-to-end ETL execution.

Does not own
-------------
- Concrete database queries or DDL (owned by infrastructure.warehouse).
- Domain transformations (owned by domain.*).
- UI progress display (owned by presentation).
"""

from __future__ import annotations

from personal_finance_etl.application.pipeline.execution import PipelineExecutor
from personal_finance_etl.application.pipeline.lifecycle import RunLifecycleCoordinator
from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.application.pipeline.transformer import TransformationDAG
from personal_finance_etl.application.pipeline.worker import (
    QueueStream,
    WorkerPoolCoordinator,
    process_wrapper,
)

__all__ = [
    "ETLOrchestrator",
    "PipelineExecutor",
    "QueueStream",
    "RunLifecycleCoordinator",
    "TransformationDAG",
    "WorkerPoolCoordinator",
    "process_wrapper",
]
