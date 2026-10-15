"""Application orchestration, use cases, and public façade.

Owns
----
- Use cases and workflow orchestration.
- Execution lifecycle coordination.
- Ingestion coordination between providers and Bronze persistence.
- Post-ISIN portfolio aggregation and performance coordination.
- High-level application façade for CLI and Desktop presentation.

Does not own
-------------
- Financial algorithms and mathematical formulas (owned by domain).
- Concrete storage, DuckDB, SQLite, or provider mechanics (owned by infrastructure).
- Human-facing rendering, CLI argument parsing, or Desktop UI (owned by presentation).
"""

from __future__ import annotations

from personal_finance_etl.application.facade import PersonalFinanceEngine

__all__ = ["PersonalFinanceEngine"]
