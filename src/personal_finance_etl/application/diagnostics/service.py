"""Application diagnostics service for personal finance configuration and admission.

Owns
----
- DiagnosticService: Application service for multi-configuration validation, source reachability,
  mapping/identity preview, capability plan preview, and zero-mutation admission dry run.

Does not own
-------------
- Terminal CLI formatting or argument parsing (owned by presentation.cli.diagnostics).
- Database commits or lakehouse writes (dry run is strictly non-mutating).
- Domain calculations or tax lot matching (owned by domain layer).
"""

from __future__ import annotations

import glob
import os
import sqlite3
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import fastexcel
import polars as pl

from personal_finance_etl.application.ingestion.admission import AdmissionService
from personal_finance_etl.application.ingestion.file_discovery import (
    discover_source_plan_files,
)
from personal_finance_etl.application.ingestion.identity import (
    IdentityCollisionError,
    compile_identity_plan,
    execute_identity_plan,
)
from personal_finance_etl.application.normalization.compiler import NormalizationCompiler
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import (
    CompiledSourcePlan,
    DatasetPlan,
    SourcePlan,
    SourcePlanner,
)
from personal_finance_etl.config.financial_rules.model import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.change_detection import ChangeDetectionPolicy
from personal_finance_etl.config.sources.identity import (
    CompositeIdentity,
    DerivedDeterministicIdentity,
    SourceFieldIdentity,
)
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    ExcelSelector,
    SqliteSelector,
)
from personal_finance_etl.contracts.canonical_plans import SourceBindingPlan
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import DatasetId, DatasetOrigin
from personal_finance_etl.contracts.diagnostics import (
    AdmissionDryRunResult,
    ConfigValidationResult,
    DatasetAdmissionDryRunStatus,
    DatasetSelectorStatus,
    DiagnosticIssue,
    DiagnosticSeverity,
    IdentityPreviewResult,
    MappingPreviewResult,
    PlanPreviewResult,
    SourceCheckDetail,
    SourceCheckResult,
    SourceReachabilityStatus,
)
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.contracts.sources import ProviderType
from personal_finance_etl.contracts.validation import (
    ValidationCheckFailure,
    ValidationContext,
    ValidationStage,
)
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.infrastructure.validation.canonical_schemas import (
    get_canonical_bronze_schema,
    has_canonical_bronze_schema,
)
from personal_finance_etl.infrastructure.validation.pandera_adapter import (
    PanderaDataFrameValidator,
)
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
)

__all__ = ["DiagnosticService"]


