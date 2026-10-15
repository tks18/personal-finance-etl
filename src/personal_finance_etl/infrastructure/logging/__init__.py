"""Logging infrastructure and formatters.

Owns
----
- Process-wide logging configuration and handler setups.
- Multi-process logging queues and formatters.
- Log file rotation and formatting.

Does not own
-------------
- UI log viewer presentation widgets (owned by presentation).
- Cross-process status message definitions (owned by contracts.application).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.logging.setup import (
    ContextFilter,
    QueueHandler,
    add_file_handler,
    add_queue_handler,
    logger,
    remove_file_handlers,
    setup_logger,
    setup_worker_logging,
    start_worker_listener,
    stop_worker_listener,
)

__all__ = [
    "ContextFilter",
    "QueueHandler",
    "add_file_handler",
    "add_queue_handler",
    "logger",
    "remove_file_handlers",
    "setup_logger",
    "setup_worker_logging",
    "start_worker_listener",
    "stop_worker_listener",
]
