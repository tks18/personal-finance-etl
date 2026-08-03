import glob
import os
import shutil
import tempfile
import uuid
from datetime import datetime

import duckdb
import polars as pl
import psutil

from src.load.schema import SQLITE_SCHEMA_DDL
from src.utils.interfaces import ILogger
from src.utils.logger import logger
from src.utils.models import EngineStatus


class DuckDBManager:
    """Manages DuckDB database creation, schema setup, indexing, and batch writing."""

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.db_path = self._generate_target_db_path()
        self.active_db_path = os.path.join(
            tempfile.gettempdir(), f"etl_tmp_{uuid.uuid4().hex}.duckdb"
        )

    def _generate_target_db_path(self) -> str:
        now = datetime.now()
        if now.month >= 4:
            fy_str = f"{now.year}-{str(now.year + 1)[-2:]}"
        else:
            fy_str = f"{now.year - 1}-{str(now.year)[-2:]}"

        month_year_str = now.strftime("%m-%Y")
        file_name = f"Personal_Finance_DB_{month_year_str}.duckdb"

        full_dir_path = os.path.join(self.base_path, fy_str, month_year_str)
        os.makedirs(full_dir_path, exist_ok=True)

        return os.path.join(full_dir_path, file_name)

    def setup_schema(self) -> None:
        """Deletes old tmp DB and creates strict schemas."""
        if os.path.exists(self.active_db_path):
            os.remove(self.active_db_path)

        with duckdb.connect(self.active_db_path) as conn:
            # Phase 2.2: DuckDB Pragma Tuning for Batch ETL
            mem_gb = max(4, int(psutil.virtual_memory().total / (1024**3) * 0.75))
            conn.execute(f"PRAGMA memory_limit='{mem_gb}GB'")
            conn.execute("PRAGMA threads=4")
            conn.execute(SQLITE_SCHEMA_DDL)

    def commit(self) -> None:
        """Atomically rename the tmp db to the final db path."""
        if os.path.exists(self.active_db_path):
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
            shutil.move(self.active_db_path, self.db_path)

    def apply_indexes_and_optimize(self) -> None:
        """DuckDB natively manages optimization and zone maps, no explicit indexes needed."""
        pass

    def enforce_retention_policy(self, max_files: int = 12) -> None:
        """Keeps only the most recent N database files to prevent disk bloat."""
        search_pattern = os.path.join(self.base_path, "**", "*.duckdb")
        db_files = glob.glob(search_pattern, recursive=True)

        if len(db_files) <= max_files:
            return

        # Sort by modification time, oldest first
        db_files.sort(key=os.path.getmtime)
        files_to_delete = db_files[:-max_files]

        for db_file in files_to_delete:
            try:
                os.remove(db_file)
                logger.info(f"Deleted old database file: {db_file}")

                # Cleanup parent dir if empty
                parent_dir = os.path.dirname(db_file)
                if not os.listdir(parent_dir):
                    shutil.rmtree(parent_dir)
            except Exception as e:
                logger.warning(f"Failed to delete old DB {db_file}: {e}")

    def cleanup(self) -> None:
        """Ensures WAL sidecar files are merged if any, removes tmp files, and enforces retention."""
        if os.path.exists(self.active_db_path):
            try:
                os.remove(self.active_db_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp DB {self.active_db_path}: {e}")

        if os.path.exists(self.db_path):
            with duckdb.connect(self.db_path) as conn:
                conn.execute("CHECKPOINT;")

        self.enforce_retention_policy()

    def batch_write_dataframe(
        self,
        df: pl.DataFrame,
        table_name: str,
        conn: duckdb.DuckDBPyConnection,
        chunk_size: int = 50000,
    ) -> None:
        """Writes a DataFrame to DuckDB using native zero-copy integration."""
        if df.height == 0:
            return

        # Clean empty strings into true nulls only for dimension tables
        if table_name.startswith("d_"):
            string_cols = [
                c
                for c, d in zip(df.columns, df.dtypes, strict=True)
                if d in (getattr(pl, "Utf8", None), getattr(pl, "String", None))
            ]
            if string_cols:
                df = df.with_columns(
                    [
                        pl.when(pl.col(c) == "").then(None).otherwise(pl.col(c)).alias(c)
                        for c in string_cols
                    ]
                )

        conn.register("temp_df", df)
        conn.execute(f"INSERT INTO {table_name} BY NAME SELECT * FROM temp_df")
        conn.unregister("temp_df")


class DuckDBLoader:
    """Orchestrates the loading of dataframes via the DuckDBManager."""

    def __init__(self, db_manager: DuckDBManager, status_queue: ILogger):
        self.db_manager = db_manager
        self.status_queue = status_queue

    def run(self, dfs: dict[str, pl.DataFrame]) -> None:
        logger.info("Writing tables to DuckDB...")
        table_mappings = {
            "df_d_calendar": "d_Calendar",
            "df_d_income_category": "d_Income_Category",
            "df_d_income_subcategory": "d_Income_Subcategory",
            "df_d_expense_category": "d_Expense_Category",
            "df_d_expense_subcategory": "d_Expense_Subcategory",
            "df_d_asset_category": "d_Asset_Category",
            "df_d_asset_subcategory": "d_Asset_SubCategory",
            "df_d_currency": "d_Currency",
            "df_d_benchmark_master": "d_Investment_Benchmark_Master",
            "df_d_tf_investment_master": "d_tf_Investment_Master",
            "df_d_macro_parameters": "d_Macro_Parameters",
            "df_f_income_transactions": "f_Income_Transactions",
            "df_f_expense_transactions": "f_Expense_Transactions",
            "df_f_transfer_transactions": "f_Transfer_Transactions",
            "df_f_opening_balances": "f_Opening_Balances",
            "df_stg_investment_market_data": "stg_Investment_Market_Data",
            "df_f_tf_inv_purchase": "f_tf_Investment_Purchase_Data",
            "df_f_tf_inv_sale": "f_tf_Investment_Sale_Data",
            "df_f_investment_benchmark_data": "f_Investment_Benchmark_Data",
            "df_f_tf_investment_analytics_lot": "f_tf_Investment_Analytics_Lot",
            "df_f_tf_investment_analytics_isin": "f_tf_Investment_Analytics_ISIN",
            "df_f_tf_investment_analytics_subtype": "f_tf_Investment_Analytics_Subtype",
            "df_f_tf_investment_analytics_class": "f_tf_Investment_Analytics_Class",
            "df_f_tf_investment_analytics_portfolio": "f_tf_Investment_Analytics_Portfolio",
            "_ETL_Metadata_Financial_Rules": "_ETL_Metadata_Financial_Rules",
        }
        presentation_tables = {
            "df_p_tf_net_worth_monthly_summary": "p_tf_Net_Worth_Monthly_Summary",
            "df_p_tf_financial_ratios_monthly": "p_tf_Financial_Ratios_Monthly",
            "df_p_tf_category_spend_analytics": "p_tf_category_spend_analytics",
            "df_p_tf_income_streams_monthly": "p_tf_income_streams_monthly",
            "df_p_tf_fire_forecasting_monthly": "p_tf_fire_forecasting_monthly",
            "df_p_tf_risk_metrics": "p_tf_risk_metrics",
            "df_p_tf_sector_allocation_monthly": "p_tf_sector_allocation_monthly",
            "df_p_tf_tax_harvesting": "p_tf_tax_harvesting",
        }
        table_mappings.update(presentation_tables)

        with duckdb.connect(self.db_manager.active_db_path) as conn:
            for df_key, table_name in table_mappings.items():
                if df_key in dfs and dfs[df_key] is not None:
                    self.db_manager.batch_write_dataframe(dfs[df_key], table_name, conn)

            logger.info("Generating Data Quality Metadata...")
            metadata_rows = []
            for key, df in dfs.items():
                if df is not None:
                    table_name = table_mappings.get(key, key)
                    metadata_rows.append({"Table_Name": table_name, "Row_Count": df.height})

            if metadata_rows:
                df_metadata = pl.DataFrame(metadata_rows).with_columns(
                    pl.lit(datetime.now()).alias("Generated_At")
                )
                self.db_manager.batch_write_dataframe(df_metadata, "_ETL_Metadata", conn)

        self.status_queue.put(EngineStatus(msg="", data=None, progress=0.9))
        logger.info("Applying indexes and optimizing database...")
        self.db_manager.apply_indexes_and_optimize()
