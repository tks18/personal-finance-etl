import logging
import logging.handlers
import multiprocessing
import os
import typing


class QueueHandler(logging.Handler):
    def __init__(
        self, log_queue: "multiprocessing.Queue[tuple[str, str | None, str | None]]"
    ) -> None:
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.log_queue.put((msg, None, None))
        except Exception:
            self.handleError(record)


class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "run_id"):
            record.run_id = "-"
        if not hasattr(record, "stage"):
            record.stage = "-"
        if not hasattr(record, "isin"):
            record.isin = "-"
        return True


def setup_logger(name: str = "etl_pipeline") -> logging.Logger:
    logger = logging.getLogger(name)
    # Prevent duplicate filters if setup_logger is called multiple times
    if not any(isinstance(f, ContextFilter) for f in logger.filters):
        logger.addFilter(ContextFilter())
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)  # Root logger captures everything
    return logger


logger = setup_logger()


def add_queue_handler(
    log_queue: "multiprocessing.Queue[tuple[str, str | None, str | None]]",
) -> None:
    # Remove existing QueueHandlers to prevent duplicates
    for h in logger.handlers[:]:
        if isinstance(h, QueueHandler):
            logger.removeHandler(h)

    handler = QueueHandler(log_queue)
    handler.setLevel(logging.INFO)  # Keep UI clean with INFO only
    # The UI handles its own timestamps, so just send the pure message
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def add_file_handler(file_path: str) -> None:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Remove existing FileHandlers
    for h in logger.handlers[:]:
        if isinstance(h, logging.FileHandler):
            logger.removeHandler(h)

    handler = logging.FileHandler(file_path, mode="w", encoding="utf-8")
    handler.setLevel(logging.DEBUG)  # Enterprise logging captures DEBUG
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d | %(levelname)-8s | Run:%(run_id)s | Stage:%(stage)s | ISIN:%(isin)s | Proc:%(processName)s | [%(module)s:%(funcName)s:%(lineno)d] | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def remove_file_handlers() -> None:
    """Closes and removes all FileHandlers from the logger."""
    for h in logger.handlers[:]:
        if isinstance(h, logging.FileHandler):
            h.flush()
            h.close()
            logger.removeHandler(h)


# Global reference to listener so it can be stopped
_listener: logging.handlers.QueueListener | None = None
_worker_manager: typing.Any | None = None
_worker_queue: "multiprocessing.Queue[logging.LogRecord] | None" = None


def start_worker_listener() -> "multiprocessing.Queue[logging.LogRecord]":
    """Starts a QueueListener in the parent process to receive logs from workers."""
    global _listener, _worker_manager, _worker_queue

    # Defensive cleanup if a previous run did not stop cleanly.
    stop_worker_listener()

    _worker_manager = multiprocessing.Manager()
    q = typing.cast("multiprocessing.Queue[logging.LogRecord]", _worker_manager.Queue(-1))
    _worker_queue = q

    # Send logs received on the queue to all handlers currently attached to the parent logger
    # that are not QueueHandlers (to avoid loops or sending to UI if not desired, though we want
    # it to go to the FileHandler primarily).
    target_handlers = [h for h in logger.handlers if not isinstance(h, QueueHandler)]

    _listener = logging.handlers.QueueListener(q, *target_handlers, respect_handler_level=True)
    _listener.start()
    return q


def stop_worker_listener() -> None:
    """Stops the QueueListener in the parent process."""
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


def setup_worker_logging(queue: "multiprocessing.Queue[logging.LogRecord]") -> None:
    """Initializes logging inside a worker process to send records to the parent."""
    # Clear existing handlers
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers:
            root.removeHandler(handler)

    # Also clear our specific logger's handlers just in case
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    if not any(isinstance(f, ContextFilter) for f in logger.filters):
        logger.addFilter(ContextFilter())

    handler = logging.handlers.QueueHandler(queue)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
