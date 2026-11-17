"""Incremental lakehouse ingestion and table management in the warehouse Bronze layer.

Owns
----
- Incremental upserting of raw extracted DataFrames into bronze.* DuckDB tables.
- Table schema evolution for newly added source columns.
- Identity migration during file renames without re-ingesting physical rows.
- Full dataset reading from Bronze tables into an immutable DatasetCollection.

Does not own
-------------
- Filesystem discovery or binary file parsing (owned by infrastructure.providers).
- Raw binary vaulting or control plane state (owned by control plane).
- DuckDB connection lifecycle (owned by infrastructure.warehouse.connection).
"""

from __future__ import annotations

import os

import duckdb
import polars as pl

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.dataset_collection import DatasetCollection
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    PresentationKind,
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
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.registry import BRONZE_CONTRACT_REGISTRY

diagnostics = get_observability_diagnostics("personal_finance_etl.warehouse.bronze")

MIGRATED_DATASETS: frozenset[DatasetId] = frozenset(
    {
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_ASSET_GROUP,
        DatasetId.HOUSEHOLD_ASSETS,
        DatasetId.HOUSEHOLD_CURRENCY,
        DatasetId.HOUSEHOLD_INOUTCOME,
        DatasetId.HOUSEHOLD_OPENING_BALANCES,
        DatasetId.INVESTMENT_MF_ISIN_MAPPING,
        DatasetId.INVESTMENT_BENCHMARK_MAPPING,
        DatasetId.INVESTMENT_BENCHMARK_MASTER,
        DatasetId.INVESTMENT_MACRO_PARAMETERS,
        DatasetId.MARKET_CURRENCY_MAPPING,
        DatasetId.MARKET_MF_HOLDINGS,
        DatasetId.INVESTMENT_MF_ORDERS,
    }
)


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

    def _evolve_schema(self, table_name: str) -> None:
        """Add any new columns found in schema_df to an existing bronze table.

        Parameters
        ----------
        table_name : str
            Target physical Bronze table name.
        """
        try:
            table_cols = {
                str(row[0]).lower()
                for row in self.db_manager.conn.execute(f"DESCRIBE {table_name}").fetchall()  # nosec B608
            }
            for col_info in self.db_manager.conn.execute("DESCRIBE schema_df").fetchall():
                col_name = str(col_info[0])
                col_type = str(col_info[1])
                if col_name.lower() not in table_cols:
                    self.db_manager.conn.execute(
                        f'ALTER TABLE {table_name} ADD COLUMN "{col_name}" {col_type}'  # nosec B608
                    )
                    diagnostics.debug(
                        "Bronze: Evolved schema for %s: added column '%s' (%s)",
                        table_name,
                        col_name,
                        col_type,
                    )
        except duckdb.CatalogException as e:
            diagnostics.debug(
                "Bronze: Table %s not yet created, skipping evolution: %s", table_name, e
            )

    def _prepare_bronze_table(
        self,
        table_name: str,
        full_replace: bool,
        filenames: list[str],
    ) -> None:
        """Create or clear partition slices in the Bronze table before row insertion.

        Parameters
        ----------
        table_name : str
            Physical table name.
        full_replace : bool
            Whether to drop and replace the table.
        filenames : list[str]
            Basenames of files to remove before re-inserting.
        """
        if full_replace:
            self.db_manager.conn.execute(f"DROP TABLE IF EXISTS {table_name}")  # nosec B608
            self.db_manager.conn.execute(
                f"CREATE TABLE {table_name} AS SELECT * FROM schema_df"  # nosec B608
            )
            diagnostics.debug("Bronze: Re-created %s for full replacement.", table_name)
        else:
            create_query = f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM schema_df"  # nosec B608
            self.db_manager.conn.execute(create_query)
            self._evolve_schema(table_name)

            placeholders = ", ".join(["?"] * len(filenames))
            delete_query = f"DELETE FROM {table_name} WHERE __file_name__ IN ({placeholders})"  # nosec B608
            diagnostics.debug("Bronze SQL: %s", delete_query)
            self.db_manager.conn.execute(delete_query, filenames)

    def _insert_bronze_records(
        self,
        table_name: str,
        df_filtered: pl.DataFrame,
    ) -> dict[str, int]:
        """Insert filtered rows into the target table and return counts per file.

        Parameters
        ----------
        table_name : str
            Physical table name.
        df_filtered : pl.DataFrame
            Filtered DataFrame with actionable rows.

        Returns
        -------
        dict[str, int]
            Mapping of file basename to inserted row count.
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

            counts = df_filtered.group_by("__file_name__").len()
            for row in counts.iter_rows():
                result[row[0]] = row[1]
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
        """Upsert DataFrame into a Bronze table using file-level partition boundaries.

        Parameters
        ----------
        df : pl.DataFrame | pl.LazyFrame
            Source tabular data.
        table_name : str
            Physical Bronze table name (e.g. 'bronze.r_MF_Transactions').
        actionable_files : list[str]
            List of filepaths actionable in this run.
        full_replace : bool, default=False
            Whether to drop and replace the entire table.

        Returns
        -------
        dict[str, int]
            Mapping of file name to inserted row count.
        """
        if isinstance(df, pl.LazyFrame):
            compact_plan = df.explain().replace("\n", " | ")
            diagnostics.debug("Physical Plan for Bronze '%s': %s", table_name, compact_plan)
            # Materialization Boundary: PUBLICATION_BOUNDARY
            # Terminal execution of lazy ingestion graph for DuckDB Bronze table insertion
            df = df.collect()

        if not actionable_files:
            return {}

        filenames = [os.path.basename(f) for f in actionable_files]
        df_filtered = df.filter(pl.col("__file_name__").is_in(filenames))

        schema_df = df.head(0)
        self.db_manager.conn.register("schema_df", schema_df)
        try:
            self._prepare_bronze_table(table_name, full_replace, filenames)
        finally:
            self.db_manager.conn.unregister("schema_df")

        return self._insert_bronze_records(table_name, df_filtered)

    def load(
        self,
        extracted_data: DatasetCollection,
        actionable_files: dict[str, list[str]],
    ) -> None:
        """Write all raw extracted DataFrames to bronze.* tables.

        Parameters
        ----------
        extracted_data : DatasetCollection
            Extracted source dataset collection.
        actionable_files : dict[str, list[str]]
            Mapping of sync category to actionable file paths.
        """
        total_upserts = 0
        total_rows = 0

        for contract in BRONZE_CONTRACT_REGISTRY:
            if (
                contract.dataset_id in MIGRATED_DATASETS
                or contract.dataset_id == DatasetId.COMMON_COLUMN_MASTER
            ):
                continue
            df = extracted_data.get(contract.dataset_id)
            if df is not None:
                actionable = actionable_files.get(contract.sync_category, [])
                if actionable:
                    diagnostics.debug(
                        "Schema: %s Schema: %s", contract.physical_table, df.collect_schema()
                    )
                    row_counts = self.upsert_table(
                        df,
                        contract.physical_table,
                        actionable,
                        full_replace=contract.is_full_replace,
                    )

                    if contract.is_full_replace:
                        self.db_manager.conn.execute(
                            "DELETE FROM meta.m_File_Registry WHERE file_category = ?",
                            [contract.sync_category],
                        )

                    rows_added = sum(row_counts.values())
                    diagnostics.debug(
                        "Bronze: Table '%s': Upserted %d rows from %d files.",
                        contract.physical_table,
                        rows_added,
                        len(actionable),
                    )
                    self.emitter.emit_event(
                        event_code=EventCode.BRONZE_UPSERT,
                        message=f"Bronze: Table '{contract.physical_table}' upserted {rows_added} rows from {len(actionable)} files.",
                        severity=DiagnosticSeverity.DEBUG,
                        presentation_kind=PresentationKind.INTERNAL,
                        stage=EngineStage.EXTRACTING,
                        entity_type="Table",
                        entity_id=contract.physical_table,
                        rows=rows_added,
                    )
                    if rows_added > 0:
                        total_upserts += 1
                        total_rows += rows_added

                    for filepath in actionable:
                        filename = os.path.basename(filepath)
                        count = row_counts.get(filename, 0)
                        self.cp.artifacts.mark_synced([filepath])
                        self.meta_layer.register_file(
                            filepath, contract.sync_category, count, self.cp
                        )

        diagnostics.info(
            "Bronze: Synchronized %d source datasets (%s new rows).",
            total_upserts,
            f"{total_rows:,}",
        )

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
            cats_to_tables.setdefault(contract.sync_category, []).append(contract.physical_table)

        for old_path, new_path, category in renames:
            tables = cats_to_tables.get(category, [])
            if not tables:
                continue

            old_name = os.path.basename(old_path)
            new_name = os.path.basename(new_path)
            old_id = generate_file_id(old_path)
            new_id = generate_file_id(new_path)

            for table in tables:
                try:
                    self.db_manager.conn.execute(
                        f"UPDATE {table} SET __file_name__ = ? WHERE __file_name__ = ?",  # nosec B608
                        [new_name, old_name],
                    )
                    try:
                        self.db_manager.conn.execute(
                            f"UPDATE {table} SET artifact_id = ? WHERE artifact_id = ?",  # nosec B608
                            [new_id, old_id],
                        )
                    except duckdb.BinderException:
                        pass
                except (duckdb.BinderException, duckdb.CatalogException) as e:
                    diagnostics.debug("Bronze: Could not rename %s in %s: %s", old_name, table, e)

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
        try:
            return self.db_manager.conn.execute(
                f"SELECT * FROM bronze.{table_name}"  # nosec B608
            ).pl()
        except duckdb.CatalogException:
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
