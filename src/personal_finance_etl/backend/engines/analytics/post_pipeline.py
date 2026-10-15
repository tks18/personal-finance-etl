"""Legacy delegation shim for post-processing pipeline.

Superseded by personal_finance_etl.application.investments.aggregation_service.
"""

from personal_finance_etl.application.investments.aggregation_service import (
    PostProcessingPipeline as PostProcessingPipeline,
)

__all__ = ["PostProcessingPipeline"]
