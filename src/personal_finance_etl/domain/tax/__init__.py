"""Tax domain logic, normalization, and classification.

Owns
----
- Normalizing ledger and Quant realized events into canonical TaxEvents.
- Income head and sub-head classification.
- Indicative tax liability estimates.
- Tax event reconciliation and audit trails.

Does not own
-------------
- Realized gain computation (owned by domain.investments).
- Tax rules configuration models (owned by config.financial_rules).
- Gold Tax table persistence (owned by infrastructure.warehouse).
"""
