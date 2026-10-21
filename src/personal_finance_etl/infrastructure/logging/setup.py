"""Process-wide logging infrastructure, contextual formatters, and multi-process queues.

Owns
----
- Root and named logger initialization with contextual execution metadata (run_id, stage, isin).
- UI message queue forwarding handler (QueueHandler).
- File logging configuration with sub-millisecond timestamps and process names.
- Multi-processing worker queue listener coordination (QueueListener).

Does not own
-------------
- UI log visual presentation and coloring (owned by presentation.desktop.theme).
- Typed cross-process status message models (owned by contracts.application).
"""

from __future__ import annotations

import logging
import logging.handlers
import multiprocessing
import os
from multiprocessing.managers import SyncManager
from typing import cast


class QueueHandler(logging.Handler):
    """Logging handler that routes formatted messages to a multiprocessing queue."""

    def __init__(
        self, log_queue: multiprocessing.Queue[tuple[str, str | None, str | None]]
    ) -> None:
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        """Format log record and enqueue message tuple to multiprocessing queue."""
        try:
            msg = self.format(record)
            self.log_queue.put((msg, None, None))
        except Exception:
            self.handleError(record)


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


def setup_logger(name: str = "etl_pipeline") -> logging.Logger:
    """Initialize and configure a contextual logger.

    Parameters
    ----------
    name : str, default="etl_pipeline"
        Logger hierarchy name.

    Returns
    -------
    logging.Logger
        Configured logger instance.
    """
    configured_logger = logging.getLogger(name)
    if not any(isinstance(f, ContextFilter) for f in configured_logger.filters):
        configured_logger.addFilter(ContextFilter())
    if not configured_logger.handlers:
        configured_logger.setLevel(logging.DEBUG)
    return configured_logger


logger = setup_logger()


def add_queue_handler(
    log_queue: multiprocessing.Queue[tuple[str, str | None, str | None]],
) -> None:
    """Attach a UI queue handler to the application logger."""
    for h in logger.handlers[:]:
        if isinstance(h, QueueHandler):
            logger.removeHandler(h)

    handler = QueueHandler(log_queue)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def add_file_handler(file_path: str) -> None:
    """Attach an enterprise-grade file handler to the application logger."""
    dir_name = os.path.dirname(file_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    for h in logger.handlers[:]:
        if isinstance(h, logging.FileHandler):
            logger.removeHandler(h)

    handler = logging.FileHandler(file_path, mode="w", encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    fmt_str = (
        "%(asctime)s.%(msecs)03d | %(levelname)-8s | Run:%(run_id)s | Stage:%(stage)s | "
        "ISIN:%(isin)s | Proc:%(processName)s | [%(module)s:%(funcName)s:%(lineno)d] | %(message)s"
    )
    formatter = logging.Formatter(fmt_str, datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def remove_file_handlers() -> None:
    """Close and remove all FileHandlers from the logger."""
    for h in logger.handlers[:]:
        if isinstance(h, logging.FileHandler):
            h.flush()
            h.close()
            logger.removeHandler(h)


_listener: logging.handlers.QueueListener | None = None
_worker_manager: SyncManager | None = None
_worker_queue: multiprocessing.Queue[logging.LogRecord] | None = None


def start_worker_listener() -> multiprocessing.Queue[logging.LogRecord]:
    """Start a QueueListener in the parent process to receive logs from workers."""
    global _listener, _worker_manager, _worker_queue

    stop_worker_listener()

    _worker_manager = multiprocessing.Manager()
    q = cast("multiprocessing.Queue[logging.LogRecord]", _worker_manager.Queue(-1))
    _worker_queue = q

    target_handlers = [h for h in logger.handlers if not isinstance(h, QueueHandler)]

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
    """Initialize logging inside a worker process to route records to the parent."""
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    for h in logger.handlers[:]:
        logger.removeHandler(h)

    if not any(isinstance(f, ContextFilter) for f in logger.filters):
        logger.addFilter(ContextFilter())

    handler = logging.handlers.QueueHandler(queue)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
