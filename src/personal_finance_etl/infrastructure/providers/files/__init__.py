"""File format and discovery evidence adapters.

Owns
----
- CSV and Excel statement parsing adapters.
- External household SQLite source extraction adapter.

Does not own
-------------
- Validation of business contents (owned by domain.common.validation).
- Bronze database storage (owned by infrastructure.warehouse.bronze).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.providers.files.csv import (
    CSVExtractor,
)
from personal_finance_etl.infrastructure.providers.files.excel import (
    ExcelExtractor,
)
from personal_finance_etl.infrastructure.providers.files.sqlite import (
    SQLiteExtractor,
)

__all__ = [
    "CSVExtractor",
    "ExcelExtractor",
    "SQLiteExtractor",
]
