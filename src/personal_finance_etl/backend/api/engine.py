import multiprocessing
import queue
import threading
from collections.abc import Callable
from typing import Any

from personal_finance_etl.backend.config.settings import PreferencesManager, Settings
from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.pipeline.etl_pipeline import process_wrapper
from personal_finance_etl.backend.utils.models import EngineStatus, LogLevel


class PersonalFinanceEngine:
    """Unified Facade for the entire Personal Finance Backend."""

    def __init__(self) -> None:
        self._prefs = PreferencesManager()

    # --- Configuration Management ---

    def get_recent_configs(self) -> list[str]:
        return self._prefs.get_recent_configs()

    def get_recent_rules(self) -> list[str]:
        return self._prefs.get_recent_rules()

    def add_recent_rules(self, path: str) -> None:
        self._prefs.add_recent_rules(path)

    def validate_config(self, path: str) -> bool:
        try:
            Settings.from_toml(path)
            return True
        except Exception:
            return False

    # --- Database Operations ---

    def snapshot_database(self, config_path: str) -> str | None:
        """Creates a backup snapshot of the DuckDB instance."""
        try:
            cfg = Settings.from_toml(config_path)
            db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)
            return db_manager.snapshot()
        except Exception:
            return None

    # --- Pipeline Execution ---

    def run_pipeline_async(
        self,
        config_path: str,
        rules_path: str,
        on_status: Callable[[EngineStatus], None],
    ) -> None:
        """
        Spawns the multiprocessing ETL pipeline and fires the callback
        whenever a status update is received.
        """
        status_queue: multiprocessing.Queue[EngineStatus | tuple[str, Any | None, float | None]] = (
            multiprocessing.Queue()
        )

        process = multiprocessing.Process(
            target=process_wrapper,
            args=(status_queue, config_path, rules_path),
            daemon=True,
        )
        process.start()

        def _queue_monitor() -> None:
            # Poll as long as process is alive or queue is not empty
            while process.is_alive() or not status_queue.empty():
                try:
                    # Timeout prevents infinite block, allows checking process.is_alive()
                    item = status_queue.get(timeout=0.1)

                    # Convert tuples to EngineStatus for backward compatibility
                    if isinstance(item, tuple):
                        msg, data, prog = item
                        status = EngineStatus(
                            msg=str(msg) if msg else "",
                            data=data,
                            progress=float(prog) if prog is not None else None,
                        )
                        # Infer level
                        if msg:
                            lw = str(msg).lower()
                            if "error" in lw or msg.startswith("Error"):
                                status.level = LogLevel.ERROR
                            elif (
                                "✅" in msg
                                or "complete" in lw
                                or "success" in lw
                                or "✓" in msg
                                or "exported" in lw
                            ):
                                status.level = LogLevel.SUCCESS
                            elif "warning" in lw:
                                status.level = LogLevel.WARNING
                            elif (
                                "fetching" in lw
                                or "loading" in lw
                                or "post-processing" in lw
                                or msg.startswith("[")
                            ):
                                status.level = LogLevel.STEP
                            else:
                                status.level = LogLevel.INFO
                    else:
                        status = item

                    on_status(status)
                except queue.Empty:
                    continue
                except Exception:
                    break

            # After process finishes, ensure we send a completion/fail signal
            # if one wasn't sent naturally by the process.
            if process.exitcode is not None:
                if process.exitcode != 0:
                    on_status(EngineStatus(msg="Process exited abnormally.", data=None, progress=0.0))
                else:
                    on_status(EngineStatus(msg="Process completed cleanly.", data=None, progress=1.0))

        threading.Thread(target=_queue_monitor, daemon=True).start()
