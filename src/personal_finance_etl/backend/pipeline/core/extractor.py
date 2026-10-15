"""Legacy DataExtractor shim.

DEACTIVATED: This module is superseded by application.ingestion.coordinator.
"""

from __future__ import annotations

from personal_finance_etl.application.ingestion.coordinator import (
    DataExtractor,
)

__all__ = ["DataExtractor"]
