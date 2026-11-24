"""Dedicated operator read services for status, info, and diagnostic health checks.

Owns
----
- OperatorService: strictly read-only inspection orchestration for CLI and GUI presentation.
- SystemStatus: pipeline lock state, database file health, latest run and sync records.
- SystemInfo: runtime environment, paths, package versions, and warehouse contract inventory.
- DoctorReport / DoctorCheckResult: actionable health checks for configuration, stores, and providers.

Does not own
-------------
- Concrete database queries or DDL (owned by infrastructure.warehouse/control_plane).
- Direct network probing, filesystem operations, or lock inspection (owned by infrastructure.operator).
- Pipeline orchestration or execution (owned by application.pipeline).
- Human-facing terminal rendering or rich markup (owned by presentation.cli).
"""

from __future__ import annotations

import importlib.metadata
import os
import sys
from dataclasses import dataclass, field
from typing import Literal

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.operator import OperatorInspector

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

    checks: list[DoctorCheckResult] = field(default_factory=list[DoctorCheckResult])
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
        inspector: OperatorInspector,
        config_path: str | None = None,
        rules_path: str | None = None,
    ) -> None:
        self._inspector = inspector
        self.config_path = config_path or self._inspector.discover_config_path()
        self.rules_path = rules_path or self._inspector.discover_rules_path()
        self._cached_settings: Settings | None = None
        self._cached_rules: FinancialRules | None = None

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

        storage = self._inspector.inspect_storage(base_path, duckdb_name, sqlite_name)
        sqlite_path = os.path.join(base_path, sqlite_name)
        cp = self._inspector.inspect_control_plane(sqlite_path)

        return SystemStatus(
            is_locked=storage.is_locked,
            lock_path=storage.lock_path,
            active_database_base_path=base_path if settings else None,
            duckdb_exists=storage.duckdb_exists,
            duckdb_size_bytes=storage.duckdb_size_bytes,
            sqlite_exists=storage.sqlite_exists,
            sqlite_size_bytes=storage.sqlite_size_bytes,
            latest_run_id=cp.latest_run_id,
            latest_run_status=cp.latest_run_status,
            latest_run_started_at=cp.latest_run_started_at,
            latest_run_finished_at=cp.latest_run_finished_at,
            latest_sync_summary=cp.latest_sync_summary,
            stale_runs_count=cp.stale_runs_count,
            recovery_required_count=cp.recovery_required_count,
        )

    def get_info(self) -> SystemInfo:
        """Inspect system environment, active paths, and warehouse table counts."""
        settings = self._load_settings_safe()

        try:
            ver = importlib.metadata.version("personal-finance-etl")
        except Exception:
            ver = "unknown"

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

        inventory = self._inspector.inspect_warehouse_inventory()

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
            bronze_tables_count=inventory.bronze_tables_count,
            silver_tables_count=inventory.silver_tables_count,
            gold_tables_count=inventory.gold_tables_count,
            warehouse_schemas=inventory.warehouse_schemas,
        )

    @staticmethod
    def _check_runtime() -> DoctorCheckResult:
        py_ver = sys.version_info
        if py_ver >= (3, 13):
            return DoctorCheckResult(
                name="Python Runtime",
                status="PASS",
                message=f"Python {py_ver.major}.{py_ver.minor}.{py_ver.micro} is supported (>= 3.13).",
            )
        return DoctorCheckResult(
            name="Python Runtime",
            status="FAIL",
            message=f"Python {py_ver.major}.{py_ver.minor}.{py_ver.micro} is unsupported.",
            remediation="Install Python >= 3.13 or activate a compliant virtual environment.",
        )

    def _check_settings(self) -> DoctorCheckResult:
        if not self.config_path:
            return DoctorCheckResult(
                name="Settings Configuration",
                status="FAIL",
                message="Configuration file not found or unconfigured.",
                remediation="Provide --config path/to/config.toml or run 'pfetl' to configure your settings.",
            )
        if not os.path.exists(self.config_path):
            return DoctorCheckResult(
                name="Settings Configuration",
                status="FAIL",
                message=f"Configuration file does not exist at '{self.config_path}'.",
                remediation="Verify the file path or create a new config.toml.",
            )
        try:
            Settings.from_toml(self.config_path)
            return DoctorCheckResult(
                name="Settings Configuration",
                status="PASS",
                message=f"Valid settings at '{self.config_path}'.",
            )
        except Exception as e:
            return DoctorCheckResult(
                name="Settings Configuration",
                status="FAIL",
                message=f"Configuration parsing error: {e}",
                remediation="Inspect and fix the syntax or schema keys in your config.toml.",
            )

    def _check_rules(self) -> DoctorCheckResult:
        if not self.rules_path:
            return DoctorCheckResult(
                name="Financial Rules",
                status="WARN",
                message="Financial rules TOML not specified; defaults will apply.",
                remediation="Provide --rules path/to/rules.toml if custom portfolio, tax, or FIRE rules are required.",
            )
        if not os.path.exists(self.rules_path):
            return DoctorCheckResult(
                name="Financial Rules",
                status="FAIL",
                message=f"Financial rules file does not exist at '{self.rules_path}'.",
                remediation="Verify the rules file path or provide a valid rules.toml.",
            )
        try:
            FinancialRules.from_toml(self.rules_path)
            return DoctorCheckResult(
                name="Financial Rules",
                status="PASS",
                message=f"Valid financial rules at '{self.rules_path}'.",
            )
        except Exception as e:
            return DoctorCheckResult(
                name="Financial Rules",
                status="FAIL",
                message=f"Rules parsing error: {e}",
                remediation="Inspect and fix syntax or policy definitions in your rules.toml.",
            )

    @staticmethod
    def _check_evidence(settings: Settings | None) -> DoctorCheckResult:
        if settings and settings.sources and settings.sources.statements_root:
            st_root = str(settings.sources.statements_root)
            if os.path.exists(st_root) and os.path.isdir(st_root):
                return DoctorCheckResult(
                    name="Evidence Storage",
                    status="PASS",
                    message=f"Statements root accessible at '{st_root}'.",
                )
            return DoctorCheckResult(
                name="Evidence Storage",
                status="FAIL",
                message=f"Statements root not found or inaccessible at '{st_root}'.",
                remediation=f"Ensure directory '{st_root}' exists and has read permissions.",
            )
        return DoctorCheckResult(
            name="Evidence Storage",
            status="WARN",
            message="Statements root is not configured in settings.",
            remediation="Define sources.statements_root in your config.toml.",
        )

    def _check_control_plane(self, settings: Settings | None) -> DoctorCheckResult | None:
        if not settings:
            return None
        base_dir = settings.database.target_db_base_path
        sqlite_file = os.path.join(base_dir, settings.database.raw_document_store_name)
        health = self._inspector.check_control_plane_health(
            base_dir, settings.database.raw_document_store_name
        )
        if not health.base_dir_exists:
            return DoctorCheckResult(
                name="Control Plane (SQLite)",
                status="WARN",
                message=f"Database target directory does not exist at '{base_dir}'.",
                remediation="The directory will be created automatically on the next 'pfetl run'.",
            )
        if not health.file_exists:
            return DoctorCheckResult(
                name="Control Plane (SQLite)",
                status="WARN",
                message=f"Raw document store not found at '{sqlite_file}'.",
                remediation="Run 'pfetl run' to bootstrap and initialize the operational control plane.",
            )
        if health.error_message:
            return DoctorCheckResult(
                name="Control Plane (SQLite)",
                status="FAIL",
                message=f"Cannot read control plane database: {health.error_message}",
                remediation="Check database file locks or permissions on Raw_Documents.sqlite.",
            )
        required_cp_tables = {"cp_runs", "cp_file_registry", "cp_artifact_run_events"}
        if required_cp_tables.issubset(health.table_names):
            return DoctorCheckResult(
                name="Control Plane (SQLite)",
                status="PASS",
                message=f"Control plane operational ({len(health.table_names)} tables).",
            )
        return DoctorCheckResult(
            name="Control Plane (SQLite)",
            status="WARN",
            message="Control plane schema tables partially initialized.",
            remediation="Execute 'pfetl run' to converge schemas.",
        )

    def _check_warehouse(self, settings: Settings | None) -> DoctorCheckResult | None:
        if not settings:
            return None
        base_dir = settings.database.target_db_base_path
        duckdb_file = os.path.join(base_dir, settings.database.target_db_name)
        health = self._inspector.check_warehouse_health(base_dir, settings.database.target_db_name)
        if not health.file_exists:
            return DoctorCheckResult(
                name="Analytical Warehouse (DuckDB)",
                status="WARN",
                message=f"DuckDB database not found at '{duckdb_file}'.",
                remediation="Run 'pfetl run' to build the analytical lakehouse.",
            )
        if health.error_message:
            return DoctorCheckResult(
                name="Analytical Warehouse (DuckDB)",
                status="FAIL",
                message=f"DuckDB read error: {health.error_message}",
                remediation="Ensure no exclusive write locks exist on Personal_Finance_DB.duckdb.",
            )
        if {"bronze", "silver", "gold"}.issubset(health.schema_names):
            return DoctorCheckResult(
                name="Analytical Warehouse (DuckDB)",
                status="PASS",
                message="DuckDB lakehouse online with bronze, silver, and gold schemas.",
            )
        return DoctorCheckResult(
            name="Analytical Warehouse (DuckDB)",
            status="WARN",
            message=f"DuckDB present but missing schemas: {health.schema_names}",
            remediation="Run 'pfetl run' to generate missing schemas.",
        )

    def _check_pipeline_lock(self, settings: Settings | None) -> DoctorCheckResult | None:
        if not settings:
            return None
        base_dir = settings.database.target_db_base_path
        storage = self._inspector.inspect_storage(
            base_dir,
            settings.database.target_db_name,
            settings.database.raw_document_store_name,
        )
        if storage.is_locked:
            return DoctorCheckResult(
                name="Pipeline Lock",
                status="WARN",
                message="Pipeline is currently locked by an active process.",
                remediation="Wait for current run to complete, or remove pipeline.lock if previous process crashed.",
            )
        return DoctorCheckResult(
            name="Pipeline Lock",
            status="PASS",
            message="Pipeline lock is free and available.",
        )

    def _check_market_data(self) -> DoctorCheckResult:
        if self._inspector.probe_market_data_provider():
            return DoctorCheckResult(
                name="Market Data Provider",
                status="PASS",
                message="External market data provider (yfinance) is reachable.",
            )
        return DoctorCheckResult(
            name="Market Data Provider",
            status="WARN",
            message="Market data provider is unreachable (offline mode).",
            remediation="Check internet connection if market prices and FX rate syncs are needed.",
        )

    def run_doctor(self) -> DoctorReport:
        """Execute actionable health checks, isolating failures without raw tracebacks."""
        settings = self._load_settings_safe()
        checks: list[DoctorCheckResult] = [
            self._check_runtime(),
            self._check_settings(),
            self._check_rules(),
            self._check_evidence(settings),
        ]

        cp_check = self._check_control_plane(settings)
        if cp_check:
            checks.append(cp_check)

        wh_check = self._check_warehouse(settings)
        if wh_check:
            checks.append(wh_check)

        lock_check = self._check_pipeline_lock(settings)
        if lock_check:
            checks.append(lock_check)

        checks.append(self._check_market_data())

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
