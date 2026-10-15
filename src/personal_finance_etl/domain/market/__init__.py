"""Market, FX, macro, and benchmark financial domain.

Owns
----
- FX rate lookup semantics, point-in-time observation models, and currency normalization.
- Benchmark return and valuation transformations.
- Macro parameters and historical macroeconomic table lookups.

Does not own
-------------
- Yahoo Finance or market API requests (owned by infrastructure.providers.market).
- Physical table persistence (owned by infrastructure.warehouse).
"""

from personal_finance_etl.domain.market.benchmarks import (
    BenchmarkTransformer,
    transform_benchmark_data,
)
from personal_finance_etl.domain.market.fx import (
    FXObservation,
    FXRateProvider,
    transform_currency_fx_rates,
)
from personal_finance_etl.domain.market.macro import (
    FYMacroParametersTable,
    FYMapEntry,
    add_months,
    get_ltcg_threshold_months,
)

__all__ = [
    "BenchmarkTransformer",
    "FXObservation",
    "FXRateProvider",
    "FYMacroParametersTable",
    "FYMapEntry",
    "add_months",
    "get_ltcg_threshold_months",
    "transform_benchmark_data",
    "transform_currency_fx_rates",
]
