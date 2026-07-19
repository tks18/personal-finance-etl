import sys
import queue
import time
from src.pipeline.etl_pipeline import run_pipeline

def main():
    print("Starting Headless ETL Pipeline...")
    q = queue.Queue()
    start_time = time.time()
    
    try:
        from src.config.settings import load_config
        cfg = load_config("config.toml")
        
        # Run in main thread for profiling
        run_pipeline(q, cfg)
    except Exception as e:
        print(f"Error: {e}")
        raise e
        
    end_time = time.time()
    print(f"Pipeline completed in {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    main()
