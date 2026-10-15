"""Market data provider adapters.

Owns
----
- Currency FX historical rates acquisition (Yahoo Finance adapter).
- Benchmark historical price series acquisition adapter.
- US market historical price series acquisition adapter.

Does not own
-------------
- Currency normalization business logic (owned by domain.market.fx).
- Investment valuation formulas (owned by domain.investments.valuation).
"""

