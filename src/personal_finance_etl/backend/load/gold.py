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
            "df_p_tf_net_worth_monthly_summary": "gold.Wealth_Net_Worth_Monthly",
            "df_p_tf_category_spend_analytics": "gold.Cashflow_Spend_Monthly",
            "df_p_tf_income_streams_monthly": "gold.Cashflow_Income_Monthly",
            "df_p_tf_wealth_risk_analytics": "gold.Wealth_Risk_Metrics",
            "df_p_tf_tax_liability_forecast": "gold.Forecast_Tax_Liability_Annual",
            "df_p_tf_budget_forecast_monthly": "gold.Forecast_Budget_Monthly",
            "df_p_tf_investment_analytics": "gold.Investment_Portfolio_Summary",
            "df_p_tf_monthly_cashflow_summary": "gold.Cashflow_Summary_Monthly",
            "df_f_investment_analytics_isin": "gold.Investment_By_ISIN",
            "df_f_investment_analytics_subtype": "gold.Investment_By_Subtype",
            "df_f_investment_analytics_class": "gold.Investment_By_Class",
            "df_f_investment_analytics_instrument_type": "gold.Investment_By_Instrument_Type",
            "df_f_investment_analytics_sector": "gold.Investment_By_Sector",
            "df_f_investment_analytics_industry": "gold.Investment_By_Industry",
            "df_f_investment_analytics_portfolio": "gold.Investment_By_Portfolio",
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
