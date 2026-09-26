import polars as pl

from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.load.registry import DATA_CONTRACT_REGISTRY
from personal_finance_etl.backend.load.schema.silver import SILVER_DDL
from personal_finance_etl.backend.utils.logger import logger


class SilverLayer:
    """Full-replace layer for engine-computed analytics and reference data."""

    def __init__(self, db_manager: DuckDBManager):
        self.db_manager = db_manager

    def _write(self, df: pl.DataFrame | pl.LazyFrame, table_name: str) -> int:
        if isinstance(df, pl.LazyFrame):
            df = df.collect()

        if df.height == 0:
            return 0

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
            critical_errors: list[str] = []
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
                    critical_errors.append("ISIN")
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
                    critical_errors.append("TAX_TYPE")

            if critical_errors:
                raise ValueError(
                    f"Critical data-quality violation in d_Investment_Master: Missing {', '.join(critical_errors)}"
                )

        self.db_manager.conn.register("temp_df", df)
        logger.debug(f"[SILVER:DETAIL] Rebuilt {table_name}: {df.height} rows processed.")
        self.db_manager.conn.execute(f"INSERT INTO {table_name} BY NAME SELECT * FROM temp_df")
        self.db_manager.conn.unregister("temp_df")
        return df.height

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
            f"[SILVER] Rebuilt {tables_built} analytical tables ({total_rows:,} total rows)."
        )
