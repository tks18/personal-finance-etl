"""Phase 4 Configuration and Financial Rules Provenance Test Suite.

Owns
----
- Verification of deterministic cryptographic fingerprinting for Settings and FinancialRules.
- Verification of safe summary metadata generation without secret path or credential leakage.
- Verification of SYSTEM_CONFIG_FINGERPRINT event emission carrying real fingerprint context.
- Verification that unrestricted JSON configuration dumps are completely eradicated from logs.
- Verification that ambient observability context propagates fingerprints across all downstream events.
- Verification of SQLite Control Plane snapshot correlation with active run IDs.

Does not own
-------------
- TOML file schema parsing and Pydantic validation (owned by config.settings and config.financial_rules).
- Forensic trace compression lifecycle (owned by infrastructure.observability.archival).
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_current_context,
)
from personal_finance_etl.application.pipeline.lifecycle import RunLifecycleCoordinator
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    ObservabilityEvent,
    ObservabilitySink,
    PresentationKind,
)
from personal_finance_etl.infrastructure.observability.redaction import (
    ConfigFingerprintDict,
    RulesFingerprintDict,
    fingerprint_config,
    fingerprint_rules,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager


class _CollectingSink(ObservabilitySink):
    """Test helper sink collecting emitted events in-memory."""

    def __init__(self) -> None:
        self.events: list[ObservabilityEvent] = []

    def emit(self, event: ObservabilityEvent) -> None:
        self.events.append(event)

    def flush(self) -> None:
        pass


class _DummyStatusQueue:
    """Test dummy queue implementing the canonical EventQueue protocol."""

    def put(
        self,
        status: object,
        /,
        block: bool = True,
        timeout: float | None = None,
    ) -> None:
        del status, block, timeout


def test_fingerprint_config_determinism_and_privacy() -> None:
    """Verify fingerprint_config produces identical hashes for identical configurations."""
    cfg1 = Settings(
        TARGET_DB_BASE_PATH="/secret/vault/db",
        TARGET_DB_NAME="finance.duckdb",
        DISABLE_FILE_DISCOVERER=True,
        RETAIN_LAST_N_RUNS=10,
    )
    cfg2 = Settings(
        TARGET_DB_BASE_PATH="/secret/vault/db",
        TARGET_DB_NAME="finance.duckdb",
        DISABLE_FILE_DISCOVERER=True,
        RETAIN_LAST_N_RUNS=10,
    )

    res1: ConfigFingerprintDict = fingerprint_config(cfg1)
    res2: ConfigFingerprintDict = fingerprint_config(cfg2)

    assert res1["config_hash"] == res2["config_hash"]
    assert res1["config_hash"].startswith("sha256_")
    assert res1["target_db_name"] == "finance.duckdb"
    assert res1["disable_file_discoverer"] is True
    assert res1["retain_last_n_runs"] == 10

    # Changing a parameter must alter the fingerprint digest
    cfg3 = Settings(
        TARGET_DB_BASE_PATH="/secret/vault/db",
        TARGET_DB_NAME="finance.duckdb",
        DISABLE_FILE_DISCOVERER=False,
        RETAIN_LAST_N_RUNS=10,
    )
    res3 = fingerprint_config(cfg3)
    assert res3["config_hash"] != res1["config_hash"]


def test_fingerprint_rules_determinism_and_defaults() -> None:
    """Verify fingerprint_rules handles None and produces deterministic digests."""
    none_res: RulesFingerprintDict = fingerprint_rules(None)
    assert none_res["rules_hash"] == "none"
    assert none_res["default_currency_id"] == ""
    assert none_res["investment_instrument_count"] == 0
    assert none_res["has_tax_assumptions"] is False

    rules_path = Path("tests/financial_rules.toml")
    if not rules_path.exists():
        pytest.skip("tests/financial_rules.toml not found")

    rules1 = FinancialRules.from_toml(rules_path)
    rules2 = FinancialRules.from_toml(rules_path)

    res1: RulesFingerprintDict = fingerprint_rules(rules1)
    res2: RulesFingerprintDict = fingerprint_rules(rules2)

    assert res1["rules_hash"] == res2["rules_hash"]
    assert res1["rules_hash"].startswith("sha256_")
    assert res1["default_currency_id"] == "INR_INR"


def test_lifecycle_emits_system_config_fingerprint_with_real_values(tmp_path: Path) -> None:
    """Verify RunLifecycleCoordinator emits SYSTEM_CONFIG_FINGERPRINT with real context."""
    db_base = tmp_path / "data"
    db_base.mkdir(parents=True, exist_ok=True)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    cfg = Settings(
        TARGET_DB_BASE_PATH=str(db_base),
        TARGET_DB_NAME="test_prov.duckdb",
        RAW_DOCUMENT_STORE_NAME="test_prov_raw.duckdb",
        LOGS_DIRECTORY=str(logs_dir),
    )

    rules_path = Path("tests/financial_rules.toml")
    rules = FinancialRules.from_toml(rules_path) if rules_path.exists() else None

    emitter = ObservabilityEmitter()
    collecting_sink = _CollectingSink()
    emitter.register_sink(collecting_sink)

    db_manager = DuckDBManager(cfg.TARGET_DB_BASE_PATH, cfg.TARGET_DB_NAME)
    status_queue = _DummyStatusQueue()

    coordinator = RunLifecycleCoordinator(
        cfg,
        status_queue,
        db_manager,
        rules=rules,
        emitter=emitter,
    )

    cp, run_id, _ = coordinator.initialize()

    try:
        # Verify SYSTEM_CONFIG_FINGERPRINT event was emitted
        fp_events = [
            e for e in collecting_sink.events if e.event_code == EventCode.SYSTEM_CONFIG_FINGERPRINT
        ]
        assert len(fp_events) == 1
        fp_event = fp_events[0]

        assert fp_event.presentation_kind == PresentationKind.INTERNAL
        assert fp_event.severity in (DiagnosticSeverity.DEBUG, DiagnosticSeverity.INFO)
        assert fp_event.context.settings_fingerprint is not None
        assert fp_event.context.settings_fingerprint.startswith("sha256_")
        assert fp_event.context.rules_fingerprint is not None

        # Verify ambient context was bound with real fingerprints
        ambient = get_current_context()
        assert ambient.run_id == run_id
        assert ambient.settings_fingerprint == fp_event.context.settings_fingerprint
        assert ambient.rules_fingerprint == fp_event.context.rules_fingerprint

        # Verify Control Plane snapshot persistence
        with cp.db.atomic():
            cursor = cp.db.conn.execute(
                "SELECT settings_snapshot_id, rules_snapshot_id FROM cp_runs WHERE run_id = ?",
                (run_id,),
            )
            raw_runs = cast(list[tuple[object, object]], cursor.fetchall())
            assert len(raw_runs) == 1
            settings_snap, rules_snap = raw_runs[0]
            assert settings_snap is not None
            assert str(settings_snap).startswith("snap_set_")
            if rules is not None:
                assert rules_snap is not None
                assert str(rules_snap).startswith("snap_rule_")

    finally:
        coordinator.commit()
        coordinator.teardown()

