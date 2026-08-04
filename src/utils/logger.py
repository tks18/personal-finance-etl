import logging
import multiprocessing


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


def setup_logger(name: str = "etl_pipeline") -> logging.Logger:
    logger = logging.getLogger(name)
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
    import os

    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    # Remove existing FileHandlers
    for h in logger.handlers[:]:
        if isinstance(h, logging.FileHandler):
            logger.removeHandler(h)

    handler = logging.FileHandler(file_path, mode="w", encoding="utf-8")
    handler.setLevel(logging.DEBUG)  # Enterprise logging captures DEBUG
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(process)d | %(module)s:%(funcName)s:%(lineno)d | %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
