# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
"""Shared pytest fixtures and offline market stubs for PFETL test suite.

Owns
----
- Paths to deterministic miniature test fixtures (household, statements, references).
- Offline monkeypatch stubs for yfinance / market data providers.
- Temporary database and engine wiring fixtures for isolated test execution.

Does not own
-------------
- Specific financial calculation assertions (owned by test_*_golden.py).
- Production business logic or extraction coordination (owned by application.*).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

# Exception TYP-003 [THIRD_PARTY_TYPING_GAP]: customtkinter lacks py.typed marker and complete stubs
import customtkinter as ctk  # type: ignore[import-untyped]
import pandas as pd  # type: ignore[import-untyped]
import pytest

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def isolate_user_preferences(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ensure tests run against an isolated temporary preferences store and never pollute user APPDATA."""
    temp_appdata = tmp_path_factory.mktemp("test_appdata")
    monkeypatch.setenv("APPDATA", str(temp_appdata))


@pytest.fixture(scope="session")
def fixtures_path() -> Path:
    """Return root path to test fixtures."""
    return FIXTURES_DIR


@pytest.fixture
def test_config_path() -> Path:
    """Return path to fixture config.toml."""
    return FIXTURES_DIR / "config.toml"


@pytest.fixture
def test_rules_path() -> Path:
    """Return path to fixture financial_rules.toml."""
    return FIXTURES_DIR / "financial_rules.toml"


@pytest.fixture
def mock_rules(test_rules_path: Path) -> FinancialRules:
    """Load parsed FinancialRules from test fixture."""
    return FinancialRules.from_toml(str(test_rules_path))


@pytest.fixture
def isolated_config(tmp_path: Path, test_config_path: Path) -> tuple[Settings, Path]:
    """Provide isolated Settings pointing database outputs to tmp_path."""
    cfg = Settings.from_toml(str(test_config_path))
    cfg.database.target_db_base_path = str(tmp_path / "outputs")
    (tmp_path / "outputs").mkdir(parents=True, exist_ok=True)
    temp_cfg_path = tmp_path / "config.toml"
    import re

    raw_cfg = test_config_path.read_text(encoding="utf-8")
    isolated_target = str(tmp_path / "outputs").replace("\\", "/")
    updated_cfg = re.sub(
        r'target_db_base_path\s*=\s*"[^"]*"',
        f'target_db_base_path = "{isolated_target}"',
        raw_cfg,
    )
    temp_cfg_path.write_text(updated_cfg, encoding="utf-8")
    return cfg, temp_cfg_path


@pytest.fixture(autouse=True)
def offline_market_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guarantee zero live network calls to external market data providers."""

    def mock_download_history(
        ticker: str,
        fetch_start: date | datetime | str | None = None,
        end_dt: date | datetime | str | None = None,
        start: date | datetime | str | None = None,
        end: date | datetime | str | None = None,
        label: str = "Mock Extractor",
        max_attempts: int = 1,
        **kwargs: Any,
    ) -> tuple[pd.DataFrame | None, int, Exception | None]:
        print(
            f"\n>>> MOCK_DOWNLOAD CALLED for {ticker}, fetch_start={fetch_start}, end_dt={end_dt}"
        )
        s = fetch_start if fetch_start is not None else start
        e = end_dt if end_dt is not None else end
        start_dt = pd.to_datetime(str(s))
        end_dt_val = pd.to_datetime(str(e))
        if start_dt > end_dt_val:
            start_dt, end_dt_val = end_dt_val, start_dt
        dates = pd.date_range(start=start_dt, end=end_dt_val, freq="D")
        dates.name = "Date"

        # Deterministic prices
        if "USDINR" in ticker:
            price = 83.0
        elif "^NSEI" in ticker:
            price = 22000.0
        elif "^GSPC" in ticker:
            price = 5000.0
        elif "AAPL" in ticker or "QQQ" in ticker:
            price = 380.0
        elif "RELIANCE" in ticker or "INE002A01018" in ticker:
            price = 2500.0
        else:
            price = 100.0

        df = pd.DataFrame(
            {
                "Open": price,
                "High": price,
                "Low": price,
                "Close": price,
                "Volume": 10000.0,
            },
            index=dates,
        )
        return df, 1, None

    monkeypatch.setattr(
        "personal_finance_etl.infrastructure.providers.market.common.download_yfinance_history",
        mock_download_history,
    )


@pytest.fixture(scope="session")
def tk_root() -> Any:
    """Provide a single shared CTk root across tests in a module."""
    root = ctk.CTk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass

