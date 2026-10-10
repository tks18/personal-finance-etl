"""Tax engine core module.

Public API
----------
``BaseEventsBuilder``  — consolidates ledger + investment events into canonical tax events.
``FYStateBuilder``     — builds the f_Tax_FY_State silver table per fiscal year.
``LossSetOffProcessor``— applies the frozen 4-step capital-loss set-off order.
``CarryForwardLoss``   — dataclass representing a carried-forward capital loss.
``TaxGoldFormatter``   — formats the gold-layer tax reconciliation output.
"""

from personal_finance_etl.backend.engines.tax.core.base_events import BaseEventsBuilder
from personal_finance_etl.backend.engines.tax.core.fy_state import FYStateBuilder
from personal_finance_etl.backend.engines.tax.core.gold_formatter import TaxGoldFormatter
from personal_finance_etl.backend.engines.tax.core.set_offs import (
    CarryForwardLoss,
    LossSetOffProcessor,
)

__all__ = [
    "BaseEventsBuilder",
    "FYStateBuilder",
    "LossSetOffProcessor",
    "CarryForwardLoss",
    "TaxGoldFormatter",
]

