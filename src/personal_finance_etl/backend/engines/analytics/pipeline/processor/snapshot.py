"""Snapshot generator (DEPRECATED).

This module is DEPRECATED as part of the Grand Refactor.
All lot snapshot generation logic has migrated to
`personal_finance_etl.domain.investments.portfolio.snapshots`.
"""

from personal_finance_etl.domain.investments.portfolio.snapshots import (
    SnapshotGenerator as SnapshotGenerator,
)
from personal_finance_etl.domain.investments.portfolio.snapshots import (
    _raise_invariant as _raise_invariant,
)

__all__ = [
    "SnapshotGenerator",
    "_raise_invariant",
]
