"""Centralized Pytest Configuration and Fixture Hub.

Owns
----
- Project directory path discovery (`repo_root`, `fixtures_dir`, `rules_path`, `config_path`).
- Canonical and function-scoped FinancialRules fixtures with deep copy isolation.
- Ephemeral Settings and database managers (DuckDB and SQLite Control Plane) isolated in `tmp_path`.
- Thread-safe typed status queue and memory event sinks.
- ServiceContainer composition root and PersonalFinanceEngine test facades.
- Optional live data settings fixture for end-to-end integration testing.

Does not own
-------------
- Concrete test assertion logic (owned by respective test modules).
- Production database persistence or disk outputs.
"""

from __future__ import annotations

import queue
from pathlib import Path

import pytest

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.bootstrap.container import ServiceContainer
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources import (
    SourceConfig,
    SourceConfiguration,
    SourceDatasetConfig,
    get_shan_baseline_dataset_bindings,
    get_shan_baseline_sources,
)
from personal_finance_etl.contracts.observability import ObservabilityEvent
from personal_finance_etl.infrastructure.control_plane.connection import SQLiteManager
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager

# ---------------------------------------------------------------------------
# Path & Discovery Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the absolute path to the repository root directory.

    Returns
    -------
    Path
        Absolute repository root path.
    """
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def fixtures_dir(repo_root: Path) -> Path:
    """Return the absolute path to the test fixtures directory.

    Parameters
    ----------
    repo_root : Path
        Project repository root.

    Returns
    -------
    Path
        Absolute path to tests/fixtures.
    """
    return repo_root / "tests" / "fixtures"


@pytest.fixture(scope="session")
def rules_path(fixtures_dir: Path) -> Path:
    """Return the path to canonical financial_rules.toml.

    Parameters
    ----------
    fixtures_dir : Path
        Fixtures directory path.

    Returns
    -------
    Path
        Path to canonical financial_rules.toml.
    """
    return fixtures_dir / "financial_rules.toml"


@pytest.fixture(scope="session")
def config_path(fixtures_dir: Path) -> Path:
    """Return the path to canonical config.toml.

    Parameters
    ----------
    fixtures_dir : Path
        Fixtures directory path.

    Returns
    -------
    Path
        Path to canonical config.toml.
    """
    return fixtures_dir / "config.toml"


@pytest.fixture(scope="session")
def sources_path(fixtures_dir: Path) -> Path:
    """Return the path to canonical sources.toml.

    Parameters
    ----------
    fixtures_dir : Path
        Fixtures directory path.

    Returns
    -------
    Path
        Path to canonical sources.toml.
    """
    return fixtures_dir / "sources.toml"


@pytest.fixture(scope="session")
def canonical_source_config(sources_path: Path) -> SourceConfiguration:
    """Load canonical SourceConfiguration once per test session.

    Parameters
    ----------
    sources_path : Path
        Path to the canonical sources TOML file.

    Returns
    -------
    SourceConfiguration
        Validated session-cached SourceConfiguration instance.
    """
    return SourceConfiguration.from_toml(sources_path)


@pytest.fixture(scope="function")
def source_config(canonical_source_config: SourceConfiguration) -> SourceConfiguration:
    """Provide a fresh, deep-copied SourceConfiguration instance for each test function.

    Parameters
    ----------
    canonical_source_config : SourceConfiguration
        Session-cached source configuration template.

    Returns
    -------
    SourceConfiguration
        Function-isolated, mutable copy of SourceConfiguration.
    """
    return canonical_source_config.model_copy(deep=True)


def get_v953_baseline_sources() -> list[SourceConfig]:
    """Return declarative SourceConfig representations of all v9.5.3 external evidence sources.

    Returns
    -------
    list[SourceConfig]
        List of configured physical evidence sources using canonical baseline paths.
    """
    return get_shan_baseline_sources()


def get_v953_baseline_dataset_bindings() -> list[SourceDatasetConfig]:
    """Return declarative SourceDatasetConfig bindings covering all external Bronze datasets.

    Returns
    -------
    list[SourceDatasetConfig]
        List of source-to-dataset bindings for all 17 externally supplied Bronze datasets.
    """
    return get_shan_baseline_dataset_bindings()


@pytest.fixture(scope="session")
def v953_baseline_topology() -> tuple[list[SourceConfig], list[SourceDatasetConfig]]:
    """Return the baseline Shan external source topology representing all v9.5.3 Bronze evidence.

    Returns
    -------
    tuple[list[SourceConfig], list[SourceDatasetConfig]]
        Tuple containing 13 SourceConfigs and 17 SourceDatasetConfigs.
    """
    return get_v953_baseline_sources(), get_v953_baseline_dataset_bindings()


# ---------------------------------------------------------------------------
# Financial Rules Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def canonical_rules(rules_path: Path) -> FinancialRules:
    """Load canonical FinancialRules once per test session.

    Parameters
    ----------
    rules_path : Path
        Path to the canonical rules TOML file.

    Returns
    -------
    FinancialRules
        Validated session-cached FinancialRules instance.
    """
    return FinancialRules.from_toml(rules_path)


@pytest.fixture(scope="function")
def rules(canonical_rules: FinancialRules) -> FinancialRules:
    """Provide a fresh, deep-copied FinancialRules instance for each test function.

    Parameters
    ----------
    canonical_rules : FinancialRules
        Session-cached rules template.

    Returns
    -------
    FinancialRules
        Function-isolated, mutable copy of FinancialRules.
    """
    return canonical_rules.model_copy(deep=True)


@pytest.fixture(scope="function")
def mock_rules(rules: FinancialRules) -> FinancialRules:
    """Backwards-compatibility alias for test functions consuming 'mock_rules'.

    Parameters
    ----------
    rules : FinancialRules
        Fresh function-isolated FinancialRules instance.

    Returns
    -------
    FinancialRules
        Identical function-isolated FinancialRules instance.
    """
    return rules


# ---------------------------------------------------------------------------
# Settings & Storage Isolation Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def isolated_settings(tmp_path: Path) -> Settings:
    """Provide an isolated Settings instance redirecting all persistence to tmp_path.

    Parameters
    ----------
    tmp_path : Path
        Pytest-provided unique temporary directory.

    Returns
    -------
    Settings
        Configured Settings instance pointing to tmp_path.
    """
    db_dir = tmp_path / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    return Settings(
        TARGET_DB_BASE_PATH=str(db_dir),
        TARGET_DB_NAME="isolated_warehouse.duckdb",
        RAW_DOCUMENT_STORE_NAME="isolated_control_plane.sqlite",
        LOGS_DIRECTORY=str(logs_dir),
    )


@pytest.fixture(scope="function")
def isolated_duckdb_manager(isolated_settings: Settings) -> DuckDBManager:
    """Provide an active DuckDBManager instance targeting the isolated tmp_path.

    Parameters
    ----------
    isolated_settings : Settings
        Isolated test settings.

    Returns
    -------
    DuckDBManager
        Initialized DuckDB warehouse manager.
    """
    return DuckDBManager(
        base_path=isolated_settings.TARGET_DB_BASE_PATH,
        db_name=isolated_settings.TARGET_DB_NAME,
    )


@pytest.fixture(scope="function")
def isolated_control_plane(isolated_settings: Settings) -> ControlPlane:
    """Provide an active ControlPlane instance targeting isolated tmp_path.

    Parameters
    ----------
    isolated_settings : Settings
        Isolated test settings.

    Returns
    -------
    ControlPlane
        Initialized SQLite Control Plane facade.
    """
    return ControlPlane(
        base_path=isolated_settings.TARGET_DB_BASE_PATH,
        db_name=isolated_settings.RAW_DOCUMENT_STORE_NAME,
    )


@pytest.fixture(scope="function")
def isolated_sqlite_manager(isolated_settings: Settings) -> SQLiteManager:
    """Provide an active SQLiteManager instance targeting isolated tmp_path.

    Parameters
    ----------
    isolated_settings : Settings
        Isolated test settings.

    Returns
    -------
    SQLiteManager
        Initialized SQLite connection manager.
    """
    return SQLiteManager(
        base_path=isolated_settings.TARGET_DB_BASE_PATH,
        db_name=isolated_settings.RAW_DOCUMENT_STORE_NAME,
    )


# ---------------------------------------------------------------------------
# Observability & Queue Fixtures
# ---------------------------------------------------------------------------


class MemoryEventSink:
    """Thread-safe in-memory event sink capturing ObservabilityEvents for assertions."""

    def __init__(self) -> None:
        self.events: list[ObservabilityEvent] = []

    def emit(self, event: ObservabilityEvent) -> None:
        """Process and route one canonical ObservabilityEvent.

        Parameters
        ----------
        event : ObservabilityEvent
            The canonical structured event to consume.
        """
        self.events.append(event)

    def handle(self, event: ObservabilityEvent) -> None:
        """Capture an emitted event into memory.

        Parameters
        ----------
        event : ObservabilityEvent
            Emitted forensic observability event.
        """
        self.events.append(event)

    def flush(self) -> None:
        """Flush buffered events."""


class ThreadSafeStatusQueue:
    """Typed Queue wrapper satisfying status queue protocols without Any."""

    def __init__(self) -> None:
        self._queue: queue.Queue[ObservabilityEvent | None] = queue.Queue()

    def put(
        self,
        event: ObservabilityEvent | None,
        /,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        """Enqueue status item.

        Parameters
        ----------
        event : ObservabilityEvent | None
            Status event or poison pill.
        block : bool, optional
            Whether to block, by default True.
        timeout : float | None, optional
            Timeout duration, by default None.
        """
        self._queue.put(event, block=block, timeout=timeout)

    @property
    def items(self) -> list[ObservabilityEvent | None]:
        """Return a snapshot list of items currently captured.

        Returns
        -------
        list[ObservabilityEvent | None]
            Captured items list.
        """
        return list(self._queue.queue)


@pytest.fixture(scope="function")
def status_queue() -> ThreadSafeStatusQueue:
    """Provide a fresh thread-safe status queue for pipeline and coordinator tests.

    Returns
    -------
    ThreadSafeStatusQueue
        Fresh status queue instance.
    """
    return ThreadSafeStatusQueue()


@pytest.fixture(scope="function")
def test_emitter() -> tuple[ObservabilityEmitter, MemoryEventSink]:
    """Provide an ObservabilityEmitter pre-wired with an in-memory test sink.

    Returns
    -------
    tuple[ObservabilityEmitter, MemoryEventSink]
        Configured emitter and its registered memory sink.
    """
    emitter = ObservabilityEmitter()
    sink = MemoryEventSink()
    emitter.register_sink(sink)
    return emitter, sink


# ---------------------------------------------------------------------------
# Composition Root & Engine Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def isolated_container(
    isolated_settings: Settings, rules: FinancialRules, rules_path: Path
) -> ServiceContainer:
    """Provide a fully wired ServiceContainer targeting isolated tmp_path.

    Parameters
    ----------
    isolated_settings : Settings
        Isolated test settings.
    rules : FinancialRules
        Isolated test rules.
    rules_path : Path
        Canonical rules path.

    Returns
    -------
    ServiceContainer
        Initialized ServiceContainer composition root.
    """
    return ServiceContainer(
        default_config_path="",
        default_rules_path=str(rules_path),
    )


@pytest.fixture(scope="function")
def isolated_engine(
    isolated_container: ServiceContainer,
) -> PersonalFinanceEngine:
    """Provide a PersonalFinanceEngine backed by the isolated ServiceContainer.

    Parameters
    ----------
    isolated_container : ServiceContainer
        Isolated composition root.

    Returns
    -------
    PersonalFinanceEngine
        Initialized engine façade.
    """
    return isolated_container.create_engine()


# ---------------------------------------------------------------------------
# Live Data Fixture (Optional G: Drive Integration)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def isolated_live_settings(tmp_path: Path) -> Settings:
    """Load user's real ETL config from G: drive if mounted, safely isolated in tmp_path.

    Parameters
    ----------
    tmp_path : Path
        Pytest-provided temporary path for output isolation.

    Returns
    -------
    Settings
        Settings instance pointing to live inputs with ephemeral tmp_path outputs.
    """
    candidate = Path(
        r"g:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\ETL App\shan_personal_finance_ETL_Test.toml"
    )
    if not candidate.is_file():
        pytest.skip("User live test config not found on G: drive")

    cfg = Settings.from_toml(candidate)

    if not Path(cfg.COLUMN_MASTER_PATH).is_file():
        pytest.skip(f"Live dependencies not accessible: {cfg.COLUMN_MASTER_PATH}")

    # Safely isolate outputs and logs into tmp_path
    db_dir = tmp_path / "live_data"
    db_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = tmp_path / "live_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    cfg.TARGET_DB_BASE_PATH = str(db_dir)
    cfg.LOGS_DIRECTORY = str(logs_dir)
    return cfg
