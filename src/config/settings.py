import json
import os
import tomllib
from typing import Any, cast

from pydantic import BaseModel, Field


class FileHashPolicy(BaseModel):
    csv: bool = True
    excel: bool = False
    sqlite: bool = False


class PreferencesManager:
    """Manages reading and writing application user preferences to disk."""

    def __init__(self) -> None:
        app_data = os.getenv("APPDATA")
        if not app_data:
            app_data = os.path.expanduser("~")

        prefs_dir = os.path.join(app_data, "PersonalFinanceETL")
        os.makedirs(prefs_dir, exist_ok=True)
        self.prefs_path = os.path.join(prefs_dir, "prefs.json")

    def add_recent_config(self, filepath: str) -> None:
        """Adds a configuration path to the recent list in preferences."""
        recents = self.get_recent_configs()

        if filepath in recents:
            recents.remove(filepath)
        recents.insert(0, filepath)

        # Keep top 10
        recents = recents[:10]

        data = {}
        if os.path.exists(self.prefs_path):
            with open(self.prefs_path) as f:
                try:
                    data = json.load(f)
                except Exception:
                    pass

        data["recent_configs"] = recents
        with open(self.prefs_path, "w") as f:
            json.dump(data, f)

    def get_recent_configs(self) -> list[str]:
        """Returns a list of recent configuration file paths."""
        if os.path.exists(self.prefs_path):
            with open(self.prefs_path) as f:
                try:
                    data = json.load(f)
                    recents = data.get("recent_configs", [])
                    if isinstance(recents, list):
                        list_recents = cast("list[Any]", recents)
                        return [
                            str(r) for r in list_recents if isinstance(r, str) and os.path.exists(r)
                        ]
                except Exception:
                    pass
        return []

    def add_recent_rules(self, filepath: str) -> None:
        """Adds a financial rules configuration path to the recent list."""
        recents = self.get_recent_rules()
        if filepath in recents:
            recents.remove(filepath)
        recents.insert(0, filepath)
        recents = recents[:10]

        data = {}
        if os.path.exists(self.prefs_path):
            with open(self.prefs_path) as f:
                try:
                    data = json.load(f)
                except Exception:
                    pass
        data["recent_rules"] = recents
        with open(self.prefs_path, "w") as f:
            json.dump(data, f)

    def get_recent_rules(self) -> list[str]:
        """Returns a list of recent financial rules file paths."""
        if os.path.exists(self.prefs_path):
            with open(self.prefs_path) as f:
                try:
                    data = json.load(f)
                    recents = data.get("recent_rules", [])
                    if isinstance(recents, list):
                        list_recents = cast("list[Any]", recents)
                        return [
                            str(r) for r in list_recents if isinstance(r, str) and os.path.exists(r)
                        ]
                except Exception:
                    pass
        return []


class Settings(BaseModel):
    SOURCE_DB_FOLDER: str = ""
    TARGET_DB_BASE_PATH: str = ""
    TARGET_DB_NAME: str = "Personal_Finance_DB.duckdb"

    # Dependencies
    COLUMN_MASTER_PATH: str = ""
    MF_ISIN_CSV_PATH: str = ""
    BENCHMARK_MAPPING_CSV_PATH: str = ""
    BENCHMARK_MASTER_CSV_PATH: str = ""
    MACRO_PARAMETERS_CSV_PATH: str = ""
    OPENING_BALANCE_CSV_PATH: str = ""

    # Statements
    STATEMENTS_FOLDER: str = ""

    # Configurable Mappings
    MF_SCHEME_MAPPINGS: dict[str, str] = Field(default_factory=dict)

    FILE_HASH_POLICY: FileHashPolicy = Field(default_factory=FileHashPolicy)

    # Defaults
    DEFAULT_CURRENCY_ID: str = "INR_INR"

    @classmethod
    def from_toml(cls, filepath: str) -> "Settings":
        """Loads a TOML configuration and returns a Settings instance."""
        if not os.path.exists(filepath):
            return cls()

        with open(filepath, "rb") as f:
            data = tomllib.load(f)

        cfg = cls(**data)
        PreferencesManager().add_recent_config(filepath)
        return cfg

    def validate_config(self) -> None:
        """Validates that all necessary files and folders exist before starting."""
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
        ]

        errors: list[str] = []

        # We don't validate TARGET_DB_BASE_PATH because it is created automatically if missing
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
        """Flattens the settings dynamically into a list of records for database auditing."""
        records: list[dict[str, str]] = []
        data = self.model_dump()

        def _flatten(node: Any, path: list[str]) -> None:
            if isinstance(node, dict):
                dict_node = cast("dict[str, Any]", node)
                for k, v in dict_node.items():
                    _flatten(v, path + [k])
            elif isinstance(node, list):
                for i, v in enumerate(node):  # type: ignore
                    _flatten(v, path + [str(i)])
            else:
                # Top level settings have length 1
                group = "General"
                if len(path) > 1:
                    group = path[0].capitalize()
                    key = "_".join(path[1:])
                else:
                    key = path[0]

                records.append(
                    {
                        "Setting_Group": group,
                        "Setting_Key": key,
                        "Setting_Value": str(node) if node is not None else "",
                    }
                )

        _flatten(data, [])
        return records
