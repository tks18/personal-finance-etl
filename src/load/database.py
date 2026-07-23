import os
import sqlite3
from datetime import datetime

import polars as pl

from src.load.schema import SQLITE_PRAGMAS, SQLITE_SCHEMA_DDL
from src.utils.interfaces import ILogger
from src.utils.logger import logger
from src.utils.models import EngineStatus


class SQLiteDatabaseManager:
    """Manages SQLite database creation, schema setup, indexing, and batch writing."""

    def __init__(self, base_path: str):
        self.base_path = base_path
        self.db_path = self._generate_target_db_path()

    def _generate_target_db_path(self) -> str:
        now = datetime.now()
        if now.month >= 4:
            fy_str = f"{now.year}-{str(now.year + 1)[-2:]}"
        else:
            fy_str = f"{now.year - 1}-{str(now.year)[-2:]}"

        month_year_str = now.strftime("%m-%Y")
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        file_name = f"Personal_Finance_DB_{timestamp_str}.db"

        full_dir_path = os.path.join(self.base_path, fy_str, month_year_str)
        os.makedirs(full_dir_path, exist_ok=True)

        return os.path.join(full_dir_path, file_name)

    def setup_schema(self) -> None:
        """Deletes old DB, applies production PRAGMAs, and creates strict schemas."""
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.executescript(SQLITE_PRAGMAS)
            cursor.executescript(SQLITE_SCHEMA_DDL)

    def apply_indexes_and_optimize(self) -> None:
        """Applies indexes to critical tables for read performance."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Asset Category Indexes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_asset_category ON d_Asset_Category(UID);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_asset_subcategory ON d_Asset_Subcategory(UID);"
            )

            # Expense Category Indexes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_expense_category ON d_Expense_Category(UID);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_expense_subcategory ON d_Expense_Subcategory(UID);"
            )

            # Income Category Indexes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_income_category ON d_Income_Category(UID);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_income_subcategory ON d_Income_Subcategory(UID);"
            )

            # Fact Table Indexes: Incomes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_inc_date ON f_Income_Transactions(DATE);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_inc_category ON f_Income_Transactions(CATEGORY_ID);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_inc_currency ON f_Income_Transactions(CURRENCY_ID);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_inc_asset ON f_Income_Transactions(ASSET_ID);"
            )

            # Fact Table Indexes: Expenses
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_exp_date ON f_Expense_Transactions(DATE);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_exp_category ON f_Expense_Transactions(CATEGORY_ID);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_exp_currency ON f_Expense_Transactions(CURRENCY_ID);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_exp_asset ON f_Expense_Transactions(ASSET_ID);"
            )

            # Fact Table Indexes: Transfers
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_trans_date ON f_Transfer_Transactions(DATE);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_trans_adj_date ON f_Transfer_Transactions(ADJUSTED_DATE_FOR_ANALYSIS);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_trans_currency ON f_Transfer_Transactions(CURRENCY_ID);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_trans_asset ON f_Transfer_Transactions(ASSET_ID);"
            )

            # Fact Table Indexes: Opening Balances
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_opbal_uid ON f_Opening_Balances(ZUID);")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_opbal_asset ON f_Opening_Balances(ZASSETUID);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_opbal_currency ON f_Opening_Balances(ZCURRENCYUID);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_opbal_category ON f_Opening_Balances(ZCATEGORYUID);"
            )

            # Final Investment Benchmark & Market Data Indexes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_inv_bm_id ON f_Investment_Benchmark_Data(ID);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_inv_bm_date ON f_Investment_Benchmark_Data(Date);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_inv_mkt_isin ON f_Investment_Market_Data(ISIN);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_inv_mkt_date ON f_Investment_Market_Data(Closing_Date);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_inv_buy_date ON f_Investment_Market_Data(Buy_Date);"
            )

            # Investment Master Indexes
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_invmst_cat ON d_tf_Investment_Master(CATEGORY_ID);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_invmst_class ON d_tf_Investment_Master(INSTRUMENT_CLASS);"
            )

            cursor.execute("PRAGMA optimize;")

    def batch_write_dataframe(
        self, df: pl.DataFrame, table_name: str, chunk_size: int = 50000
    ) -> None:
        """Writes a DataFrame to SQLite using the ultra-fast ADBC driver."""
        if df.height == 0:
            return

        db_uri = f"sqlite:///{self.db_path}"

        for i in range(0, df.height, chunk_size):
            chunk = df.slice(i, chunk_size)
            chunk.write_database(
                table_name=table_name, connection=db_uri, if_table_exists="append", engine="adbc"
            )


class SQLiteLoader:
    """Orchestrates the loading of dataframes via the SQLiteDatabaseManager."""

    def __init__(self, db_manager: SQLiteDatabaseManager, status_queue: ILogger):
        self.db_manager = db_manager
        self.status_queue = status_queue

    def run(self, dfs: dict[str, pl.DataFrame]) -> None:
        logger.info("Writing tables to SQLite in batches...")
        self.db_manager.batch_write_dataframe(dfs["df_d_calendar"], "d_Calendar")
        self.db_manager.batch_write_dataframe(dfs["df_d_income_category"], "d_Income_Category")
        self.db_manager.batch_write_dataframe(
            dfs["df_d_income_subcategory"], "d_Income_Subcategory"
        )
        self.db_manager.batch_write_dataframe(dfs["df_d_expense_category"], "d_Expense_Category")
        self.db_manager.batch_write_dataframe(
            dfs["df_d_expense_subcategory"], "d_Expense_Subcategory"
        )
        self.db_manager.batch_write_dataframe(dfs["df_d_asset_category"], "d_Asset_Category")
        self.db_manager.batch_write_dataframe(dfs["df_d_asset_subcategory"], "d_Asset_SubCategory")
        self.db_manager.batch_write_dataframe(dfs["df_d_currency"], "d_Currency")
        self.db_manager.batch_write_dataframe(
            dfs["df_d_benchmark_master"], "d_Investment_Benchmark_Master"
        )
        self.db_manager.batch_write_dataframe(
            dfs["df_d_tf_investment_master"], "d_tf_Investment_Master"
        )
        self.db_manager.batch_write_dataframe(dfs["df_d_tax_rates"], "d_Tax_Rates")
        self.db_manager.batch_write_dataframe(
            dfs["df_f_income_transactions"], "f_Income_Transactions"
        )
        self.db_manager.batch_write_dataframe(
            dfs["df_f_expense_transactions"], "f_Expense_Transactions"
        )
        self.db_manager.batch_write_dataframe(
            dfs["df_f_transfer_transactions"], "f_Transfer_Transactions"
        )
        self.db_manager.batch_write_dataframe(dfs["df_f_opening_balances"], "f_Opening_Balances")
        self.db_manager.batch_write_dataframe(
            dfs["df_stg_investment_market_data"], "stg_Investment_Market_Data"
        )
        self.db_manager.batch_write_dataframe(
            dfs["df_f_tf_inv_purchase"], "f_tf_Investment_Purchase_Data"
        )
        self.db_manager.batch_write_dataframe(dfs["df_f_tf_inv_sale"], "f_tf_Investment_Sale_Data")
        self.db_manager.batch_write_dataframe(
            dfs["df_f_investment_benchmark_data"], "f_Investment_Benchmark_Data"
        )
        self.db_manager.batch_write_dataframe(
            dfs["df_f_investment_market_data"], "f_Investment_Market_Data"
        )
        presentation_tables = {
            "df_p_tf_net_worth_monthly_summary": "p_tf_Net_Worth_Monthly_Summary",
            "df_p_tf_financial_ratios_monthly": "p_tf_Financial_Ratios_Monthly",
            "df_p_tf_category_spend_analytics": "p_tf_category_spend_analytics",
            "df_p_tf_income_streams_monthly": "p_tf_income_streams_monthly",
            "df_p_tf_fire_forecasting_monthly": "p_tf_fire_forecasting_monthly",
        }
        for df_key, table_name in presentation_tables.items():
            if df_key in dfs:
                self.db_manager.batch_write_dataframe(dfs[df_key], table_name)

        self.status_queue.put(EngineStatus(msg="", data=None, progress=0.9))
        logger.info("Applying indexes and optimizing database...")
        self.db_manager.apply_indexes_and_optimize()

        with sqlite3.connect(self.db_manager.db_path) as conn:
            conn.cursor().execute("PRAGMA optimize;")
            conn.cursor().execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.cursor().execute("PRAGMA journal_mode = DELETE;")
