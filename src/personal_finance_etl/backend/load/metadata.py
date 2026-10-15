"""Pass-through delegation shim for MetaLayer.

Superseded by personal_finance_etl.infrastructure.warehouse.meta.
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer

__all__ = ["MetaLayer"]