class DiagnosticService:
    """Non-I/O application service managing configuration diagnostics and admission previews."""

    def __init__(
        self,
        admission_service: AdmissionService | None = None,
        normalization_compiler: NormalizationCompiler | None = None,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self._admission_service = admission_service or AdmissionService()
        self._normalization_compiler = normalization_compiler or NormalizationCompiler()
        self._emitter = emitter or get_global_emitter()

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
        """Validate the full tri-configuration triumvirate against active capability contracts."""
        issues: list[DiagnosticIssue] = []
        active_caps: tuple[CapabilityId, ...] = ()
        active_datasets: tuple[DatasetId, ...] = ()

        # 1. Validate Settings & Execution Plan
        resolved_settings = settings
        if resolved_settings is None:
            if not os.path.exists(config_path):
                issues.append(
                    DiagnosticIssue(
                        category="SETTINGS",
                        severity=DiagnosticSeverity.ERROR,
                        location=config_path,
                        message=f"Settings configuration file not found at: {config_path}",
                        remediation="Create a valid config.toml file or specify --config <path>.",
                    )
                )
            else:
                try:
                    resolved_settings = Settings.from_toml(config_path)
                except Exception as e:
                    issues.append(
                        DiagnosticIssue(
                            category="SETTINGS",
                            severity=DiagnosticSeverity.ERROR,
                            location=config_path,
                            message=f"Failed to parse settings: {e}",
                            remediation="Check config.toml syntax, database paths, and data types.",
                        )
                    )

        # Resolve ExecutionPlan from settings if available
        resolved_plan = plan
        if resolved_plan is not None:
            active_caps = resolved_plan.resolved_capabilities
            active_datasets = tuple(
                sorted(
                    resolved_plan.required_bronze_datasets + resolved_plan.optional_bronze_datasets,
                    key=lambda d: d.value,
                )
            )
        elif resolved_settings is not None:
            try:
                requested = resolved_settings.capabilities.resolved_capabilities
                resolved_plan = CapabilityPlanner().create_plan(requested_capabilities=requested)
                active_caps = resolved_plan.resolved_capabilities
                active_datasets = tuple(
                    sorted(
                        resolved_plan.required_bronze_datasets
                        + resolved_plan.optional_bronze_datasets,
                        key=lambda d: d.value,
                    )
                )
            except Exception as e:
                issues.append(
                    DiagnosticIssue(
                        category="SETTINGS",
                        severity=DiagnosticSeverity.ERROR,
                        location=config_path,
                        field="capabilities",
                        message=f"Capability resolution failure: {e}",
                        remediation="Ensure settings.capabilities defines valid CapabilityId values.",
                    )
                )

        # 2. Validate SourceConfiguration
        source_config: SourceConfiguration | None = sources
        if source_config is None:
            if not os.path.exists(sources_path):
                issues.append(
                    DiagnosticIssue(
                        category="SOURCES",
                        severity=DiagnosticSeverity.ERROR,
                        location=sources_path,
                        message=f"Source configuration file not found at: {sources_path}",
                        remediation="Create a valid sources.toml file or specify --sources <path>.",
                    )
                )
            else:
                try:
                    source_config = SourceConfiguration.from_toml(sources_path)
                except Exception as e:
                    issues.append(
                        DiagnosticIssue(
                            category="SOURCES",
                            severity=DiagnosticSeverity.ERROR,
                            location=sources_path,
                            message=f"Source configuration schema violation: {e}",
                            remediation="Ensure sources.toml satisfies SourceConfiguration model schema.",
                        )
                    )

        # Cross-validate source config against execution plan if both available
        if source_config is not None and resolved_plan is not None:
            try:
                SourcePlanner(source_config, resolved_plan).compile_plan()
            except Exception as e:
                issues.append(
                    DiagnosticIssue(
                        category="SOURCES",
                        severity=DiagnosticSeverity.ERROR,
                        location=sources_path,
                        message=f"Source satisfiability error under active plan: {e}",
                        remediation="Ensure all required Bronze datasets have valid bindings in sources.toml.",
                    )
                )

        # 3. Validate FinancialRules
        resolved_rules = rules
        if resolved_rules is not None:
            if resolved_plan is not None:
                issues.extend(resolved_rules.validate_against_plan(resolved_plan))
        elif rules_path and os.path.exists(rules_path):
            try:
                loaded_rules = FinancialRules.from_toml(rules_path)
                if resolved_plan is not None:
                    issues.extend(loaded_rules.validate_against_plan(resolved_plan))
            except Exception as e:
                issues.append(
                    DiagnosticIssue(
                        category="RULES",
                        severity=DiagnosticSeverity.ERROR,
                        location=rules_path,
                        message=f"Financial rules contract violation: {e}",
                        remediation="Ensure financial_rules.toml follows capability namespaces and valid bounds.",
                    )
                )
        elif rules_path and not os.path.exists(rules_path):
            issues.append(
                DiagnosticIssue(
                    category="RULES",
                    severity=DiagnosticSeverity.ERROR,
                    location=rules_path,
                    message=f"Financial rules file not found at: {rules_path}",
                    remediation="Create a valid financial_rules.toml file or specify --rules <path>.",
                )
            )

        compiled_count = 0
        if source_config is not None:
            try:
                topology = source_config.compile_binding_topology()
                compiled_count = len(topology.bindings)
            except Exception:
                pass

        is_valid = not any(i.severity == DiagnosticSeverity.ERROR for i in issues)
        return ConfigValidationResult(
            is_valid=is_valid,
            active_capabilities=active_caps,
            active_datasets=active_datasets,
            issues=tuple(issues),
            settings_path=config_path,
            rules_path=rules_path,
            sources_path=sources_path,
            compiled_bindings_count=compiled_count,
        )

    def check_sources(
        self,
        sources_path: str = "sources.toml",
        config_path: str | None = None,
        source_config: SourceConfiguration | None = None,
        source_plan: CompiledSourcePlan | None = None,
    ) -> SourceCheckResult:
        """Verify configured file/DB reachability and table/sheet selectors without state mutation.

        Parameters
        ----------
        sources_path : str, default "sources.toml"
            Path to sources TOML configuration file.
        config_path : str | None, default None
            Optional path to application settings TOML file.
        source_config : SourceConfiguration | None, default None
            Pre-loaded SourceConfiguration instance.
        source_plan : CompiledSourcePlan | None, default None
            Pre-compiled source plan to discover files against.

        Returns
        -------
        SourceCheckResult
            Complete reachability and selector status outcome.
        """
        issues: list[DiagnosticIssue] = []
        source_details: list[SourceCheckDetail] = []

        source_cfg = source_config
        if source_cfg is None:
            if not os.path.exists(sources_path):
                issue = DiagnosticIssue(
                    category="SOURCES",
                    severity=DiagnosticSeverity.ERROR,
                    location=sources_path,
                    message=f"Sources file not found at: {sources_path}",
                    remediation="Provide a valid sources.toml path.",
                )
                return SourceCheckResult(
                    is_all_reachable=False,
                    sources=(),
                    issues=(issue,),
                )

            try:
                source_cfg = SourceConfiguration.from_toml(sources_path)
            except Exception as e:
                issue = DiagnosticIssue(
                    category="SOURCES",
                    severity=DiagnosticSeverity.ERROR,
                    location=sources_path,
                    message=f"Failed to load sources.toml: {e}",
                    remediation="Fix sources.toml schema errors.",
                )
                return SourceCheckResult(
                    is_all_reachable=False,
                    sources=(),
                    issues=(issue,),
                )

        # Build or use authoritative SourcePlans and run discover_source_plan_files
        plans_to_discover: Sequence[SourcePlan]
        if source_plan is not None:
            plans_to_discover = source_plan.source_plans
        else:
            synthetic_plans: list[SourcePlan] = []
            topology = source_cfg.compile_binding_topology()
            for src in source_cfg.sources:
                if not src.enabled:
                    continue
                dps = [
                    DatasetPlan(
                        source_id=src.source_id,
                        dataset_id=b.dataset_id,
                        provider_type=src.provider_type,
                        location=src.location,
                        selector=b.selector,
                        change_detection=ChangeDetectionPolicy(),
                        origin=DatasetOrigin.EXTERNAL_CONFIGURED_SOURCE,
                        is_required=True,
                        is_enabled=b.enabled,
                    )
                    for b in source_cfg.datasets
                    if b.source_id == src.source_id and b.enabled
                ]
                bps = [
                    SourceBindingPlan(
                        binding_id=b_cfg.binding_id,
                        source_id=b_cfg.source_id,
                        provider_type=src.provider_type,
                        location=src.location,
                        selector=b_cfg.selector,
                        change_detection=b_cfg.change_detection or ChangeDetectionPolicy(),
                        enabled=b_cfg.enabled,
                        route_ids=tuple(r.route_id for r in b_cfg.routes),
                        binding_config=b_cfg,
                        target_dataset_id=(
                            b_cfg.routes[0].target_dataset_id if b_cfg.routes else None
                        ),
                    )
                    for b_cfg in topology.bindings
                    if b_cfg.source_id == src.source_id and b_cfg.enabled
                ]
                synthetic_plans.append(
                    SourcePlan(
                        source_id=src.source_id,
                        provider_type=src.provider_type,
                        location=src.location,
                        enabled=src.enabled,
                        dataset_plans=tuple(dps),
                        binding_plans=tuple(bps),
                    )
                )
            plans_to_discover = synthetic_plans

        discovered_by_dataset = discover_source_plan_files(plans_to_discover)

        datasets_by_source = {
            s.source_id: [b for b in source_cfg.datasets if b.source_id == s.source_id]
            for s in source_cfg.sources
        }
        all_reachable = True

        for source in source_cfg.sources:
            loc = source.location.strip()
            p_loc = Path(loc)
            resolved_loc = str(p_loc.resolve()) if p_loc.exists() else loc
            selectors: list[DatasetSelectorStatus] = []

            child_bindings = datasets_by_source.get(source.source_id, [])
            source_discovered_files: list[str] = []
            for binding in child_bindings:
                source_discovered_files.extend(
                    discovered_by_dataset.get(binding.dataset_id.value, [])
                )
            unique_source_files = sorted(set(source_discovered_files))

            source_status, msg, is_loc_reachable = self._evaluate_source_location(
                source, child_bindings, unique_source_files, p_loc, loc
            )
            if not is_loc_reachable:
                all_reachable = False

            # Validate each dataset binding under this source
            for binding in child_bindings:
                if not binding.enabled:
                    continue
                ds_files = discovered_by_dataset.get(binding.dataset_id.value, [])
                sel_status, sel_issue, status_override = self._validate_binding_selector(
                    binding, ds_files, sources_path, source.source_id
                )
                selectors.append(sel_status)
                if sel_issue is not None:
                    issues.append(sel_issue)
                if status_override is not None:
                    all_reachable = False
                    if source_status == SourceReachabilityStatus.REACHABLE:
                        source_status = status_override

            detail = SourceCheckDetail(
                source_id=source.source_id,
                provider_type=source.provider_type,
                location=loc,
                resolved_location=resolved_loc,
                status=source_status,
                message=msg,
                dataset_selectors=tuple(selectors),
            )
            source_details.append(detail)

        return SourceCheckResult(
            is_all_reachable=all_reachable,
            sources=tuple(source_details),
            issues=tuple(issues),
        )

    @staticmethod
    def _evaluate_source_location(
        source: SourceConfig,
        child_bindings: Sequence[SourceDatasetConfig],
        unique_source_files: Sequence[str],
        p_loc: Path,
        loc: str,
    ) -> tuple[SourceReachabilityStatus, str, bool]:
        """Determine source reachability status, narrative message, and reachability flag.

        Parameters
        ----------
        source : SourceConfig
            Source configuration definition.
        child_bindings : Sequence[SourceDatasetConfig]
            Dataset bindings belonging to this source.
        unique_source_files : Sequence[str]
            Unique file paths discovered for this source.
        p_loc : Path
            Path object of the configured source location.
        loc : str
            Raw string of the configured source location.

        Returns
        -------
        tuple[SourceReachabilityStatus, str, bool]
            Status enum, human-readable message, and boolean reachability flag.
        """
        if source.provider_type == ProviderType.MARKET_DATA:
            return (
                SourceReachabilityStatus.REACHABLE,
                "External market data stream provider (network managed)",
                True,
            )

        if not child_bindings:
            if p_loc.exists() or glob.glob(loc, recursive=True):
                return (
                    SourceReachabilityStatus.REACHABLE,
                    "Reachable location (no child datasets bound)",
                    True,
                )
            return (
                SourceReachabilityStatus.UNREACHABLE,
                f"Path does not exist: {loc}",
                False,
            )

        if not unique_source_files:
            if not p_loc.exists() and not glob.glob(loc, recursive=True):
                return (
                    SourceReachabilityStatus.UNREACHABLE,
                    f"Path does not exist: {loc}",
                    False,
                )
            return (
                SourceReachabilityStatus.UNREACHABLE,
                (
                    f"Location exists at '{loc}', but no evidence files "
                    "matched selectors or supported extensions"
                ),
                False,
            )

        return (
            SourceReachabilityStatus.REACHABLE,
            f"Reachable ({len(unique_source_files)} evidence file(s) discovered)",
            True,
        )

    @staticmethod
    def _inspect_sqlite_selector(
        sel: SqliteSelector,
        sample_file: str,
        dataset_id: DatasetId,
        sources_path: str,
    ) -> tuple[DatasetSelectorStatus, DiagnosticIssue | None, bool]:
        """Validate an SQLite table selector against a sample database file.

        Parameters
        ----------
        sel : SqliteSelector
            SQLite selector configuration.
        sample_file : str
            Path to sample database file.
        dataset_id : DatasetId
            Target canonical dataset identifier.
        sources_path : str
            Path to sources configuration file for issue location.

        Returns
        -------
        tuple[DatasetSelectorStatus, DiagnosticIssue | None, bool]
            Selector status model, optional diagnostic issue if invalid, and boolean valid flag.
        """
        try:
            conn = sqlite3.connect(f"file:{sample_file}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = tuple(row[0] for row in cursor.fetchall())
            conn.close()

            valid = sel.table_name in tables
            issue: DiagnosticIssue | None = None
            if not valid:
                issue = DiagnosticIssue(
                    category="SELECTOR",
                    severity=DiagnosticSeverity.ERROR,
                    location=sources_path,
                    field=dataset_id.value,
                    message=f"Table '{sel.table_name}' not found in SQLite database '{sample_file}'.",
                    remediation=f"Available tables: {list(tables)}.",
                )
            status = DatasetSelectorStatus(
                dataset_id=dataset_id,
                selector_type="sqlite_table",
                selector_target=sel.table_name,
                is_valid=valid,
                details="Table present" if valid else f"Missing table '{sel.table_name}'",
                available_targets=tables,
            )
            return status, issue, valid
        except Exception as e:
            status = DatasetSelectorStatus(
                dataset_id=dataset_id,
                selector_type="sqlite_table",
                selector_target=sel.table_name,
                is_valid=False,
                details=f"Connection error: {e}",
            )
            return status, None, False

    @staticmethod
    def _inspect_excel_selector(
        sel: ExcelSelector,
        sample_file: str,
        dataset_id: DatasetId,
        sources_path: str,
    ) -> tuple[DatasetSelectorStatus, DiagnosticIssue | None, bool]:
        """Validate an Excel sheet selector against a sample workbook file.

        Parameters
        ----------
        sel : ExcelSelector
            Excel selector configuration.
        sample_file : str
            Path to sample workbook file.
        dataset_id : DatasetId
            Target canonical dataset identifier.
        sources_path : str
            Path to sources configuration file for issue location.

        Returns
        -------
        tuple[DatasetSelectorStatus, DiagnosticIssue | None, bool]
            Selector status model, optional diagnostic issue if invalid, and boolean valid flag.
        """
        try:
            excel_reader = fastexcel.read_excel(str(sample_file))
            available_sheets = tuple(excel_reader.sheet_names)
            if sel.sheet_name:
                valid = sel.sheet_name in available_sheets
                target_repr = sel.sheet_name
            elif sel.candidate_sheets:
                valid = any(cs in available_sheets for cs in sel.candidate_sheets)
                target_repr = f"candidates: {sel.candidate_sheets}"
            else:
                valid = len(available_sheets) > 0
                target_repr = available_sheets[0] if available_sheets else "default"

            issue: DiagnosticIssue | None = None
            if not valid:
                issue = DiagnosticIssue(
                    category="SELECTOR",
                    severity=DiagnosticSeverity.ERROR,
                    location=sources_path,
                    field=dataset_id.value,
                    message=f"Sheet target '{target_repr}' not found in Excel file '{sample_file}'.",
                    remediation=f"Available sheets: {list(available_sheets)}.",
                )
            status = DatasetSelectorStatus(
                dataset_id=dataset_id,
                selector_type="excel_sheet",
                selector_target=target_repr,
                is_valid=valid,
                details="Sheet present" if valid else f"Missing sheet target '{target_repr}'",
                available_targets=available_sheets,
            )
            return status, issue, valid
        except Exception as e:
            status = DatasetSelectorStatus(
                dataset_id=dataset_id,
                selector_type="excel_sheet",
                selector_target=sel.sheet_name or "default",
                is_valid=False,
                details=f"Read error: {e}",
            )
            return status, None, False

    @staticmethod
    def _inspect_csv_selector(
        sel: CsvSelector,
        sample_file: str,
        dataset_id: DatasetId,
        ds_files: Sequence[str],
    ) -> DatasetSelectorStatus:
        """Validate a CSV pattern selector against discovered files.

        Parameters
        ----------
        sel : CsvSelector
            CSV selector configuration.
        sample_file : str
            Path to sample CSV file.
        dataset_id : DatasetId
            Target canonical dataset identifier.
        ds_files : Sequence[str]
            All discovered files matching the dataset.

        Returns
        -------
        DatasetSelectorStatus
            Selector status model.
        """
        valid = os.path.isfile(sample_file) and os.path.getsize(sample_file) > 0
        return DatasetSelectorStatus(
            dataset_id=dataset_id,
            selector_type="csv_pattern",
            selector_target=sel.file_pattern or os.path.basename(sample_file),
            is_valid=valid,
            details=f"{len(ds_files)} matching file(s) found",
        )

    @classmethod
    def _validate_binding_selector(
        cls,
        binding: SourceDatasetConfig,
        ds_files: Sequence[str],
        sources_path: str,
        source_id: str,
    ) -> tuple[DatasetSelectorStatus, DiagnosticIssue | None, SourceReachabilityStatus | None]:
        """Validate a single dataset binding and its selector against discovered files.

        Parameters
        ----------
        binding : SourceDatasetConfig
            Dataset binding configuration.
        ds_files : Sequence[str]
            Discovered files for this dataset binding.
        sources_path : str
            Path to sources configuration file.
        source_id : str
            Owning source identifier.

        Returns
        -------
        tuple[DatasetSelectorStatus, DiagnosticIssue | None, SourceReachabilityStatus | None]
            Selector status, optional diagnostic issue, and optional status override.
        """
        sel = binding.selector
        if not ds_files:
            missing_issue = DiagnosticIssue(
                category="SELECTOR",
                severity=DiagnosticSeverity.ERROR,
                location=sources_path,
                field=binding.dataset_id.value,
                message=(
                    f"No matching evidence files found for dataset '{binding.dataset_id.value}' "
                    f"under source '{source_id}'."
                ),
                remediation="Verify directory path, file_pattern, or extension filtering.",
            )
            status = DatasetSelectorStatus(
                dataset_id=binding.dataset_id,
                selector_type=type(sel).__name__,
                selector_target=str(getattr(sel, "file_pattern", "all")),
                is_valid=False,
                details="No matching evidence files found",
            )
            return status, missing_issue, SourceReachabilityStatus.INVALID_SELECTOR

        sample_file = ds_files[0]
        if isinstance(sel, SqliteSelector):
            selector_status, sqlite_issue, valid = cls._inspect_sqlite_selector(
                sel, sample_file, binding.dataset_id, sources_path
            )
            override_status = None if valid else SourceReachabilityStatus.INVALID_SELECTOR
            return selector_status, sqlite_issue, override_status

        if isinstance(sel, ExcelSelector):
            selector_status, excel_issue, valid = cls._inspect_excel_selector(
                sel, sample_file, binding.dataset_id, sources_path
            )
            override_status = None if valid else SourceReachabilityStatus.INVALID_SELECTOR
            return selector_status, excel_issue, override_status

        if isinstance(sel, CsvSelector):
            selector_status = cls._inspect_csv_selector(
                sel, sample_file, binding.dataset_id, ds_files
            )
            return selector_status, None, None

        fallback_status = DatasetSelectorStatus(
            dataset_id=binding.dataset_id,
            selector_type=type(sel).__name__,
            selector_target="default",
            is_valid=True,
            details=f"{len(ds_files)} matching file(s) found",
        )
        return fallback_status, None, None

    def preview_mapping(
        self,
        dataset_id: DatasetId | str,
        sources_path: str = "sources.toml",
    ) -> MappingPreviewResult:
        """Preview field mappings and ordered normalization operations for a dataset."""
        target_id = DatasetId(str(dataset_id))
        source_cfg = SourceConfiguration.from_toml(sources_path)
        binding = next((b for b in source_cfg.datasets if b.dataset_id == target_id), None)
        if binding is None:
            raise ValueError(
                f"Dataset '{target_id.value}' is not bound to any source in {sources_path}."
            )

        source = next((s for s in source_cfg.sources if s.source_id == binding.source_id), None)
        plan = self._normalization_compiler.compile(binding)

        field_mappings = tuple((m.source_field, m.canonical_field) for m in binding.mapping)
        pre_rules = tuple(str(r) for r in plan.pre_rename_rules)
        post_rules = tuple(str(r) for r in plan.post_rename_rules)

        # Derive compiled binding ID and route ID
        topology = source_cfg.compile_binding_topology()
        compiled_prod = topology.get_production(target_id)
        source_binding_id: str | None = None
        canonical_route_id: str | None = None
        if compiled_prod and compiled_prod.source_routes:
            ref = compiled_prod.source_routes[0]
            source_binding_id = str(ref.binding_id)
            canonical_route_id = str(ref.route_id)

        return MappingPreviewResult(
            dataset_id=target_id,
            source_id=binding.source_id,
            provider_type=source.provider_type if source else None,
            field_mappings=field_mappings,
            pre_rename_rules=pre_rules,
            post_rename_rules=post_rules,
            expected_canonical_fields=plan.expected_output_fields,
            provenance_fields=plan.provenance_fields,
            source_binding_id=source_binding_id,
            canonical_route_id=canonical_route_id,
        )

    def preview_identity(
        self,
        dataset_id: DatasetId | str,
        sources_path: str = "sources.toml",
        config_path: str | None = None,
        sample_limit: int = 10,
    ) -> IdentityPreviewResult:
        """Preview row identity strategy, target fields, and duplicate collision diagnostics."""
        target_id = DatasetId(str(dataset_id))
        source_cfg = SourceConfiguration.from_toml(sources_path)
        binding = next((b for b in source_cfg.datasets if b.dataset_id == target_id), None)
        if binding is None:
            raise ValueError(f"Dataset '{target_id.value}' is not bound in {sources_path}.")

        contract = next((c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id == target_id), None)
        if contract is None:
            raise ValueError(f"No BronzeDataContract registered for dataset '{target_id.value}'.")

        strategy = binding.identity
        strategy_kind = type(strategy).__name__ if strategy else "None"
        target_fields: tuple[str, ...] = ()
        is_trusted = False

        match strategy:
            case SourceFieldIdentity(field=f):
                target_fields = (f,)
                is_trusted = True
            case CompositeIdentity(fields=fl):
                target_fields = tuple(fl)
            case DerivedDeterministicIdentity(fields=fl):
                target_fields = tuple(fl)
            case _:
                pass

        source = next((s for s in source_cfg.sources if s.source_id == binding.source_id), None)
        sample_ids: list[str] = []
        collision_detected = False
        collision_diag: str | None = None

        # Attempt to read sample data from source if reachable
        if source and Path(source.location).is_file():
            try:
                available_cols = [m.canonical_field for m in binding.mapping] or list(target_fields)
                ident_plan = compile_identity_plan(
                    contract=contract,
                    available_fields=available_cols,
                    strategy=strategy,
                    allow_optional_identity=True,
                )
                if source.provider_type == ProviderType.EXCEL and isinstance(
                    binding.selector, ExcelSelector
                ):
                    sheet_df = pl.read_excel(
                        source.location, sheet_name=binding.selector.sheet_name
                    )
                    # Apply mapping rename
                    col_map = {m.source_field: m.canonical_field for m in binding.mapping}
                    renamed = sheet_df.rename(col_map)
                    sample_df = renamed.head(sample_limit)
                    try:
                        ids = execute_identity_plan(ident_plan, sample_df)
                        if isinstance(ids, pl.DataFrame) and "__identity_id__" in ids.columns:
                            sample_ids = ids.get_column("__identity_id__").to_list()
                    except IdentityCollisionError as ice:
                        collision_detected = True
                        collision_diag = str(ice)
            except Exception:
                pass

        namespace = (
            strategy.namespace
            if isinstance(strategy, DerivedDeterministicIdentity) and strategy.namespace
            else f"BRONZE_{contract.dataset_id.name}"
        )

        return IdentityPreviewResult(
            dataset_id=target_id,
            requirement=contract.identity_requirement,
            strategy_kind=strategy_kind,
            strategy_target_fields=target_fields,
            namespace=namespace,
            sample_ids=tuple(str(s) for s in sample_ids),
            collision_detected=collision_detected,
            collision_diagnostic=collision_diag,
            is_trusted_source_id=is_trusted,
        )

    def preview_plan(
        self,
        config_path: str = "config.toml",
        sources_path: str = "sources.toml",
    ) -> PlanPreviewResult:
        """Preview resolved capability dependency graph, engine stages, and active outputs."""
        settings = Settings.from_toml(config_path) if os.path.exists(config_path) else Settings()
        requested = settings.capabilities.resolved_capabilities
        plan = CapabilityPlanner().create_plan(requested_capabilities=requested)

        return PlanPreviewResult(
            plan_fingerprint=plan.plan_fingerprint,
            requested_capabilities=plan.requested_capabilities,
            resolved_capabilities=plan.resolved_capabilities,
            required_bronze_datasets=plan.required_bronze_datasets,
            optional_bronze_datasets=plan.optional_bronze_datasets,
            active_silver_datasets=plan.active_silver_datasets,
            active_gold_datasets=plan.active_gold_datasets,
            required_external_enrichments=plan.required_external_enrichments,
            ordered_engine_stages=plan.ordered_engine_stages,
        )

    def dry_run_admission(
        self,
        dataset_selector: str | None = None,
        config_path: str = "config.toml",
        rules_path: str | None = None,
        sources_path: str = "sources.toml",
        emitter: ObservabilityEmitter | None = None,
    ) -> AdmissionDryRunResult:
        """Execute extraction, normalization, identity, and Pandera validation in-memory without warehouse mutation."""
        start_time = time.perf_counter()
        active_emitter = emitter or self._emitter
        source_cfg = SourceConfiguration.from_toml(sources_path)
        settings = Settings.from_toml(config_path) if os.path.exists(config_path) else Settings()
        plan = CapabilityPlanner().create_plan(
            requested_capabilities=settings.capabilities.resolved_capabilities
        )
        source_plan = SourcePlanner(source_cfg, plan).compile_plan()
        validator = PanderaDataFrameValidator(emitter=active_emitter)

        target_datasets = (
            [
                dp
                for dp in source_plan.dataset_plans
                if dp.dataset_id.value == dataset_selector or dataset_selector == "all"
            ]
            if dataset_selector and dataset_selector != "all"
            else [dp for dp in source_plan.dataset_plans if dp.is_enabled]
        )

        dataset_statuses: list[DatasetAdmissionDryRunStatus] = []
        total_admitted = 0
        overall_success = True

        for dp in target_datasets:
            ds_start = time.perf_counter()
            contract = next(
                (c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id == dp.dataset_id), None
            )
            if contract is None:
                continue

            binding = next((b for b in source_cfg.datasets if b.dataset_id == dp.dataset_id), None)
            if binding is None:
                continue

            try:
                # Read raw evidence in isolated memory
                source = next((s for s in source_cfg.sources if s.source_id == dp.source_id), None)
                if source is None or not Path(source.location).is_file():
                    dataset_statuses.append(
                        DatasetAdmissionDryRunStatus(
                            dataset_id=dp.dataset_id,
                            status="SKIPPED",
                            rows_read=0,
                            rows_admitted=0,
                            duration_seconds=time.perf_counter() - ds_start,
                            error_message="Source location unreachable or file missing.",
                        )
                    )
                    continue

                raw_df: pl.DataFrame
                if source.provider_type == ProviderType.EXCEL and isinstance(
                    binding.selector, ExcelSelector
                ):
                    raw_df = pl.read_excel(source.location, sheet_name=binding.selector.sheet_name)
                elif source.provider_type == ProviderType.SQLITE and isinstance(
                    binding.selector, SqliteSelector
                ):
                    raw_df = pl.read_database_uri(
                        f"SELECT * FROM {binding.selector.table_name}",
                        f"sqlite:///{Path(source.location).resolve()}",
                    )
                else:
                    raw_df = pl.read_csv(source.location)

                rows_read = len(raw_df)

                # Compile admission plan
                adm_plan = self._admission_service.compile_admission_plan(
                    dataset_config=binding,
                    bronze_contract=contract,
                    available_source_columns=raw_df.columns,
                )

                # Execute admission (normalization + identity)
                admitted_lf = self._admission_service.execute_admission(adm_plan, raw_df.lazy())
                admitted_df = admitted_lf.collect()
                rows_admitted = len(admitted_df)

                # Validate against canonical Bronze Pandera contract
                failures: tuple[ValidationCheckFailure, ...] = ()
                if has_canonical_bronze_schema(dp.dataset_id):
                    bronze_schema = get_canonical_bronze_schema(dp.dataset_id)
                    ctx = ValidationContext(
                        stage=ValidationStage.CANONICAL_BRONZE,
                        dataset_id=dp.dataset_id,
                        source_id=dp.source_id,
                        contract_id=f"canonical_bronze_{dp.dataset_id.value}",
                    )
                    val_res = validator.validate(
                        admitted_df, bronze_schema, context=ctx, raise_on_error=False
                    )
                    failures = val_res.failures

                status_val: Literal["PASSED", "FAILED", "SKIPPED"] = (
                    "PASSED" if not failures else "FAILED"
                )
                if failures:
                    overall_success = False

                total_admitted += rows_admitted
                dataset_statuses.append(
                    DatasetAdmissionDryRunStatus(
                        dataset_id=dp.dataset_id,
                        status=status_val,
                        rows_read=rows_read,
                        rows_admitted=rows_admitted,
                        duration_seconds=time.perf_counter() - ds_start,
                        failures=failures,
                    )
                )

            except Exception as e:
                overall_success = False
                dataset_statuses.append(
                    DatasetAdmissionDryRunStatus(
                        dataset_id=dp.dataset_id,
                        status="FAILED",
                        rows_read=0,
                        rows_admitted=0,
                        duration_seconds=time.perf_counter() - ds_start,
                        error_message=str(e),
                    )
                )

        total_duration = time.perf_counter() - start_time
        return AdmissionDryRunResult(
            is_success=overall_success,
            dataset_results=tuple(dataset_statuses),
            total_rows_admitted=total_admitted,
            total_duration_seconds=total_duration,
            zero_warehouse_mutation_guaranteed=True,
        )
