"""Legacy delegation shim for post-processing coordinator.

Superseded by personal_finance_etl.application.investments.aggregation_service.
"""

from personal_finance_etl.application.investments.aggregation_service import (
    PostProcessor as PostProcessor,
)

__all__ = ["PostProcessor"]
