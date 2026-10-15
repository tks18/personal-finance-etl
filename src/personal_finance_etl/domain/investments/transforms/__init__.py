"""Investment canonical Polars transformations.

Owns
----
- Mutual fund transaction and holdings transformations.
- Indian equity transaction and market transformations.
- US equity transaction and market transformations.
- Common investment transformation helpers.

Does not own
-------------
- Stateful FIFO lot matching (owned by domain.investments.lots).
- Physical table insertion (owned by infrastructure.warehouse).
"""

