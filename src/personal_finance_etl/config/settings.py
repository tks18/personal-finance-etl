"""Application environment settings and pipeline execution configurations.

Owns
----
- Pipeline environment settings (source databases, output warehouse paths, dependency paths).
- Statement file/folder pattern definitions for statement discovery.
- Evidence-source hashing policy configurations for source change detection.
- Configuration validation ensuring required source directories and files exist.
- Dynamic flattening of settings for database auditing.

Does not own
-------------
- Financial domain policies and rules (owned by config.financial_rules).
- User UI preference persistence on disk (owned by infrastructure.preferences).
- Database connection lifecycle (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import os
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HashPolicy(StrEnum):
    """Evidence hash policy mode determining change detection behavior."""

    NONE = "NONE"
    CONTENT = "CONTENT"


class SourceHashPolicy(BaseModel):
    """Evidence-source hash policy flags for source deduplication across categories."""

    model_config = ConfigDict(extra="forbid")

    household_database: HashPolicy = Field(
        default=HashPolicy.CONTENT,
        description="Hash policy for household SQLite database content verification.",
        json_schema_extra={
            "ui_widget": "choice",
            "options": ["CONTENT", "NONE"],
            "unit": "mode",
        },
    )
    statements: HashPolicy = Field(
        default=HashPolicy.NONE,
        description="Hash policy for broker and fund statements content verification.",
        json_schema_extra={
            "ui_widget": "choice",
            "options": ["CONTENT", "NONE"],
            "unit": "mode",
        },
    )
    reference_data: HashPolicy = Field(
        default=HashPolicy.CONTENT,
        description="Hash policy for reference Excel spreadsheets content verification.",
        json_schema_extra={
            "ui_widget": "choice",
            "options": ["CONTENT", "NONE"],
            "unit": "mode",
        },
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_values(cls, data: Any) -> Any:
        """Coerce boolean and case-insensitive strings to canonical HashPolicy."""
        if isinstance(data, dict):
            dict_data = cast("dict[str, Any]", data)
            coerced: dict[str, Any] = {}
            for k, v in dict_data.items():
                if isinstance(v, bool):
                    coerced[k] = HashPolicy.CONTENT if v else HashPolicy.NONE
                elif isinstance(v, str):
                    upper_v = v.strip().upper()
                    if upper_v in ("TRUE", "CONTENT"):
                        coerced[k] = HashPolicy.CONTENT
                    elif upper_v in ("FALSE", "NONE"):
                        coerced[k] = HashPolicy.NONE
                    else:
                        coerced[k] = v
                else:
                    coerced[k] = v
            return coerced
        return data

    def should_check_hash(self, category: str) -> bool:
        """Evaluate if an evidence stream category requires SHA-256 hash comparison.

        Parameters
        ----------
        category : str
            The evidence stream or category identifier.

        Returns
        -------
        bool
            True if SHA-256 content drift checks should run, False otherwise.
        """
        if category in ("sqlite_source", "household_database"):
            return self.household_database == HashPolicy.CONTENT
        if category in (
            "stock_pl",
            "mf_holdings",
            "stock_orders",
            "mf_orders",
            "us_stock_transactions",
            "statements",
        ):
            return self.statements == HashPolicy.CONTENT
        # Default for reference categories (column_master, mf_isin, benchmark_mapping, etc.)
        return self.reference_data == HashPolicy.CONTENT


class DatabaseSettings(BaseModel):
    """Runtime database and raw store persistence paths."""

    model_config = ConfigDict(extra="forbid")

    target_db_base_path: str = Field(
        default="",
        description="Base directory path where DuckDB and SQLite databases are created and maintained.",
        json_schema_extra={
            "ui_widget": "directory",
            "must_exist": True,
            "placeholder": "Select warehouse database output directory...",
        },
    )
    target_db_name: str = Field(
        default="Personal_Finance_DB.duckdb",
        description="Filename of the primary analytical DuckDB warehouse database.",
        json_schema_extra={
            "ui_widget": "text",
            "placeholder": "Personal_Finance_DB.duckdb",
        },
    )
    raw_document_store_name: str = Field(
        default="Personal_Finance_DB_Raw_Store.sqlite",
        description="Filename of the SQLite raw document and audit store database.",
        json_schema_extra={
            "ui_widget": "text",
            "placeholder": "Personal_Finance_DB_Raw_Store.sqlite",
        },
    )
    disable_file_discoverer: bool = Field(
        default=False,
        description="Skip scanning statements_root on disk and reuse existing raw document store cache.",
        json_schema_extra={
            "ui_widget": "switch",
            "active_label": "Bypassed (Skip Scan)",
            "inactive_label": "Active (Scan Disk)",
        },
    )


class SourcesSettings(BaseModel):
    """The nine frozen evidence sources and location paths."""

    model_config = ConfigDict(extra="forbid")

    household_database: str = Field(
        default="",
        description="Path to household expense SQLite database directory or file.",
        json_schema_extra={
            "ui_widget": "directory",
            "must_exist": True,
            "kind": "sqlite",
            "placeholder": "Select MoneyManager database folder or .sqlite file...",
        },
    )
    statements_root: str = Field(
        default="",
        description="Root directory containing broker and fund statement subdirectories.",
        json_schema_extra={
            "ui_widget": "directory",
            "must_exist": True,
            "kind": "directory",
            "placeholder": "Select statements root directory...",
        },
    )
    column_master: str = Field(
        default="",
        description="Path to column mapping and canonical schema master Excel file.",
        json_schema_extra={
            "ui_widget": "file",
            "must_exist": True,
            "kind": "excel",
            "placeholder": "Select column_master.xlsx...",
        },
    )
    mutual_fund_instrument_mapping: str = Field(
        default="",
        description="Path to mutual fund instrument ISIN and scheme mapping Excel file.",
        json_schema_extra={
            "ui_widget": "file",
            "must_exist": True,
            "kind": "excel",
            "placeholder": "Select mutual_fund_instrument_mapping.xlsx...",
        },
    )
    instrument_master: str = Field(
        default="",
        description="Path to instrument taxonomy, asset class, and security master Excel file.",
        json_schema_extra={
            "ui_widget": "file",
            "must_exist": True,
            "kind": "excel",
            "placeholder": "Select instrument_master.xlsx...",
        },
    )
    benchmark_master: str = Field(
        default="",
        description="Path to benchmark ticker indices mapping Excel file.",
        json_schema_extra={
            "ui_widget": "file",
            "must_exist": True,
            "kind": "excel",
            "placeholder": "Select benchmark_master.xlsx...",
        },
    )
    currency_reference: str = Field(
        default="",
        description="Path to historical currency exchange rate reference Excel file.",
        json_schema_extra={
            "ui_widget": "file",
            "must_exist": True,
            "kind": "excel",
            "placeholder": "Select currency_reference.xlsx...",
        },
    )
    financial_year_parameters: str = Field(
        default="",
        description="Path to financial year parameters and inflation assumptions Excel file.",
        json_schema_extra={
            "ui_widget": "file",
            "must_exist": True,
            "kind": "excel",
            "placeholder": "Select financial_year_parameters.xlsx...",
        },
    )
    opening_balances: str = Field(
        default="",
        description="Path to portfolio opening balances and historic capital gains Excel file.",
        json_schema_extra={
            "ui_widget": "file",
            "must_exist": True,
            "kind": "excel",
            "placeholder": "Select opening_balances.xlsx...",
        },
    )


class StatementPatternsSettings(BaseModel):
    """Folder and filename keyword patterns for statement categorization."""

    model_config = ConfigDict(extra="forbid")

    stock_pl: str = Field(
        default="Stock PL Statements",
        description="Folder or file keyword pattern for stock P&L statements.",
        json_schema_extra={
            "ui_widget": "text",
            "placeholder": "e.g. Stock PL Statements",
        },
    )
    mf_holdings: str = Field(
        default="Mutual Funds - Holdings",
        description="Folder or file keyword pattern for mutual fund holdings statements.",
        json_schema_extra={
            "ui_widget": "text",
            "placeholder": "e.g. Mutual Funds - Holdings",
        },
    )
    stock_orders: str = Field(
        default="Stock - Orders",
        description="Folder or file keyword pattern for stock order transaction statements.",
        json_schema_extra={
            "ui_widget": "text",
            "placeholder": "e.g. Stock - Orders",
        },
    )
    mf_orders: str = Field(
        default="Mutual Funds - Orders",
        description="Folder or file keyword pattern for mutual fund order transaction statements.",
        json_schema_extra={
            "ui_widget": "text",
            "placeholder": "e.g. Mutual Funds - Orders",
        },
    )
    us_stock_transactions: list[str] = Field(
        default_factory=lambda: ["IND Money (US Stocks)", "Transaction Reports"],
        description="Folder or file keyword patterns for US stock transaction statements.",
        json_schema_extra={
            "ui_widget": "list",
            "placeholder": "Comma-separated patterns...",
        },
    )


class PerformanceSettings(BaseModel):
    """Runtime parallelism and concurrency parameters."""

    model_config = ConfigDict(extra="forbid")

    market_workers: int = Field(
        default=8,
        ge=1,
        le=64,
        description="Number of parallel worker processes for market data extraction.",
        json_schema_extra={
            "ui_widget": "int",
            "min": 1,
            "max": 64,
            "step": 1,
            "unit": "workers",
        },
    )
    isin_workers: int = Field(
        default=4,
        ge=1,
        le=32,
        description="Maximum number of parallel worker processes for ISIN quant simulation.",
        json_schema_extra={
            "ui_widget": "int",
            "min": 1,
            "max": 32,
            "step": 1,
            "unit": "workers",
        },
    )
    duckdb_threads: int = Field(
        default=4,
        ge=1,
        le=64,
        description="Number of worker threads allocated to DuckDB analytical query processing.",
        json_schema_extra={
            "ui_widget": "int",
            "min": 1,
            "max": 64,
            "step": 1,
            "unit": "threads",
        },
    )


class MarketDataSettings(BaseModel):
    """Provider fetch windows, download retries, and price acceptance thresholds."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    fetch_buffer_days: int = Field(
        default=15,
        ge=0,
        le=90,
        description="Calendar buffer days added to market data fetch start date to ensure overlap.",
        json_schema_extra={
            "ui_widget": "int",
            "min": 0,
            "max": 90,
            "step": 1,
            "unit": "days",
        },
    )
    max_download_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum download attempts for Yahoo Finance market data with backoff.",
        json_schema_extra={
            "ui_widget": "int",
            "min": 1,
            "max": 10,
            "step": 1,
            "unit": "retries",
        },
    )
    anomalous_drop_threshold: float = Field(
        default=-0.50,
        ge=-1.0,
        le=0.0,
        alias="benchmark_anomalous_drop_threshold",
        description="Single-day benchmark decline threshold for anomaly warning (-0.50 default).",
        json_schema_extra={
            "ui_widget": "float",
            "min": -1.0,
            "max": 0.0,
            "step": 0.05,
            "unit": "ratio",
        },
    )
    fx_backward_fill_days: int = Field(
        default=30,
        ge=0,
        le=365,
        description="Maximum backward calendar days to search for valid FX rates on holidays/weekends.",
        json_schema_extra={
            "ui_widget": "int",
            "min": 0,
            "max": 365,
            "step": 5,
            "unit": "days",
        },
    )
    benchmark_max_staleness_days: int = Field(
        default=7,
        ge=0,
        le=60,
        description="Maximum calendar days a benchmark price quote can remain stale before rejection.",
        json_schema_extra={
            "ui_widget": "int",
            "min": 0,
            "max": 60,
            "step": 1,
            "unit": "days",
        },
    )
    us_price_max_staleness_days: int = Field(
        default=7,
        ge=0,
        le=60,
        description="Maximum calendar days a US stock price quote can remain stale before rejection.",
        json_schema_extra={
            "ui_widget": "int",
            "min": 0,
            "max": 60,
            "step": 1,
            "unit": "days",
        },
    )


