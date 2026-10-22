"""Incremental lakehouse ingestion and table management in the warehouse Bronze layer.

Owns
----
- Incremental upserting of raw extracted DataFrames into bronze.* DuckDB tables.
- Table schema evolution for newly added source columns.
- Identity migration during file renames without re-ingesting physical rows.
- Full dataset reading from Bronze tables into a typed ExtractionResult.

Does not own
-------------
- Filesystem discovery or binary file parsing (owned by infrastructure.providers).
- Raw binary vaulting or control plane state (owned by control plane).
- DuckDB connection lifecycle (owned by infrastructure.warehouse.connection).
"""

from __future__ import annotations

import logging
import os

import duckdb
import polars as pl

from personal_finance_etl.contracts.extraction import ExtractionResult
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.registry import BRONZE_CONTRACT_REGISTRY

logger = logging.getLogger("personal_finance_etl.warehouse.bronze")


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

    def __init__(self, db_manager: DuckDBManager, cp: ControlPlane, meta_layer: MetaLayer) -> None:
        self.db_manager = db_manager
        self.cp = cp
        self.meta_layer = meta_layer

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
                    logger.debug(
                        "[Bronze] Evolved schema for %s: added column '%s' (%s)",
                        table_name,
                        col_name,
                        col_type,
                    )
        except duckdb.CatalogException as e:
            logger.debug("[Bronze] Table %s not yet created, skipping evolution: %s", table_name, e)

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
            logger.debug("[Bronze] Re-created %s for full replacement.", table_name)
        else:
            create_query = f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM schema_df"  # nosec B608
            self.db_manager.conn.execute(create_query)
            self._evolve_schema(table_name)

            placeholders = ", ".join(["?"] * len(filenames))
            delete_query = f"DELETE FROM {table_name} WHERE __file_name__ IN ({placeholders})"  # nosec B608
            logger.debug("[BRONZE:DETAIL] Executing SQL: %s", delete_query)
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
            logger.debug("[BRONZE:DETAIL] Executing SQL: %s", insert_query)
            self.db_manager.conn.execute(insert_query)
            logger.debug(
                "[BRONZE:DETAIL] Upserted %s: %d rows processed.",
                table_name,
                df_filtered.height,
            )
            self.db_manager.conn.unregister("temp_df")

            counts = df_filtered.group_by("__file_name__").len()
            for row in counts.iter_rows():
                result[row[0]] = row[1]
        else:
            logger.debug(
                "[BRONZE:DETAIL] Upserted %s: 0 rows processed (empty source).", table_name
            )
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
            logger.debug("Physical Plan for Bronze '%s': %s", table_name, compact_plan)
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
        extracted_data: ExtractionResult,
        actionable_files: dict[str, list[str]],
    ) -> None:
        """Write all raw extracted DataFrames to bronze.* tables.

        Parameters
        ----------
        extracted_data : ExtractionResult
            Extracted source frames.
        actionable_files : dict[str, list[str]]
            Mapping of sync category to actionable file paths.
        """
        total_upserts = 0
        total_rows = 0

        for contract in BRONZE_CONTRACT_REGISTRY:
            df = getattr(extracted_data, contract.extraction_attribute, None)
            if df is not None:
                actionable = actionable_files.get(contract.sync_category, [])
                if actionable:
                    logger.debug(
                        "[SCHEMA] %s Schema: %s", contract.physical_table, df.collect_schema()
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
                    logger.debug(
                        "[BRONZE:TRACE] Table '%s': Upserted %d rows from %d files.",
                        contract.physical_table,
                        rows_added,
                        len(actionable),
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

        logger.info(
            "[BRONZE] Synchronized %d source datasets (%s new rows).",
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

        cat_to_table = {
            contract.sync_category: contract.physical_table for contract in BRONZE_CONTRACT_REGISTRY
        }

        for old_path, new_path, category in renames:
            table = cat_to_table.get(category)
            if not table:
                continue

            old_name = os.path.basename(old_path)
            new_name = os.path.basename(new_path)

            try:
                self.db_manager.conn.execute(
                    f"UPDATE {table} SET __file_name__ = ? WHERE __file_name__ = ?",  # nosec B608
                    [new_name, old_name],
                )
            except (duckdb.BinderException, duckdb.CatalogException) as e:
                logger.debug("[Bronze] Could not rename %s in %s: %s", old_name, table, e)

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

    def get_full_dataset(self, original_mappings: dict[str, dict[str, str]]) -> ExtractionResult:
        """Read full dataset from Bronze tables via DuckDB and return complete ExtractionResult.

        Parameters
        ----------
        original_mappings : dict[str, dict[str, str]]
            Original column mappings.

        Returns
        -------
        ExtractionResult
            Complete typed ExtractionResult.
        """
        logger.info("Reading full dataset from Bronze Layer Lakehouse...")

        def _get_lf(table_name: str) -> pl.LazyFrame:
            try:
                return (
                    self.db_manager.conn.query(
                        f"SELECT * FROM {table_name}"  # nosec B608
                    )
                    .pl()
                    .lazy()
                )
            except duckdb.CatalogException:
                logger.debug("[Bronze] Table %s does not exist. Returning empty frame.", table_name)
                return pl.LazyFrame()

        def _get_df(table_name: str) -> pl.DataFrame:
            try:
                return self.db_manager.conn.query(
                    f"SELECT * FROM {table_name}"  # nosec B608
                ).pl()
            except duckdb.CatalogException:
                logger.debug("[Bronze] Table %s does not exist. Returning empty frame.", table_name)
                return pl.DataFrame()

        return ExtractionResult(
            zcategory=_get_lf("bronze.r_SQLite_ZCategory"),
            assetgroup=_get_lf("bronze.r_SQLite_AssetGroup"),
            assets=_get_lf("bronze.r_SQLite_Assets"),
            currency=_get_lf("bronze.r_SQLite_Currency"),
            inoutcome=_get_lf("bronze.r_SQLite_InOutcome"),
            mappings=original_mappings,
            stg_mf_isin_mapping=_get_lf("bronze.r_MF_ISIN_Mapping"),
            stg_benchmark_mapping=_get_lf("bronze.r_Benchmark_Mapping"),
            mf_market_data_raw=_get_lf("bronze.r_MF_Market_Data"),
            mf_transactions_raw=_get_lf("bronze.r_MF_Transactions"),
            stock_market_data_raw=_get_lf("bronze.r_Stock_Market_Data"),
            stock_transactions_raw=_get_lf("bronze.r_Stock_Transactions"),
            raw_opening_balances=_get_lf("bronze.r_Opening_Balances"),
            raw_benchmark_master=_get_lf("bronze.r_Benchmark_Master"),
            raw_macro_parameters=_get_lf("bronze.r_Macro_Parameters"),
            column_master=_get_df("bronze.r_Column_Master"),
            us_stock_transactions_raw=_get_lf("bronze.r_US_Stock_Transactions"),
            currency_mapping_raw=_get_lf("bronze.r_Currency_Mapping"),
        )
