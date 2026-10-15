"""Pass-through delegation shim for GoldLayer.

Superseded by personal_finance_etl.infrastructure.warehouse.gold.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.gold import GoldLayer

__all__ = ["GoldLayer"]
