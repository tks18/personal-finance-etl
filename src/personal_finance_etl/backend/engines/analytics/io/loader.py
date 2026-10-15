"""Legacy delegation shim for tax data loader and formatting helpers.

Superseded by personal_finance_etl.application.investments.input_adapter.
"""

from personal_finance_etl.application.investments.input_adapter import (
    TaxDataLoader as TaxDataLoader,
)
from personal_finance_etl.application.investments.input_adapter import (
    clean_numeric_col as clean_numeric_col,
)
from personal_finance_etl.application.investments.input_adapter import (
    parse_date_col as parse_date_col,
)

__all__ = ["TaxDataLoader", "clean_numeric_col", "parse_date_col"]
