"""Legacy deactivation shim for backend.engines.analytics.rules.macro.

Delegates completely to canonical domain.market.macro.
"""

from personal_finance_etl.domain.market.macro import (
    FYMacroParametersTable as FYMacroParametersTable,
)
from personal_finance_etl.domain.market.macro import (
    FYMapEntry as FYMapEntry,
)
from personal_finance_etl.domain.market.macro import (
    add_months as add_months,
)
from personal_finance_etl.domain.market.macro import (
    get_ltcg_threshold_months as get_ltcg_threshold_months,
)

__all__ = [
    "FYMacroParametersTable",
    "FYMapEntry",
    "add_months",
    "get_ltcg_threshold_months",
]
