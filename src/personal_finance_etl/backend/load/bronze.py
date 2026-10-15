"""Pass-through delegation shim for BronzeLayer.

Superseded by personal_finance_etl.infrastructure.warehouse.bronze.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer

__all__ = ["BronzeLayer"]
