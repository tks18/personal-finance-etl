"""
Backend Domain and Infrastructure Layer.

This package encapsulates the core quantitative engines, ETL orchestration,
and the dual-plane Lakehouse architecture (SQLite for ACID Control Plane,
DuckDB for high-performance Analytical Engine). It is strictly isolated from the frontend.

The `PersonalFinanceEngine` API facade acts as the single entry point
for any presentation layer (Desktop, Web, or CLI) to safely interact with the backend.
"""

from personal_finance_etl.backend.api.engine import PersonalFinanceEngine

__all__ = ["PersonalFinanceEngine"]
