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
from personal_finance_etl.application.pipeline.source_planner import DatasetPlan
from personal_finance_etl.config.sources.identity import SourceFieldIdentity
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.selectors import (
    CsvSelector,
    SqliteSelector,
)
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    PresentationKind,
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
    get_bronze_contract_by_dataset_id,
    get_pre_bronze_contract_by_dataset_id,
)

__all__ = ["DatasetIngestionService"]

diagnostics = get_observability_diagnostics(__name__)


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
    ) -> None:
        self.emitter = emitter or get_global_emitter()
        self.validator = validator or PanderaDataFrameValidator(emitter=self.emitter)
        self.admission_service = admission_service or AdmissionService()

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
    ) -> bool:
        """Execute the end-to-end generalized ingestion pipeline for a single dataset.

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
        bronze_contract: BronzeDataContract | None = get_bronze_contract_by_dataset_id(
            dataset_plan.dataset_id
        )
        if bronze_contract is None:
            raise ValueError(f"No BronzeDataContract found for dataset {dataset_plan.dataset_id}")

        pb_contract: PreBronzeDataContract | None = get_pre_bronze_contract_by_dataset_id(
            dataset_plan.dataset_id
        )
        if pb_contract is None:
            raise ValueError(
                f"No PreBronzeDataContract found for dataset {dataset_plan.dataset_id}"
            )

        ds_config = source_config.get_dataset_binding(dataset_plan.dataset_id)
        if ds_config is None:
            raise ValueError(f"No SourceDatasetConfig found for dataset {dataset_plan.dataset_id}")

        target_paths: list[str]
        if isinstance(actionable_files, dict):
            target_paths = list(actionable_files.get(bronze_contract.sync_category, []))
        else:
            target_paths = list(actionable_files)

        if not target_paths:
            diagnostics.debug(
                "Generalized Ingestion: No actionable files for %s (%s). Skipping.",
                dataset_plan.dataset_id.value,
                bronze_contract.sync_category,
            )
            return False

        diagnostics.info(
            "Generalized Ingestion: Ingesting dataset '%s' from %d actionable file(s)...",
            dataset_plan.dataset_id.value,
            len(target_paths),
        )
        self.emitter.emit_event(
            event_code=EventCode.EXTRACTION_START,
            message=(
                f"Ingesting dataset '{dataset_plan.dataset_id.value}' from {len(target_paths)} "
                f"actionable file(s)..."
            ),
            severity=DiagnosticSeverity.INFO,
            presentation_kind=PresentationKind.STEP,
            stage=EngineStage.EXTRACTING,
            entity_type="dataset",
            entity_id=dataset_plan.dataset_id.value,
            rows=len(target_paths),
        )

        total_rows_added = 0
        for filepath in target_paths:
            norm_filepath = filepath.replace("\\", "/")
            filename = os.path.basename(norm_filepath)
            folder_path = os.path.dirname(norm_filepath)
            artifact_id = generate_file_id(norm_filepath)

            # 1. Provider Extraction
            raw_bytes = self._resolve_raw_bytes(norm_filepath, cp)
            if isinstance(dataset_plan.selector, SqliteSelector):
                table_name = dataset_plan.selector.table_name
                extractor = SQLiteExtractor(folder_path)
                source_lazy = extractor.extract_table(filename, folder_path, raw_bytes, table_name)
            elif isinstance(dataset_plan.selector, CsvSelector):
                csv_extractor = CSVExtractor(folder_path)
                source_lazy = csv_extractor.extract_csv(
                    filename,
                    folder_path,
                    raw_bytes,
                    delimiter=dataset_plan.selector.delimiter,
                    encoding=dataset_plan.selector.encoding,
                    has_header=dataset_plan.selector.has_header,
                )
            else:
                excel_extractor = ExcelExtractor(folder_path)
                category = (
                    "Indian MF"
                    if dataset_plan.dataset_id
                    in (DatasetId.MARKET_MF_HOLDINGS, DatasetId.INVESTMENT_MF_ORDERS)
                    else "Indian Stocks"
                    if dataset_plan.dataset_id
                    in (DatasetId.MARKET_STOCK_HOLDINGS, DatasetId.INVESTMENT_STOCK_ORDERS)
                    else None
                )
                source_lazy = excel_extractor.extract_sheet(
                    filename,
                    folder_path,
                    raw_bytes,
                    sheet_name=dataset_plan.selector.sheet_name,
                    candidate_sheets=dataset_plan.selector.candidate_sheets,
                    header_row=dataset_plan.selector.header_row,
                    header_anchor=dataset_plan.selector.header_anchor,
                    anchor_offset=dataset_plan.selector.anchor_offset,
                    stop_on_blank=dataset_plan.selector.stop_on_blank,
                    file_category=category,
                )

            raw_df = source_lazy.collect()

            # Align column types inferred by Polars with declared source field dtypes
            cols_to_cast: list[pl.Expr] = []
            field_types = {f.name: f.data_type.strip().lower() for f in ds_config.fields}
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
                            and (
                                raw_df[col].null_count() == len(raw_df)
                                or raw_df[col].is_null().all()
                            )
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
                raw_df = raw_df.with_columns(cols_to_cast)

            # 2. Gate 1: Source Validation (PRE_BRONZE)
            source_schema = compile_source_schema(ds_config)
            source_ctx = ValidationContext(
                stage=ValidationStage.PRE_BRONZE,
                dataset_id=dataset_plan.dataset_id,
                source_id=dataset_plan.source_id,
                contract_id=f"pre_bronze_{dataset_plan.dataset_id.value}",
                run_id=run_id,
            )
            self.validator.validate(raw_df, source_schema, source_ctx, raise_on_error=True)

            # 3. Pre-Bronze Persistence
            if pb_contract.sync_strategy == SyncStrategy.FULL_REPLACE:
                pre_bronze.write_full_replace(
                    pb_contract, raw_df, artifact_id=artifact_id, source_id=dataset_plan.source_id
                )
            else:
                pre_bronze.write_incremental(
                    pb_contract, raw_df, artifact_id=artifact_id, source_id=dataset_plan.source_id
                )

            # Ensure artifact_id is present for canonical Bronze admission
            if "artifact_id" not in raw_df.columns:
                raw_df = raw_df.with_columns(pl.lit(artifact_id).alias("artifact_id"))

            # 4. Admission Normalization & Row Identity Derivation
            id_col = "UID"
            if isinstance(
                ds_config.identity, SourceFieldIdentity
            ) and ds_config.identity.field not in ("Z_PK", "UID", "ZUID"):
                id_col = ds_config.identity.field

            admission_plan = self.admission_service.compile_admission_plan(
                dataset_config=ds_config,
                bronze_contract=bronze_contract,
                available_source_columns=raw_df.columns,
                id_column=id_col,
            )
            admitted_lf = self.admission_service.execute_admission(admission_plan, raw_df)

            # 5. Gate 2: Canonical Bronze Validation (CANONICAL_BRONZE)
            canonical_schema = get_canonical_bronze_schema(dataset_plan.dataset_id)
            canonical_ctx = ValidationContext(
                stage=ValidationStage.CANONICAL_BRONZE,
                dataset_id=dataset_plan.dataset_id,
                source_id=dataset_plan.source_id,
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
            total_rows_added += file_rows

            if bronze_contract.is_full_replace:
                bronze.db_manager.conn.execute(
                    "DELETE FROM meta.m_File_Registry WHERE file_category = ?",
                    [bronze_contract.sync_category],
                )

            # 7. Control Plane & Meta Layer Synchronization
            cp.artifacts.mark_synced([norm_filepath])
            meta_layer.register_file(norm_filepath, bronze_contract.sync_category, file_rows, cp)

        self.emitter.emit_event(
            event_code=EventCode.BRONZE_UPSERT,
            message=(
                f"Bronze: Table '{bronze_contract.physical_table}' upserted "
                f"{total_rows_added} rows from {len(target_paths)} files via generalized admission."
            ),
            severity=DiagnosticSeverity.INFO,
            presentation_kind=PresentationKind.SUCCESS,
            stage=EngineStage.EXTRACTING,
            entity_type="Table",
            entity_id=bronze_contract.physical_table,
            rows=total_rows_added,
        )
        return True
