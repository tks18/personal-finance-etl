"""Legacy ETL pipeline orchestration module.

.. deprecated::
    personal_finance_etl.backend.pipeline.etl_pipeline is deprecated and will be removed in Phase 11.
    Use personal_finance_etl.application.pipeline instead.
"""

from __future__ import annotations

import warnings

from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.application.pipeline.worker import process_wrapper

warnings.warn(
    "personal_finance_etl.backend.pipeline.etl_pipeline is deprecated. "
    "Use personal_finance_etl.application.pipeline instead.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["ETLOrchestrator", "process_wrapper"]
