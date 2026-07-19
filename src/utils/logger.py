import logging


class QueueHandler(logging.Handler):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_queue.put((msg, None, None))
        except Exception:
            self.handleError(record)


def setup_logger(name: str = "etl_pipeline") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        # Console handler is removed to force all logs exclusively to the UI queue
    return logger


logger = setup_logger()


def add_queue_handler(log_queue):
    handler = QueueHandler(log_queue)
    # The UI handles its own timestamps, so just send the pure message
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
