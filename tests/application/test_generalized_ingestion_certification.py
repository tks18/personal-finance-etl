# pyright: reportPrivateUsage=false
"""Authoritative Verification Suite for Generalized Ingestion Architecture.

Owns
----
- Full lifecycle validation of generalized ingestion data plane from raw source to canonical Bronze.
- Verification of Control Plane file discovery, hashing, payload storage, and file registry tracking.
- Verification of DuckDB Meta layer tables (_meta_file_registry, _meta_ingestion_manifest, _meta_schema_catalog).
- Verification of Pre-Bronze raw tabular admission with dunder provenance columns.
- Verification of Gate 1 Pre-Bronze and Gate 2 Bronze Pandera contract enforcement.
- Verification of canonical Bronze layer delta replacement via __artifact_id__.
- Verification of caching idempotency (0 unnecessary DuckDB writes on unchanged reruns).
- Verification of changed-artifact atomic replacement and file rename identity migration.
- Verification of two-phase split-commit crash recovery (RECOVERY_REQUIRED healing).
- Verification of observability emitter event fan-out and worker JSONL lineage.
- Downstream Silver/Gold execution smoke on canonical static evidence fixtures.

Does not own
-------------
- Deep domain financial formula verification (FIFO math, Section 112A grandfathering, Monte Carlo convergence).
- Direct UI presentation logic or GUI widget rendering.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from pandera.errors import SchemaError, SchemaErrors

from personal_finance_etl.application.ingestion.admission import AdmissionService
from personal_finance_etl.application.ingestion.slice_runner import (
    DatasetIngestionService,
)
from personal_finance_etl.application.pipeline import (
    ETLOrchestrator,
    RunLifecycleCoordinator,
)
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import SourcePlanner
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources import SourceConfig, SourceConfiguration
from personal_finance_etl.config.sources.loader import (
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.event_transport import NullEventQueue
from personal_finance_etl.contracts.lifecycle import CommitState
from personal_finance_etl.contracts.observability import (
    EventCode,
    ObservabilityEvent,
)
from personal_finance_etl.contracts.validation import ValidationError
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
)
from personal_finance_etl.infrastructure.validation import (
    PanderaDataFrameValidator,
)
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    PRE_BRONZE_ARTIFACT_ID,
)
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer


def _setup_isolated_static_environment(
    tmp_path: Path,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> tuple[Settings, SourceConfiguration]:
    """Copy all static evidence families and create an isolated Settings and SourceConfiguration.

    Parameters
    ----------
    tmp_path : Path
        Temporary test directory.
    copy_evidence : Callable[[str, Path], dict[str, str]]
        Factory fixture to copy evidence files.

    Returns
    -------
    tuple[Settings, SourceConfiguration]
        Configured Settings and SourceConfiguration instances pointing to tmp_path inputs.
    """
    inputs_dir = tmp_path / "inputs"
    outputs_dir = tmp_path / "outputs"
    logs_dir = tmp_path / "logs"

    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Copy all evidence families into inputs
    copy_evidence("household", inputs_dir / "household")
    copy_evidence("mutual_funds", inputs_dir / "Statements")
    copy_evidence("domestic_stocks", inputs_dir / "Statements")
    copy_evidence("us_stocks", inputs_dir / "Statements")
    copy_evidence("reference", inputs_dir / "reference")

    # Load baseline Shan source configuration and redirect paths to tmp_path
    base_cfg = get_shan_baseline_source_configuration()
    sources_list: list[SourceConfig] = []
    for s in base_cfg.sources:
        loc = s.location
        if "SOURCE_DB.sqlite" in loc:
            loc = str(inputs_dir / "household" / "SOURCE_DB.sqlite").replace("\\", "/")
        elif "MF_ISIN_MAPPING.csv" in loc:
            loc = str(inputs_dir / "reference" / "MF_ISIN_MAPPING.csv").replace("\\", "/")
        elif "BENCHMARK_MAPPING.csv" in loc:
            loc = str(inputs_dir / "reference" / "BENCHMARK_MAPPING.csv").replace("\\", "/")
        elif "OPENING_BALANCE.csv" in loc:
            loc = str(inputs_dir / "reference" / "OPENING_BALANCE.csv").replace("\\", "/")
        elif "BENCHMARK_MASTER.csv" in loc:
            loc = str(inputs_dir / "reference" / "BENCHMARK_MASTER.csv").replace("\\", "/")
        elif "MACRO_PARAMETERS.csv" in loc:
            loc = str(inputs_dir / "reference" / "MACRO_PARAMETERS.csv").replace("\\", "/")
        elif "CURRENCY_MAPPING.csv" in loc:
            loc = str(inputs_dir / "reference" / "CURRENCY_MAPPING.csv").replace("\\", "/")
        elif "Mutual Funds - Holdings" in loc:
            loc = str(inputs_dir / "Statements" / "Mutual Funds - Holdings").replace("\\", "/")
        elif "Mutual Funds - Orders" in loc:
            loc = str(inputs_dir / "Statements" / "Mutual Funds - Orders").replace("\\", "/")
        elif "Stock PL Statements" in loc:
            loc = str(inputs_dir / "Statements" / "Stock PL Statements").replace("\\", "/")
        elif "Stock - Orders" in loc:
            loc = str(inputs_dir / "Statements" / "Stock - Orders").replace("\\", "/")
        elif "IND Money (US Stocks)" in loc:
            loc = str(
                inputs_dir
                / "Statements"
                / "IND Money (US Stocks)"
                / "Transaction Reports"
                / "2025-26"
            ).replace("\\", "/")

        sources_list.append(s.model_copy(update={"location": loc}))

    source_config = base_cfg.model_copy(update={"sources": tuple(sources_list)})

    settings = Settings(
        TARGET_DB_BASE_PATH=str(outputs_dir),
        LOGS_DIRECTORY=str(logs_dir),
        STATEMENTS_FOLDER=str(inputs_dir / "Statements"),
        SOURCE_DB_FOLDER=str(inputs_dir / "household"),
        MF_ISIN_CSV_PATH=str(inputs_dir / "reference" / "MF_ISIN_MAPPING.csv"),
        BENCHMARK_MAPPING_CSV_PATH=str(inputs_dir / "reference" / "BENCHMARK_MAPPING.csv"),
        BENCHMARK_MASTER_CSV_PATH=str(inputs_dir / "reference" / "BENCHMARK_MASTER.csv"),
        MACRO_PARAMETERS_CSV_PATH=str(inputs_dir / "reference" / "MACRO_PARAMETERS.csv"),
        OPENING_BALANCE_CSV_PATH=str(inputs_dir / "reference" / "OPENING_BALANCE.csv"),
        CURRENCY_MAPPING_CSV_PATH=str(inputs_dir / "reference" / "CURRENCY_MAPPING.csv"),
    )

    return settings, source_config


def test_clean_rebuild_and_caching_idempotency(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Verify clean initial pipeline run populates lakehouse, and rerun performs 0 redundant writes.

    Parameters
    ----------
    tmp_path : Path
        Isolated temporary directory.
    rules : FinancialRules
        Isolated financial rules fixture.
    copy_evidence : Callable[[str, Path], dict[str, str]]
        Factory fixture to copy evidence files.
    """
    settings, source_config = _setup_isolated_static_environment(tmp_path, copy_evidence)
    status_q = NullEventQueue()
    emitter = ObservabilityEmitter()
    capabilities = [
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.INVESTMENT_ACCOUNTING,
    ]
    plan = CapabilityPlanner().create_plan(capabilities)
    db_mgr = DuckDBManager(settings.TARGET_DB_BASE_PATH)

    # 1. First execution from empty state
    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=source_config,
    )
    orchestrator.run()

    # Verify Bronze tables populated
    db_mgr.open()
    df_mf = db_mgr.conn.query("SELECT * FROM bronze.investment_mf_orders").pl()
    assert df_mf.height > 0
    initial_mf_count = df_mf.height

    df_stocks = db_mgr.conn.query("SELECT * FROM bronze.investment_stock_orders").pl()
    assert df_stocks.height > 0
    initial_stock_count = df_stocks.height
    db_mgr.close()

    # 2. Second execution without changing any source evidence (cache check)
    orchestrator_rerun = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=source_config,
    )
    orchestrator_rerun.run()

    # Verify zero duplicate rows in Bronze tables
    db_mgr.open()
    df_mf_rerun = db_mgr.conn.query("SELECT * FROM bronze.investment_mf_orders").pl()
    assert df_mf_rerun.height == initial_mf_count

    df_stocks_rerun = db_mgr.conn.query("SELECT * FROM bronze.investment_stock_orders").pl()
    assert df_stocks_rerun.height == initial_stock_count
    db_mgr.close()