class ObservabilitySettings(BaseModel):
    """Forensic logging and observability parameters."""

    model_config = ConfigDict(extra="forbid")

    logs_directory: str = Field(
        default="logs/runs",
        description="Subdirectory or absolute path for forensic execution logs and traces.",
        json_schema_extra={
            "ui_widget": "text",
            "placeholder": "logs/runs",
        },
    )
    retain_last_n_runs: int = Field(
        default=12,
        ge=1,
        le=100,
        description="Maximum number of historical pipeline runs to retain logs for before pruning.",
        json_schema_extra={
            "ui_widget": "int",
            "min": 1,
            "max": 100,
            "step": 1,
            "unit": "runs",
        },
    )
    max_age_days: int | None = Field(
        default=30,
        ge=1,
        le=365,
        description="Maximum age threshold in days before execution logs and traces are pruned.",
        json_schema_extra={
            "ui_widget": "int",
            "min": 1,
            "max": 365,
            "step": 5,
            "unit": "days",
        },
    )


def _flatten_settings_to_records(
    node: object, path: list[str], records: list[dict[str, str]]
) -> None:
    """Recursively traverse the settings tree to extract flat key-value pairs."""
    if isinstance(node, dict):
        dict_node = cast("dict[str, object]", node)
        for k, v in dict_node.items():
            _flatten_settings_to_records(v, path + [k], records)
    elif isinstance(node, list):
        list_node = cast(list[object], node)
        for i, v in enumerate(list_node):
            _flatten_settings_to_records(v, path + [str(i)], records)
    else:
        group = "General"
        if len(path) > 1:
            group = path[0].capitalize()
            key = "_".join(path[1:])
        elif path:
            key = path[0]
        else:
            key = "Unknown"

        records.append(
            {
                "Setting_Group": group,
                "Setting_Key": key,
                "Setting_Value": str(node) if node is not None else "",
            }
        )


