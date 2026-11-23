"""Infrastructure operator inspection and diagnostic health checks.

Owns
----
- LocalOperatorInspector: concrete file, database, filelock, and provider inspection.
- Executing read-only queries against SQLite control plane and DuckDB warehouse.
- Probing network connectivity to external market data providers.

Does not own
-------------
- Operator read models or doctor business evaluations (owned by application.operator).
- Presentation formatting or CLI command parsing (owned by presentation.*).
"""

from personal_finance_etl.infrastructure.operator.inspector import LocalOperatorInspector

__all__ = ["LocalOperatorInspector"]
