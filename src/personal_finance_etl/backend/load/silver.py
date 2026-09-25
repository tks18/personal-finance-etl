import polars as pl

from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.load.registry import DATA_CONTRACT_REGISTRY
from personal_finance_etl.backend.load.schema.silver import SILVER_DDL
from personal_finance_etl.backend.utils.logger import logger


class SilverLayer:
    """Full-replace layer for engine-computed analytics and reference data."""

    def __init__(self, db_manager: DuckDBManager):
        self.db_manager = db_manager

    def _write(self, df: pl.DataFrame | pl.LazyFrame, table_name: str) -> None:
        if isinstance(df, pl.LazyFrame):
            df = df.collect()

        if df.height == 0:
            return

        # Clean empty strings into true nulls only for dimension tables
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
            if "ISIN" in df.columns:
                missing_isin = df.filter(pl.col("ISIN").is_null())
                if missing_isin.height > 0:
                    logger.error(
                        f"CRITICAL: Found {missing_isin.height} rows with missing ISIN in d_Investment_Master."
                    )
                    logger.error(
                        "Please add the ISIN for the following instruments to your tracker:"
                    )
                    for row in missing_isin.to_dicts():
                        logger.error(f"-> {row}")
            if "TAX_TYPE" in df.columns:
                missing_tax = df.filter(pl.col("TAX_TYPE").is_null())
                if missing_tax.height > 0:
                    logger.error(
                        f"CRITICAL: Found {missing_tax.height} rows with missing TAX_TYPE in d_Investment_Master."
                    )
                    logger.error(
                        "Please add the TAX_TYPE for the following instruments to your tracker:"
                    )
                    for row in missing_tax.to_dicts():
                        logger.error(f"-> {row}")

        self.db_manager.conn.register("temp_df", df)
        logger.debug(f"[Silver] Replacing {df.height} rows into {table_name}")
        self.db_manager.conn.execute(f"INSERT INTO {table_name} BY NAME SELECT * FROM temp_df")
        self.db_manager.conn.unregister("temp_df")

    def load(self, dfs: dict[str, pl.DataFrame]) -> None:
        """Truncates all silver.* tables and re-inserts via db_manager.conn."""

        logger.info("Loading transformed datasets into Silver layer...")

        contracts = sorted(
            (c for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"),
            key=lambda c: c.publication_order,
        )
        # Phase 1: Cleanly wipe the entire schema and its foreign keys
        self.db_manager.conn.execute("DROP SCHEMA IF EXISTS silver CASCADE")
        self.db_manager.conn.execute("CREATE SCHEMA silver")
        self.db_manager.conn.execute(SILVER_DDL)

        # Phase 2: Insert all data in forward topological order (Dimensions -> Facts)
        for contract in contracts:
          if contract.contract_id in dfs:
              self._write(
                  dfs[contract.contract_id],
                  contract.physical_table,
              )

        logger.info("Silver layer load complete.")
