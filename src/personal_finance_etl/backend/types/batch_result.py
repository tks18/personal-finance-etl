"""Extraction outcome types across entity workers (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
Extraction outcome contracts have migrated to `personal_finance_etl.contracts.extraction`.
"""

from personal_finance_etl.contracts.extraction import (
    ExtractionBatchResult,
    ExtractionCompletenessError,
    ExtractorEntityResult,
    ExtractorEntityStatus,
)

__all__ = [
    "ExtractionBatchResult",
    "ExtractionCompletenessError",
    "ExtractorEntityResult",
    "ExtractorEntityStatus",
]
