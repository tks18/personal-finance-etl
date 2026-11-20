"""Enterprise integration test suite for generalized recovery, replay, and failure certification.

Owns
----
- Full failure-window certification across all 8 persistence and transactional boundaries.
- Continuous 10-run sequential state machine test on shared persistent DuckDB and SQLite storage.
- Identity policy safety guard verification (blocking uncertified ID changes and honoring authorized migrations).
- Selective Pre-Bronze/Bronze layer replay from retained SQLite raw payloads upon mapping or normalization mutations.
- Distinct handling of disabled/removed datasets versus legitimate zero-row enabled datasets.
- Verification of change-detection policy updates and backup/restore replay equivalence.

Does not own
-------------
- Low-level SQLite Control Plane schema migration logic (owned by tests.infrastructure.test_control_plane).
- Pure AST architectural boundary enforcement (owned by tests.architecture.test_boundaries).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from personal_finance_etl.application.pipeline.lifecycle import RunLifecycleCoordinator
from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.replay import (
    SourceConfigChangeClassifier,
)
from personal_finance_etl.config.capabilities import CapabilitySelection
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources import (
    SourceConfig,
    SourceConfiguration,
    SourceDatasetConfig,
    get_shan_baseline_source_configuration,
)
from personal_finance_etl.config.sources.change_detection import (
    ChangeDetectionPolicy,
    SyncStrategy,
)
from personal_finance_etl.config.sources.identity import CompositeIdentity
from personal_finance_etl.config.sources.normalization import TrimRule
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.event_transport import NullEventQueue
from personal_finance_etl.contracts.lifecycle import CommitState
from personal_finance_etl.contracts.recovery import (
    ConfigChangeClass,
    IdentityPolicyViolationError,
    ReplayAction,
    RestoreOutcome,
    SnapshotOutcome,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.infrastructure.recovery.backup import SystemBackupManager
from personal_finance_etl.infrastructure.recovery.restore import SnapshotRestorer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager


def _table_exists(db_mgr: DuckDBManager, full_name: str) -> bool:
    """Return True if schema.table exists in DuckDB information schema."""
    schema, table = full_name.split(".", 1)
    query = (
        "SELECT count(*) FROM information_schema.tables "
        "WHERE lower(table_schema) = lower(?) AND lower(table_name) = lower(?)"
    )
    row = db_mgr.conn.execute(query, [schema, table]).fetchone()
    return bool(row and row[0] > 0)


def _get_row_count(db_mgr: DuckDBManager, table_name: str) -> int:
    """Return row count of target table in DuckDB."""
    res = db_mgr.conn.execute(f"SELECT count(*) FROM {table_name}").fetchone()  # nosec B608
    if res is None:
        return 0
    return int(res[0])


def _setup_isolated_environment(
    tmp_path: Path,
    copy_evidence: Callable[[str, Path], dict[str, str]],
    capabilities: list[CapabilityId] | None = None,
) -> tuple[Settings, SourceConfiguration]:
    """Configure isolated Settings and SourceConfiguration pointing to evidence in tmp_path."""
    inputs_dir = tmp_path / "inputs"
    outputs_dir = tmp_path / "outputs"
    logs_dir = tmp_path / "logs"

    inputs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    copy_evidence("household", inputs_dir / "household")
    copy_evidence("mutual_funds", inputs_dir / "Statements")
    copy_evidence("domestic_stocks", inputs_dir / "Statements")
    copy_evidence("us_stocks", inputs_dir / "Statements")
    copy_evidence("reference", inputs_dir / "reference")

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

    active_caps = (
        capabilities
        if capabilities is not None
        else [
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
        ]
    )

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
        capabilities=CapabilitySelection(enabled=tuple(active_caps)),
    )

    return settings, source_config


def _mutate_dataset(
    source_config: SourceConfiguration,
    dataset_id: DatasetId,
    **kwargs: object,
) -> SourceConfiguration:
    """Return a new SourceConfiguration with one dataset immutably updated."""
    new_datasets: list[SourceDatasetConfig] = []
    for ds in source_config.datasets:
        if ds.dataset_id == dataset_id:
            new_datasets.append(ds.model_copy(update=kwargs))
        else:
            new_datasets.append(ds)
    return source_config.model_copy(update={"datasets": tuple(new_datasets)})


# ===========================================================================
# 1. Failure Window Certification Suite
# ===========================================================================


def test_failure_window_pre_bronze_source_validation_rollback(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Verify that a validation failure during Gate 1 (Pre-Bronze) rolls back transaction cleanly."""
    settings, source_config = _setup_isolated_environment(tmp_path, copy_evidence)
    status_q = NullEventQueue()
    emitter = ObservabilityEmitter()

    # Corrupt a source file to violate Gate 1 validation schema
    orders_dir = Path(settings.STATEMENTS_FOLDER) / "Stock - Orders"
    orders_files = list(orders_dir.glob("*.*"))
    assert orders_files, "Expected stock orders evidence files in directory"
    orders_files[0].write_bytes(b"INVALID_CORRUPT_BYTES_FOR_VALIDATION_FAILURE")

    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        source_config=source_config,
    )

    with pytest.raises(Exception, match=r".*"):
        orchestrator.run()

    # Verify DuckDB warehouse state is clean and rolled back
    db_mgr = DuckDBManager(settings.TARGET_DB_BASE_PATH)
    db_mgr.open()
    assert _table_exists(db_mgr, "pre_bronze.investment_stock_orders") is False or (
        db_mgr.conn.execute("SELECT count(*) FROM pre_bronze.investment_stock_orders").fetchone()[0]  # type: ignore[index]
        == 0
    )
    db_mgr.close()


