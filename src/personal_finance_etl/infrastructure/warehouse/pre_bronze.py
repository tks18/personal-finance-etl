"""Persistence, retrieval, and table management in the warehouse Pre-Bronze layer.

Owns
----
- Deterministic, PFETL-controlled physical table naming for Pre-Bronze tables.
- Full table replacement persistence for source-shaped evidence frames.
- Artifact-keyed incremental upsert and replacement persistence in pre_bronze.* DuckDB tables.
- Table schema evolution for newly added source columns in incremental writes.
- Artifact identity migration during file renames without re-ingesting physical rows.
- Parameterized artifact row deletion.
- Source-shaped DataFrame and LazyFrame reading by DatasetId with optional provenance columns.

Does not own
-------------
- DuckDB connection lifecycle or commit boundaries (owned by infrastructure.warehouse.connection).
- Control Plane SQLite artifact vaulting or hashing (owned by control plane).
- Canonical Bronze transformation, standardization, or validation (owned by bronze.py / domain).
- Production pipeline extraction orchestration (owned by application.pipeline).
"""

from __future__ import annotations

import re

import duckdb
import polars as pl

from personal_finance_etl.config.sources.change_detection import SyncStrategy
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    PRE_BRONZE_ARTIFACT_ID,
    PRE_BRONZE_DATASET_ID,
    PRE_BRONZE_PROVENANCE_COLUMNS,
    PRE_BRONZE_SOURCE_ID,
    PreBronzeDataContract,
)
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_pre_bronze_contract_by_dataset_id,
)

__all__ = [
    "PreBronzeLayer",
    "get_pre_bronze_table_name",
    "sanitize_physical_identifier",
]

diagnostics = get_observability_diagnostics("personal_finance_etl.warehouse.pre_bronze")

_UNSAFE_PATTERN = re.compile(r"['\";\s\\]|--")


def sanitize_physical_identifier(name: object) -> str:
    """Sanitize and validate a candidate physical table identifier.

    Parameters
    ----------
    name : object
        Candidate identifier object.

    Returns
    -------
    str
        Sanitized lowercase alphanumeric identifier.

    Raises
    ------
    TypeError
        If name is not a string.
    ValueError
        If name is empty, whitespace, or contains forbidden/injection characters.
    """
    if not isinstance(name, str):
        raise TypeError(f"Identifier must be a str, got {type(name).__name__}")
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Identifier cannot be empty or whitespace.")
    if _UNSAFE_PATTERN.search(cleaned):
        raise ValueError(f"Unsafe physical identifier contains forbidden characters: {name!r}")
    sanitized = re.sub(r"[.\-]+", "_", cleaned)
    if not re.match(r"^[a-zA-Z0-9_]+$", sanitized):
        raise ValueError(f"Unsafe physical identifier contains invalid characters: {name!r}")
    return sanitized.lower()


def get_pre_bronze_table_name(
    dataset_id: DatasetId | str,
    source_id: SourceId | str | None = None,
) -> str:
    """Derive deterministic PFETL-controlled physical table name for Pre-Bronze.

    Parameters
    ----------
    dataset_id : DatasetId | str
        Authoritative dataset identifier.
    source_id : SourceId | str | None, default=None
        Optional source identifier for source-scoped tables.

    Returns
    -------
    str
        Physical DuckDB table name prefixed with 'pre_bronze.pb_'.
    """
    ds_str = dataset_id.value if isinstance(dataset_id, DatasetId) else str(dataset_id)
    clean_ds = sanitize_physical_identifier(ds_str)
    if source_id is not None:
        src_str = str(source_id)
        clean_src = sanitize_physical_identifier(src_str)
        return f"pre_bronze.pb_{clean_src}_{clean_ds}"
    return f"pre_bronze.pb_{clean_ds}"


def _validate_table_name(table_name: str) -> str:
    """Validate that table name has expected pre_bronze.pb_ prefix and clean identifier."""
    if not table_name.startswith("pre_bronze.pb_"):
        raise ValueError(
            f"Pre-Bronze physical table must start with 'pre_bronze.pb_': {table_name}"
        )
    raw_ident = table_name.removeprefix("pre_bronze.pb_")
    sanitize_physical_identifier(raw_ident)
    return table_name


