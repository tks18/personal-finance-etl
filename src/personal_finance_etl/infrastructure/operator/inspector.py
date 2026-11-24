"""Local file, database, and network inspector for operator diagnostics and telemetry.

Owns
----
- LocalOperatorInspector implementation satisfying the OperatorInspector protocol.
- Direct read-only database connections (SQLite control plane and DuckDB analytical lakehouse).
- File system checks (lock status, sizes, paths) and network probing for market providers.
- Resolution of default/recent configuration and rules paths via PreferencesManager.

Does not own
-------------
- Operator health evaluation logic or remediation determination (owned by application.operator).
- Presentation rendering or user command handling (owned by presentation.*).
"""

from __future__ import annotations

import os
import socket
import sqlite3
import urllib.error
import urllib.request

import duckdb
from filelock import FileLock

from personal_finance_etl.contracts.operator import (
    ControlPlaneHealth,
    ControlPlaneInspection,
    StorageInspection,
    WarehouseHealth,
    WarehouseInventory,
)
from personal_finance_etl.infrastructure.preferences import PreferencesManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
)

__all__ = ["LocalOperatorInspector"]


class LocalOperatorInspector:
    """Concrete local implementation of the OperatorInspector protocol."""

    def __init__(self, preferences_manager: PreferencesManager | None = None) -> None:
        self._prefs = preferences_manager or PreferencesManager()

    def discover_config_path(self) -> str | None:
        """Discover configuration file path via preferences, environment, or default paths."""
        recent = self._prefs.get_recent_configs()
        if recent and os.path.exists(recent[0]):
            return recent[0]

        env_path = os.getenv("PFETL_CONFIG")
        if env_path and os.path.exists(env_path):
            return env_path

        candidates = ["config.toml", "config/config.toml", ".config/config.toml"]
        for cand in candidates:
            if os.path.exists(cand):
                return cand
        return None

    def discover_rules_path(self) -> str | None:
        """Discover financial rules file path via preferences, environment, or default paths."""
        recent = self._prefs.get_recent_rules()
        if recent and os.path.exists(recent[0]):
            return recent[0]

        env_path = os.getenv("PFETL_RULES")
        if env_path and os.path.exists(env_path):
            return env_path

        candidates = ["rules.toml", "config/rules.toml", ".config/rules.toml"]
        for cand in candidates:
            if os.path.exists(cand):
                return cand
        return None

    def inspect_storage(
        self, base_path: str, duckdb_name: str, sqlite_name: str
    ) -> StorageInspection:
        """Inspect pipeline lock and database file health read-only."""
        lock_path = os.path.join(base_path, "pipeline.lock")
        is_locked = FileLock(lock_path).is_locked

        duckdb_path = os.path.join(base_path, duckdb_name)
        duckdb_exists = os.path.exists(duckdb_path)
        duckdb_size = os.path.getsize(duckdb_path) if duckdb_exists else None

        sqlite_path = os.path.join(base_path, sqlite_name)
        sqlite_exists = os.path.exists(sqlite_path)
        sqlite_size = os.path.getsize(sqlite_path) if sqlite_exists else None

        return StorageInspection(
            lock_path=lock_path,
            is_locked=is_locked,
            duckdb_exists=duckdb_exists,
            duckdb_size_bytes=duckdb_size,
            sqlite_exists=sqlite_exists,
            sqlite_size_bytes=sqlite_size,
        )

    def inspect_control_plane(self, sqlite_path: str) -> ControlPlaneInspection:
        """Query latest execution telemetry and sync summary from SQLite control plane."""
        latest_run_id: str | None = None
        latest_run_status: str | None = None
        latest_run_started: str | None = None
        latest_run_finished: str | None = None
        latest_sync_summary: dict[str, object] | None = None
        stale_runs_count = 0
        recovery_required_count = 0

        if os.path.exists(sqlite_path):
            try:
                uri = f"file:{os.path.abspath(sqlite_path)}?mode=ro"
                with sqlite3.connect(uri, uri=True, timeout=1.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT run_id, status, started_at, finished_at "
                        "FROM cp_runs ORDER BY started_at DESC LIMIT 1"
                    )
                    row = cursor.fetchone()
                    if row:
                        latest_run_id = str(row[0])
                        latest_run_status = str(row[1]) if row[1] else None
                        latest_run_started = str(row[2]) if row[2] else None
                        latest_run_finished = str(row[3]) if row[3] else None

                    cursor.execute(
                        "SELECT COUNT(*) FROM cp_runs "
                        "WHERE UPPER(status) IN ('STARTED', 'RUNNING', 'COMMITTING')"
                    )
                    stale_row = cursor.fetchone()
                    stale_runs_count = int(stale_row[0]) if stale_row else 0

                    cursor.execute(
                        "SELECT COUNT(*) FROM cp_runs WHERE UPPER(status) = 'RECOVERY_REQUIRED'"
                    )
                    rec_row = cursor.fetchone()
                    recovery_required_count = int(rec_row[0]) if rec_row else 0

                    if latest_run_id:
                        cursor.execute(
                            "SELECT actionable_count, synced_count, healed_count, "
                            "failed_count, deferred_count, sync_status, created_at "
                            "FROM cp_run_sync_summaries WHERE run_id = ?",
                            (latest_run_id,),
                        )
                        s_row = cursor.fetchone()
                        if s_row:
                            latest_sync_summary = {
                                "actionable": s_row[0],
                                "synced": s_row[1],
                                "healed": s_row[2],
                                "failed": s_row[3],
                                "deferred": s_row[4],
                                "status": s_row[5],
                                "created_at": s_row[6],
                            }
            except Exception:
                pass

        return ControlPlaneInspection(
            latest_run_id=latest_run_id,
            latest_run_status=latest_run_status,
            latest_run_started_at=latest_run_started,
            latest_run_finished_at=latest_run_finished,
            latest_sync_summary=latest_sync_summary,
            stale_runs_count=stale_runs_count,
            recovery_required_count=recovery_required_count,
        )

    def inspect_warehouse_inventory(self) -> WarehouseInventory:
        """Inspect registered warehouse contracts and active schema inventory."""
        bronze_count = len(BRONZE_CONTRACT_REGISTRY)
        silver_count = sum(
            1 for c in DATA_CONTRACT_REGISTRY if c.physical_table.startswith("silver.")
        )
        gold_count = sum(1 for c in DATA_CONTRACT_REGISTRY if c.physical_table.startswith("gold."))

        return WarehouseInventory(
            bronze_tables_count=bronze_count,
            silver_tables_count=silver_count,
            gold_tables_count=gold_count,
            warehouse_schemas=["bronze", "silver", "gold", "meta"],
        )

    def check_control_plane_health(self, base_dir: str, sqlite_name: str) -> ControlPlaneHealth:
        """Check SQLite control plane directory, database accessibility, and tables."""
        base_exists = os.path.exists(base_dir)
        sqlite_file = os.path.join(base_dir, sqlite_name)
        file_exists = os.path.exists(sqlite_file)

        if not base_exists or not file_exists:
            return ControlPlaneHealth(
                base_dir_exists=base_exists,
                file_exists=file_exists,
                is_readable=False,
                table_names=set(),
            )

        try:
            uri = f"file:{os.path.abspath(sqlite_file)}?mode=ro"
            with sqlite3.connect(uri, uri=True, timeout=1.0) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tbls = {r[0] for r in cursor.fetchall()}
                return ControlPlaneHealth(
                    base_dir_exists=True,
                    file_exists=True,
                    is_readable=True,
                    table_names=tbls,
                )
        except Exception as e:
            return ControlPlaneHealth(
                base_dir_exists=True,
                file_exists=True,
                is_readable=False,
                table_names=set(),
                error_message=str(e),
            )

    def check_warehouse_health(self, base_dir: str, duckdb_name: str) -> WarehouseHealth:
        """Check DuckDB warehouse file accessibility and canonical schemas."""
        duckdb_file = os.path.join(base_dir, duckdb_name)
        if not os.path.exists(duckdb_file):
            return WarehouseHealth(
                file_exists=False,
                is_readable=False,
                schema_names=set(),
            )

        try:
            duck_conn = duckdb.connect(duckdb_file, read_only=True)
            schemas = {
                r[0]
                for r in duck_conn.execute(
                    "SELECT schema_name FROM information_schema.schemata"
                ).fetchall()
            }
            duck_conn.close()
            return WarehouseHealth(
                file_exists=True,
                is_readable=True,
                schema_names=schemas,
            )
        except Exception as e:
            return WarehouseHealth(
                file_exists=True,
                is_readable=False,
                schema_names=set(),
                error_message=str(e),
            )

    def probe_market_data_provider(self, timeout: float = 3.0) -> bool:
        """Probe external market data provider connectivity without throwing."""
        endpoints = [
            "https://fc.yahoo.com",
            "https://query1.finance.yahoo.com/v8/finance/chart/%5ENSEI",
            "https://query2.finance.yahoo.com/v8/finance/chart/%5ENSEI",
            "https://finance.yahoo.com",
        ]
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
        }
        per_req_timeout = min(timeout, 2.0)
        for url in endpoints:
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=per_req_timeout) as resp:
                    if resp.status in (200, 301, 302):
                        return True
            except urllib.error.HTTPError:
                # An HTTP error response confirms network reachability to host
                return True
            except Exception:  # pylint: disable=broad-exception-caught
                continue

        # Fallback TCP socket connection probe to port 443
        hosts = ("query1.finance.yahoo.com", "query2.finance.yahoo.com", "finance.yahoo.com")
        for host in hosts:
            try:
                with socket.create_connection((host, 443), timeout=per_req_timeout):
                    return True
            except Exception:  # pylint: disable=broad-exception-caught
                continue

        return False
