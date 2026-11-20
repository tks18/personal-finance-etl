"""Application environment settings and pipeline execution configurations.

Owns
----
- Pipeline environment settings (source databases, output warehouse paths, dependency paths).
- File hashing policy configurations for source deduplication.
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
from pathlib import Path
from typing import cast

from pydantic import BaseModel, ConfigDict, Field

from personal_finance_etl.config.capabilities import CapabilitySelection


class FileHashPolicy(BaseModel):
    """File content hashing policy flags for source deduplication across format categories."""

    csv: bool = True
    excel: bool = False
    sqlite: bool = False


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
    """Execution environment settings, warehouse paths, and runtime configurations."""

    model_config = ConfigDict(extra="ignore")

    TARGET_DB_BASE_PATH: str = ""
    TARGET_DB_NAME: str = "Personal_Finance_DB.duckdb"

    # Raw Store Config
    DISABLE_FILE_DISCOVERER: bool = False
    RAW_DOCUMENT_STORE_NAME: str = "Personal_Finance_DB_Raw_Store.sqlite"

    FILE_HASH_POLICY: FileHashPolicy = Field(default_factory=FileHashPolicy)

    # Capability Execution Scope
    capabilities: CapabilitySelection = Field(default_factory=CapabilitySelection)

    # Observability & Forensic Logging
    LOGS_DIRECTORY: str = "logs/runs"
    RETAIN_LAST_N_RUNS: int = 12

    # Deprecated source paths (retained as optional for backward compatibility during demolition)
    SOURCE_DB_FOLDER: str = ""
    COLUMN_MASTER_PATH: str = ""
    MF_ISIN_CSV_PATH: str = ""
    BENCHMARK_MAPPING_CSV_PATH: str = ""
    BENCHMARK_MASTER_CSV_PATH: str = ""
    MACRO_PARAMETERS_CSV_PATH: str = ""
    OPENING_BALANCE_CSV_PATH: str = ""
    CURRENCY_MAPPING_CSV_PATH: str = ""
    STATEMENTS_FOLDER: str = ""

    def resolve_logs_dir(self) -> Path:
        """Resolve the active logs directory path against target base path if relative.

        Returns
        -------
        Path
            Absolute or fully qualified Path to the forensic log directory.
        """
        raw_path = Path(self.LOGS_DIRECTORY)
        if raw_path.is_absolute() or not self.TARGET_DB_BASE_PATH:
            return raw_path
        return Path(self.TARGET_DB_BASE_PATH) / raw_path

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

        cfg = cls(**data)
        return cfg

    def validate_config(self) -> None:
        """Validate that required runtime environment settings exist before starting.

        Raises
        ------
        FileNotFoundError
            If TARGET_DB_BASE_PATH is empty in configuration.
        """
        if not self.TARGET_DB_BASE_PATH:
            raise FileNotFoundError("TARGET_DB_BASE_PATH is empty in configuration.")

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