class PreBronzeLayer:
    """Persistence, retrieval, and table management in the DuckDB Pre-Bronze schema.

    Parameters
    ----------
    db_manager : DuckDBManager
        Active DuckDB warehouse connection manager.
    emitter : ObservabilityEmitter | None, default=None
        Observability emitter for diagnostic logging and telemetry.
    """

    def __init__(
        self,
        db_manager: DuckDBManager,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self.db_manager = db_manager
        self.emitter = emitter or get_global_emitter()

    def _prepare_provenance_frame(
        self,
        df: pl.DataFrame,
        dataset_id: DatasetId,
        artifact_id: str | None,
        source_id: SourceId | str | None,
    ) -> pl.DataFrame:
        """Attach standard operational provenance columns to source DataFrame if missing."""
        res = df
        if PRE_BRONZE_ARTIFACT_ID not in res.columns:
            if not artifact_id:
                raise ValueError(
                    f"artifact_id must be provided when '{PRE_BRONZE_ARTIFACT_ID}' column is missing from DataFrame."
                )
            res = res.with_columns(
                pl.lit(artifact_id).cast(pl.String).alias(PRE_BRONZE_ARTIFACT_ID)
            )

        if PRE_BRONZE_SOURCE_ID not in res.columns:
            src_val = str(source_id) if source_id is not None else None
            res = res.with_columns(pl.lit(src_val).cast(pl.String).alias(PRE_BRONZE_SOURCE_ID))

        if PRE_BRONZE_DATASET_ID not in res.columns:
            res = res.with_columns(
                pl.lit(dataset_id.value).cast(pl.String).alias(PRE_BRONZE_DATASET_ID)
            )

        return res

    def _evolve_schema(self, table_name: str, df: pl.DataFrame) -> None:
        """Evolve existing DuckDB table schema to include any new columns from incoming DataFrame."""
        try:
            table_cols = {
                str(row[0]).lower()
                for row in self.db_manager.conn.execute(f"DESCRIBE {table_name}").fetchall()  # nosec B608
            }
            schema_sample = df.head(0)
            self.db_manager.conn.register("_pb_schema_sample", schema_sample)
            try:
                for col_info in self.db_manager.conn.execute(
                    "DESCRIBE _pb_schema_sample"
                ).fetchall():
                    col_name = str(col_info[0])
                    col_type = str(col_info[1])
                    if col_name.lower() not in table_cols:
                        clean_col = col_name.replace('"', '""')
                        self.db_manager.conn.execute(
                            f'ALTER TABLE {table_name} ADD COLUMN "{clean_col}" {col_type}'  # nosec B608
                        )
                        diagnostics.debug(
                            "Pre-Bronze: Evolved schema for %s: added column '%s' (%s)",
                            table_name,
                            clean_col,
                            col_type,
                        )
            finally:
                self.db_manager.conn.unregister("_pb_schema_sample")
        except duckdb.CatalogException:
            pass

    def table_exists(self, contract_or_table: PreBronzeDataContract | str) -> bool:
        """Check whether physical Pre-Bronze table exists in DuckDB.

        Parameters
        ----------
        contract_or_table : PreBronzeDataContract | str
            Contract or physical table name.

        Returns
        -------
        bool
            True if table exists in DuckDB catalog, False otherwise.
        """
        table_name = (
            contract_or_table.physical_table
            if isinstance(contract_or_table, PreBronzeDataContract)
            else contract_or_table
        )
        _validate_table_name(table_name)
        try:
            self.db_manager.conn.execute(f"DESCRIBE {table_name}")  # nosec B608
            return True
        except duckdb.CatalogException:
            return False

    def write_full_replace(
        self,
        contract: PreBronzeDataContract,
        df: pl.DataFrame | pl.LazyFrame,
        artifact_id: str | None = None,
        source_id: SourceId | str | None = None,
    ) -> int:
        """Write tabular evidence to Pre-Bronze DuckDB table replacing all prior rows.

        Parameters
        ----------
        contract : PreBronzeDataContract
            Target Pre-Bronze persistence contract.
        df : pl.DataFrame | pl.LazyFrame
            Source-shaped tabular evidence.
        artifact_id : str | None, default=None
            Originating artifact identifier. Required if df lacks __artifact_id__ column.
        source_id : SourceId | str | None, default=None
            Originating physical source identifier.

        Returns
        -------
        int
            Number of rows persisted into Pre-Bronze table.
        """
        table_name = _validate_table_name(contract.physical_table)
        mat_df = df.collect() if isinstance(df, pl.LazyFrame) else df
        prepared_df = self._prepare_provenance_frame(
            mat_df, contract.dataset_id, artifact_id, source_id
        )

        self.db_manager.conn.register("_pb_temp_df", prepared_df)
        try:
            self.db_manager.conn.execute(f"DROP TABLE IF EXISTS {table_name}")  # nosec B608
            self.db_manager.conn.execute(
                f"CREATE TABLE {table_name} AS SELECT * FROM _pb_temp_df"  # nosec B608
            )
            diagnostics.debug(
                "Pre-Bronze: Re-created %s with %d rows (full replace).",
                table_name,
                prepared_df.height,
            )
        finally:
            self.db_manager.conn.unregister("_pb_temp_df")

        return prepared_df.height

    def write_incremental(
        self,
        contract: PreBronzeDataContract,
        df: pl.DataFrame | pl.LazyFrame,
        artifact_id: str | None = None,
        source_id: SourceId | str | None = None,
    ) -> int:
        """Write tabular evidence using artifact-keyed replacement semantics.

        Deletes existing rows belonging to the given artifact identity and inserts
        the current extracted rows, ensuring unchanged sibling artifacts are untouched.

        Parameters
        ----------
        contract : PreBronzeDataContract
            Target Pre-Bronze persistence contract.
        df : pl.DataFrame | pl.LazyFrame
            Source-shaped tabular evidence.
        artifact_id : str | None, default=None
            Originating artifact identifier.
        source_id : SourceId | str | None, default=None
            Originating physical source identifier.

        Returns
        -------
        int
            Number of rows persisted for this artifact write.
        """
        table_name = _validate_table_name(contract.physical_table)
        mat_df = df.collect() if isinstance(df, pl.LazyFrame) else df
        prepared_df = self._prepare_provenance_frame(
            mat_df, contract.dataset_id, artifact_id, source_id
        )

        # Collect target artifact IDs to replace
        if artifact_id:
            target_artifact_ids = [artifact_id]
        else:
            target_artifact_ids = [
                str(val) for val in prepared_df[PRE_BRONZE_ARTIFACT_ID].unique().to_list()
            ]

        self.db_manager.conn.register("_pb_temp_df", prepared_df)
        try:
            if not self.table_exists(table_name):
                self.db_manager.conn.execute(
                    f"CREATE TABLE {table_name} AS SELECT * FROM _pb_temp_df"  # nosec B608
                )
                diagnostics.debug(
                    "Pre-Bronze: Created %s with %d rows (initial incremental write).",
                    table_name,
                    prepared_df.height,
                )
            else:
                self._evolve_schema(table_name, prepared_df)

                if target_artifact_ids:
                    placeholders = ", ".join(["?"] * len(target_artifact_ids))
                    delete_query = f"DELETE FROM {table_name} WHERE {PRE_BRONZE_ARTIFACT_ID} IN ({placeholders})"  # nosec B608
                    self.db_manager.conn.execute(delete_query, target_artifact_ids)
                    diagnostics.debug(
                        "Pre-Bronze: Cleared previous rows in %s for artifacts: %s",
                        table_name,
                        target_artifact_ids,
                    )

                if prepared_df.height > 0:
                    insert_query = f"INSERT INTO {table_name} BY NAME SELECT * FROM _pb_temp_df"  # nosec B608
                    self.db_manager.conn.execute(insert_query)
                    diagnostics.debug(
                        "Pre-Bronze: Inserted %d rows into %s.",
                        prepared_df.height,
                        table_name,
                    )
        finally:
            self.db_manager.conn.unregister("_pb_temp_df")

        return prepared_df.height

    def write(
        self,
        contract: PreBronzeDataContract,
        df: pl.DataFrame | pl.LazyFrame,
        artifact_id: str | None = None,
        source_id: SourceId | str | None = None,
    ) -> int:
        """Write tabular evidence according to the contract's configured SyncStrategy.

        Parameters
        ----------
        contract : PreBronzeDataContract
            Target Pre-Bronze persistence contract.
        df : pl.DataFrame | pl.LazyFrame
            Source-shaped tabular evidence.
        artifact_id : str | None, default=None
            Originating artifact identifier.
        source_id : SourceId | str | None, default=None
            Originating physical source identifier.

        Returns
        -------
        int
            Number of rows persisted.
        """
        if contract.sync_strategy == SyncStrategy.FULL_REPLACE:
            return self.write_full_replace(
                contract, df, artifact_id=artifact_id, source_id=source_id
            )
        return self.write_incremental(contract, df, artifact_id=artifact_id, source_id=source_id)

    def migrate_artifact_identity(
        self,
        old_artifact_id: str,
        new_artifact_id: str,
        contract_or_table: PreBronzeDataContract | str,
    ) -> int:
        """Update artifact identity across file renames without re-ingesting physical rows.

        Parameters
        ----------
        old_artifact_id : str
            Previous artifact identifier.
        new_artifact_id : str
            New artifact identifier.
        contract_or_table : PreBronzeDataContract | str
            Target Pre-Bronze contract or physical table name.

        Returns
        -------
        int
            Number of rows updated.
        """
        table_name = (
            contract_or_table.physical_table
            if isinstance(contract_or_table, PreBronzeDataContract)
            else contract_or_table
        )
        _validate_table_name(table_name)
        if not self.table_exists(table_name):
            return 0

        update_query = (
            f"UPDATE {table_name} SET {PRE_BRONZE_ARTIFACT_ID} = ? "  # nosec B608
            f"WHERE {PRE_BRONZE_ARTIFACT_ID} = ? RETURNING 1"
        )
        res = self.db_manager.conn.execute(
            update_query, [new_artifact_id, old_artifact_id]
        ).fetchall()
        updated_count = len(res)
        diagnostics.debug(
            "Pre-Bronze: Migrated %d rows in %s from %s to %s.",
            updated_count,
            table_name,
            old_artifact_id,
            new_artifact_id,
        )
        return updated_count

    def delete_artifact(
        self,
        artifact_id: str,
        contract_or_table: PreBronzeDataContract | str,
    ) -> int:
        """Delete all rows belonging to a specific artifact identity from the table.

        Parameters
        ----------
        artifact_id : str
            Artifact identifier to remove.
        contract_or_table : PreBronzeDataContract | str
            Target Pre-Bronze contract or physical table name.

        Returns
        -------
        int
            Number of rows deleted.
        """
        table_name = (
            contract_or_table.physical_table
            if isinstance(contract_or_table, PreBronzeDataContract)
            else contract_or_table
        )
        _validate_table_name(table_name)
        if not self.table_exists(table_name):
            return 0

        delete_query = f"DELETE FROM {table_name} WHERE {PRE_BRONZE_ARTIFACT_ID} = ? RETURNING 1"  # nosec B608
        res = self.db_manager.conn.execute(delete_query, [artifact_id]).fetchall()
        return len(res)

    def read(
        self,
        dataset_id: DatasetId | str,
        source_id: SourceId | str | None = None,
        include_provenance: bool = True,
    ) -> pl.DataFrame:
        """Read source-shaped tabular data from Pre-Bronze DuckDB table.

        Parameters
        ----------
        dataset_id : DatasetId | str
            Authoritative dataset identifier to query.
        source_id : SourceId | str | None, default=None
            Optional source identifier to filter rows.
        include_provenance : bool, default=True
            Whether to retain __artifact_id__, __source_id__, and __dataset_id__ columns.

        Returns
        -------
        pl.DataFrame
            Source-shaped Polars DataFrame, or empty DataFrame if table does not exist.
        """
        contract = get_pre_bronze_contract_by_dataset_id(dataset_id)
        table_name = (
            contract.physical_table
            if contract is not None
            else get_pre_bronze_table_name(dataset_id)
        )
        _validate_table_name(table_name)

        if not self.table_exists(table_name):
            return pl.DataFrame()

        if source_id is not None:
            query = f"SELECT * FROM {table_name} WHERE {PRE_BRONZE_SOURCE_ID} = ?"  # nosec B608
            df = self.db_manager.conn.execute(query, [str(source_id)]).pl()
        else:
            query = f"SELECT * FROM {table_name}"  # nosec B608
            df = self.db_manager.conn.execute(query).pl()

        if not include_provenance and df.height > 0:
            cols_to_drop = [col for col in PRE_BRONZE_PROVENANCE_COLUMNS if col in df.columns]
            if cols_to_drop:
                df = df.drop(cols_to_drop)

        return df

    def read_lazy(
        self,
        dataset_id: DatasetId | str,
        source_id: SourceId | str | None = None,
        include_provenance: bool = True,
    ) -> pl.LazyFrame:
        """Read source-shaped tabular data from Pre-Bronze DuckDB table as a LazyFrame.

        Parameters
        ----------
        dataset_id : DatasetId | str
            Authoritative dataset identifier to query.
        source_id : SourceId | str | None, default=None
            Optional source identifier to filter rows.
        include_provenance : bool, default=True
            Whether to retain __artifact_id__, __source_id__, and __dataset_id__ columns.

        Returns
        -------
        pl.LazyFrame
            Source-shaped Polars LazyFrame.
        """
        return self.read(
            dataset_id,
            source_id=source_id,
            include_provenance=include_provenance,
        ).lazy()