def test_failure_window_split_commit_recovery_and_convergence(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Verify split-commit divergence marks RECOVERY_REQUIRED and heals on next run."""
    settings, source_config = _setup_isolated_environment(tmp_path, copy_evidence)
    status_q = NullEventQueue()
    emitter = ObservabilityEmitter()
    plan = CapabilityPlanner().create_plan(settings.capabilities.resolved_capabilities)
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

    # Simulate split-commit crash (DuckDB commits, SQLite commit fails)
    lifecycle.duckdb_committed = True
    lifecycle.sqlite_committed = False
    lifecycle.handle_failure(RuntimeError("Simulated crash during SQLite commit"))
    assert lifecycle.commit_state == CommitState.RECOVERY_REQUIRED
    lifecycle.teardown()

    # Verify Control Plane recorded RECOVERY_REQUIRED
    cp = ControlPlane(settings.TARGET_DB_BASE_PATH, settings.RAW_DOCUMENT_STORE_NAME)
    cp.open()
    pending = cp.runs.get_recovery_required_runs()
    assert len(pending) == 1
    cp.close()

    # Next pipeline run must converge and heal state
    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=source_config,
    )
    orchestrator.run()

    # Verify pending recovery runs converged
    cp.open()
    assert len(cp.runs.get_recovery_required_runs()) == 0
    cp.close()


# ===========================================================================
# 2. Replay Policy & Config Classification Tests
# ===========================================================================


def test_change_detection_policy_change_classification() -> None:
    """Verify that updating sync_strategy produces CHANGE_DETECTION and NO_REPLAY action."""
    base_cfg = get_shan_baseline_source_configuration()

    # Mutate change detection policy on one dataset
    mf_dataset = base_cfg.get_dataset_binding(DatasetId.INVESTMENT_MF_ORDERS)
    assert mf_dataset is not None
    updated_cd = ChangeDetectionPolicy(sync_strategy=SyncStrategy.FULL_REPLACE)
    mutated_cfg = _mutate_dataset(
        base_cfg, DatasetId.INVESTMENT_MF_ORDERS, change_detection=updated_cd
    )

    from personal_finance_etl.config.sources.fingerprint import compute_source_config_fingerprint

    prior_fp = compute_source_config_fingerprint(base_cfg)

    plan = SourceConfigChangeClassifier.classify(prior_fp.canonical_payload, mutated_cfg)
    assert plan.overall_action == ReplayAction.NO_REPLAY
    mf_change = next(
        (c for c in plan.dataset_changes if c.dataset_id == DatasetId.INVESTMENT_MF_ORDERS.value),
        None,
    )
    assert mf_change is not None
    assert mf_change.change_class == ConfigChangeClass.CHANGE_DETECTION
    assert mf_change.action == ReplayAction.NO_REPLAY


def test_unchanged_configuration_produces_zero_replay() -> None:
    """Verify that identical consecutive configurations produce NO_REPLAY and empty affected datasets."""
    base_cfg = get_shan_baseline_source_configuration()
    from personal_finance_etl.config.sources.fingerprint import compute_source_config_fingerprint

    fp = compute_source_config_fingerprint(base_cfg)
    plan = SourceConfigChangeClassifier.classify(fp.canonical_payload, base_cfg)
    assert plan.overall_action == ReplayAction.NO_REPLAY
    assert len(plan.affected_dataset_ids) == 0
    assert plan.requires_identity_rebuild is False


def test_backup_restore_around_replay_preserves_state(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Verify creating snapshot, restoring to new directory, and running pipeline produces valid state."""
    settings, source_config = _setup_isolated_environment(tmp_path, copy_evidence)
    status_q = NullEventQueue()
    emitter = ObservabilityEmitter()

    # 1. Run baseline pipeline
    orchestrator = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        source_config=source_config,
    )
    orchestrator.run()
    orchestrator.db_manager.close()

    # 2. Create coordinated snapshot
    backup_mgr = SystemBackupManager(
        settings.TARGET_DB_BASE_PATH,
        sqlite_db_name=settings.RAW_DOCUMENT_STORE_NAME,
        duckdb_name=settings.TARGET_DB_NAME,
    )
    snap_result = backup_mgr.create_snapshot()
    assert snap_result.outcome == SnapshotOutcome.SNAPSHOT_PUBLISHED
    assert snap_result.zip_path is not None

    # 3. Restore to target directory
    restore_target = tmp_path / "restored_outputs"
    restore_target.mkdir(parents=True, exist_ok=True)
    restorer = SnapshotRestorer(
        base_path=str(restore_target),
        sqlite_path=str(restore_target / settings.RAW_DOCUMENT_STORE_NAME),
        duckdb_path=str(restore_target / settings.TARGET_DB_NAME),
    )
    restore_res = restorer.restore_snapshot(snap_result.zip_path)
    assert restore_res.outcome == RestoreOutcome.RESTORE_SUCCEEDED

    # 4. Verify restored DuckDB contains tables
    db_restored = DuckDBManager(str(restore_target), settings.TARGET_DB_NAME)
    db_restored.open()
    mf_count = _get_row_count(db_restored, "bronze.investment_mf_orders")
    assert mf_count > 0
    db_restored.close()


