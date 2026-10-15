"""Market, FX, macro, and benchmark financial domain.

Owns
----
- FX rate lookup semantics and currency normalization.
- Benchmark return and valuation transformations.
- Macro parameters and historical macroeconomic table lookups.

Does not own
-------------
- Yahoo Finance or market API requests (owned by infrastructure.providers.market).
- Physical table persistence (owned by infrastructure.warehouse).
"""