class Settings(BaseModel):
    """Execution environment settings, warehouse paths, and dependency file locations."""

    model_config = ConfigDict(extra="forbid")

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    sources: SourcesSettings = Field(default_factory=SourcesSettings)
    statement_patterns: StatementPatternsSettings = Field(default_factory=StatementPatternsSettings)
    hash_policy: SourceHashPolicy = Field(default_factory=SourceHashPolicy)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    market_data: MarketDataSettings = Field(default_factory=MarketDataSettings)

    def resolve_logs_dir(self) -> Path:
        """Resolve the active logs directory path against target base path if relative.

        Returns
        -------
        Path
            Absolute or fully qualified Path to the forensic log directory.
        """
        raw_path = Path(self.observability.logs_directory)
        if raw_path.is_absolute() or not self.database.target_db_base_path:
            return raw_path
        return Path(self.database.target_db_base_path) / raw_path

    @classmethod
    def from_toml(cls, filepath: str | os.PathLike[str]) -> Settings:
        """Load a TOML configuration and return a Settings instance.

        Parameters
        ----------
        filepath : str | os.PathLike[str]
            Path to the configuration TOML file.

        Returns
        -------
        Settings
            Loaded Settings instance, or default Settings if the file does not exist.
        """
        path_str = os.fspath(filepath)
        if not os.path.exists(path_str):
            return cls()

        with open(path_str, "rb") as f:
            data = tomllib.load(f)

        return cls(**data)

    def validate_config(self) -> None:
        """Validate that all necessary files and folders exist before starting.

        Raises
        ------
        FileNotFoundError
            If any required directory or file is missing or invalid.
        """
        required_dirs = [
            ("household_database", self.sources.household_database),
            ("statements_root", self.sources.statements_root),
        ]

        required_files = [
            ("column_master", self.sources.column_master),
            ("mutual_fund_instrument_mapping", self.sources.mutual_fund_instrument_mapping),
            ("instrument_master", self.sources.instrument_master),
            ("benchmark_master", self.sources.benchmark_master),
            ("financial_year_parameters", self.sources.financial_year_parameters),
            ("opening_balances", self.sources.opening_balances),
            ("currency_reference", self.sources.currency_reference),
        ]

        errors: list[str] = []

        if not self.database.target_db_base_path:
            errors.append("target_db_base_path is empty in configuration.")

        for name, path in required_dirs:
            if not path or not os.path.isdir(path):
                errors.append(f"Directory {name} not found: '{path}'")

        for name, path in required_files:
            if not path or not os.path.isfile(path):
                errors.append(f"File {name} not found: '{path}'")

        if errors:
            raise FileNotFoundError(
                "Configuration Validation Failed. The following paths are missing or invalid:\n"
                + "\n".join(errors)
            )

    def export_to_db_records(self) -> list[dict[str, str]]:
        """Flatten the settings dynamically into a list of records for database auditing.

        Returns
        -------
        list[dict[str, str]]
            List of Setting records with Setting_Group, Setting_Key, and Setting_Value.
        """
        records: list[dict[str, str]] = []
        data = self.model_dump()
        _flatten_settings_to_records(data, [], records)
        return records
