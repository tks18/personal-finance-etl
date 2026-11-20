"""Incremental lakehouse ingestion and table management in the warehouse Bronze layer.

Owns
----
- Incremental upserting of canonical DataFrames into bronze.* DuckDB tables.
- Fixed canonical schema enforcement (no dynamic runtime schema evolution).
- Identity migration during file renames without re-ingesting physical rows.
- Full dataset reading from Bronze tables into an immutable DatasetCollection.

Does not own
-------------
- Dynamic runtime schema evolution (prohibited by strict canonical schemas).
- Filesystem discovery or binary file parsing (owned by infrastructure.providers).
- Raw binary vaulting or control plane state (owned by control plane).
- DuckDB connection lifecycle (owned by infrastructure.warehouse.connection).
"""

from __future__ import annotations

import os

import duckdb
import polars as pl

from personal_finance_etl.contracts.canonical_fields import get_canonical_fields
from personal_finance_etl.contracts.dataset_collection import DatasetCollection
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.control_plane.hashing import generate_file_id
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.registry import BRONZE_CONTRACT_REGISTRY

diagnostics = get_observability_diagnostics("personal_finance_etl.warehouse.bronze")

MIGRATED_DATASETS: frozenset[DatasetId] = frozenset()


class BronzeLayer:
    """Handles incremental loading of raw extracted data into the bronze schema.

    Parameters
    ----------
    db_manager : DuckDBManager
        Active DuckDB connection manager.
    cp : ControlPlane
        Active control plane facade.
    meta_layer : MetaLayer
        Metadata projection layer manager.
    """

    def __init__(
        self,
        db_manager: DuckDBManager,
        cp: ControlPlane,
        meta_layer: MetaLayer,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self.db_manager = db_manager
        self.cp = cp
        self.meta_layer = meta_layer
        self.emitter = emitter or get_global_emitter()

    def _prepare_bronze_table(
        self,
        table_name: str,
        full_replace: bool,
        artifact_ids: list[str],
    ) -> None:
        """Clear partition slices or truncate in the Bronze table before row insertion.

        Parameters
        ----------
        table_name : str
            Physical table name.
        full_replace : bool
            Whether to truncate the entire table.
        artifact_ids : list[str]
            Artifact IDs of items to remove before re-inserting.
        """
        if full_replace:
            self.db_manager.conn.execute(f"DELETE FROM {table_name}")  # nosec B608
            diagnostics.debug("Bronze: Truncated %s for full replacement.", table_name)
        else:
            placeholders = ", ".join(["?"] * len(artifact_ids))
            delete_query = f"DELETE FROM {table_name} WHERE artifact_id IN ({placeholders})"  # nosec B608
            diagnostics.debug("Bronze SQL: %s", delete_query)
            self.db_manager.conn.execute(delete_query, artifact_ids)

    def _insert_bronze_records(
        self,
        table_name: str,
        df_filtered: pl.DataFrame,
    ) -> dict[str, int]:
        """Insert filtered rows into the target table and return counts per artifact.

        Parameters
        ----------
        table_name : str
            Physical table name.
        df_filtered : pl.DataFrame
            Filtered DataFrame with actionable rows.

        Returns
        -------
        dict[str, int]
            Mapping of artifact ID to inserted row count.
        """
        result: dict[str, int] = {}
        if df_filtered.height > 0:
            self.db_manager.conn.register("temp_df", df_filtered)
            insert_query = f"INSERT INTO {table_name} BY NAME SELECT * FROM temp_df"  # nosec B608
            diagnostics.debug("Bronze SQL: %s", insert_query)
            self.db_manager.conn.execute(insert_query)
            diagnostics.debug(
                "Bronze: Upserted %s: %d rows processed.",
                table_name,
                df_filtered.height,
            )
            self.db_manager.conn.unregister("temp_df")

            counts = df_filtered.group_by("artifact_id").len()
            for row in counts.iter_rows():
                result[str(row[0])] = int(row[1])
        else:
            diagnostics.debug("Bronze: Upserted %s: 0 rows processed (empty source).", table_name)
        return result

    def upsert_table(
        self,
        df: pl.DataFrame | pl.LazyFrame,
        table_name: str,
        actionable_files: list[str],
        full_replace: bool = False,
    ) -> dict[str, int]:
        """Upsert DataFrame into a Bronze table using artifact-level partition boundaries.

        Parameters
        ----------
        df : pl.DataFrame | pl.LazyFrame
            Source tabular data.
        table_name : str
            Physical Bronze table name (e.g. 'bronze.investment_mf_orders').
        actionable_files : list[str]
            List of filepaths or artifact IDs actionable in this run.
        full_replace : bool, default=False
            Whether to drop and replace the entire table.

        Returns
        -------
        dict[str, int]
            Mapping of artifact ID and file name to inserted row count.
        """
        if isinstance(df, pl.LazyFrame):
            compact_plan = df.explain().replace("\n", " | ")
            diagnostics.debug("Physical Plan for Bronze '%s': %s", table_name, compact_plan)
            # Materialization Boundary: PUBLICATION_BOUNDARY
            # Terminal execution of lazy ingestion graph for DuckDB Bronze table insertion
            df = df.collect()

        if not actionable_files:
            return {}

        artifact_to_file: dict[str, str] = {}
        for f in actionable_files:
            art_id = generate_file_id(f) if ("/" in f or "\\" in f or "." in f) else f
            artifact_to_file[art_id] = os.path.basename(f)

        artifact_ids = list(artifact_to_file.keys())
        df_filtered = df.filter(pl.col("artifact_id").is_in(artifact_ids))

        self._prepare_bronze_table(table_name, full_replace, artifact_ids)

        counts = self._insert_bronze_records(table_name, df_filtered)
        for art_id, count in list(counts.items()):
            fname = artifact_to_file.get(art_id)
            if fname and fname not in counts:
                counts[fname] = count
        return counts

    def migrate_identity(self, renames: list[tuple[str, str, str]]) -> None:
        """Migrate file identity (rename) in all Bronze tables without re-ingesting rows.

        Parameters
        ----------
        renames : list[tuple[str, str, str]]
            Triplets of (old_path, new_path, category).
        """
        if not renames:
            return

        cats_to_tables: dict[str, list[str]] = {}
        for contract in BRONZE_CONTRACT_REGISTRY:
            cats_to_tables.setdefault(contract.dataset_id.value, []).append(contract.physical_table)
            cats_to_tables.setdefault(contract.sync_category, []).append(contract.physical_table)

        for old_path, new_path, category in renames:
            tables = cats_to_tables.get(category, [])
            if not tables:
                continue

            old_id = generate_file_id(old_path)
            new_id = generate_file_id(new_path)

            for table in tables:
                try:
                    self.db_manager.conn.execute(
                        f"UPDATE {table} SET artifact_id = ? WHERE artifact_id = ?",  # nosec B608
                        [new_id, old_id],
                    )
                except (duckdb.BinderException, duckdb.CatalogException) as e:
                    diagnostics.debug(
                        "Bronze: Could not migrate artifact %s in %s: %s", old_id, table, e
                    )

    def get_table(self, table_name: str) -> pl.DataFrame:
        """Read a table from the Bronze schema. Returns empty DataFrame if missing.

        Parameters
        ----------
        table_name : str
            Table name within bronze schema.

        Returns
        -------
        pl.DataFrame
            Queried DataFrame or empty frame.
        """
        raw_table = table_name.removeprefix("bronze.")
        try:
            return self.db_manager.conn.execute(
                f"SELECT * FROM bronze.{raw_table}"  # nosec B608
            ).pl()
        except (duckdb.CatalogException, duckdb.BinderException):
            return pl.DataFrame()

    def get_dataset_collection(self) -> DatasetCollection:
        """Read full dataset state from Bronze tables via DuckDB and return complete DatasetCollection.

        Returns
        -------
        DatasetCollection
            Immutable DatasetCollection containing all Bronze lakehouse tables indexed by DatasetId.
        """
        diagnostics.info("Reading full dataset collection from Bronze Layer Lakehouse...")
        frames: dict[DatasetId, pl.LazyFrame | pl.DataFrame] = {}

        for contract in BRONZE_CONTRACT_REGISTRY:
            table_name = contract.physical_table
            try:
                # Column master is currently consumed as a DataFrame
                if contract.dataset_id == DatasetId.COMMON_COLUMN_MASTER:
                    frames[contract.dataset_id] = self.db_manager.conn.query(
                        f"SELECT * FROM {table_name}"  # nosec B608
                    ).pl()
                else:
                    frames[contract.dataset_id] = (
                        self.db_manager.conn.query(
                            f"SELECT * FROM {table_name}"  # nosec B608
                        )
                        .pl()
                        .lazy()
                    )
            except duckdb.CatalogException:
                diagnostics.debug(
                    "Bronze: Table %s does not exist. Registering empty frame.", table_name
                )
                if contract.dataset_id == DatasetId.COMMON_COLUMN_MASTER:
                    frames[contract.dataset_id] = pl.DataFrame()
                else:
                    frames[contract.dataset_id] = pl.LazyFrame()

        return DatasetCollection(frames=frames)


def verify_canonical_bronze_schemas(conn: duckdb.DuckDBPyConnection) -> list[str]:
    """Verify that existing physical Bronze tables conform to canonical contracts.

    Parameters
    ----------
    conn : duckdb.DuckDBPyConnection
        Active DuckDB connection handle.

    Returns
    -------
    list[str]
        List of schema mismatch diagnostic messages, if any.
    """
    mismatches: list[str] = []
    for contract in BRONZE_CONTRACT_REGISTRY:
        table_name = contract.physical_table
        ds_id = contract.dataset_id
        try:
            db_cols = {str(row[0]) for row in conn.execute(f"DESCRIBE {table_name}").fetchall()}  # nosec B608
            permitted = get_canonical_fields(ds_id)
            if permitted is not None:
                extra_cols = db_cols - permitted
                if extra_cols:
                    mismatches.append(
                        f"Table {table_name} contains unpermitted extra columns: {sorted(extra_cols)}"
                    )
        except duckdb.CatalogException:
            continue
    return mismatches
