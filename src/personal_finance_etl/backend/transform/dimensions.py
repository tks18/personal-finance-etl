"""Legacy deactivation shim for backend.transform.dimensions.

Delegates completely to canonical domain.household.transforms.dimensions.
"""

from personal_finance_etl.domain.household.transforms.dimensions import (
    _get_tax_maps as _get_tax_maps,  # pyright: ignore[reportPrivateUsage]
)
from personal_finance_etl.domain.household.transforms.dimensions import (
    transform_d_asset_category as transform_d_asset_category,
)
from personal_finance_etl.domain.household.transforms.dimensions import (
    transform_d_asset_subcategory as transform_d_asset_subcategory,
)
from personal_finance_etl.domain.household.transforms.dimensions import (
    transform_d_currency as transform_d_currency,
)
from personal_finance_etl.domain.household.transforms.dimensions import (
    transform_d_expense_category as transform_d_expense_category,
)
from personal_finance_etl.domain.household.transforms.dimensions import (
    transform_d_expense_subcategory as transform_d_expense_subcategory,
)
from personal_finance_etl.domain.household.transforms.dimensions import (
    transform_d_income_category as transform_d_income_category,
)
from personal_finance_etl.domain.household.transforms.dimensions import (
    transform_d_income_subcategory as transform_d_income_subcategory,
)
from personal_finance_etl.domain.household.transforms.dimensions import (
    transform_d_investment_benchmark_master as transform_d_investment_benchmark_master,
)
from personal_finance_etl.domain.household.transforms.dimensions import (
    transform_d_macro_parameters as transform_d_macro_parameters,
)

__all__ = [
    "_get_tax_maps",
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
