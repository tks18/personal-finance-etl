import polars as pl

from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.load.registry import DATA_CONTRACT_REGISTRY
from personal_finance_etl.backend.load.schema.gold import GOLD_DDL
from personal_finance_etl.backend.utils.logger import logger


class GoldLayer:
    """Full-replace layer for BI-ready presentation tables."""

    def __init__(self, db_manager: DuckDBManager):
        self.db_manager = db_manager

    def _write(self, df: pl.DataFrame | pl.LazyFrame, table_name: str) -> int:
        if isinstance(df, pl.LazyFrame):
            compact_plan = df.explain().replace("\n", " | ")
            logger.debug(f"[DAG:OPTIMIZER] Physical Plan for Gold '{table_name}': {compact_plan}")
            df = df.collect()

        if df.height == 0:
            return 0

        self.db_manager.conn.register("temp_df", df)
        logger.debug(f"[GOLD:DETAIL] Rebuilt {table_name}: {df.height} rows processed.")
        self.db_manager.conn.execute(f"INSERT INTO {table_name} BY NAME SELECT * FROM temp_df")
        self.db_manager.conn.unregister("temp_df")
        return df.height

    def load(self, dfs: dict[str, pl.DataFrame]) -> None:
        """Truncates all gold.* tables and re-inserts presentation DataFrames."""

        logger.info("Loading presentation datasets into Gold layer...")

        contracts = sorted(
            (c for c in DATA_CONTRACT_REGISTRY if c.layer == "gold"),
            key=lambda c: c.publication_order,
        )
        # Phase 1: Cleanly wipe the entire schema
        self.db_manager.conn.execute("DROP SCHEMA IF EXISTS gold CASCADE")
        self.db_manager.conn.execute("CREATE SCHEMA gold")
        self.db_manager.conn.execute(GOLD_DDL)

        # Phase 2: Insert all data
        total_rows = 0
        tables_built = 0

        for contract in contracts:
            if contract.contract_id in dfs:
                rows = self._write(
                    dfs[contract.contract_id],
                    contract.physical_table,
                )
                if rows > 0:
                    tables_built += 1
                    total_rows += rows

        logger.info(
            f"[GOLD] Rebuilt {tables_built} presentation tables ({total_rows:,} total rows)."
        )
