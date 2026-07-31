import json
import os
import tomllib
from dataclasses import dataclass, field, fields


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

        with open(self.prefs_path, "w") as f:
            json.dump({"recent_configs": recents}, f)

    def get_recent_configs(self) -> list[str]:
        """Returns a list of recent configuration file paths."""
        if os.path.exists(self.prefs_path):
            with open(self.prefs_path) as f:
                try:
                    data = json.load(f)
                    recents = data.get("recent_configs", [])
                    if isinstance(recents, list):
                        return [r for r in recents if os.path.exists(r)]
                except Exception:
                    pass
        return []


@dataclass
class Settings:
    SOURCE_DB_FOLDER: str = ""
    TARGET_DB_BASE_PATH: str = ""

    # Dependencies
    COLUMN_MASTER_PATH: str = ""
    MF_ISIN_CSV_PATH: str = ""
    BENCHMARK_MAPPING_CSV_PATH: str = ""
    BENCHMARK_MASTER_CSV_PATH: str = ""
    TAX_RATES_CSV_PATH: str = ""
    OPENING_BALANCE_CSV_PATH: str = ""

    # Statements
    STATEMENTS_FOLDER: str = ""

    # Configurable Mappings
    MF_SCHEME_MAPPINGS: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_toml(cls, filepath: str) -> "Settings":
        """Loads a TOML configuration and returns a Settings instance."""
        cfg = cls()
        if not os.path.exists(filepath):
            return cfg

        with open(filepath, "rb") as f:
            data = tomllib.load(f)

        for fld in fields(cls):
            if fld.name in data:
                setattr(cfg, fld.name, data[fld.name])

        PreferencesManager().add_recent_config(filepath)
        return cfg

    def validate(self) -> None:
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
            ("TAX_RATES_CSV_PATH", self.TAX_RATES_CSV_PATH),
            ("OPENING_BALANCE_CSV_PATH", self.OPENING_BALANCE_CSV_PATH),
        ]

        errors = []

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
