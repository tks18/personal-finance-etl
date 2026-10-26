"""Logging infrastructure and formatters.

Owns
----
- Process-wide logging configuration and contextual filters.
- Multi-process logging queues and listener setups.

Does not own
-------------
- UI log viewer presentation widgets (owned by presentation).
- Typed cross-process event contracts (owned by contracts.observability).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.logging.setup import (
    ContextFilter,
    setup_package_logger,
    setup_worker_logging,
    start_worker_listener,
    stop_worker_listener,
)

__all__ = [
    "ContextFilter",
    "setup_package_logger",
    "setup_worker_logging",
    "start_worker_listener",
    "stop_worker_listener",
]
