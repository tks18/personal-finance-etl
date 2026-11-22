"""Dedicated operator read services for status, info, and diagnostic health checks.

Owns
----
- OperatorService: strictly read-only inspection queries for CLI and GUI presentation.
- SystemStatus: pipeline lock state, database file health, latest run and sync records.
- SystemInfo: runtime environment, paths, package versions, and warehouse contract inventory.
- DoctorReport / DoctorCheckResult: actionable health checks for configuration, stores, and providers.

Does not own
-------------
- Pipeline orchestration or execution (owned by application.pipeline).
- Database mutations, DDL, or lock acquisition (owned by infrastructure.warehouse/control_plane).
- Human-facing terminal rendering or rich markup (owned by presentation.cli).
"""

from __future__ import annotations

import importlib.metadata
import os
import sqlite3
import sys
import urllib.request
from dataclasses import dataclass, field
from typing import Literal

import duckdb
from filelock import FileLock

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.infrastructure.preferences import PreferencesManager
from personal_finance_etl.infrastructure.warehouse.contracts import DATA_CONTRACT_REGISTRY

__all__ = [
    "DoctorCheckResult",
    "DoctorReport",
    "OperatorService",
    "SystemInfo",
    "SystemStatus",
]


@dataclass
class DoctorCheckResult:
    """Outcome of an isolated diagnostic health check."""

    name: str
    status: Literal["PASS", "WARN", "FAIL"]
    message: str
    remediation: str | None = None


@dataclass
class DoctorReport:
    """Complete collection of diagnostic checks and aggregate health status."""

    checks: list[DoctorCheckResult] = field(default_factory=list)
    overall_status: Literal["PASS", "WARN", "FAIL"] = "PASS"
    passed_count: int = 0
    warn_count: int = 0
    failed_count: int = 0


@dataclass
class SystemStatus:
    """Point-in-time operational state and execution health (strictly read-only)."""

    is_locked: bool
    lock_path: str
    active_database_base_path: str | None
    duckdb_exists: bool
    duckdb_size_bytes: int | None
    sqlite_exists: bool
    sqlite_size_bytes: int | None
    latest_run_id: str | None
    latest_run_status: str | None
    latest_run_started_at: str | None
    latest_run_finished_at: str | None
    latest_sync_summary: dict[str, object] | None
    stale_runs_count: int
    recovery_required_count: int


@dataclass
class SystemInfo:
    """System metadata, runtime environment, resolved paths, and warehouse inventory."""

    version: str
    python_version: str
    platform: str
    executable: str
    config_path: str | None
    rules_path: str | None
    database_path: str | None
    raw_store_path: str | None
    statements_root: str | None
    household_db_path: str | None
    bronze_tables_count: int
    silver_tables_count: int
    gold_tables_count: int
    warehouse_schemas: list[str]


