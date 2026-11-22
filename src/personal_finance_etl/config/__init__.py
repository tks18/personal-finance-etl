"""Configuration and financial policy package.

Owns
----
- Validated runtime environment settings (Settings).
- Financial policy and rule definitions (FinancialRules).
- Validation of TOML configuration files.

Does not own
-------------
- Filesystem persistence of preferences (owned by infrastructure.preferences).
- Domain calculations or execution workflows (owned by domain and application).
- UI configuration forms (owned by presentation).
"""

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import FileHashPolicy, Settings

__all__ = [
    "FileHashPolicy",
    "FinancialRules",
    "Settings",
]
