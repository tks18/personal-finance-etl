"""Legacy delegation shim for pipeline run context and FX rate provider.

Superseded by personal_finance_etl.application.investments.context and
personal_finance_etl.domain.market.fx.
"""

from personal_finance_etl.application.investments.context import (
    RunContext as RunContext,
)
from personal_finance_etl.domain.market.fx import (
    FXRateProvider as FXRateProvider,
)

__all__ = ["FXRateProvider", "RunContext"]
