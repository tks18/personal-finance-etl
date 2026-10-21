"""Portfolio aggregation and post-processing orchestration service facade.

Owns
----
- PostProcessor: Constructs aggregated multi-asset analytics tables across 10 dimensions.
- PostProcessingPipeline: Scans intermediate per-ISIN Parquet partitions and executes post-processing.
- Realized and reconciliation event builders.

Does not own
-------------
- Chronological per-ISIN daily simulation (owned by application.investments.isin_service).
- FIFO lot accounting and matching algorithms (owned by domain.investments.lots.fifo).
"""

from __future__ import annotations

from personal_finance_etl.application.investments.aggregation_service.events import (
    build_realized_events,
    build_reconciliation_events,
)
from personal_finance_etl.application.investments.aggregation_service.pipeline import (
    PostProcessingPipeline,
)
from personal_finance_etl.application.investments.aggregation_service.service import (
    PostProcessor,
)

__all__ = [
    "PostProcessingPipeline",
    "PostProcessor",
    "build_realized_events",
    "build_reconciliation_events",
]
