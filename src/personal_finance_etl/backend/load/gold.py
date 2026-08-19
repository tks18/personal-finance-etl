import polars as pl

from personal_finance_etl.backend.load.database import DuckDBManager
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
            "df_p_tf_net_worth_monthly_summary": "gold.p_Net_Worth_Monthly_Summary",
            "df_p_tf_category_spend_analytics": "gold.p_Category_Spend_Analytics",
            "df_p_tf_income_streams_monthly": "gold.p_Income_Streams_Monthly",
            "df_p_tf_wealth_risk_analytics": "gold.p_Wealth_Risk_Analytics",
            "df_p_tf_tax_liability_forecast": "gold.p_Tax_Liability_Forecast",
            "df_p_tf_budget_forecast_monthly": "gold.p_Budget_Forecast_Monthly",
            "df_p_tf_investment_analytics": "gold.p_Portfolio_Management_Analytics",
            "df_p_tf_monthly_cashflow_summary": "gold.p_Monthly_Cashflow_Summary",
            "df_f_investment_analytics_isin": "gold.p_Investment_Analytics_ISIN",
            "df_f_investment_analytics_subtype": "gold.p_Investment_Analytics_Subtype",
            "df_f_investment_analytics_class": "gold.p_Investment_Analytics_Class",
            "df_f_investment_analytics_instrument_type": "gold.p_Investment_Analytics_Instrument_Type",
            "df_f_investment_analytics_sector": "gold.p_Investment_Analytics_Sector",
            "df_f_investment_analytics_industry": "gold.p_Investment_Analytics_Industry",
            "df_f_investment_analytics_portfolio": "gold.p_Investment_Analytics_Portfolio",
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
