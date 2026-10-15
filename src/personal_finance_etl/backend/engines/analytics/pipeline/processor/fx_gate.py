"""FX rate validation gate (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All FX gate validation has migrated to
`personal_finance_etl.domain.investments.valuation.fx`.
"""

from personal_finance_etl.domain.investments.valuation.fx import (
    FXProviderMissingError as FXProviderMissingError,
)
from personal_finance_etl.domain.investments.valuation.fx import (
    FXRateUnavailableError as FXRateUnavailableError,
)
from personal_finance_etl.domain.investments.valuation.fx import (
    FXValidationGate as FXValidationGate,
)

__all__ = [
    "FXProviderMissingError",
    "FXRateUnavailableError",
    "FXValidationGate",
]
