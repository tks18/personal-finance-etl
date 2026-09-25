import os

import duckdb
import polars as pl

from personal_finance_etl.backend.load.control_plane.orchestrator import ControlPlane
from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.load.metadata import MetaLayer
from personal_finance_etl.backend.load.registry import BRONZE_CONTRACT_REGISTRY
from personal_finance_etl.backend.utils.logger import logger
from personal_finance_etl.backend.utils.models import ExtractionResult


class BronzeLayer:
    """Handles incremental loading of raw extracted data into the bronze schema."""

    def __init__(self, db_manager: DuckDBManager, cp: ControlPlane, meta_layer: MetaLayer):
        self.db_manager = db_manager
        self.cp = cp
        self.meta_layer = meta_layer

    def upsert_table(
        self,
        df: pl.DataFrame | pl.LazyFrame,
        table_name: str,
        actionable_files: list[str],
        full_replace: bool = False,
    ) -> dict[str, int]:
        """Uses db_manager.conn directly. If full_replace is True, truncates the table first.
        Otherwise, deletes existing rows matching __file_name__ then re-inserts.
        Returns dict mapping filename to row count."""
        if isinstance(df, pl.LazyFrame):
            df = df.collect()

        if df.height == 0 or not actionable_files:
            return {}

        filenames = [os.path.basename(f) for f in actionable_files]
        df_filtered = df.filter(pl.col("__file_name__").is_in(filenames))

        if df_filtered.height == 0:
            return {}

        # Dynamically create table schema if it doesn't exist or drop if full_replace
        schema_df = df.head(0)
        self.db_manager.conn.register("schema_df", schema_df)
        if full_replace:
            self.db_manager.conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            self.db_manager.conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM schema_df")
            logger.debug(f"[Bronze] Re-created {table_name} for full replacement.")
        else:
            self.db_manager.conn.execute(
                f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM schema_df"
            )
            placeholders = ", ".join(["?"] * len(filenames))
            delete_query = f"DELETE FROM {table_name} WHERE __file_name__ IN ({placeholders})"
            self.db_manager.conn.execute(delete_query, filenames)

        self.db_manager.conn.unregister("schema_df")

        # Insert new rows
        self.db_manager.conn.register("temp_df", df_filtered)
        logger.debug(
            f"[Bronze] Upserting {df_filtered.height} rows into {table_name} from {len(filenames)} files."
        )
        self.db_manager.conn.execute(f"INSERT INTO {table_name} BY NAME SELECT * FROM temp_df")
        self.db_manager.conn.unregister("temp_df")

        # Calculate per-file row count
        counts = df_filtered.group_by("__file_name__").len()
        # Polars group_by returns a dataframe, we convert it to dict
        result: dict[str, int] = {}
        for row in counts.iter_rows():
            result[row[0]] = row[1]
        return result

    def load(
        self,
        extracted_data: ExtractionResult,
        new_files: dict[str, list[str]],
        changed_files: dict[str, list[str]],
    ) -> None:
        """Writes all raw extracted dataframes to bronze.* via db_manager.conn."""
        logger.info("Loading raw datasets into Bronze layer...")

        for contract in BRONZE_CONTRACT_REGISTRY:
            df = getattr(extracted_data, contract.extraction_attribute, None)
            if df is not None:
                actionable = new_files.get(contract.sync_category, []) + changed_files.get(
                    contract.sync_category, []
                )
                if actionable:
                    row_counts = self.upsert_table(
                        df,
                        contract.physical_table,
                        actionable,
                        full_replace=contract.is_full_replace,
                    )

                    # Wipe old registry entries for full-replace sources to prevent obsolete file bloating
                    if contract.is_full_replace:
                        self.db_manager.conn.execute(
                            "DELETE FROM meta.m_File_Registry WHERE file_category = ?",
                            [contract.sync_category],
                        )

                    for filepath in actionable:
                        filename = os.path.basename(filepath)
                        count = row_counts.get(filename, 0)
                        self.cp.artifacts.mark_synced([filepath])
                        self.meta_layer.register_file(
                            filepath, contract.sync_category, count, self.cp
                        )

        logger.info("Bronze layer load complete.")

    def get_table(self, table_name: str) -> pl.DataFrame:
        """Reads a table from the Bronze schema. Returns empty DataFrame if it doesn't exist."""
        try:
            return self.db_manager.conn.execute(f"SELECT * FROM bronze.{table_name}").pl()
        except duckdb.CatalogException:
            return pl.DataFrame()

    def get_full_dataset(self, original_mappings: dict[str, dict[str, str]]) -> ExtractionResult:
        """Reads the full dataset from Bronze tables via DuckDB and returns a complete ExtractionResult."""
        logger.info("Reading full dataset from Bronze Layer Lakehouse...")

        def _get_lf(table_name: str) -> pl.LazyFrame:
            try:
                return self.db_manager.conn.query(f"SELECT * FROM {table_name}").pl().lazy()
            except duckdb.CatalogException:
                logger.debug(f"[Bronze] Table {table_name} does not exist. Returning empty frame.")
                return pl.LazyFrame()

        def _get_df(table_name: str) -> pl.DataFrame:
            try:
                return self.db_manager.conn.query(f"SELECT * FROM {table_name}").pl()
            except duckdb.CatalogException:
                logger.debug(f"[Bronze] Table {table_name} does not exist. Returning empty frame.")
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
        )
