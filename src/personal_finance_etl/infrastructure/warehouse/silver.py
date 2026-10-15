"""Full-replace analytical layer loading and table management in the warehouse Silver layer.

Owns
----
- Full-replace publishing of transformed DataFrames into silver.* DuckDB tables.
- Topological schema recreation and foreign key ordering.
- Dimension string normalization (converting empty strings to nulls).
- Critical data quality gatekeeping for d_Investment_Master (ISIN, TAX_TYPE null checks).

Does not own
-------------
- Upstream financial transformations (owned by domain services).
- Gold presentation layer publishing (owned by infrastructure.warehouse.gold).
- DuckDB connection lifecycle (owned by infrastructure.warehouse.connection).
"""

from __future__ import annotations

import logging

import polars as pl

from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.registry import DATA_CONTRACT_REGISTRY
from personal_finance_etl.infrastructure.warehouse.schema.silver import SILVER_DDL

logger = logging.getLogger("personal_finance_etl.warehouse.silver")


class SilverLayer:
    """Full-replace layer for engine-computed analytics and reference data.

    Parameters
    ----------
    db_manager : DuckDBManager
        Active DuckDB connection manager.
    """

    def __init__(self, db_manager: DuckDBManager) -> None:
        self.db_manager = db_manager

    def _write(self, df: pl.DataFrame | pl.LazyFrame, table_name: str) -> int:
        """Write DataFrame or LazyFrame into a Silver table with quality checks."""
        if isinstance(df, pl.LazyFrame):
            df = df.collect()

        if df.height == 0:
            return 0

        if "d_" in table_name:
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

        if table_name == "silver.d_Investment_Master":
            critical_errors: list[str] = []
            if "ISIN" in df.columns:
                missing_isin = df.filter(pl.col("ISIN").is_null())
                if missing_isin.height > 0:
                    logger.error(
                        "CRITICAL: Found %d rows with missing ISIN in d_Investment_Master.",
                        missing_isin.height,
                    )
                    logger.error(
                        "Please add the ISIN for the following instruments to your tracker:"
                    )
                    for row in missing_isin.to_dicts():
                        logger.error("-> %s", row)
                    critical_errors.append("ISIN")
            if "TAX_TYPE" in df.columns:
                missing_tax = df.filter(pl.col("TAX_TYPE").is_null())
                if missing_tax.height > 0:
                    logger.error(
                        "CRITICAL: Found %d rows with missing TAX_TYPE in d_Investment_Master.",
                        missing_tax.height,
                    )
                    logger.error(
                        "Please add the TAX_TYPE for the following instruments to your tracker:"
                    )
                    for row in missing_tax.to_dicts():
                        logger.error("-> %s", row)
                    critical_errors.append("TAX_TYPE")

            if critical_errors:
                raise ValueError(
                    f"Critical data-quality violation in d_Investment_Master: Missing {', '.join(critical_errors)}"
                )

        self.db_manager.conn.register("temp_df", df)
        logger.debug("[SILVER:DETAIL] Rebuilt %s: %d rows processed.", table_name, df.height)
        self.db_manager.conn.execute(f"INSERT INTO {table_name} BY NAME SELECT * FROM temp_df")
        self.db_manager.conn.unregister("temp_df")
        return df.height

    def load(self, dfs: dict[str, pl.DataFrame]) -> None:
        """Truncate all silver.* tables and re-insert transformed DataFrames."""
        logger.info("Loading transformed datasets into Silver layer...")

        contracts = sorted(
            (c for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"),
            key=lambda c: c.publication_order,
        )
        self.db_manager.conn.execute("DROP SCHEMA IF EXISTS silver CASCADE")
        self.db_manager.conn.execute("CREATE SCHEMA silver")
        self.db_manager.conn.execute(SILVER_DDL)

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
            "[SILVER] Rebuilt %d analytical tables (%s total rows).",
            tables_built,
            f"{total_rows:,}",
        )
