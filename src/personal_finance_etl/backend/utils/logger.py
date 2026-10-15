"""Pass-through delegation shim for application logger.

Superseded by personal_finance_etl.infrastructure.logging.setup.
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
