"""Per-ISIN processing facade and orchestration exports.

Owns
----
- Facade exports for ISIN processing, pipeline pooling, metrics, and classification.

Does not own
-------------
- Chronological simulation implementation (owned by application.investments.isin_processor).
- Multiprocessing pipeline pooling (owned by application.investments.isin_pipeline).
- Worker execution (owned by application.investments.isin_worker).
- Daily metrics and valuation math (owned by application.investments.isin_metrics).
- Simulation state container (owned by application.investments.isin_state).
- Rights entitlement pattern matching (owned by application.investments.isin_classifier).
"""

from __future__ import annotations

from personal_finance_etl.application.investments.isin_service.classifier import (
    is_indian_rights_entitlement_isin,
    is_zero_proceeds_re_adjustment,
)
from personal_finance_etl.application.investments.isin_service.metrics import _DailyTerminals
from personal_finance_etl.application.investments.isin_service.pipeline import IsinPipeline
from personal_finance_etl.application.investments.isin_service.processor import IsinProcessor
from personal_finance_etl.application.investments.isin_service.state import _IsinState
from personal_finance_etl.application.investments.isin_service.worker import _process_isin_worker

_is_zero_proceeds_re_adjustment = is_zero_proceeds_re_adjustment

__all__ = [
    "IsinPipeline",
    "IsinProcessor",
    "_DailyTerminals",
    "_IsinState",
    "_is_zero_proceeds_re_adjustment",
    "_process_isin_worker",
    "is_indian_rights_entitlement_isin",
]