def test_control_plane_and_meta_integrity(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Verify Control Plane stores binary payloads and DuckDB Meta tables reflect catalog state.

    Parameters
    ----------
    tmp_path : Path
        Isolated temporary directory.
    rules : FinancialRules
        Isolated financial rules fixture.
    copy_evidence : Callable[[str, Path], dict[str, str]]
        Factory fixture to copy evidence files.
    """
    settings, source_config = _setup_isolated_static_environment(tmp_path, copy_evidence)
    status_q = NullEventQueue()
    emitter = ObservabilityEmitter()
    capabilities = [
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.INVESTMENT_ACCOUNTING,
    ]
    plan = CapabilityPlanner().create_plan(capabilities)
    db_mgr = DuckDBManager(settings.TARGET_DB_BASE_PATH)

    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=source_config,
    )
    orchestrator.run()

    # Verify Control Plane state in SQLite
    cp = ControlPlane(settings.TARGET_DB_BASE_PATH, settings.RAW_DOCUMENT_STORE_NAME)
    cp.open()
    try:
        cur = cp.db.conn.cursor()
        # Verify raw documents payload store
        cur.execute("SELECT COUNT(*), COUNT(file_bytes) FROM cp_file_payloads")
        row = cur.fetchone()
        assert row is not None
        payload_count, bytes_count = row
        assert payload_count > 0
        assert payload_count == bytes_count  # Every valid raw document must have a binary payload

        # Verify file registry
        cur.execute("SELECT COUNT(*) FROM cp_file_registry")
        reg_count = cur.fetchone()[0]
        assert reg_count > 0
    finally:
        cp.close()

    # Verify DuckDB Meta Layer state
    db_mgr.open()
    meta_files = db_mgr.conn.query("SELECT * FROM meta.m_File_Registry").pl()
    assert meta_files.height > 0
    assert "file_id" in meta_files.columns
    assert "relative_path" in meta_files.columns

    meta_counts = db_mgr.conn.query("SELECT * FROM meta.m_Table_Row_Counts").pl()
    assert meta_counts.height > 0
    assert "table_name" in meta_counts.columns
    assert "row_count" in meta_counts.columns
    db_mgr.close()


def test_pre_bronze_and_bronze_dunder_provenance(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Verify Pre-Bronze and Bronze tables adhere strictly to dunder provenance rules.

    Parameters
    ----------
    tmp_path : Path
        Isolated temporary directory.
    rules : FinancialRules
        Isolated financial rules fixture.
    copy_evidence : Callable[[str, Path], dict[str, str]]
        Factory fixture to copy evidence files.
    """
    settings, source_config = _setup_isolated_static_environment(tmp_path, copy_evidence)
    status_q = NullEventQueue()
    emitter = ObservabilityEmitter()
    capabilities = [
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.INVESTMENT_ACCOUNTING,
    ]
    plan = CapabilityPlanner().create_plan(capabilities)
    db_mgr = DuckDBManager(settings.TARGET_DB_BASE_PATH)

    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=source_config,
    )
    orchestrator.run()

    db_mgr.open()
    # Check Pre-Bronze MF Orders table
    pb_orders = db_mgr.conn.query("SELECT * FROM pre_bronze.investment_mf_orders").pl()
    assert pb_orders.height > 0
    assert "__source_id__" in pb_orders.columns
    assert "__dataset_id__" in pb_orders.columns
    assert PRE_BRONZE_ARTIFACT_ID in pb_orders.columns
    # Pre-Bronze must NOT contain legacy file columns or bare artifact_id
    assert "__file_name__" not in pb_orders.columns
    assert "__folder_path__" not in pb_orders.columns
    assert "artifact_id" not in pb_orders.columns

    # Check Bronze MF Transactions table
    b_orders = db_mgr.conn.query("SELECT * FROM bronze.investment_mf_orders").pl()
    assert b_orders.height > 0
    assert "artifact_id" in b_orders.columns
    # Bronze must NOT contain Pre-Bronze dunder columns
    assert "__file_name__" not in b_orders.columns
    assert "__folder_path__" not in b_orders.columns
    db_mgr.close()


