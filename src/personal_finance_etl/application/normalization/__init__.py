"""Application services for source evidence mapping and bounded normalization.

Owns
----
- NormalizationCompiler: Pure non-I/O service compiling SourceDatasetConfig into NormalizationPlan.
- NormalizationExecutor: Vectorized execution engine transforming source frames to canonical frames.
- NormalizationPlan: Deterministic, immutable execution plan models.
- NormalizationError: Typed exception hierarchy for normalization planning and execution.
- MappingCompilationError, MissingSourceFieldError, InvalidCanonicalTargetError: Compilation errors.
- DuplicateMappingError, NormalizationExecutionError: Collision and execution errors.

Does not own
-------------
- User configuration models (owned by config.sources).
- Canonical Bronze schema contracts (owned by contracts.canonical_fields).
- Warehouse persistence or DDL (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from personal_finance_etl.application.normalization.compiler import (
    NormalizationCompiler,
)
from personal_finance_etl.application.normalization.errors import (
    DuplicateMappingError,
    InvalidCanonicalTargetError,
    MappingCompilationError,
    MissingSourceFieldError,
    NormalizationError,
    NormalizationExecutionError,
)
from personal_finance_etl.application.normalization.executor import (
    NormalizationExecutor,
)
from personal_finance_etl.application.normalization.models import (
    NormalizationPlan,
)

__all__ = [
    "DuplicateMappingError",
    "InvalidCanonicalTargetError",
    "MappingCompilationError",
    "MissingSourceFieldError",
    "NormalizationCompiler",
    "NormalizationError",
    "NormalizationExecutionError",
    "NormalizationExecutor",
    "NormalizationPlan",
]
