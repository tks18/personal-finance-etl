"""Legacy delegation shim for multiprocessing ISIN pipeline.

Superseded by personal_finance_etl.application.investments.isin_service.
"""

from personal_finance_etl.application.investments.isin_service import (
    IsinPipeline as IsinPipeline,
)
from personal_finance_etl.application.investments.isin_service import (
    _process_isin_worker as _process_isin_worker,
)

__all__ = ["IsinPipeline", "_process_isin_worker"]
