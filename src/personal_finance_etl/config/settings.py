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
from typing import Any, cast

from pydantic import BaseModel, Field

from personal_finance_etl.infrastructure.preferences import PreferencesManager


class FileHashPolicy(BaseModel):
    csv: bool = True
    excel: bool = False
    sqlite: bool = False


def _flatten_settings_to_records(node: Any, path: list[str], records: list[dict[str, str]]) -> None:
    """Recursively traverse the settings tree to extract flat key-value pairs."""
    if isinstance(node, dict):
        dict_node = cast("dict[str, Any]", node)
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
    SOURCE_DB_FOLDER: str = ""
    TARGET_DB_BASE_PATH: str = ""
    TARGET_DB_NAME: str = "Personal_Finance_DB.duckdb"

    # Raw Store Config
    DISABLE_FILE_DISCOVERER: bool = False
    RAW_DOCUMENT_STORE_NAME: str = "Personal_Finance_DB_Raw_Store.sqlite"

    # Dependencies
    COLUMN_MASTER_PATH: str = ""
    MF_ISIN_CSV_PATH: str = ""
    BENCHMARK_MAPPING_CSV_PATH: str = ""
    BENCHMARK_MASTER_CSV_PATH: str = ""
    MACRO_PARAMETERS_CSV_PATH: str = ""
    OPENING_BALANCE_CSV_PATH: str = ""
    CURRENCY_MAPPING_CSV_PATH: str = ""

    # Statements
    STATEMENTS_FOLDER: str = ""

    FILE_HASH_POLICY: FileHashPolicy = Field(default_factory=FileHashPolicy)

    @classmethod
    def from_toml(cls, filepath: str | os.PathLike[str], track_recent: bool = True) -> Settings:
        """Load a TOML configuration and return a Settings instance.

        Parameters
        ----------
        filepath : str | os.PathLike[str]
            Path to the configuration TOML file.
        track_recent : bool, default=True
            Whether to record this filepath into the user's recent configuration list.

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
        if track_recent:
            try:
                PreferencesManager().add_recent_config(path_str)
            except Exception:
                pass
        return cfg

    def validate_config(self) -> None:
        """Validate that all necessary files and folders exist before starting.

        Raises
        ------
        FileNotFoundError
            If any required directory or file is missing or invalid.
        """
        required_dirs = [
            ("SOURCE_DB_FOLDER", self.SOURCE_DB_FOLDER),
            ("STATEMENTS_FOLDER", self.STATEMENTS_FOLDER),
        ]

        required_files = [
            ("COLUMN_MASTER_PATH", self.COLUMN_MASTER_PATH),
            ("MF_ISIN_CSV_PATH", self.MF_ISIN_CSV_PATH),
            ("BENCHMARK_MAPPING_CSV_PATH", self.BENCHMARK_MAPPING_CSV_PATH),
            ("BENCHMARK_MASTER_CSV_PATH", self.BENCHMARK_MASTER_CSV_PATH),
            ("MACRO_PARAMETERS_CSV_PATH", self.MACRO_PARAMETERS_CSV_PATH),
            ("OPENING_BALANCE_CSV_PATH", self.OPENING_BALANCE_CSV_PATH),
            ("CURRENCY_MAPPING_CSV_PATH", self.CURRENCY_MAPPING_CSV_PATH),
        ]

        errors: list[str] = []

        # TARGET_DB_BASE_PATH is created automatically if missing, but cannot be blank
        if not self.TARGET_DB_BASE_PATH:
            errors.append("TARGET_DB_BASE_PATH is empty in configuration.")

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
