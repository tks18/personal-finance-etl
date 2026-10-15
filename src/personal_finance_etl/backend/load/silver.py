"""Pass-through delegation shim for SilverLayer.

Superseded by personal_finance_etl.infrastructure.warehouse.silver.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.silver import SilverLayer

__all__ = ["SilverLayer"]
