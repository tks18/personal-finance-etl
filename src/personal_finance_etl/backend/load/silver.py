import polars as pl

from personal_finance_etl.backend.load.database import DuckDBManager
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

        self.db_manager.conn.register("temp_df", df)
        logger.debug(f"[Silver] Replacing {df.height} rows into {table_name}")
        self.db_manager.conn.execute(f"INSERT INTO {table_name} BY NAME SELECT * FROM temp_df")
        self.db_manager.conn.unregister("temp_df")

    def load(self, dfs: dict[str, pl.DataFrame]) -> None:
        """Truncates all silver.* tables and re-inserts via db_manager.conn."""
        logger.info("Loading transformed datasets into Silver layer...")
        table_mappings = {
            "df_d_calendar": "silver.d_Calendar",
            "df_d_income_category": "silver.d_Income_Category",
            "df_d_income_subcategory": "silver.d_Income_Subcategory",
            "df_d_expense_category": "silver.d_Expense_Category",
            "df_d_expense_subcategory": "silver.d_Expense_Subcategory",
            "df_d_asset_category": "silver.d_Asset_Category",
            "df_d_asset_subcategory": "silver.d_Asset_SubCategory",
            "df_d_currency": "silver.d_Currency",
            "df_d_benchmark_master": "silver.d_Investment_Benchmark_Master",
            "df_d_tf_investment_master": "silver.d_tf_Investment_Master",
            "df_d_macro_parameters": "silver.d_Macro_Parameters",
            "df_f_income_transactions": "silver.f_Income_Transactions",
            "df_f_expense_transactions": "silver.f_Expense_Transactions",
            "df_f_transfer_transactions": "silver.f_Transfer_Transactions",
            "df_f_opening_balances": "silver.f_Opening_Balances",
            "df_stg_investment_market_data": "silver.stg_Investment_Market_Data",
            "df_f_tf_inv_purchase": "silver.f_tf_Investment_Purchase_Data",
            "df_f_tf_inv_sale": "silver.f_tf_Investment_Sale_Data",
            "df_f_investment_benchmark_data": "silver.f_Investment_Benchmark_Data",
            "df_f_tf_investment_analytics_lot": "silver.f_tf_Investment_Analytics_Lot",
            "df_f_tf_investment_analytics_isin": "silver.f_tf_Investment_Analytics_ISIN",
            "df_f_tf_investment_analytics_subtype": "silver.f_tf_Investment_Analytics_Subtype",
            "df_f_tf_investment_analytics_class": "silver.f_tf_Investment_Analytics_Class",
            "df_f_tf_investment_analytics_portfolio": "silver.f_tf_Investment_Analytics_Portfolio",
        }
        # Phase 1: Cleanly wipe the entire schema and its foreign keys
        self.db_manager.conn.execute("DROP SCHEMA IF EXISTS silver CASCADE")
        self.db_manager.conn.execute("CREATE SCHEMA silver")
        self.db_manager.conn.execute(SILVER_DDL)

        # Phase 2: Insert all data in forward topological order (Dimensions -> Facts)
        for df_key, table_name in table_mappings.items():
            if df_key in dfs:
                self._write(dfs[df_key], table_name)

        logger.info("Silver layer load complete.")
