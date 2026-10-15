"""Legacy delegation shim for investment quant engine.

Superseded by personal_finance_etl.application.investments.quant_service.
"""

from personal_finance_etl.application.investments.quant_service import (
    InvestmentQuantEngine as InvestmentQuantEngine,
)
from personal_finance_etl.application.investments.quant_service import (
    QuantService as QuantService,
)

__all__ = ["InvestmentQuantEngine", "QuantService"]
