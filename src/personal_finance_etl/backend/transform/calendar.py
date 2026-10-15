"""Legacy deactivation shim for backend.transform.calendar.

Delegates completely to canonical domain.household.transforms.calendar.
"""

from personal_finance_etl.domain.household.transforms.calendar import (
    get_stg_calendar_ref as get_stg_calendar_ref,
)
from personal_finance_etl.domain.household.transforms.calendar import (
    transform_d_calendar as transform_d_calendar,
)

__all__ = [
    "get_stg_calendar_ref",
    "transform_d_calendar",
]
