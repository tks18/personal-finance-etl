import polars as pl

from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.load.registry import DATA_CONTRACT_REGISTRY
from personal_finance_etl.backend.load.schema.gold import GOLD_DDL
from personal_finance_etl.backend.utils.logger import logger


class GoldLayer:
    """Full-replace layer for BI-ready presentation tables."""

    def __init__(self, db_manager: DuckDBManager):
        self.db_manager = db_manager

    def _write(self, df: pl.DataFrame | pl.LazyFrame, table_name: str) -> None:
        if isinstance(df, pl.LazyFrame):
            df = df.collect()

        if df.height == 0:
            return

        self.db_manager.conn.register("temp_df", df)
        logger.debug(f"[Gold] Replacing {df.height} rows into {table_name}")
        self.db_manager.conn.execute(f"INSERT INTO {table_name} BY NAME SELECT * FROM temp_df")
        self.db_manager.conn.unregister("temp_df")

    def load(self, dfs: dict[str, pl.DataFrame]) -> None:
        """Truncates all gold.* tables and re-inserts presentation DataFrames."""

        logger.info("Loading presentation datasets into Gold layer...")

        table_mappings = {
            c.contract_id: c.physical_table for c in DATA_CONTRACT_REGISTRY if c.layer == "gold"
        }
        # Phase 1: Cleanly wipe the entire schema
        self.db_manager.conn.execute("DROP SCHEMA IF EXISTS gold CASCADE")
        self.db_manager.conn.execute("CREATE SCHEMA gold")
        self.db_manager.conn.execute(GOLD_DDL)

        # Phase 2: Insert all data
        for df_key, table_name in table_mappings.items():
            if df_key in dfs:
                self._write(dfs[df_key], table_name)

        logger.info("Gold layer load complete.")
