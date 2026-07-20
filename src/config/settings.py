import os
import tomllib
from dataclasses import dataclass, fields

from src.utils.prefs import add_recent_config


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


def load_config(filepath: str) -> Settings:
    """Loads a TOML configuration and returns a Settings instance."""
    cfg = Settings()
    if not os.path.exists(filepath):
        return cfg

    with open(filepath, "rb") as f:
        data = tomllib.load(f)
    for field in fields(Settings):
        if field.name in data:
            setattr(cfg, field.name, data[field.name])

    add_recent_config(filepath)
    return cfg
