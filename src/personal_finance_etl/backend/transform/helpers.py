"""Legacy deactivation shim for backend.transform.helpers.

Delegates completely to canonical domain.household.transforms.common.
"""

from personal_finance_etl.domain.household.transforms.common import (
    get_column_mapping as get_column_mapping,
)

__all__ = [
    "get_column_mapping",
]
