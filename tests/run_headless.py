import queue
import time

from src.config.settings import Settings
from src.pipeline.etl_pipeline import ETLOrchestrator


def main():
    print("Starting Headless ETL Pipeline...")
    q = queue.Queue()
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
