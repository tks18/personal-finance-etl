import json
import os
import tomllib
from dataclasses import dataclass, fields


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

    @classmethod
    def from_toml(cls, filepath: str) -> "Settings":
        """Loads a TOML configuration and returns a Settings instance."""
        cfg = cls()
        if not os.path.exists(filepath):
            return cfg

        with open(filepath, "rb") as f:
            data = tomllib.load(f)

        for field in fields(cls):
            if field.name in data:
                setattr(cfg, field.name, data[field.name])

        PreferencesManager().add_recent_config(filepath)
        return cfg
