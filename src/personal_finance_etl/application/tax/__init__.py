"""Tax application orchestration service.

Owns
----
- Orchestrating TaxEvent generation, classification, and estimation pipelines.
- Coordinating Gold Tax table presentation views.

Does not own
-------------
- Realized gain calculation (owned by domain.investments).
- Tax classification rules and statutory rates (owned by domain.tax and config.financial_rules).
- Physical DuckDB execution or warehouse registration (owned by infrastructure.warehouse).
"""

from personal_finance_etl.application.tax.tax_service import TaxEngine, TaxService

__all__ = ["TaxEngine", "TaxService"]
