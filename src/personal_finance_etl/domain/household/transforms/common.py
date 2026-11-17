"""Household transformation shared helpers.

Owns
----
- Pure tabular transformation utilities for household streams.

Does not own
-------------
- Validation logic (owned by domain.common.validation).
- Date calculation logic (owned by domain.common.dates).
- Column mapping extraction (retired in Phase 030; owned by config.sources).
"""

from __future__ import annotations

__all__: list[str] = []
