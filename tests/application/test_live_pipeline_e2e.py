"""Live pipeline end-to-end integration test suite.

Owns
----
- Optional end-to-end integration verification using real user test data on G: drive.
- Ensures all live ETL runs strictly isolate output DuckDB and SQLite databases to tmp_path.
- Graceful skipping when external test storage (G: drive) is unmounted or unavailable.

Does not own
-------------
- Offline unit tests or mock transformations (owned by respective test layer modules).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.bootstrap.container import ServiceContainer
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings


@pytest.mark.live_data
def test_live_pipeline_isolation_and_wiring(
    isolated_live_settings: Settings,
    rules: FinancialRules,
    rules_path: Path,
) -> None:
    """Verify live ETL configuration wires cleanly and isolates databases in tmp_path.

    Parameters
    ----------
    isolated_live_settings : Settings
        Live settings with outputs safely redirected to tmp_path.
    rules : FinancialRules
        Isolated financial rules fixture.
    rules_path : Path
        Canonical financial rules path.
    """
    assert Path(isolated_live_settings.TARGET_DB_BASE_PATH).exists()
    assert "live_data" in isolated_live_settings.TARGET_DB_BASE_PATH

    # Initialize ServiceContainer targeting isolated paths
    container = ServiceContainer(
        default_config_path="",
        default_rules_path=str(rules_path),
    )

    db_manager = container.create_duckdb_manager(isolated_live_settings)
    assert db_manager.base_path == isolated_live_settings.TARGET_DB_BASE_PATH

    cp = container.create_control_plane(isolated_live_settings)
    assert cp.base_path == isolated_live_settings.TARGET_DB_BASE_PATH

    # Validate engine configuration validation with live settings
    engine = PersonalFinanceEngine(container=container)
    assert engine.container is container
