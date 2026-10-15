"""Tax application orchestration service.

Owns
----
- Orchestrating TaxEvent generation, classification, and estimation pipelines.
- Coordinating Gold Tax table persistence preparation.

Does not own
-------------
- Realized gain calculation (owned by domain.investments).
- Tax classification rules and statutory rates (owned by domain.tax and config.financial_rules).
- Physical DuckDB execution (owned by infrastructure.warehouse).
"""
