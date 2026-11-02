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
from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    ExcelSelector,
    SqliteSelector,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.observability import ObservabilityEvent
from personal_finance_etl.contracts.sources import ProviderType, SourceId
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


def get_v953_baseline_sources() -> list[SourceConfig]:
    """Return declarative SourceConfig representations of all v9.5.3 external evidence sources.

    Returns
    -------
    list[SourceConfig]
        List of configured physical evidence sources using test-safe placeholder paths.
    """
    return [
        SourceConfig(
            source_id=SourceId("household_db"),
            provider_type=ProviderType.SQLITE,
            location="inputs/SOURCE_DB.sqlite",
            enabled=True,
            description="External household money management SQLite database backup",
        ),
        SourceConfig(
            source_id=SourceId("mf_isin_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/MF_ISIN_MAPPING.csv",
            enabled=True,
            description="Mutual fund name to ISIN mapping table",
        ),
        SourceConfig(
            source_id=SourceId("benchmark_mapping_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/BENCHMARK_MAPPING.csv",
            enabled=True,
            description="Asset to benchmark index mapping table",
        ),
        SourceConfig(
            source_id=SourceId("opening_balance_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/OPENING_BALANCE.csv",
            enabled=True,
            description="Historical household ledger opening balances",
        ),
        SourceConfig(
            source_id=SourceId("benchmark_master_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/BENCHMARK_MASTER.csv",
            enabled=True,
            description="Benchmark index master catalog",
        ),
        SourceConfig(
            source_id=SourceId("macro_parameters_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/MACRO_PARAMETERS.csv",
            enabled=True,
            description="Macroeconomic and tax policy parameters",
        ),
        SourceConfig(
            source_id=SourceId("currency_mapping_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/CURRENCY_MAPPING.csv",
            enabled=True,
            description="Currency ticker mapping and exchange symbols",
        ),
        SourceConfig(
            source_id=SourceId("column_master_csv"),
            provider_type=ProviderType.CSV,
            location="inputs/COLUMN_MASTER.csv",
            enabled=True,
            description="Transitional column mapping dictionary (scheduled for retirement in Phase 030/035)",
        ),
        SourceConfig(
            source_id=SourceId("mf_holdings_excel"),
            provider_type=ProviderType.EXCEL,
            location="inputs/Statements/Mutual Funds - Holdings",
            enabled=True,
            description="Monthly mutual fund holdings spreadsheet directory",
        ),
        SourceConfig(
            source_id=SourceId("mf_orders_excel"),
            provider_type=ProviderType.EXCEL,
            location="inputs/Statements/Mutual Funds - Orders",
            enabled=True,
            description="Monthly mutual fund orders and transactions spreadsheet directory",
        ),
        SourceConfig(
            source_id=SourceId("stock_pl_excel"),
            provider_type=ProviderType.EXCEL,
            location="inputs/Statements/Stock PL Statements",
            enabled=True,
            description="Monthly stock profit and loss statement directory",
        ),
        SourceConfig(
            source_id=SourceId("stock_orders_excel"),
            provider_type=ProviderType.EXCEL,
            location="inputs/Statements/Stock - Orders",
            enabled=True,
            description="Monthly stock order execution statement directory",
        ),
        SourceConfig(
            source_id=SourceId("us_stock_transactions"),
            provider_type=ProviderType.CSV,
            location="inputs/Statements/IND Money (US Stocks)/Transaction Reports",
            enabled=False,
            description="Optional US stock transaction reports directory (default disabled)",
        ),
    ]


def get_v953_baseline_dataset_bindings() -> list[SourceDatasetConfig]:
    """Return declarative SourceDatasetConfig bindings covering all external Bronze datasets.

    Returns
    -------
    list[SourceDatasetConfig]
        List of source-to-dataset bindings for all 16 externally supplied Bronze datasets.
    """
    return [
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
            selector=SqliteSelector(table_name="ZCATEGORY"),
            enabled=True,
            description="Household expense categories table",
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
            selector=SqliteSelector(table_name="ASSETGROUP"),
            enabled=True,
            description="Household asset grouping table",
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_ASSETS,
            selector=SqliteSelector(table_name="ASSETS"),
            enabled=True,
            description="Household financial accounts and assets table",
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
            selector=SqliteSelector(table_name="CURRENCY"),
            enabled=True,
            description="Household currency denominations table",
        ),
        SourceDatasetConfig(
            source_id=SourceId("household_db"),
            dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
            selector=SqliteSelector(table_name="INOUTCOME"),
            enabled=True,
            description="Household financial ledger income and expense transactions table",
        ),
        SourceDatasetConfig(
            source_id=SourceId("mf_isin_csv"),
            dataset_id=DatasetId.INVESTMENT_MF_ISIN_MAPPING,
            selector=CsvSelector(),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("benchmark_mapping_csv"),
            dataset_id=DatasetId.INVESTMENT_BENCHMARK_MAPPING,
            selector=CsvSelector(),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("opening_balance_csv"),
            dataset_id=DatasetId.HOUSEHOLD_OPENING_BALANCES,
            selector=CsvSelector(),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("benchmark_master_csv"),
            dataset_id=DatasetId.INVESTMENT_BENCHMARK_MASTER,
            selector=CsvSelector(),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("macro_parameters_csv"),
            dataset_id=DatasetId.INVESTMENT_MACRO_PARAMETERS,
            selector=CsvSelector(),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("currency_mapping_csv"),
            dataset_id=DatasetId.MARKET_CURRENCY_MAPPING,
            selector=CsvSelector(),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("column_master_csv"),
            dataset_id=DatasetId.COMMON_COLUMN_MASTER,
            selector=CsvSelector(),
            enabled=True,
            description="Transitional column master mapping dataset (scheduled for retirement in Phase 030/035)",
        ),
        SourceDatasetConfig(
            source_id=SourceId("mf_holdings_excel"),
            dataset_id=DatasetId.MARKET_MF_HOLDINGS,
            selector=ExcelSelector(sheet_name="Holdings"),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("mf_orders_excel"),
            dataset_id=DatasetId.INVESTMENT_MF_ORDERS,
            selector=ExcelSelector(sheet_name="Transactions"),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("stock_pl_excel"),
            dataset_id=DatasetId.MARKET_STOCK_HOLDINGS,
            selector=ExcelSelector(sheet_name="Trade Level"),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("stock_orders_excel"),
            dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
            selector=ExcelSelector(sheet_name="Sheet1", header_row=5),
            enabled=True,
        ),
        SourceDatasetConfig(
            source_id=SourceId("us_stock_transactions"),
            dataset_id=DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS,
            selector=CsvSelector(file_pattern="*.csv"),
            enabled=False,
            description="Optional US stock transactions reports",
        ),
    ]


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
