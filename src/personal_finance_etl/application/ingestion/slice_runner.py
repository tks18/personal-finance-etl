"""Generalized vertical dataset ingestion execution service.

Owns
----
- DatasetIngestionService: Coordinates end-to-end admission for migrated canonical datasets:
  provider extraction, Gate 1 (source Pandera validation), Pre-Bronze persistence,
  admission normalization and row identity, Gate 2 (canonical Bronze validation),
  canonical Bronze persistence, and Control Plane artifact synchronization.

Does not own
-------------
- Validation schema definitions (owned by infrastructure.validation).
- Warehouse table schemas and DDL (owned by infrastructure.warehouse).
- Source configuration models (owned by config.sources).
- Downstream financial ledger transformations (owned by domain).
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import polars as pl

from personal_finance_etl.application.ingestion.admission import AdmissionService
from personal_finance_etl.application.ingestion.canonical_production import (
    CanonicalProductionEngine,
)
from personal_finance_etl.application.ingestion.route_compiler import RouteCompiler
from personal_finance_etl.application.ingestion.route_executor import RouteExecutor
from personal_finance_etl.application.pipeline.source_planner import DatasetPlan
from personal_finance_etl.config.sources.binding_model import SourceBindingConfig
from personal_finance_etl.config.sources.compiler import derive_source_binding_id
from personal_finance_etl.config.sources.identity import SourceFieldIdentity
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.model import (
    SourceDatasetConfig,
    SourceFieldDeclaration,
)
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    ExcelSelector,
    SqliteSelector,
)
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.canonical_plans import (
    CanonicalDatasetPlan,
    CanonicalProducerKind,
    SourceAssemblyMode,
    SourceBindingPlan,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    PresentationKind,
)
from personal_finance_etl.contracts.sources import (
    CanonicalRouteId,
    ProviderType,
)
from personal_finance_etl.contracts.validation import (
    DataFrameValidator,
    ValidationContext,
    ValidationStage,
)
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.control_plane.hashing import generate_file_id
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.providers.files.csv import CSVExtractor
from personal_finance_etl.infrastructure.providers.files.excel import (
    ExcelExtractor,
)
from personal_finance_etl.infrastructure.providers.files.sqlite import (
    SQLiteExtractor,
)
from personal_finance_etl.infrastructure.validation import (
    POLARS_TYPE_MAP,
    PanderaDataFrameValidator,
    compile_source_schema,
    get_canonical_bronze_schema,
)
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BronzeDataContract,
    PreBronzeDataContract,
    SyncStrategy,
)
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer
from personal_finance_etl.infrastructure.warehouse.registry import (
    create_pre_bronze_contract_for_binding,
    get_bronze_contract_by_dataset_id,
    get_pre_bronze_contract_by_binding_id,
)

__all__ = ["DatasetIngestionService"]

diagnostics = get_observability_diagnostics(__name__)


def _resolve_target_paths(
    plan: SourceBindingPlan | DatasetPlan,
    bronze_contract: BronzeDataContract,
    actionable_files: Sequence[str] | dict[str, list[str]],
    target_dataset_id: DatasetId | None = None,
) -> list[str]:
    """Resolve target actionable filepaths for a binding or dataset plan.

    Parameters
    ----------
    plan : SourceBindingPlan | DatasetPlan
        Compiled execution plan for the target stream or dataset.
    bronze_contract : BronzeDataContract
        Canonical Bronze persistence contract.
    actionable_files : Sequence[str] | dict[str, list[str]]
        Category-mapped actionable paths or explicit list of paths.
    target_dataset_id : DatasetId | None, default None
        Optional target canonical dataset identifier override.

    Returns
    -------
    list[str]
        Deduplicated, sorted list of actionable file paths.
    """
    if not isinstance(actionable_files, dict):
        return sorted(set(actionable_files))

    target_paths: list[str] = []
    b_id_str: str | None = None
    if isinstance(plan, SourceBindingPlan):
        b_id_str = str(plan.binding_id)
        if b_id_str in actionable_files:
            target_paths.extend(actionable_files[b_id_str])

    ds_id = target_dataset_id or (getattr(plan, "dataset_id", None))
    ds_val = ds_id.value if ds_id is not None else ""
    if ds_val and ds_val in actionable_files:
        target_paths.extend(actionable_files[ds_val])

    cat = getattr(bronze_contract, "sync_category", None)
    if cat and cat in actionable_files and cat != ds_val and cat != b_id_str:
        target_paths.extend(actionable_files[cat])

    if not target_paths:
        for leg_key, files in actionable_files.items():
            matches_sqlite = (
                leg_key == "sqlite_source" and plan.provider_type == ProviderType.SQLITE
            )
            matches_stock_pl = leg_key == "stock_pl" and ds_id == DatasetId.MARKET_STOCK_HOLDINGS
            matches_key = bool(ds_val and leg_key in ds_val) or bool(
                b_id_str and leg_key in b_id_str
            )
            if matches_sqlite or matches_stock_pl or matches_key:
                target_paths.extend(files)

    return sorted(set(target_paths))


def _resolve_transitional_dataset_config(
    binding_plan: SourceBindingPlan,
    b_cfg: SourceBindingConfig | None,
    legacy_ds_config: SourceDatasetConfig | None,
    target_ds_id: DatasetId,
) -> SourceDatasetConfig:
    """Resolve or synthesize a transitional dataset config for admission."""
    if legacy_ds_config is not None:
        return legacy_ds_config
    if b_cfg is not None and b_cfg.routes:
        return SourceDatasetConfig(
            dataset_id=target_ds_id,
            source_id=binding_plan.source_id,
            selector=b_cfg.selector,
            fields=b_cfg.fields,
            mapping=b_cfg.routes[0].mapping,
            normalization=b_cfg.routes[0].normalization,
            identity=b_cfg.routes[0].identity,
        )
    raise ValueError(
        f"Transitional admission requires legacy dataset config for {binding_plan.binding_id}"
    )


def _align_declared_field_types(
    raw_df: pl.DataFrame,
    declared_fields: Sequence[SourceFieldDeclaration],
) -> pl.DataFrame:
    """Align column types inferred by Polars with declared source field dtypes."""
    field_types = {f.name: f.data_type.strip().lower() for f in declared_fields}
    cols_to_cast: list[pl.Expr] = []
    for col in raw_df.columns:
        if col in field_types:
            norm_t = field_types[col]
            target_dtype = POLARS_TYPE_MAP.get(norm_t)
            if target_dtype is not None:
                current_dtype = raw_df[col].dtype
                if current_dtype == pl.Null:
                    cols_to_cast.append(pl.col(col).cast(target_dtype))
                elif target_dtype.is_float() and current_dtype.is_integer():
                    cols_to_cast.append(pl.col(col).cast(pl.Float64))
                elif target_dtype.is_(pl.String) and not current_dtype.is_(pl.String):
                    cols_to_cast.append(pl.col(col).cast(pl.String))
                elif (
                    target_dtype.is_integer()
                    and current_dtype.is_integer()
                    and current_dtype != target_dtype
                ):
                    cols_to_cast.append(pl.col(col).cast(target_dtype))
                elif (
                    (target_dtype.is_integer() or target_dtype.is_float())
                    and current_dtype.is_(pl.String)
                    and (raw_df[col].null_count() == len(raw_df) or raw_df[col].is_null().all())
                ):
                    cols_to_cast.append(pl.col(col).cast(target_dtype))
                elif target_dtype.is_integer() and current_dtype.is_float():
                    cols_to_cast.append(pl.col(col).cast(target_dtype))
                elif target_dtype == pl.Date and current_dtype.is_(pl.String):
                    cols_to_cast.append(
                        pl.coalesce(
                            pl.col(col).str.to_date("%Y-%m-%d", strict=False),
                            pl.col(col).str.to_date("%d-%m-%Y", strict=False),
                            pl.col(col).str.to_date("%Y/%m/%d", strict=False),
                            pl.col(col).str.to_date("%d/%m/%Y", strict=False),
                        )
                    )
    if cols_to_cast:
        return raw_df.with_columns(cols_to_cast)
    return raw_df


class DatasetIngestionService:
    """Executes the generalized vertical ingestion slice for a canonical dataset plan.

    Parameters
    ----------
    validator : DataFrameValidator | None, default None
        Authoritative tabular validator instance. If None, instantiates PanderaDataFrameValidator.
    admission_service : AdmissionService | None, default None
        Application admission and normalization execution service. If None, instantiates default.
    emitter : ObservabilityEmitter | None, default None
        Active observability emitter.
    """

    def __init__(
        self,
        validator: DataFrameValidator | None = None,
        admission_service: AdmissionService | None = None,
        emitter: ObservabilityEmitter | None = None,
        route_compiler: RouteCompiler | None = None,
        route_executor: RouteExecutor | None = None,
        production_engine: CanonicalProductionEngine | None = None,
    ) -> None:
        self.emitter = emitter or get_global_emitter()
        self.validator = validator or PanderaDataFrameValidator(emitter=self.emitter)
        self.admission_service = admission_service or AdmissionService()
        self.route_compiler = route_compiler or RouteCompiler()
        self.route_executor = route_executor or RouteExecutor()
        self.production_engine = production_engine or CanonicalProductionEngine(
            validator=self.validator
        )

    def _resolve_raw_bytes(self, filepath: str, cp: ControlPlane) -> bytes:
        """Resolve raw file bytes from Control Plane artifact store or physical disk.

        Parameters
        ----------
        filepath : str
            Target file path.
        cp : ControlPlane
            Active operational control plane.

        Returns
        -------
        bytes
            Binary payload contents.

        Raises
        ------
        FileNotFoundError
            If binary content is absent from both Control Plane and filesystem.
        """
        raw_bytes = cp.artifacts.get_file_bytes(filepath)
        if raw_bytes is not None:
            return raw_bytes
        disk_path = Path(filepath).resolve()
        if disk_path.is_file():
            return disk_path.read_bytes()
        raise FileNotFoundError(f"Binary payload not found in Control Plane or disk: {filepath}")

    def ingest_binding(
        self,
        binding_plan: SourceBindingPlan,
        source_config: SourceConfiguration,
        cp: ControlPlane,
        pre_bronze: PreBronzeLayer,
        bronze: BronzeLayer,
        meta_layer: MetaLayer,
        actionable_files: Sequence[str] | dict[str, list[str]],
        run_id: str,
        current_binding_idx: int = 0,
        total_bindings: int = 1,
        dataset_plan: DatasetPlan | None = None,
    ) -> bool:
        """Execute the end-to-end generalized ingestion pipeline for a physical source binding.

        Parameters
        ----------
        binding_plan : SourceBindingPlan
            Compiled execution plan for the target physical binding.
        source_config : SourceConfiguration
            Authoritative root source configuration.
        cp : ControlPlane
            Active operational control plane.
        pre_bronze : PreBronzeLayer
            Pre-Bronze DuckDB persistence layer.
        bronze : BronzeLayer
            Bronze DuckDB persistence layer.
        meta_layer : MetaLayer
            Metadata registration layer.
        actionable_files : Sequence[str] | dict[str, list[str]]
            Category-mapped actionable paths or explicit list of paths.
        run_id : str
            Active pipeline execution ID.
        current_binding_idx : int, default 0
            Zero-based index of current binding within active ingestion phase.
        total_bindings : int, default 1
            Total number of bindings scheduled for ingestion in active phase.
        dataset_plan : DatasetPlan | None, default None
            Optional transitional dataset plan for backward compatibility.

        Returns
        -------
        bool
            True if one or more files were ingested, False if skipped (no actionable files).
        """
        pb_contract: PreBronzeDataContract | None = get_pre_bronze_contract_by_binding_id(
            binding_plan.binding_id
        )
        if pb_contract is None:
            pb_contract = create_pre_bronze_contract_for_binding(binding_plan)

        topology = source_config.compile_binding_topology()
        b_cfg = topology.get_binding(binding_plan.binding_id)

        target_ds_id: DatasetId | None = None
        if b_cfg and b_cfg.routes:
            target_ds_id = b_cfg.routes[0].target_dataset_id
        elif dataset_plan is not None:
            target_ds_id = dataset_plan.dataset_id
        elif pb_contract.dataset_id is not None:
            target_ds_id = pb_contract.dataset_id

        if target_ds_id is None:
            raise ValueError(
                f"Cannot resolve target canonical DatasetId for binding '{binding_plan.binding_id}'"
            )

        bronze_contract: BronzeDataContract | None = get_bronze_contract_by_dataset_id(target_ds_id)
        if bronze_contract is None:
            raise ValueError(f"No BronzeDataContract found for dataset {target_ds_id}")

        legacy_ds_config = source_config.get_dataset_binding(target_ds_id)

        target_paths = _resolve_target_paths(
            binding_plan, bronze_contract, actionable_files, target_dataset_id=target_ds_id
        )

        if not target_paths:
            diagnostics.debug(
                "Generalized Ingestion: No actionable files for %s (%s). Skipping.",
                str(binding_plan.binding_id),
                bronze_contract.sync_category,
            )
            return False

        b_slot = 0.20 / max(total_bindings, 1)
        b_base = 0.20 + (current_binding_idx * b_slot)

        diagnostics.info(
            "Generalized Ingestion: Ingesting binding '%s' (target '%s') from %d actionable file(s)...",
            str(binding_plan.binding_id),
            target_ds_id.value,
            len(target_paths),
        )
        self.emitter.emit_event(
            event_code=EventCode.EXTRACTION_START,
            message=(
                f"Ingesting binding '{binding_plan.binding_id}' from {len(target_paths)} "
                f"actionable file(s)..."
            ),
            severity=DiagnosticSeverity.INFO,
            presentation_kind=PresentationKind.STEP,
            progress=b_base,
            stage=EngineStage.EXTRACTING,
            entity_type="binding",
            entity_id=str(binding_plan.binding_id),
            rows=len(target_paths),
        )

        total_rows_added = 0
        total_files = len(target_paths)
        for file_idx, filepath in enumerate(target_paths, 1):
            norm_filepath = filepath.replace("\\", "/")
            filename = os.path.basename(norm_filepath)
            folder_path = os.path.dirname(norm_filepath)
            artifact_id = generate_file_id(norm_filepath)

            # 1. Provider Extraction
            raw_bytes = self._resolve_raw_bytes(norm_filepath, cp)
            selector = binding_plan.selector
            if isinstance(selector, SqliteSelector):
                table_name = selector.table_name
                extractor = SQLiteExtractor(folder_path)
                source_lazy = extractor.extract_table(filename, folder_path, raw_bytes, table_name)
            elif isinstance(selector, CsvSelector):
                csv_extractor = CSVExtractor(folder_path)
                source_lazy = csv_extractor.extract_csv(
                    filename,
                    folder_path,
                    raw_bytes,
                    delimiter=selector.delimiter,
                    encoding=selector.encoding,
                    has_header=selector.has_header,
                )
            elif isinstance(selector, ExcelSelector):
                excel_extractor = ExcelExtractor(folder_path)
                category = (
                    "Indian MF"
                    if target_ds_id
                    in (DatasetId.MARKET_MF_HOLDINGS, DatasetId.INVESTMENT_MF_ORDERS)
                    else "Indian Stocks"
                    if target_ds_id
                    in (DatasetId.MARKET_STOCK_HOLDINGS, DatasetId.INVESTMENT_STOCK_ORDERS)
                    else "US Stocks"
                    if target_ds_id == DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS
                    else None
                )
                source_lazy = excel_extractor.extract_sheet(
                    filename,
                    folder_path,
                    raw_bytes,
                    sheet_name=selector.sheet_name,
                    candidate_sheets=selector.candidate_sheets,
                    header_row=selector.header_row,
                    header_anchor=selector.header_anchor,
                    anchor_offset=selector.anchor_offset,
                    stop_on_blank=selector.stop_on_blank,
                    file_category=category,
                )
            else:
                raise TypeError(
                    f"Unsupported selector type for file ingestion: {type(selector).__name__}"
                )

            raw_df = source_lazy.collect()

            # Align column types inferred by Polars with declared source field dtypes
            declared_fields = (
                b_cfg.fields
                if b_cfg and b_cfg.fields
                else (legacy_ds_config.fields if legacy_ds_config else [])
            )
            raw_df = _align_declared_field_types(raw_df, declared_fields)

            # 2. Gate 1: Source Validation (PRE_BRONZE)
            schema_holder = b_cfg if b_cfg is not None else legacy_ds_config
            if schema_holder is None:
                raise ValueError(f"No source configuration available for {binding_plan.binding_id}")
            source_schema = compile_source_schema(schema_holder)
            source_ctx = ValidationContext(
                stage=ValidationStage.PRE_BRONZE,
                dataset_id=target_ds_id,
                source_id=binding_plan.source_id,
                contract_id=f"pre_bronze_{binding_plan.binding_id}",
                run_id=run_id,
                binding_id=binding_plan.binding_id,
            )
            self.validator.validate(raw_df, source_schema, source_ctx, raise_on_error=True)

            # 3. Pre-Bronze Persistence
            if pb_contract.sync_strategy == SyncStrategy.FULL_REPLACE:
                pre_bronze.write_full_replace(
                    pb_contract, raw_df, artifact_id=artifact_id, source_id=binding_plan.source_id
                )
            else:
                pre_bronze.write_incremental(
                    pb_contract, raw_df, artifact_id=artifact_id, source_id=binding_plan.source_id
                )

            # Ensure artifact_id is present for canonical Bronze admission
            if "artifact_id" not in raw_df.columns:
                raw_df = raw_df.with_columns(pl.lit(artifact_id).alias("artifact_id"))

            # 4. Canonical Route Interpretation & Row Identity Derivation
            legacy_ds_config = _resolve_transitional_dataset_config(
                binding_plan, b_cfg, legacy_ds_config, target_ds_id
            )

            id_col = "UID"
            if isinstance(
                legacy_ds_config.identity, SourceFieldIdentity
            ) and legacy_ds_config.identity.field not in ("Z_PK", "UID", "ZUID"):
                id_col = legacy_ds_config.identity.field

            matching_route = None
            if b_cfg is not None and b_cfg.routes:
                matching_route = next(
                    (r for r in b_cfg.routes if r.target_dataset_id == target_ds_id),
                    None,
                )

            if matching_route is not None and (
                matching_route.predicates or matching_route.semantics
            ):
                compiled_route = self.route_compiler.compile(
                    matching_route,
                    binding_id=binding_plan.binding_id,
                    available_source_columns=raw_df.columns,
                )
                mat_fragment = self.route_executor.execute(compiled_route, raw_df)
                canonical_ds_plan = CanonicalDatasetPlan(
                    dataset_id=target_ds_id,
                    producer_kind=CanonicalProducerKind.SOURCE,
                    assembly_mode=SourceAssemblyMode.DIRECT,
                    is_required=True,
                    is_enabled=True,
                )
                admitted_df, _ = self.production_engine.produce(
                    plan=canonical_ds_plan,
                    fragments=[mat_fragment],
                    contract=bronze_contract,
                    identity_strategy=legacy_ds_config.identity,
                    run_id=run_id,
                    allow_identical_collapse=True,
                )
                admitted_lf = admitted_df.lazy()
            else:
                admission_plan = self.admission_service.compile_admission_plan(
                    dataset_config=legacy_ds_config,
                    bronze_contract=bronze_contract,
                    available_source_columns=raw_df.columns,
                    id_column=id_col,
                )
                admitted_lf = self.admission_service.execute_admission(admission_plan, raw_df)

                # 5. Gate 2: Canonical Bronze Validation (CANONICAL_BRONZE)
                canonical_schema = get_canonical_bronze_schema(target_ds_id)
                canonical_ctx = ValidationContext(
                    stage=ValidationStage.CANONICAL_BRONZE,
                    dataset_id=target_ds_id,
                    source_id=binding_plan.source_id,
                    contract_id=bronze_contract.physical_table,
                    run_id=run_id,
                )
                self.validator.validate(
                    admitted_lf, canonical_schema, canonical_ctx, raise_on_error=True
                )

            # 6. Canonical Bronze Persistence
            row_counts = bronze.upsert_table(
                admitted_lf,
                bronze_contract.physical_table,
                [norm_filepath],
                full_replace=bronze_contract.is_full_replace,
            )
            file_rows = row_counts.get(filename, 0)
            total_rows_added = (
                file_rows if bronze_contract.is_full_replace else (total_rows_added + file_rows)
            )

            if bronze_contract.is_full_replace:
                bronze.db_manager.conn.execute(
                    "DELETE FROM meta.m_File_Registry WHERE file_category = ?",
                    [bronze_contract.sync_category],
                )

            # 7. Control Plane & Meta Layer Synchronization
            cp.artifacts.mark_synced([norm_filepath])
            meta_layer.register_file(norm_filepath, bronze_contract.sync_category, file_rows, cp)

            file_progress = b_base + ((file_idx / max(total_files, 1)) * b_slot)
            self.emitter.emit_event(
                event_code=EventCode.EXTRACTION_BATCH,
                message=(
                    f"[{binding_plan.binding_id}] Ingested file ({file_idx}/{total_files}): "
                    f"'{filename}' -> Pre-Bronze & Bronze ({file_rows:,} rows)"
                ),
                severity=DiagnosticSeverity.INFO,
                presentation_kind=PresentationKind.PROGRESS,
                progress=file_progress,
                stage=EngineStage.EXTRACTING,
                entity_type="File",
                entity_id=filename,
                rows=file_rows,
            )

        self.emitter.emit_event(
            event_code=EventCode.BRONZE_UPSERT,
            message=(
                f"Bronze: Table '{bronze_contract.physical_table}' upserted "
                f"{total_rows_added} rows from {len(target_paths)} files via generalized admission."
            ),
            severity=DiagnosticSeverity.INFO,
            presentation_kind=PresentationKind.SUCCESS,
            progress=b_base + b_slot,
            stage=EngineStage.EXTRACTING,
            entity_type="Table",
            entity_id=bronze_contract.physical_table,
            rows=total_rows_added,
        )
        return True

    def ingest_dataset(
        self,
        dataset_plan: DatasetPlan,
        source_config: SourceConfiguration,
        cp: ControlPlane,
        pre_bronze: PreBronzeLayer,
        bronze: BronzeLayer,
        meta_layer: MetaLayer,
        actionable_files: Sequence[str] | dict[str, list[str]],
        run_id: str,
        current_dataset_idx: int = 0,
        total_datasets: int = 1,
    ) -> bool:
        """Execute the end-to-end generalized ingestion pipeline for a single dataset.

        Removal Owner
        -------------
        Phase 055 (when DatasetPlan physical acquisition is decommissioned).

        Parameters
        ----------
        dataset_plan : DatasetPlan
            Compiled execution plan for the target dataset.
        source_config : SourceConfiguration
            Authoritative root source configuration.
        cp : ControlPlane
            Active operational control plane.
        pre_bronze : PreBronzeLayer
            Pre-Bronze DuckDB persistence layer.
        bronze : BronzeLayer
            Bronze DuckDB persistence layer.
        meta_layer : MetaLayer
            Metadata registration layer.
        actionable_files : Sequence[str] | dict[str, list[str]]
            Category-mapped actionable paths or explicit list of paths.
        run_id : str
            Active pipeline execution ID.
        current_dataset_idx : int, default 0
            Zero-based index of current dataset within active ingestion phase.
        total_datasets : int, default 1
            Total number of datasets scheduled for ingestion in active phase.

        Returns
        -------
        bool
            True if one or more files were ingested, False if skipped (no actionable files).

        Raises
        ------
        ValueError
            If dataset contracts or source dataset configurations cannot be resolved.
        NotImplementedError
            If selector provider type is unsupported.
        """
        b_id = derive_source_binding_id(dataset_plan.source_id, dataset_plan.dataset_id)
        binding_plan = SourceBindingPlan(
            binding_id=b_id,
            source_id=dataset_plan.source_id,
            provider_type=dataset_plan.provider_type,
            location=dataset_plan.location,
            enabled=dataset_plan.is_enabled,
            selector=dataset_plan.selector,
            change_detection=dataset_plan.change_detection,
            route_ids=(CanonicalRouteId("direct"),),
        )
        return self.ingest_binding(
            binding_plan=binding_plan,
            source_config=source_config,
            cp=cp,
            pre_bronze=pre_bronze,
            bronze=bronze,
            meta_layer=meta_layer,
            actionable_files=actionable_files,
            run_id=run_id,
            current_binding_idx=current_dataset_idx,
            total_bindings=total_datasets,
            dataset_plan=dataset_plan,
        )
