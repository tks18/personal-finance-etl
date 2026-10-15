"""Benchmark price provider (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All benchmark valuation lookup logic has migrated to
`personal_finance_etl.domain.investments.valuation.benchmark`.
"""

from personal_finance_etl.domain.investments.valuation.benchmark import (
    BenchmarkPriceProvider as BenchmarkPriceProvider,
)

__all__ = ["BenchmarkPriceProvider"]
