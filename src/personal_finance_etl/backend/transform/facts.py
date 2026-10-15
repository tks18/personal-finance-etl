"""Legacy deactivation shim for backend.transform.facts.

Delegates completely to canonical domain.household.transforms.transactions.
"""

from personal_finance_etl.domain.household.transforms.transactions import (
    BASE_TRANSACTION_COLS as BASE_TRANSACTION_COLS,
)
from personal_finance_etl.domain.household.transforms.transactions import (
    get_base_transactions as get_base_transactions,
)
from personal_finance_etl.domain.household.transforms.transactions import (
    transform_f_expense_transactions as transform_f_expense_transactions,
)
from personal_finance_etl.domain.household.transforms.transactions import (
    transform_f_income_transactions as transform_f_income_transactions,
)
from personal_finance_etl.domain.household.transforms.transactions import (
    transform_f_opening_balances as transform_f_opening_balances,
)
from personal_finance_etl.domain.household.transforms.transactions import (
    transform_f_transfer_transactions as transform_f_transfer_transactions,
)

__all__ = [
    "BASE_TRANSACTION_COLS",
    "get_base_transactions",
    "transform_f_expense_transactions",
    "transform_f_income_transactions",
    "transform_f_opening_balances",
    "transform_f_transfer_transactions",
]
