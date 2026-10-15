"""DEPRECATED - Legacy date utilities shim module.

This module has been deactivated as part of Phase 2 of the Grand Refactor.
Canonical date and fiscal year helpers now reside in:
`personal_finance_etl.domain.common.dates`

This file is maintained strictly as a backwards-compatible pass-through delegation shim.
Do not edit or add logic here.
"""

from personal_finance_etl.domain.common.dates import add_fy_if_missing

__all__ = ["add_fy_if_missing"]
