import queue
import time

from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.application import EngineStatusMessage


class LoggerQueue:
    def __init__(self) -> None:
        self._q: queue.Queue[EngineStatusMessage] = queue.Queue()

    def put(
        self, status: EngineStatusMessage, block: bool = True, timeout: float | None = None
    ) -> None:
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
