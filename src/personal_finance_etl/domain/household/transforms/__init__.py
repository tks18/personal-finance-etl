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

from personal_finance_etl.domain.household.transforms.calendar import (
    get_stg_calendar_ref,
    transform_d_calendar,
)
from personal_finance_etl.domain.household.transforms.common import (
    get_column_mapping,
)
from personal_finance_etl.domain.household.transforms.dimensions import (
    transform_d_asset_category,
    transform_d_asset_subcategory,
    transform_d_currency,
    transform_d_expense_category,
    transform_d_expense_subcategory,
    transform_d_income_category,
    transform_d_income_subcategory,
    transform_d_investment_benchmark_master,
    transform_d_macro_parameters,
)
from personal_finance_etl.domain.household.transforms.transactions import (
    BASE_TRANSACTION_COLS,
    get_base_transactions,
    transform_f_expense_transactions,
    transform_f_income_transactions,
    transform_f_opening_balances,
    transform_f_transfer_transactions,
)

__all__ = [
    "BASE_TRANSACTION_COLS",
    "get_base_transactions",
    "get_column_mapping",
    "get_stg_calendar_ref",
    "transform_d_asset_category",
    "transform_d_asset_subcategory",
    "transform_d_calendar",
    "transform_d_currency",
    "transform_d_expense_category",
    "transform_d_expense_subcategory",
    "transform_d_income_category",
    "transform_d_income_subcategory",
    "transform_d_investment_benchmark_master",
    "transform_d_macro_parameters",
    "transform_f_expense_transactions",
    "transform_f_income_transactions",
    "transform_f_opening_balances",
    "transform_f_transfer_transactions",
]
