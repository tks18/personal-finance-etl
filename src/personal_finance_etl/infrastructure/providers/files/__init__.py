"""File format and discovery evidence adapters.

Owns
----
- CSV and Excel statement parsing adapters.
- External household SQLite source extraction adapter.
- Local filesystem statement discovery and locator adapter.

Does not own
-------------
- Validation of business contents (owned by domain.common.validation).
- Bronze database storage (owned by infrastructure.warehouse.bronze).
"""