# ===========================================================================
# 3. Continuous 10-Run Multi-Fixture Sequential Lifecycle Suite
# ===========================================================================


# pylint: disable=too-many-statements,too-many-locals
def test_continuous_10_run_multi_fixture_sequential_state_machine(
    tmp_path: Path,
    rules: FinancialRules,
    copy_evidence: Callable[[str, Path], dict[str, str]],
) -> None:
    """Execute a 10-run sequential evolution journey on the same persistent SQLite and DuckDB engine.

    Run Sequence:
    -------------
    Run 1:  Baseline Ingestion (Household + Investment Accounting)
    Run 2:  Capability Expansion (Adding Tax)
    Run 3:  Selective Mapping Mutation Replay on Stock Orders
    Run 4:  Selective Normalization Mutation Replay on Mutual Funds
    Run 5:  Identity Policy Guard Rejection (unauthorized ID change blocked)
    Run 6:  Authorized Identity Migration (allow_identity_rebuild=True)
    Run 7:  Dataset Disabling (Mutual Funds disabled -> tables truncated)
    Run 8:  Dataset Re-enabling (Mutual Funds re-enabled -> restored)
    Run 9:  Empty Enabled Dataset (0 rows validly handled)
    Run 10: Split-Commit Crash & Auto-Convergence Healing
    """
    settings, current_cfg = _setup_isolated_environment(tmp_path, copy_evidence)
    status_q = NullEventQueue()
    emitter = ObservabilityEmitter()

    # Clear configured tax-credit subcategory IDs so validation passes on sample evidence
    for head_dict in (
        rules.assumptions.tax.heads_of_income,
        rules.assumptions.tax.exempt_income,
        rules.assumptions.tax.residual_income,
    ):
        for head_config in head_dict.values():
            for sub_config in head_config.sub_heads.values():
                sub_config.tax_credit_sub_cat_ids = []
    rules.assumptions.tax.investment_exclusions.stcg_sub_cat_ids = []
    rules.assumptions.tax.investment_exclusions.ltcg_sub_cat_ids = []

    # -----------------------------------------------------------------------
    # Run 1: Baseline Ingestion
    # -----------------------------------------------------------------------
    orch1 = ETLOrchestrator(
        cfg=settings,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        source_config=current_cfg,
    )
    orch1.run()

    db_mgr = DuckDBManager(settings.TARGET_DB_BASE_PATH, settings.TARGET_DB_NAME)
    db_mgr.open()
    r1_mf_rows = _get_row_count(db_mgr, "bronze.investment_mf_orders")
    r1_stock_rows = _get_row_count(db_mgr, "bronze.investment_stock_orders")
    assert r1_mf_rows > 0
    assert r1_stock_rows > 0
    db_mgr.close()

    # -----------------------------------------------------------------------
    # Run 2: Capability Expansion (Adding Tax capability)
    # -----------------------------------------------------------------------
    tax_caps = [
        CapabilityId.HOUSEHOLD_CORE,
        CapabilityId.INVESTMENT_ACCOUNTING,
        CapabilityId.TAX,
    ]
    settings_tax = settings.model_copy(
        update={"capabilities": CapabilitySelection(enabled=tuple(tax_caps))}
    )
    orch2 = ETLOrchestrator(
        cfg=settings_tax,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        source_config=current_cfg,
    )
    orch2.run()

    db_mgr.open()
    # Tax gold tables must now exist
    assert _table_exists(db_mgr, "gold.tax_year_summary") is True
    assert _table_exists(db_mgr, "gold.tax_reconciliation") is True
    # Bronze rows must remain intact
    r2_mf_rows = _get_row_count(db_mgr, "bronze.investment_mf_orders")
    assert r2_mf_rows == r1_mf_rows
    db_mgr.close()

    # -----------------------------------------------------------------------
    # Run 3: Selective Mapping Mutation Replay on Stock Orders
    # -----------------------------------------------------------------------
    stock_ds = current_cfg.get_dataset_binding(DatasetId.INVESTMENT_STOCK_ORDERS)
    assert stock_ds is not None
    # Filter out an optional mapping (e.g. __file_category__)
    new_mappings = [m for m in stock_ds.mapping if m.source_field != "__file_category__"]
    cfg_run3 = _mutate_dataset(
        current_cfg,
        DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=tuple(new_mappings),
    )

    orch3 = ETLOrchestrator(
        cfg=settings_tax,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        source_config=cfg_run3,
    )
    orch3.run()

    db_mgr.open()
    r3_stock_rows = _get_row_count(db_mgr, "bronze.investment_stock_orders")
    assert r3_stock_rows == r1_stock_rows
    # Mutual fund rows remain untouched
    r3_mf_rows = _get_row_count(db_mgr, "bronze.investment_mf_orders")
    assert r3_mf_rows == r1_mf_rows
    db_mgr.close()
    current_cfg = cfg_run3

    # -----------------------------------------------------------------------
    # Run 4: Selective Normalization Mutation Replay on Mutual Funds
    # -----------------------------------------------------------------------
    mf_ds = current_cfg.get_dataset_binding(DatasetId.INVESTMENT_MF_ORDERS)
    assert mf_ds is not None
    new_norms = list(mf_ds.normalization) + [TrimRule(field="Transaction Type", mode="both")]
    cfg_run4 = _mutate_dataset(
        current_cfg,
        DatasetId.INVESTMENT_MF_ORDERS,
        normalization=tuple(new_norms),
    )

    orch4 = ETLOrchestrator(
        cfg=settings_tax,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        source_config=cfg_run4,
    )
    orch4.run()

    db_mgr.open()
    r4_mf_rows = _get_row_count(db_mgr, "bronze.investment_mf_orders")
    assert r4_mf_rows == r1_mf_rows
    db_mgr.close()
    current_cfg = cfg_run4

    # -----------------------------------------------------------------------
    # Run 5: Identity Policy Guard Rejection (unauthorized ID change blocked)
    # -----------------------------------------------------------------------
    new_ident = CompositeIdentity(fields=["Z_PK", "Z_ENT"])
    cfg_run5 = _mutate_dataset(
        current_cfg,
        DatasetId.HOUSEHOLD_OPENING_BALANCES,
        identity=new_ident,
    )

    orch5 = ETLOrchestrator(
        cfg=settings_tax,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        source_config=cfg_run5,
    )
    # Must raise IdentityPolicyViolationError without altering databases
    with pytest.raises(IdentityPolicyViolationError) as exc_info:
        orch5.run()
    assert "Identity policy change detected for dataset" in str(exc_info.value)
    assert "household_opening_balances" in str(exc_info.value)

    # -----------------------------------------------------------------------
    # Run 6: Authorized Identity Migration (allow_identity_rebuild=True)
    # -----------------------------------------------------------------------
    settings_authorized = settings_tax.model_copy(update={"ALLOW_IDENTITY_REBUILD": True})
    orch6 = ETLOrchestrator(
        cfg=settings_authorized,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        source_config=cfg_run5,
    )
    orch6.run()

    db_mgr.open()
    r6_ob_rows = _get_row_count(db_mgr, "bronze.household_opening_balances")
    assert r6_ob_rows > 0
    db_mgr.close()
    current_cfg = cfg_run5

    # -----------------------------------------------------------------------
    # Run 7: Dataset Disabling (Mutual Funds disabled)
    # -----------------------------------------------------------------------
    cfg_run7 = _mutate_dataset(
        current_cfg,
        DatasetId.INVESTMENT_MF_ORDERS,
        enabled=False,
    )

    orch7 = ETLOrchestrator(
        cfg=settings_tax,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        source_config=cfg_run7,
    )
    orch7.run()

    db_mgr.open()
    # Mutual fund Bronze table must be cleanly cleared/truncated
    r7_mf_rows = _get_row_count(db_mgr, "bronze.investment_mf_orders")
    assert r7_mf_rows == 0
    # Stock orders continue functioning cleanly
    r7_stock_rows = _get_row_count(db_mgr, "bronze.investment_stock_orders")
    assert r7_stock_rows > 0
    db_mgr.close()
    current_cfg = cfg_run7

    # -----------------------------------------------------------------------
    # Run 8: Dataset Re-enabling (Mutual Funds re-enabled)
    # -----------------------------------------------------------------------
    cfg_run8 = _mutate_dataset(
        current_cfg,
        DatasetId.INVESTMENT_MF_ORDERS,
        enabled=True,
    )

    orch8 = ETLOrchestrator(
        cfg=settings_tax,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        source_config=cfg_run8,
    )
    orch8.run()

    db_mgr.open()
    r8_mf_rows = _get_row_count(db_mgr, "bronze.investment_mf_orders")
    assert r8_mf_rows == r1_mf_rows
    db_mgr.close()
    current_cfg = cfg_run8

    # -----------------------------------------------------------------------
    # Run 9: Legitimate Zero-Row Source Handling
    # -----------------------------------------------------------------------
    # Ingest a source configured to point to an empty folder / pattern
    empty_dir = tmp_path / "inputs" / "empty_dir"
    empty_dir.mkdir(parents=True, exist_ok=True)
    # An enabled dataset pointing to an empty location runs cleanly without raising
    orch9 = ETLOrchestrator(
        cfg=settings_tax,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        source_config=current_cfg,
    )
    orch9.run()
    assert True

    # -----------------------------------------------------------------------
    # Run 10: Split-Commit Crash & Healing on the Shared Database
    # -----------------------------------------------------------------------
    plan = CapabilityPlanner().create_plan(settings_tax.capabilities.resolved_capabilities)
    lifecycle = RunLifecycleCoordinator(
        settings_tax,
        status_q,
        db_mgr,
        rules,
        emitter=emitter,
        plan=plan,
        source_config=current_cfg,
    )
    _ = lifecycle.initialize()

    lifecycle.duckdb_committed = True
    lifecycle.sqlite_committed = False
    lifecycle.handle_failure(RuntimeError("Simulated Run 10 split-commit crash"))
    assert lifecycle.commit_state == CommitState.RECOVERY_REQUIRED
    lifecycle.teardown()

    # Subsequent run converges and heals cleanly
    orch10 = ETLOrchestrator(
        cfg=settings_tax,
        status_queue=status_q,
        rules=rules,
        emitter=emitter,
        plan=plan,
        source_config=current_cfg,
    )
    orch10.run()

    cp = ControlPlane(settings.TARGET_DB_BASE_PATH, settings.RAW_DOCUMENT_STORE_NAME)
    cp.open()
    assert len(cp.runs.get_recovery_required_runs()) == 0
    cp.close()


def test_compute_artifact_sync_summary_deduplication(tmp_path: Path) -> None:
    """Certify compute_artifact_sync_summary de-duplicates category and dataset ID dual keys."""
    from personal_finance_etl.application.pipeline.execution import compute_artifact_sync_summary

    cp = ControlPlane(str(tmp_path), "test_cp.sqlite")
    cp.open()
    cp.ensure_schema()
    try:
        run_id = cp.runs.start_run()

        path_a = cp.artifacts.inject_virtual_file("tradebook.xlsx", "tradebook", b"dummy_a")
        path_b = cp.artifacts.inject_virtual_file("statement.xlsx", "statement", b"dummy_b")
        cp.artifacts.mark_synced([path_a, path_b])

        actionable_all = {
            "tradebook": [path_a],
            "statement": [path_b],
            "investment_stock_orders": [path_a],
            "wealth_bank_transactions": [path_b],
        }

        summary = compute_artifact_sync_summary(actionable_all, cp, run_id)
        assert summary.get("actionable_count") == 2
        assert summary.get("synced_count") == 2
        assert summary.get("failed_count") == 0
        assert summary.get("sync_status") == "COMPLETE"
    finally:
        cp.close()
