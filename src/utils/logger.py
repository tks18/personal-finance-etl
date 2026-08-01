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
        logger.setLevel(logging.INFO)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    return logger


logger = setup_logger()


def add_queue_handler(
    log_queue: "multiprocessing.Queue[tuple[str, str | None, str | None]]",
) -> None:
    handler = QueueHandler(log_queue)
    # The UI handles its own timestamps, so just send the pure message
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
