"""Process-wide logging infrastructure, contextual filters, and worker process listeners.

Owns
----
- Root personal_finance_etl package logger initialization.
- ContextFilter injecting default contextual execution metadata (run_id, stage, isin).
- Worker process QueueListener coordination for isolated ISIN multiprocessing pools.
- Worker process logging initialization routing records to parent listener.

Does not own
-------------
- UI event narrative formatting (owned by presentation.observability).
- Forensic JSONL file persistence (owned by infrastructure.observability).
- Typed cross-process event contracts (owned by contracts.observability).
"""

from __future__ import annotations

import logging
import logging.handlers
import multiprocessing
from multiprocessing.managers import SyncManager
from typing import cast

__all__ = [
    "ContextFilter",
    "setup_package_logger",
    "setup_worker_logging",
    "start_worker_listener",
    "stop_worker_listener",
]


class ContextFilter(logging.Filter):
    """Injects contextual attributes into log records if missing."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Inject default contextual attributes (run_id, stage, isin) into record if absent."""
        if not hasattr(record, "run_id"):
            record.run_id = "-"
        if not hasattr(record, "stage"):
            record.stage = "-"
        if not hasattr(record, "isin"):
            record.isin = "-"
        return True


def setup_package_logger(
    name: str = "personal_finance_etl", level: int = logging.DEBUG
) -> logging.Logger:
    """Initialize and configure a contextual logger under the personal_finance_etl namespace.

    Parameters
    ----------
    name : str, default="personal_finance_etl"
        Logger hierarchy name rooted under personal_finance_etl.
    level : int, default=logging.DEBUG
        Base logging severity threshold.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    configured_logger = logging.getLogger(name)
    if not any(isinstance(f, ContextFilter) for f in configured_logger.filters):
        configured_logger.addFilter(ContextFilter())
    if not configured_logger.handlers:
        configured_logger.setLevel(level)
    return configured_logger


_listener: logging.handlers.QueueListener | None = None
_worker_manager: SyncManager | None = None
_worker_queue: multiprocessing.Queue[logging.LogRecord] | None = None


def start_worker_listener() -> multiprocessing.Queue[logging.LogRecord]:
    """Start a QueueListener in the parent process to receive logs from workers.

    Returns
    -------
    multiprocessing.Queue[logging.LogRecord]
        Inter-process logging queue for worker pools.
    """
    global _listener, _worker_manager, _worker_queue

    stop_worker_listener()

    _worker_manager = multiprocessing.Manager()
    q = cast("multiprocessing.Queue[logging.LogRecord]", _worker_manager.Queue(-1))
    _worker_queue = q

    pkg_logger = logging.getLogger("personal_finance_etl")
    target_handlers = list(pkg_logger.handlers)

    _listener = logging.handlers.QueueListener(q, *target_handlers, respect_handler_level=True)
    _listener.start()
    return q


def stop_worker_listener() -> None:
    """Stop the QueueListener and clean up worker manager resources."""
    global _listener, _worker_manager, _worker_queue

    if _listener is not None:
        try:
            _listener.stop()
        finally:
            _listener = None

    _worker_queue = None

    if _worker_manager is not None:
        try:
            _worker_manager.shutdown()
        finally:
            _worker_manager = None


def setup_worker_logging(queue: multiprocessing.Queue[logging.LogRecord]) -> None:
    """Initialize logging inside a worker process to route records to the parent listener.

    Parameters
    ----------
    queue : multiprocessing.Queue[logging.LogRecord]
        Inter-process logging queue passed from the parent process.
    """
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    pkg_logger = logging.getLogger("personal_finance_etl")
    for h in pkg_logger.handlers[:]:
        pkg_logger.removeHandler(h)

    if not any(isinstance(f, ContextFilter) for f in pkg_logger.filters):
        pkg_logger.addFilter(ContextFilter())

    handler = logging.handlers.QueueHandler(queue)
    pkg_logger.addHandler(handler)
    pkg_logger.setLevel(logging.DEBUG)