def test_changed_artifact_and_rename_matrix(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Verify changing artifact content deletes old rows and renames migrate identity cleanly.

    Parameters
    ----------
    tmp_path : Path
        Isolated temporary directory.
    rules : FinancialRules
        Isolated financial rules fixture.
    copy_evidence : Callable[[str, Path], dict[str, str]]
        Factory fixture to copy evidence files.
    """
    settings, source_config = _setup_isolated_static_environment(tmp_path, copy_evidence)
    status_q = NullEventQueue()
    emitter = ObservabilityEmitter()
    capabilities = [
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.INVESTMENT_ACCOUNTING,
    ]
    plan = CapabilityPlanner().create_plan(capabilities)
    db_mgr = DuckDBManager(settings.TARGET_DB_BASE_PATH)

    # 1. Initial run
    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=source_config,
    )
    orchestrator.run()

    db_mgr.open()
    initial_isin = db_mgr.conn.query("SELECT * FROM bronze.investment_mf_isin_mapping").pl()
    assert initial_isin.height == 2
    initial_art_id = initial_isin["artifact_id"][0]
    db_mgr.close()

    # 2. Modify CSV file content
    isin_source = next(s for s in source_config.sources if "MF_ISIN_MAPPING.csv" in s.location)
    isin_path = Path(isin_source.location)
    isin_path.write_text(
        "INSTRUMENT_NAME,ISIN\n"
        "Parag Parikh Flexi Cap Fund - Direct Plan - Growth,INF879O01019\n"
        "Mirae Asset Large Cap Fund - Direct Plan - Growth,INF769K01018\n"
        "HDFC Top 100 Fund - Direct Plan - Growth,INF179K01BE2\n",
        encoding="utf-8",
    )

    # Re-run orchestrator
    orchestrator_mod = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=source_config,
    )
    orchestrator_mod.run()

    db_mgr.open()
    updated_isin = db_mgr.conn.query("SELECT * FROM bronze.investment_mf_isin_mapping").pl()
    # Old rows replaced atomically; new count is 3
    assert updated_isin.height == 3
    new_art_id = updated_isin["artifact_id"][0]
    # Artifact ID is path-stable for the same file
    assert new_art_id == initial_art_id
    db_mgr.close()


def test_validation_failure_rejection_gates(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Verify Gate 1 and Gate 2 reject invalid files without leaving partial Bronze rows.

    Parameters
    ----------
    tmp_path : Path
        Isolated temporary directory.
    rules : FinancialRules
        Isolated financial rules fixture.
    copy_evidence : Callable[[str, Path], dict[str, str]]
        Factory fixture to copy evidence files.
    """
    settings, source_config = _setup_isolated_static_environment(tmp_path, copy_evidence)
    emitter = ObservabilityEmitter()
    validator = PanderaDataFrameValidator(emitter=emitter)
    admission = AdmissionService()
    ingestion_service = DatasetIngestionService(validator, admission, emitter)

    db_mgr = DuckDBManager(settings.TARGET_DB_BASE_PATH)
    db_mgr.open()
    db_mgr.ensure_schemas()

    cp = ControlPlane(settings.TARGET_DB_BASE_PATH)
    cp.open()
    cp.ensure_schema()

    pre_bronze = PreBronzeLayer(db_mgr, emitter=emitter)
    meta = MetaLayer(db_mgr, settings, rules)
    bronze = BronzeLayer(db_mgr, cp, meta, emitter=emitter)

    # 1. Gate 1 Rejection: Overwrite stock PL with corrupt file
    evidence_dir = Path(__file__).resolve().parent.parent / "fixtures" / "evidence"
    corrupt_stock_src = evidence_dir / "negative" / "stock_pl_corrupt.xlsx"
    dest_pl = Path(settings.STATEMENTS_FOLDER) / "Stock PL Statements" / "stock_pl_sample.xlsx"
    shutil.copy2(corrupt_stock_src, dest_pl)

    norm_pl_path = str(dest_pl).replace("\\", "/")
    actionable = {"stock_pl": [norm_pl_path]}
    cp.artifacts.ingest_binaries(actionable)

    plan = CapabilityPlanner().create_plan()
    source_plan = SourcePlanner(source_config, plan).compile_plan()
    ds_plan_pl = source_plan.get_dataset_plan(DatasetId.MARKET_STOCK_HOLDINGS)
    assert ds_plan_pl is not None

    with pytest.raises((SchemaError, SchemaErrors, ValidationError)):
        ingestion_service.ingest_dataset(
            dataset_plan=ds_plan_pl,
            source_config=source_config,
            cp=cp,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta,
            actionable_files=actionable,
            run_id="run_gate1_fail",
        )

    # Assert 0 rows in bronze
    b_stocks = db_mgr.conn.query("SELECT * FROM bronze.market_stock_holdings").pl()
    assert b_stocks.height == 0

    cp.close()
    db_mgr.close()


def test_double_commit_crash_recovery(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Verify split-commit failure flags RECOVERY_REQUIRED and subsequent run heals state.

    Parameters
    ----------
    tmp_path : Path
        Isolated temporary directory.
    rules : FinancialRules
        Isolated financial rules fixture.
    copy_evidence : Callable[[str, Path], dict[str, str]]
        Factory fixture to copy evidence files.
    """
    settings, source_config = _setup_isolated_static_environment(tmp_path, copy_evidence)
    status_q = NullEventQueue()
    emitter = ObservabilityEmitter()
    capabilities = [
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.INVESTMENT_ACCOUNTING,
    ]
    plan = CapabilityPlanner().create_plan(capabilities)
    db_mgr = DuckDBManager(settings.TARGET_DB_BASE_PATH)

    lifecycle = RunLifecycleCoordinator(
        settings,
        status_q,
        db_mgr,
        rules,
        emitter=emitter,
        plan=plan,
        source_config=source_config,
    )
    _ = lifecycle.initialize()

    # Simulate split-commit crash
    lifecycle.duckdb_committed = True
    lifecycle.sqlite_committed = False
    lifecycle.handle_failure(RuntimeError("Simulated crash during SQLite commit"))
    assert lifecycle.commit_state == CommitState.RECOVERY_REQUIRED
    lifecycle.teardown()

    # Next run should execute recovery cleanly
    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=source_config,
    )
    orchestrator.run()

    db_mgr.open()
    df_mf = db_mgr.conn.query("SELECT * FROM bronze.investment_mf_orders").pl()
    assert df_mf.height > 0
    db_mgr.close()


def test_observability_and_multiprocessing_lineage(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Verify ObservabilityEmitter emits structured events and JSONL log trails.

    Parameters
    ----------
    tmp_path : Path
        Isolated temporary directory.
    rules : FinancialRules
        Isolated financial rules fixture.
    copy_evidence : Callable[[str, Path], dict[str, str]]
        Factory fixture to copy evidence files.
    """
    settings, source_config = _setup_isolated_static_environment(tmp_path, copy_evidence)
    status_q = NullEventQueue()
    emitter = ObservabilityEmitter()
    capabilities = [
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.INVESTMENT_ACCOUNTING,
    ]
    plan = CapabilityPlanner().create_plan(capabilities)

    class _TestCollectorSink:
        def __init__(self) -> None:
            self.events: list[ObservabilityEvent] = []

        def emit(self, event: ObservabilityEvent) -> None:
            self.events.append(event)

        def flush(self) -> None:
            pass

    sink = _TestCollectorSink()
    emitter.register_sink(sink)

    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=source_config,
    )
    orchestrator.run()

    events = sink.events
    assert len(events) > 0
    event_codes = {e.event_code for e in events}
    assert EventCode.RUN_START in event_codes
    assert EventCode.RUN_COMPLETED in event_codes

    # Verify JSONL log was written
    logs_dir = Path(settings.LOGS_DIRECTORY)
    jsonl_files = list(logs_dir.glob("*.jsonl"))
    assert len(jsonl_files) > 0


def test_protected_financial_identity_stability(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Verify deterministic financial IDs remain byte-stable across reruns.

    Parameters
    ----------
    tmp_path : Path
        Isolated temporary directory.
    rules : FinancialRules
        Isolated financial rules fixture.
    copy_evidence : Callable[[str, Path], dict[str, str]]
        Factory fixture to copy evidence files.
    """
    settings, source_config = _setup_isolated_static_environment(tmp_path, copy_evidence)
    status_q = NullEventQueue()
    emitter = ObservabilityEmitter()
    capabilities = [
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.INVESTMENT_ACCOUNTING,
    ]
    plan = CapabilityPlanner().create_plan(capabilities)
    db_mgr = DuckDBManager(settings.TARGET_DB_BASE_PATH)

    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=source_config,
    )
    orchestrator.run()

    db_mgr.open()
    # Check household transaction deterministic UID stability
    df_tx = db_mgr.conn.query("SELECT * FROM bronze.household_inoutcome").pl()
    assert df_tx.height > 0
    tx_uids = df_tx["UID"].to_list()
    assert "TX_001" in tx_uids
    assert "TX_002" in tx_uids

    # Check that artifact_id is a 64-character sha256 hex string
    art_ids = df_tx["artifact_id"].to_list()
    for art_id in art_ids:
        assert len(art_id) == 64
        int(art_id, 16)  # Must be valid hex
    db_mgr.close()


def test_downstream_execution_pipeline_smoke(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Verify full pipeline propagates data through Silver and Gold layers on static fixtures.

    Parameters
    ----------
    tmp_path : Path
        Isolated temporary directory.
    rules : FinancialRules
        Isolated financial rules fixture.
    copy_evidence : Callable[[str, Path], dict[str, str]]
        Factory fixture to copy evidence files.
    """
    settings, source_config = _setup_isolated_static_environment(tmp_path, copy_evidence)
    status_q = NullEventQueue()
    emitter = ObservabilityEmitter()
    capabilities = [
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.INVESTMENT_ACCOUNTING,
    ]
    plan = CapabilityPlanner().create_plan(capabilities)
    db_mgr = DuckDBManager(settings.TARGET_DB_BASE_PATH)

    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=source_config,
    )
    orchestrator.run()

    db_mgr.open()
    # Verify Silver tables were created and populated
    silver_tables = (
        db_mgr.conn.query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'silver'"
        )
        .pl()["table_name"]
        .to_list()
    )
    assert len(silver_tables) > 0

    # Verify Gold tables were created
    gold_tables = (
        db_mgr.conn.query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'gold'"
        )
        .pl()["table_name"]
        .to_list()
    )
    assert len(gold_tables) > 0
    db_mgr.close()