class OperatorService:
    """Strictly read-only query and diagnostic service for system operators."""

    def __init__(
        self,
        config_path: str | None = None,
        rules_path: str | None = None,
    ) -> None:
        self.config_path = config_path or self._discover_config_path()
        self.rules_path = rules_path or self._discover_rules_path()
        self._cached_settings: Settings | None = None
        self._cached_rules: FinancialRules | None = None

    @classmethod
    def _discover_config_path(cls) -> str | None:
        """Discover configuration file path via preferences, environment, or default paths."""
        prefs = PreferencesManager()
        recent = prefs.get_recent_configs()
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

    @classmethod
    def _discover_rules_path(cls) -> str | None:
        """Discover financial rules file path via preferences, environment, or default paths."""
        prefs = PreferencesManager()
        recent = prefs.get_recent_rules()
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

    def _load_settings_safe(self) -> Settings | None:
        """Safely load settings without throwing unhandled exceptions."""
        if self._cached_settings is not None:
            return self._cached_settings
        if not self.config_path or not os.path.exists(self.config_path):
            return None
        try:
            self._cached_settings = Settings.from_toml(self.config_path)
            return self._cached_settings
        except Exception:
            return None

    def _load_rules_safe(self) -> FinancialRules | None:
        """Safely load financial rules without throwing unhandled exceptions."""
        if self._cached_rules is not None:
            return self._cached_rules
        if not self.rules_path or not os.path.exists(self.rules_path):
            return None
        try:
            self._cached_rules = FinancialRules.from_toml(self.rules_path)
            return self._cached_rules
        except Exception:
            return None

    def get_status(self) -> SystemStatus:
        """Query system status, database health, and latest run telemetry read-only."""
        settings = self._load_settings_safe()
        base_path = settings.database.target_db_base_path if settings else "."
        duckdb_name = settings.database.target_db_name if settings else "Personal_Finance_DB.duckdb"
        sqlite_name = (
            settings.database.raw_document_store_name if settings else "Raw_Documents.sqlite"
        )

        lock_path = os.path.join(base_path, "pipeline.lock")
        is_locked = FileLock(lock_path).is_locked

        duckdb_path = os.path.join(base_path, duckdb_name)
        duckdb_exists = os.path.exists(duckdb_path)
        duckdb_size = os.path.getsize(duckdb_path) if duckdb_exists else None

        sqlite_path = os.path.join(base_path, sqlite_name)
        sqlite_exists = os.path.exists(sqlite_path)
        sqlite_size = os.path.getsize(sqlite_path) if sqlite_exists else None

        latest_run_id: str | None = None
        latest_run_status: str | None = None
        latest_run_started: str | None = None
        latest_run_finished: str | None = None
        latest_sync_summary: dict[str, object] | None = None
        stale_runs_count = 0
        recovery_required_count = 0

        if sqlite_exists:
            try:
                uri = f"file:{os.path.abspath(sqlite_path)}?mode=ro"
                with sqlite3.connect(uri, uri=True, timeout=1.0) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT run_id, status, started_at, finished_at FROM cp_runs ORDER BY started_at DESC LIMIT 1"
                    )
                    row = cursor.fetchone()
                    if row:
                        latest_run_id = str(row[0])
                        latest_run_status = str(row[1]) if row[1] else None
                        latest_run_started = str(row[2]) if row[2] else None
                        latest_run_finished = str(row[3]) if row[3] else None

                    cursor.execute(
                        "SELECT COUNT(*) FROM cp_runs WHERE UPPER(status) IN ('STARTED', 'RUNNING', 'COMMITTING')"
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
                            "SELECT actionable_count, synced_count, healed_count, failed_count, deferred_count, sync_status, created_at "
                            "FROM cp_sync_summaries WHERE run_id = ?",
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

        return SystemStatus(
            is_locked=is_locked,
            lock_path=lock_path,
            active_database_base_path=base_path if settings else None,
            duckdb_exists=duckdb_exists,
            duckdb_size_bytes=duckdb_size,
            sqlite_exists=sqlite_exists,
            sqlite_size_bytes=sqlite_size,
            latest_run_id=latest_run_id,
            latest_run_status=latest_run_status,
            latest_run_started_at=latest_run_started,
            latest_run_finished_at=latest_run_finished,
            latest_sync_summary=latest_sync_summary,
            stale_runs_count=stale_runs_count,
            recovery_required_count=recovery_required_count,
        )

    def get_info(self) -> SystemInfo:
        """Inspect system environment, active paths, and warehouse table counts."""
        settings = self._load_settings_safe()

        try:
            ver = importlib.metadata.version("personal-finance-etl")
        except Exception:
            ver = "11.4.0"

        base_path = settings.database.target_db_base_path if settings else None
        duckdb_name = settings.database.target_db_name if settings else "Personal_Finance_DB.duckdb"
        sqlite_name = (
            settings.database.raw_document_store_name if settings else "Raw_Documents.sqlite"
        )

        db_path = os.path.join(base_path, duckdb_name) if base_path else None
        sqlite_path = os.path.join(base_path, sqlite_name) if base_path else None

        statements_root = (
            str(settings.sources.statements_root)
            if settings and settings.sources and settings.sources.statements_root
            else None
        )
        household_db = (
            str(settings.sources.household_database)
            if settings and settings.sources and settings.sources.household_database
            else None
        )

        bronze_count = sum(
            1 for c in DATA_CONTRACT_REGISTRY if c.physical_table.startswith("bronze.")
        )
        silver_count = sum(
            1 for c in DATA_CONTRACT_REGISTRY if c.physical_table.startswith("silver.")
        )
        gold_count = sum(1 for c in DATA_CONTRACT_REGISTRY if c.physical_table.startswith("gold."))

        return SystemInfo(
            version=ver,
            python_version=sys.version.split()[0],
            platform=sys.platform,
            executable=sys.executable,
            config_path=self.config_path,
            rules_path=self.rules_path,
            database_path=db_path,
            raw_store_path=sqlite_path,
            statements_root=statements_root,
            household_db_path=household_db,
            bronze_tables_count=bronze_count,
            silver_tables_count=silver_count,
            gold_tables_count=gold_count,
            warehouse_schemas=["bronze", "silver", "gold", "meta"],
        )

    def run_doctor(self) -> DoctorReport:
        """Execute actionable health checks, isolating failures without raw tracebacks."""
        checks: list[DoctorCheckResult] = []

        # Check 1: Python Runtime Version
        py_ver = sys.version_info
        if py_ver >= (3, 13):
            checks.append(
                DoctorCheckResult(
                    name="Python Runtime",
                    status="PASS",
                    message=f"Python {py_ver.major}.{py_ver.minor}.{py_ver.micro} is supported (>= 3.13).",
                )
            )
        else:
            checks.append(
                DoctorCheckResult(
                    name="Python Runtime",
                    status="FAIL",
                    message=f"Python {py_ver.major}.{py_ver.minor}.{py_ver.micro} is unsupported.",
                    remediation="Install Python >= 3.13 or activate a compliant virtual environment.",
                )
            )

        # Check 2: Settings Configuration
        if not self.config_path:
            checks.append(
                DoctorCheckResult(
                    name="Settings Configuration",
                    status="FAIL",
                    message="Configuration file not found or unconfigured.",
                    remediation="Provide --config path/to/config.toml or run 'pfetl' to configure your settings.",
                )
            )
        elif not os.path.exists(self.config_path):
            checks.append(
                DoctorCheckResult(
                    name="Settings Configuration",
                    status="FAIL",
                    message=f"Configuration file does not exist at '{self.config_path}'.",
                    remediation="Verify the file path or create a new config.toml.",
                )
            )
        else:
            try:
                Settings.from_toml(self.config_path)
                checks.append(
                    DoctorCheckResult(
                        name="Settings Configuration",
                        status="PASS",
                        message=f"Valid settings at '{self.config_path}'.",
                    )
                )
            except Exception as e:
                checks.append(
                    DoctorCheckResult(
                        name="Settings Configuration",
                        status="FAIL",
                        message=f"Configuration parsing error: {e}",
                        remediation="Inspect and fix the syntax or schema keys in your config.toml.",
                    )
                )

        # Check 3: Financial Rules
        if not self.rules_path:
            checks.append(
                DoctorCheckResult(
                    name="Financial Rules",
                    status="WARN",
                    message="Financial rules TOML not specified; defaults will apply.",
                    remediation="Provide --rules path/to/rules.toml if custom portfolio, tax, or FIRE rules are required.",
                )
            )
        elif not os.path.exists(self.rules_path):
            checks.append(
                DoctorCheckResult(
                    name="Financial Rules",
                    status="FAIL",
                    message=f"Financial rules file does not exist at '{self.rules_path}'.",
                    remediation="Verify the rules file path or provide a valid rules.toml.",
                )
            )
        else:
            try:
                FinancialRules.from_toml(self.rules_path)
                checks.append(
                    DoctorCheckResult(
                        name="Financial Rules",
                        status="PASS",
                        message=f"Valid financial rules at '{self.rules_path}'.",
                    )
                )
            except Exception as e:
                checks.append(
                    DoctorCheckResult(
                        name="Financial Rules",
                        status="FAIL",
                        message=f"Rules parsing error: {e}",
                        remediation="Inspect and fix syntax or policy definitions in your rules.toml.",
                    )
                )

        # Check 4: Evidence Directory / Storage
        settings = self._load_settings_safe()
        if settings and settings.sources and settings.sources.statements_root:
            st_root = str(settings.sources.statements_root)
            if os.path.exists(st_root) and os.path.isdir(st_root):
                checks.append(
                    DoctorCheckResult(
                        name="Evidence Storage",
                        status="PASS",
                        message=f"Statements root accessible at '{st_root}'.",
                    )
                )
            else:
                checks.append(
                    DoctorCheckResult(
                        name="Evidence Storage",
                        status="FAIL",
                        message=f"Statements root not found or inaccessible at '{st_root}'.",
                        remediation=f"Ensure directory '{st_root}' exists and has read permissions.",
                    )
                )
        else:
            checks.append(
                DoctorCheckResult(
                    name="Evidence Storage",
                    status="WARN",
                    message="Statements root is not configured in settings.",
                    remediation="Define sources.statements_root in your config.toml.",
                )
            )

        # Check 5: Database Paths & Control Plane (SQLite)
        if settings:
            base_dir = settings.database.target_db_base_path
            sqlite_file = os.path.join(base_dir, settings.database.raw_document_store_name)
            if not os.path.exists(base_dir):
                checks.append(
                    DoctorCheckResult(
                        name="Control Plane (SQLite)",
                        status="WARN",
                        message=f"Database target directory does not exist at '{base_dir}'.",
                        remediation="The directory will be created automatically on the next 'pfetl run'.",
                    )
                )
            elif not os.path.exists(sqlite_file):
                checks.append(
                    DoctorCheckResult(
                        name="Control Plane (SQLite)",
                        status="WARN",
                        message=f"Raw document store not found at '{sqlite_file}'.",
                        remediation="Run 'pfetl run' to bootstrap and initialize the operational control plane.",
                    )
                )
            else:
                try:
                    uri = f"file:{os.path.abspath(sqlite_file)}?mode=ro"
                    with sqlite3.connect(uri, uri=True, timeout=1.0) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                        tbls = {r[0] for r in cursor.fetchall()}
                        if "cp_runs" in tbls and "cp_artifacts" in tbls:
                            checks.append(
                                DoctorCheckResult(
                                    name="Control Plane (SQLite)",
                                    status="PASS",
                                    message=f"Control plane operational ({len(tbls)} tables).",
                                )
                            )
                        else:
                            checks.append(
                                DoctorCheckResult(
                                    name="Control Plane (SQLite)",
                                    status="WARN",
                                    message="Control plane schema tables partially initialized.",
                                    remediation="Execute 'pfetl run' to converge schemas.",
                                )
                            )
                except Exception as e:
                    checks.append(
                        DoctorCheckResult(
                            name="Control Plane (SQLite)",
                            status="FAIL",
                            message=f"Cannot read control plane database: {e}",
                            remediation="Check database file locks or permissions on Raw_Documents.sqlite.",
                        )
                    )

        # Check 6: Analytical Warehouse (DuckDB)
        if settings:
            base_dir = settings.database.target_db_base_path
            duckdb_file = os.path.join(base_dir, settings.database.target_db_name)
            if not os.path.exists(duckdb_file):
                checks.append(
                    DoctorCheckResult(
                        name="Analytical Warehouse (DuckDB)",
                        status="WARN",
                        message=f"DuckDB database not found at '{duckdb_file}'.",
                        remediation="Run 'pfetl run' to build the analytical lakehouse.",
                    )
                )
            else:
                try:
                    duck_conn = duckdb.connect(duckdb_file, read_only=True)
                    schemas = {
                        r[0]
                        for r in duck_conn.execute(
                            "SELECT schema_name FROM information_schema.schemata"
                        ).fetchall()
                    }
                    duck_conn.close()
                    if {"bronze", "silver", "gold"}.issubset(schemas):
                        checks.append(
                            DoctorCheckResult(
                                name="Analytical Warehouse (DuckDB)",
                                status="PASS",
                                message="DuckDB lakehouse online with bronze, silver, and gold schemas.",
                            )
                        )
                    else:
                        checks.append(
                            DoctorCheckResult(
                                name="Analytical Warehouse (DuckDB)",
                                status="WARN",
                                message=f"DuckDB present but missing schemas: {schemas}",
                                remediation="Run 'pfetl run' to generate missing schemas.",
                            )
                        )
                except Exception as e:
                    checks.append(
                        DoctorCheckResult(
                            name="Analytical Warehouse (DuckDB)",
                            status="FAIL",
                            message=f"DuckDB read error: {e}",
                            remediation="Ensure no exclusive write locks exist on Personal_Finance_DB.duckdb.",
                        )
                    )

        # Check 7: Pipeline Lock & Recovery State
        if settings:
            base_dir = settings.database.target_db_base_path
            lock_path = os.path.join(base_dir, "pipeline.lock")
            if os.path.exists(lock_path) and FileLock(lock_path).is_locked:
                checks.append(
                    DoctorCheckResult(
                        name="Pipeline Lock",
                        status="WARN",
                        message="Pipeline is currently locked by an active process.",
                        remediation="Wait for current run to complete, or remove pipeline.lock if previous process crashed.",
                    )
                )
            else:
                checks.append(
                    DoctorCheckResult(
                        name="Pipeline Lock",
                        status="PASS",
                        message="Pipeline lock is free and available.",
                    )
                )

        # Check 8: Market Data Connectivity
        try:
            req = urllib.request.Request(
                "https://query1.finance.yahoo.com",
                headers={"User-Agent": "pfetl-doctor/1.0"},
            )
            with urllib.request.urlopen(req, timeout=2.5):
                checks.append(
                    DoctorCheckResult(
                        name="Market Data Provider",
                        status="PASS",
                        message="External market data provider (yfinance) is reachable.",
                    )
                )
        except Exception:
            checks.append(
                DoctorCheckResult(
                    name="Market Data Provider",
                    status="WARN",
                    message="Market data provider is unreachable (offline mode).",
                    remediation="Check internet connection if market prices and FX rate syncs are needed.",
                )
            )

        passed = sum(1 for c in checks if c.status == "PASS")
        warns = sum(1 for c in checks if c.status == "WARN")
        fails = sum(1 for c in checks if c.status == "FAIL")

        overall: Literal["PASS", "WARN", "FAIL"] = (
            "FAIL" if fails > 0 else ("WARN" if warns > 0 else "PASS")
        )

        return DoctorReport(
            checks=checks,
            overall_status=overall,
            passed_count=passed,
            warn_count=warns,
            failed_count=fails,
        )
