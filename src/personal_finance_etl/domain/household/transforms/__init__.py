"""Household canonical Polars transformations.

Owns
----
- Calendar dimension generation.
- Household dimensions transformation (categories, assets, currencies).
- Transaction facts transformation and normalization.
- Pure functional LazyFrame transformations.

Does not own
-------------
- Physical table insertion (owned by infrastructure.warehouse).
- Source parsing (owned by infrastructure.providers).
"""

