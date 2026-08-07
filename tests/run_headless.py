import queue
import time

from src.config.settings import Settings
from src.pipeline.etl_pipeline import ETLOrchestrator
from src.utils.models import EngineStatus


class LoggerQueue:
    def __init__(self) -> None:
        self._q: queue.Queue[EngineStatus] = queue.Queue()

    def put(self, status: EngineStatus, block: bool = True, timeout: float | None = None) -> None:
        self._q.put(status, block=block, timeout=timeout)


def main():
    print("Starting Headless ETL Pipeline...")
    q = LoggerQueue()
    start_time = time.time()

    try:
        cfg = Settings.from_toml("config.toml")

        # Run in main thread for profiling
        orchestrator = ETLOrchestrator(cfg, q)
        orchestrator.run()
    except Exception as e:
        print(f"Error: {e}")
        raise e

    end_time = time.time()
    print(f"Pipeline completed in {end_time - start_time:.2f} seconds.")


if __name__ == "__main__":
    main()
