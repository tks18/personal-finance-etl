"""Household dimension transformations facade.

Owns
----
- Unified re-export facade for income, expense, asset, and reference dimensions.
- Pure LazyFrame transformations without I/O or storage dependencies.

Does not own
-------------
- Concrete dimension classification rules (owned by submodules: income_dimensions,
  expense_dimensions, asset_dimensions, reference_dimensions).
- Extraction of raw SQLite or CSV source evidence (owned by infrastructure.providers).
- Physical table insertion into DuckDB (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from personal_finance_etl.domain.household.transforms.asset_dimensions import (
    transform_d_asset_category,
    transform_d_asset_subcategory,
)
from personal_finance_etl.domain.household.transforms.expense_dimensions import (
    transform_d_expense_category,
    transform_d_expense_subcategory,
)
from personal_finance_etl.domain.household.transforms.income_dimensions import (
    transform_d_income_category,
    transform_d_income_subcategory,
)
from personal_finance_etl.domain.household.transforms.reference_dimensions import (
    transform_d_currency,
    transform_d_investment_benchmark_master,
    transform_d_macro_parameters,
)

__all__ = [
    "transform_d_asset_category",
    "transform_d_asset_subcategory",
    "transform_d_currency",
    "transform_d_expense_category",
    "transform_d_expense_subcategory",
    "transform_d_income_category",
    "transform_d_income_subcategory",
    "transform_d_investment_benchmark_master",
    "transform_d_macro_parameters",
]
