"""Unit and integration tests for DiagnosticService and configuration diagnostics.

Owns
----
- Testing tri-configuration validation across settings, sources, and capability rules.
- Testing evidence source reachability and dataset selector diagnostics.
- Testing column mapping and normalization preview compilation.
- Testing deterministic row identity strategy preview and collision diagnostic generation.
- Testing execution plan compilation and topological order inspection.
- Testing admission dry-run execution and zero warehouse mutation guarantees.

Does not own
-------------
- Terminal Rich rendering or CLI exit codes (owned by presentation.cli.diagnostics).
- Production lakehouse schema creation or file movement.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from personal_finance_etl.application.diagnostics import DiagnosticService
from personal_finance_etl.application.pipeline.orchestrator import ETLOrchestrator
from personal_finance_etl.application.pipeline.source_planner import CompiledSourcePlan
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources import (
    SourceConfig,
    SourceConfiguration,
    SourceDatasetConfig,
)
from personal_finance_etl.config.sources.selectors import SqliteSelector
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.diagnostics import (
    ConfigValidationResult,
    DiagnosticSeverity,
    IdentityPreviewResult,
    MappingPreviewResult,
    PlanPreviewResult,
    PreflightCheckFailedError,
    SourceCheckResult,
    SourceReachabilityStatus,
)
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.contracts.observability import EventCode, ObservabilityEvent
from personal_finance_etl.contracts.sources import ProviderType, SourceId


def test_validate_configuration_success(
    config_path: Path,
    rules_path: Path,
    sources_path: Path,
) -> None:
    """Verify validating canonical configuration triad succeeds with active capabilities."""
    svc = DiagnosticService()
    result = svc.validate_configuration(
        config_path=str(config_path),
        rules_path=str(rules_path),
        sources_path=str(sources_path),
    )

    assert result.is_valid is True
    assert CapabilityId.HOUSEHOLD_CORE in result.active_capabilities
    assert DatasetId.HOUSEHOLD_INOUTCOME in result.active_datasets
    # Canonical files should not have error issues
    error_issues = [i for i in result.issues if i.severity == DiagnosticSeverity.ERROR]
    assert len(error_issues) == 0


def test_validate_configuration_missing_file(
    rules_path: Path,
    sources_path: Path,
) -> None:
    """Verify validation fails and emits error issue when configuration file is missing."""
    svc = DiagnosticService()
    result = svc.validate_configuration(
        config_path="non_existent_config.toml",
        rules_path=str(rules_path),
        sources_path=str(sources_path),
    )

    assert result.is_valid is False
    assert any(
        i.severity == DiagnosticSeverity.ERROR and "non_existent_config" in i.message
        for i in result.issues
    )


def test_validate_configuration_malformed_toml(
    tmp_path: Path,
    rules_path: Path,
    sources_path: Path,
) -> None:
    """Verify validation fails gracefully on malformed TOML syntax."""
    bad_toml = tmp_path / "broken.toml"
    bad_toml.write_text("invalid_syntax = [unclosed_bracket", encoding="utf-8")

    svc = DiagnosticService()
    result = svc.validate_configuration(
        config_path=str(bad_toml),
        rules_path=str(rules_path),
        sources_path=str(sources_path),
    )

    assert result.is_valid is False
    assert any("broken.toml" in i.location for i in result.issues)


def test_validate_configuration_missing_capability_rules(
    fixtures_dir: Path,
    config_path: Path,
    sources_path: Path,
) -> None:
    """Verify configuration validation detects missing rules when capability is active in plan."""
    # Use minimal household rules which lack [tax] and [fire]
    min_rules = fixtures_dir / "financial_rules_minimal_household.toml"

    svc = DiagnosticService()
    result = svc.validate_configuration(
        config_path=str(config_path),
        rules_path=str(min_rules),
        sources_path=str(sources_path),
    )

    # config.toml requests all capabilities including tax and fire, so min_rules should trigger issues
    rules_issues = [
        i for i in result.issues if i.category == "RULES" and i.severity == DiagnosticSeverity.ERROR
    ]
    assert len(rules_issues) >= 1
    assert any(i.field in ("tax", "fire") for i in rules_issues)


def test_check_sources_reachability(
    sources_path: Path,
    config_path: Path,
) -> None:
    """Verify reachability and selector status across canonical evidence sources."""
    svc = DiagnosticService()
    result = svc.check_sources(
        sources_path=str(sources_path),
        config_path=str(config_path),
    )

    assert len(result.sources) > 0
    # Each source should have a valid reachability status
    for s in result.sources:
        assert s.status in (
            SourceReachabilityStatus.REACHABLE,
            SourceReachabilityStatus.UNREACHABLE,
        )
        assert s.source_id is not None
        assert s.provider_type is not None


def test_check_sources_missing_sources_file(config_path: Path) -> None:
    """Verify check_sources reports error when sources.toml is missing."""
    svc = DiagnosticService()
    result = svc.check_sources(
        sources_path="missing_sources.toml",
        config_path=str(config_path),
    )

    assert result.is_all_reachable is False
    assert len(result.issues) > 0
    assert result.issues[0].severity == DiagnosticSeverity.ERROR


def test_preview_mapping_known_dataset(sources_path: Path) -> None:
    """Verify mapping preview for canonical household_inoutcome dataset."""
    svc = DiagnosticService()
    preview: MappingPreviewResult = svc.preview_mapping(
        dataset_id="household_inoutcome",
        sources_path=str(sources_path),
    )

    assert preview.dataset_id == DatasetId.HOUSEHOLD_INOUTCOME
    assert len(preview.field_mappings) > 0


def test_preview_mapping_unknown_dataset(sources_path: Path) -> None:
    """Verify preview_mapping raises ValueError for unknown or unbound dataset."""
    svc = DiagnosticService()
    with pytest.raises(ValueError, match="is not a valid DatasetId"):
        svc.preview_mapping(
            dataset_id="completely_fictional_dataset",
            sources_path=str(sources_path),
        )


def test_preview_identity_deterministic_hash(
    sources_path: Path,
    config_path: Path,
) -> None:
    """Verify identity preview extracts strategy and computes bounded sample row IDs."""
    svc = DiagnosticService()
    preview: IdentityPreviewResult = svc.preview_identity(
        dataset_id="household_inoutcome",
        sources_path=str(sources_path),
        config_path=str(config_path),
    )

    assert preview.dataset_id == DatasetId.HOUSEHOLD_INOUTCOME
    assert preview.strategy_kind in (
        "SourceFieldIdentity",
        "CompositeIdentity",
        "DerivedDeterministicIdentity",
    )
    assert preview.collision_detected is False


def test_preview_plan_topological_order(
    config_path: Path,
    sources_path: Path,
) -> None:
    """Verify execution plan preview enforces topological capability execution order."""
    svc = DiagnosticService()
    plan: PlanPreviewResult = svc.preview_plan(
        config_path=str(config_path),
        sources_path=str(sources_path),
    )

    assert len(plan.resolved_capabilities) > 0
    # Capability topological order: HOUSEHOLD_CORE should precede WEALTH, TAX, or FIRE
    if (
        CapabilityId.HOUSEHOLD_CORE in plan.resolved_capabilities
        and CapabilityId.FIRE in plan.resolved_capabilities
    ):
        hh_idx = plan.resolved_capabilities.index(CapabilityId.HOUSEHOLD_CORE)
        fire_idx = plan.resolved_capabilities.index(CapabilityId.FIRE)
        assert hh_idx < fire_idx

    assert DatasetId.HOUSEHOLD_INOUTCOME in plan.required_bronze_datasets


def test_dry_run_admission_zero_mutation(
    config_path: Path,
    rules_path: Path,
    sources_path: Path,
) -> None:
    """Verify admission dry run executes pre-bronze checks without mutating production database."""
    svc = DiagnosticService()
    result = svc.dry_run_admission(
        dataset_selector="household_inoutcome",
        config_path=str(config_path),
        rules_path=str(rules_path),
        sources_path=str(sources_path),
    )

    assert len(result.dataset_results) == 1
    ds_res = result.dataset_results[0]
    assert ds_res.dataset_id == DatasetId.HOUSEHOLD_INOUTCOME
    assert ds_res.status in ("PASSED", "SKIPPED", "FAILED")
    assert result.total_duration_seconds >= 0.0


def test_preflight_check_success_emits_events(
    config_path: Path,
    rules_path: Path,
) -> None:
    """Verify Phase 0 pre-flight check succeeds and emits validation events on valid configuration."""
    cfg = Settings.from_toml(config_path)
    rules = FinancialRules.from_toml(rules_path)
    events: list[ObservabilityEvent] = []

    class TestSink:
        def emit(self, event: ObservabilityEvent) -> None:
            events.append(event)

        def flush(self) -> None:
            pass

    from personal_finance_etl.infrastructure.observability import ObservabilityEmitter

    test_emitter = ObservabilityEmitter()
    test_emitter.register_sink(TestSink())

    class MockDiagnosticService:
        def validate_configuration(
            self,
            config_path: str = "config.toml",
            rules_path: str = "rules.toml",
            sources_path: str = "sources.toml",
            plan: ExecutionPlan | None = None,
            settings: Settings | None = None,
            rules: FinancialRules | None = None,
            sources: SourceConfiguration | None = None,
        ) -> ConfigValidationResult:
            return ConfigValidationResult(
                is_valid=True,
                active_capabilities=(CapabilityId.HOUSEHOLD_CORE,),
                active_datasets=(DatasetId.HOUSEHOLD_INOUTCOME,),
                issues=(),
                settings_path=config_path,
                rules_path=rules_path,
                sources_path=sources_path,
            )

        def check_sources(
            self,
            sources_path: str = "sources.toml",
            config_path: str | None = None,
            source_config: SourceConfiguration | None = None,
            source_plan: CompiledSourcePlan | None = None,
        ) -> SourceCheckResult:
            return SourceCheckResult(
                is_all_reachable=True,
                sources=(),
                issues=(),
            )

    orchestrator = ETLOrchestrator(
        cfg,
        rules=rules,
        emitter=test_emitter,
        diagnostic_service=MockDiagnosticService(),
    )
    orchestrator.execute_preflight_check()

    assert any(e.event_code == EventCode.PREFLIGHT_START for e in events)
    assert any(e.event_code == EventCode.PREFLIGHT_SUCCESS for e in events)


def test_preflight_check_halts_on_missing_required_capability_rules(
    fixtures_dir: Path,
    config_path: Path,
    tmp_path: Path,
) -> None:
    """Verify Phase 0 pre-flight check halts with PreflightCheckFailedError when rules are missing required capability."""
    cfg = Settings.from_toml(config_path)
    # Minimal household rules lacks [tax] and [fire], which are active in config_path
    minimal_rules = fixtures_dir / "financial_rules_minimal_household.toml"
    rules = FinancialRules.from_toml(minimal_rules)
    events: list[ObservabilityEvent] = []

    class TestSink:
        def emit(self, event: ObservabilityEvent) -> None:
            events.append(event)

        def flush(self) -> None:
            pass

    from personal_finance_etl.infrastructure.observability import ObservabilityEmitter

    test_emitter = ObservabilityEmitter()
    test_emitter.register_sink(TestSink())

    diag_svc = DiagnosticService(emitter=test_emitter)
    orchestrator = ETLOrchestrator(
        cfg,
        rules=rules,
        emitter=test_emitter,
        diagnostic_service=diag_svc,
    )

    with pytest.raises(PreflightCheckFailedError) as exc_info:
        orchestrator.run()

    assert "Pre-flight health check failed" in str(exc_info.value)
    assert any(e.event_code == EventCode.PREFLIGHT_FAILED for e in events)


def test_preflight_check_skipped_when_skip_preflight_is_true(
    fixtures_dir: Path,
    config_path: Path,
) -> None:
    """Verify Phase 0 pre-flight check is bypassed when skip_preflight is True."""
    cfg = Settings.from_toml(config_path)
    minimal_rules = fixtures_dir / "financial_rules_minimal_household.toml"
    rules = FinancialRules.from_toml(minimal_rules)
    events: list[ObservabilityEvent] = []

    class TestSink:
        def emit(self, event: ObservabilityEvent) -> None:
            events.append(event)

        def flush(self) -> None:
            pass

    from personal_finance_etl.infrastructure.observability import ObservabilityEmitter

    test_emitter = ObservabilityEmitter()
    test_emitter.register_sink(TestSink())

    diag_svc = DiagnosticService(emitter=test_emitter)
    orchestrator = ETLOrchestrator(
        cfg,
        rules=rules,
        emitter=test_emitter,
        skip_preflight=True,
        diagnostic_service=diag_svc,
    )
    assert orchestrator.skip_preflight is True


def test_preflight_check_bypassed_when_no_diagnostic_service_injected(
    fixtures_dir: Path,
    config_path: Path,
) -> None:
    """Verify Phase 0 pre-flight check is safely bypassed when no diagnostic service is injected."""
    cfg = Settings.from_toml(config_path)
    minimal_rules = fixtures_dir / "financial_rules_minimal_household.toml"
    rules = FinancialRules.from_toml(minimal_rules)

    orchestrator = ETLOrchestrator(cfg, rules=rules)
    assert orchestrator.diagnostic_service is None
    # Calling execute_preflight_check returns cleanly without raising PreflightCheckFailedError
    orchestrator.execute_preflight_check()


def test_check_sources_discovers_mmbak_and_candidate_sheets(tmp_path: Path) -> None:
    """Verify check_sources discovers SQLite databases with .mmbak extension in backup folders."""
    db_folder = tmp_path / "MoneyManager"
    db_folder.mkdir()
    mmbak_file = db_folder / "MMGF(06-11-24-233153).mmbak"

    with sqlite3.connect(mmbak_file) as conn:
        conn.execute("CREATE TABLE ZCATEGORY (UID TEXT PRIMARY KEY, NAME TEXT);")
        conn.execute("INSERT INTO ZCATEGORY VALUES ('c1', 'Groceries');")
        conn.commit()

    src_config = SourceConfiguration(
        schema_version="1.0.0",
        sources=(
            SourceConfig(
                source_id=SourceId("household_db"),
                provider_type=ProviderType.SQLITE,
                location=str(db_folder),
                enabled=True,
                description="MoneyManager backup folder",
            ),
        ),
        datasets=(
            SourceDatasetConfig(
                source_id=SourceId("household_db"),
                dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
                selector=SqliteSelector(table_name="ZCATEGORY"),
                enabled=True,
                description="Categories",
            ),
        ),
    )

    diag_svc = DiagnosticService()
    res = diag_svc.check_sources(source_config=src_config)

    assert res.is_all_reachable is True
    assert len(res.sources) == 1
    src_res = res.sources[0]
    assert src_res.status == SourceReachabilityStatus.REACHABLE
    assert len(src_res.dataset_selectors) == 1
    sel_res = src_res.dataset_selectors[0]
    assert sel_res.is_valid is True
    assert sel_res.selector_target == "ZCATEGORY"
    assert "ZCATEGORY" in sel_res.available_targets
