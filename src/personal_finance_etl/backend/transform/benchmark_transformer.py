"""Legacy deactivation shim for backend.transform.benchmark_transformer.

Delegates completely to canonical domain.market.benchmarks.
"""

from personal_finance_etl.domain.market.benchmarks import (
    BenchmarkTransformer as BenchmarkTransformer,
)
from personal_finance_etl.domain.market.benchmarks import (
    transform_benchmark_data as transform_benchmark_data,
)

__all__ = [
    "BenchmarkTransformer",
    "transform_benchmark_data",
]
