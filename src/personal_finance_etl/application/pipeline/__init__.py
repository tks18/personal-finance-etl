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

from personal_finance_etl.application.pipeline.replay import (
    ReplayCoordinator,
    SourceConfigChangeClassifier,
)
from personal_finance_etl.application.pipeline.satisfiability import (
    CanonicalSatisfiabilityPlanner,
)
from personal_finance_etl.application.pipeline.source_planner import (
    CompiledSourcePlan,
    DatasetPlan,
    SourcePlan,
    SourcePlanner,
    SourcePlanningError,
)
from personal_finance_etl.application.pipeline.transformer import TransformationDAG

__all__ = [
    "CanonicalSatisfiabilityPlanner",
    "CompiledSourcePlan",
    "DatasetPlan",
    "ReplayCoordinator",
    "SourceConfigChangeClassifier",
    "SourcePlan",
    "SourcePlanner",
    "SourcePlanningError",
    "TransformationDAG",
]
