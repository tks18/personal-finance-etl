"""Household financial domain.

Owns
----
- Household ledger modelling.
- Cashflow statement generation and monthly summaries.
- Deterministic budget forecasting and spending analytics.
- Income stream analysis.

Does not own
-------------
- Raw extraction of SQLite or CSV evidence (owned by infrastructure.providers).
- Investment lot accounting (owned by domain.investments).
- UI presentation or tab rendering (owned by presentation).
"""

