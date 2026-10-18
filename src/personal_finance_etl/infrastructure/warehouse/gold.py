"""Full-replace presentation layer loading and table management in the warehouse Gold layer.

Owns
----
- Full-replace publishing of presentation DataFrames into gold.* DuckDB tables.
- Presentation schema recreation and publication in forward topological order.
- LazyFrame execution plan logging and row insertion via DuckDB BY NAME.

Does not own
-------------
- Presentation engine calculations (owned by domain and application services).
- Silver analytical layer publishing (owned by infrastructure.warehouse.silver).
- DuckDB connection lifecycle (owned by infrastructure.warehouse.connection).
"""

from __future__ import annotations

import logging

import polars as pl

from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.registry import DATA_CONTRACT_REGISTRY
from personal_finance_etl.infrastructure.warehouse.schema.gold import GOLD_DDL

logger = logging.getLogger("personal_finance_etl.warehouse.gold")


class GoldLayer:
    """Full-replace layer for BI-ready presentation tables.

    Parameters
    ----------
    db_manager : DuckDBManager
        Active DuckDB connection manager.
    """

    def __init__(self, db_manager: DuckDBManager) -> None:
        self.db_manager = db_manager

    def _write(self, df: pl.DataFrame | pl.LazyFrame, table_name: str) -> int:
        """Write DataFrame or LazyFrame into a Gold presentation table."""
        if isinstance(df, pl.LazyFrame):
            compact_plan = df.explain().replace("\n", " | ")
            logger.debug(
                "[DAG:OPTIMIZER] Physical Plan for Gold '%s': %s", table_name, compact_plan
            )
            # Materialization Boundary: PUBLICATION_BOUNDARY
            # Terminal execution of lazy presentation graph for DuckDB Gold table insertion
            df = df.collect()

        if df.height == 0:
            return 0

        self.db_manager.conn.register("temp_df", df)
        self.db_manager.conn.execute(
            f"INSERT INTO {table_name} BY NAME SELECT * FROM temp_df"  # nosec B608
        )
        self.db_manager.conn.unregister("temp_df")
        return df.height

    def load(self, dfs: dict[str, pl.DataFrame]) -> None:
        """Truncate all gold.* tables and re-insert presentation DataFrames."""
        logger.info("Loading presentation datasets into Gold layer...")

        contracts = sorted(
            (c for c in DATA_CONTRACT_REGISTRY if c.layer == "gold"),
            key=lambda c: c.publication_order,
        )
        self.db_manager.conn.execute("DROP SCHEMA IF EXISTS gold CASCADE")
        self.db_manager.conn.execute("CREATE SCHEMA gold")
        self.db_manager.conn.execute(GOLD_DDL)

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
            "[GOLD] Rebuilt %d presentation tables (%s total rows).",
            tables_built,
            f"{total_rows:,}",
        )
