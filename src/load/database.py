import polars as pl
import sqlite3
import os
from datetime import datetime


def setup_sqlite_schema(db_path):
    """Deletes old DB, applies production PRAGMAs, and creates strict schemas."""
    if os.path.exists(db_path):
        os.remove(db_path)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # --- Production PRAGMAs ---
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA temp_store = MEMORY;")
        cursor.execute("PRAGMA cache_size = -20000;")
        cursor.execute("PRAGMA mmap_size = 2147483648;")

        # --- DDL: d_Income_Category ---
        # Assuming UID is the primary key based on the naming convention
        cursor.executescript("""
            -- DDL: d_Calendar
            CREATE TABLE d_Calendar (
                Date DATE PRIMARY KEY,
                Day INTEGER,
                "Day Name" TEXT,
                "Day Name Short" TEXT,
                "Day Ordinal" INTEGER,
                "Day Ordinal Name" TEXT,
                Weekday INTEGER,
                Week INTEGER,
                "Week Ordinal" INTEGER,
                "Week Ordinal Name" TEXT,
                Month INTEGER,
                "Month Name" TEXT,
                "Month Name Short" TEXT,
                Quarter INTEGER,
                "Quarter Name" TEXT,
                Year INTEGER,
                "FY Month" INTEGER,
                "FY Year" INTEGER,
                "Start of Month" DATE,
                "FY Start of Month" DATE,
                "FY Quarter" INTEGER,
                "FY Quarter Name" TEXT,
                "Month - Year" TEXT,
                "Short Month - Year" TEXT,
                "Quarter - Year" TEXT,
                "FY Quarter - Year" TEXT,
                "Financial Year" TEXT,
                "Start of Quarter" DATE,
                "FY Start of Quarter" DATE,
                "End of Month" DATE,
                "FY End of Month" DATE,
                "End of Quarter" DATE,
                "FY End of Quarter" DATE,
                "V Short Month - Year" TEXT,
                "Week - Year" TEXT,
                "Week Name" TEXT,
                "Start of Week" DATE,
                "End of Week" DATE,
                "Week Name - Year" TEXT,
                IS_WEEKEND INTEGER
            );
            
            -- DDL: d_Income_Category
            CREATE TABLE d_Income_Category (
                S_NO INTEGER,
                MODIFY_DATE INTEGER,
                UID TEXT PRIMARY KEY,
                CATEGORY_NAME TEXT,
                ORDER_SEQUENCE INTEGER,
                CATEGORY_NAME_SHORT TEXT
            );

            -- DDL: d_Income_Subcategory
            CREATE TABLE d_Income_Subcategory (
                S_NO INTEGER,
                MODIFY_DATE INTEGER,
                UID TEXT PRIMARY KEY,
                CATEGORY_NAME TEXT,
                ORDER_SEQUENCE INTEGER,
                CATEGORY_ID TEXT,
                CATEGORY_GROUPS TEXT,
                FOREIGN KEY (CATEGORY_ID) REFERENCES d_Income_Category(UID)
            );

            -- DDL: d_Expense_Category
            CREATE TABLE d_Expense_Category (
                S_NO INTEGER,
                MODIFY_DATE INTEGER,
                UID TEXT PRIMARY KEY,
                CATEGORY_NAME TEXT,
                ORDER_SEQUENCE INTEGER
            );

            -- DDL: d_Expense_Subcategory
            CREATE TABLE d_Expense_Subcategory (
                S_NO INTEGER,
                MODIFY_DATE INTEGER,
                UID TEXT PRIMARY KEY,
                CATEGORY_NAME TEXT,
                ORDER_SEQUENCE INTEGER,
                CATEGORY_ID TEXT,
                FOREIGN KEY(CATEGORY_ID) REFERENCES d_Expense_Category(UID)
            );

            -- DDL: d_Asset_Category
            CREATE TABLE d_Asset_Category (
                DEVICE_ID INTEGER,
                UID TEXT PRIMARY KEY,
                USE_TIME INTEGER,
                ASSET_GROUP TEXT,
                TYPE INTEGER,
                ORDER_SEQUENCE INTEGER
            );

            -- DDL: d_AssetSubCategory
            CREATE TABLE d_Asset_SubCategory (
                S_NO INTEGER,
                CARD_STATEMENT_DATE INTEGER,
                CARD_PAYMENT_DATE INTEGER,
                ASSET_NAME TEXT,
                ORDER_SEQUENCE INTEGER,
                ASSET_DESCRIPTION TEXT,
                NOTES INTEGER,
                TRANSFER_EXPENSE INTEGER,
                CARD_AUTOPAY INTEGER,
                ADDED_TIME INTEGER,
                UID TEXT PRIMARY KEY,
                CURRENCY_ID TEXT,
                AUTOPAY_ASSET_ID INTEGER,
                ASSET_GROUP_ID TEXT,
                FOREIGN KEY(ASSET_GROUP_ID) REFERENCES d_Asset_Category(UID)
            );

            -- DDL: d_Currency
            CREATE TABLE d_Currency (
                S_NO INTEGER,
                UID TEXT PRIMARY KEY,
                CURRENCY_NAME TEXT,
                ISO TEXT,
                MAIN_ISO TEXT,
                ORDER_SEQUENCE INTEGER,
                RATE REAL,
                SYMBOL TEXT,
                INSERT_TYPE TEXT,
                SYMBOL_POSITION TEXT,
                IS_MAIN_CURRENCY INTEGER,
                IS_SHOW INTEGER,
                MODIFY_DATE INTEGER,
                DECIMAL_POINT INTEGER
            );

            -- DDL: d_Investment_Benchmark_Master
            CREATE TABLE d_Investment_Benchmark_Master (
                ID TEXT PRIMARY KEY,
                Benchmark_Name TEXT,
                yF_Ticker TEXT,
                Currency TEXT
            );
            
            -- DDL: d_tf_InvestmentMaster
            CREATE TABLE d_tf_Investment_Master (
                ISIN TEXT PRIMARY KEY,
                INSTRUMENT_NAME TEXT,
                INSTRUMENT_HOUSE TEXT,
                INSTRUMENT_CLASS TEXT,
                INSTRUMENT_TYPE TEXT,
                INSTRUMENT_SUBTYPE TEXT,
                CATEGORY_ID TEXT,
                SECTOR TEXT,
                INDUSTRY TEXT,
                BENCHMARK_ID TEXT,
                TAX_TYPE TEXT,
                TAX_SUBTYPE TEXT,
                FOREIGN KEY(CATEGORY_ID) REFERENCES d_AssetSubCategory(UID),
                FOREIGN KEY(BENCHMARK_ID) REFERENCES d_Investment_Benchmark_Master(ID)
            );

            -- DDL: d_Tax_Rates
            CREATE TABLE d_Tax_Rates (
                FY TEXT PRIMARY KEY,
                FY_Start_Date DATE,
                FY_End_Date DATE,
                Debt_MF_Cutoff_Date DATE,
                Equity_Listed_LTCG REAL,
                Equity_Listed_STCG REAL,
                Equity_Unlisted_LTCG REAL,
                Equity_Unlisted_STCG REAL,
                Gold_LTCG REAL,
                Gold_STCG REAL,
                Debt_MF_Pre_Cutoff_LTCG REAL,
                Debt_MF_Pre_Cutoff_STCG REAL,
                Debt_MF_Post_Cutoff_LTCG REAL,
                Debt_MF_Post_Cutoff_STCG REAL,
                Other_Debt_LTCG REAL,
                Other_Debt_STCG REAL,
                Default_LTCG REAL,
                Default_STCG REAL,
                Equity_LTCG_Exemption INTEGER,
                Remarks TEXT,
                FOREIGN KEY(FY_Start_Date) REFERENCES d_Calendar(Date)
            );

            -- DDL: f_Income_Transactions
            CREATE TABLE f_Income_Transactions (
                S_NO INTEGER,
                UID TEXT PRIMARY KEY,
                ASSET_ID TEXT,
                CARDDIVIDMONTH INTEGER,
                CATEGORY_ID TEXT,
                TO_ASSET_ID TEXT,
                DESCRIPTION TEXT,
                TIMESTAMP INTEGER,
                DATE DATE,
                TIME TEXT,
                PAID TEXT,
                TRANSACTION_TYPE INTEGER,
                BASE_AMOUNT REAL,
                TRANSFER_UID TEXT,
                FEES_NOTES TEXT,
                LOCAL_AMOUNT REAL,
                MARK TEXT,
                TRANSFER_FEES TEXT,
                UPDATED_TIME INTEGER,
                CURRENCY_ID TEXT,
                AMOUNT_ACCOUNT REAL,
                EXCH_RATE REAL,
                FOREIGN KEY(CATEGORY_ID) REFERENCES d_Income_Subcategory(UID),
                FOREIGN KEY(ASSET_ID) REFERENCES d_AssetSubCategory(UID),
                FOREIGN KEY(CURRENCY_ID) REFERENCES d_Currency(UID),
                FOREIGN KEY(DATE) REFERENCES d_Calendar(Date)
            );

            CREATE TABLE f_Expense_Transactions (
                S_NO INTEGER,
                UID TEXT PRIMARY KEY,
                ASSET_ID TEXT,
                CARDDIVIDMONTH INTEGER,
                CATEGORY_ID TEXT,
                TO_ASSET_ID TEXT,
                DESCRIPTION TEXT,
                TIMESTAMP INTEGER,
                DATE DATE,
                TIME TEXT,
                PAID TEXT,
                TRANSACTION_TYPE INTEGER,
                BASE_AMOUNT REAL,
                TRANSFER_UID TEXT,
                FEES_NOTES TEXT,
                LOCAL_AMOUNT REAL,
                MARK TEXT,
                TRANSFER_FEES TEXT,
                UPDATED_TIME INTEGER,
                CURRENCY_ID TEXT,
                AMOUNT_ACCOUNT REAL,
                EXCH_RATE REAL,
                FOREIGN KEY(CATEGORY_ID) REFERENCES d_Income_Subcategory(UID),
                FOREIGN KEY(ASSET_ID) REFERENCES d_AssetSubCategory(UID),
                FOREIGN KEY(CURRENCY_ID) REFERENCES d_Currency(UID),
                FOREIGN KEY(DATE) REFERENCES d_Calendar(Date)
            );

            -- DDL: f_Transfer_Transactions
            CREATE TABLE f_Transfer_Transactions (
                S_NO INTEGER,
                UID TEXT PRIMARY KEY,
                ASSET_ID TEXT,
                CARDDIVIDMONTH INTEGER,
                CATEGORY_ID TEXT,
                TO_ASSET_ID TEXT,
                DESCRIPTION TEXT,
                TIMESTAMP INTEGER,
                DATE DATE,
                TIME TEXT,
                PAID TEXT,
                TRANSACTION_TYPE INTEGER,
                BASE_AMOUNT REAL,
                TRANSFER_UID TEXT,
                FEES_NOTES TEXT,
                LOCAL_AMOUNT REAL,
                MARK TEXT,
                TRANSFER_FEES TEXT,
                UPDATED_TIME INTEGER,
                CURRENCY_ID TEXT,
                AMOUNT_ACCOUNT REAL,
                TRANSFER_TYPE TEXT,
                EXCH_RATE REAL,
                AMOUNT_PROPER REAL,
                ADJUSTED_DATE_FOR_ANALYSIS DATE,
                FOREIGN KEY(CURRENCY_ID) REFERENCES d_Currency(UID),
                FOREIGN KEY(ASSET_ID) REFERENCES d_AssetSubCategory(UID),
                FOREIGN KEY(TO_ASSET_ID) REFERENCES d_AssetSubCategory(UID),
                FOREIGN KEY(DATE) REFERENCES d_Calendar(Date),
                FOREIGN KEY(ADJUSTED_DATE_FOR_ANALYSIS) REFERENCES d_Calendar(Date)
            );

            -- DDL: f_Opening_Balances
            CREATE TABLE f_Opening_Balances (
                Z_PK INTEGER PRIMARY KEY,
                ZUTIME INTEGER,
                ZDATE REAL,
                ZAMOUNT REAL,
                ZAMOUNTACCOUNT REAL,
                ZAMOUNTSUB REAL,
                ZCONTENT TEXT,
                ZDO_TYPE INTEGER,
                ZASSETUID TEXT,
                ZCATEGORYUID TEXT,
                ZCURRENCYUID TEXT,
                ZTOASSETUID TEXT,
                ZTXDATESTR DATE,
                ZTXUIDFEE TEXT,
                ZTXUIDTRANS TEXT,
                ZUID TEXT,
                FOREIGN KEY(ZCURRENCYUID) REFERENCES d_Currency(UID),
                FOREIGN KEY(ZASSETUID) REFERENCES d_AssetSubCategory(UID),
                FOREIGN KEY(ZTXDATESTR) REFERENCES d_Calendar(Date)
            );

            -- DDL: stg_InvestmentMarketData
            CREATE TABLE stg_Investment_Market_Data (
                Date DATE,
                ISIN TEXT,
                Quantity REAL,
                "Closing Price" REAL,
                "Buy Price" REAL,
                "Closing Value" REAL,
                "Buy Value" REAL,
                "Unit P/L" REAL,
                "Total P/L" REAL,
                FOREIGN KEY(Date) REFERENCES d_Calendar(Date),
                FOREIGN KEY(ISIN) REFERENCES d_tf_InvestmentMaster(ISIN)
            );

            -- DDL: f_tf_InvestmentPurchaseData
            CREATE TABLE f_tf_Investment_Purchase_Data (
                ISIN TEXT,
                Date DATE,
                Price REAL,
                Quantity REAL,
                Value REAL,
                CURRENCY_ID TEXT,
                FOREIGN KEY(Date) REFERENCES d_Calendar(Date),
                FOREIGN KEY(ISIN) REFERENCES d_tf_InvestmentMaster(ISIN),
                FOREIGN KEY(CURRENCY_ID) REFERENCES d_Currency(UID)
            );

            -- DDL: f_tf_InvestmentSaleData
            CREATE TABLE f_tf_Investment_Sale_Data (
                ISIN TEXT,
                Date DATE,
                Quantity REAL,
                "Sell Price" REAL,
                "Sell Value" REAL,
                "Buy Price" REAL,
                "Buy Value" REAL,
                "Unit P/L" REAL,
                "Total P/L" REAL,
                CURRENCY_ID TEXT,
                FOREIGN KEY(Date) REFERENCES d_Calendar(Date),
                FOREIGN KEY(ISIN) REFERENCES d_tf_InvestmentMaster(ISIN),
                FOREIGN KEY(CURRENCY_ID) REFERENCES d_Currency(UID)
            );

            -- DDL: f_Investment_Benchmark_Data
            CREATE TABLE f_Investment_Benchmark_Data (
                Date DATE,
                ID TEXT,
                Benchmark_Name TEXT,
                yF_Ticker TEXT,
                Currency TEXT,
                Close REAL,
                FOREIGN KEY(Date) REFERENCES d_Calendar(Date),
                FOREIGN KEY(ID) REFERENCES d_Investment_Benchmark_Master(ID)
            );

            -- DDL: f_Investment_Market_Data
            -- (Simplified schema definition for brevity, SQLite's loose typing will handle the rest)
            CREATE TABLE f_Investment_Market_Data (
                Closing_Date DATE, ISIN TEXT, BENCHMARK_ID TEXT, TAX_TYPE TEXT, 
                TAX_SUBTYPE TEXT, Buy_Date DATE, Age_Days INTEGER, LTCG_Threshold_Days INTEGER, 
                Days_To_LTCG INTEGER, Holding_Type TEXT, Quantity REAL, Buy_Price REAL, 
                Market_Price REAL, Buy_Value REAL, Close_Value REAL, "P/L" REAL, 
                "Returns_%" REAL, Lot_CAGR REAL, CAGR REAL, XIRR REAL, BM_Buy_Price REAL, 
                BM_Market_Price REAL, "Lot_BM_Returns_%" REAL, Lot_BM_CAGR REAL, BM_CAGR REAL, 
                BM_XIRR REAL, Active_Return REAL, Lot_Alpha REAL, Is_Lagging_Benchmark INTEGER, 
                Beta REAL, Tracking_Error REAL, Information_Ratio REAL, Upside_Capture REAL, 
                Downside_Capture REAL, Tax_Rate REAL, Unrealized_LTCG REAL, Unrealized_STCG REAL, 
                Unrealized_Loss REAL, LTCG_Tax_If_Sold REAL, STCG_Tax_If_Sold REAL, After_Tax_PL REAL, 
                After_Tax_Close_Value REAL, Outperformance_Probability REAL, Portfolio_XIRR REAL, 
                Portfolio_BM_XIRR REAL, Portfolio_Active_Return REAL, "Portfolio_Weight_%" REAL, 
                "Lot_Weight_%" REAL, FY TEXT, FY_Realized_LTCG REAL, FY_Realized_STCG REAL, 
                FY_Realized_Loss REAL, FY_LTCG_Remaining_Exemption INTEGER, Stepup_Eligible INTEGER, 
                Harvest_Recommendation TEXT,
                FOREIGN KEY(Closing_Date) REFERENCES d_Calendar(Date),
                FOREIGN KEY(BENCHMARK_ID) REFERENCES d_Investment_Benchmark_Master(ID),
                FOREIGN KEY(ISIN) REFERENCES d_tf_InvestmentMaster(ISIN),
                FOREIGN KEY(Buy_Date) REFERENCES d_Calendar(Date)
            );
        """)


def apply_indexes_and_optimize(db_path):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        # Asset Category Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_category ON d_Asset_Category(UID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_asset_subcategory ON d_Asset_Subcategory(UID);")

        # Expense Category Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_expense_category ON d_Expense_Category(UID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_expense_subcategory ON d_Expense_Subcategory(UID);")

        # Income Category Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_income_category ON d_Income_Category(UID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_income_subcategory ON d_Income_Subcategory(UID);")

        # Fact Table Indexes: Incomes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inc_date ON f_Income_Transactions(DATE);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inc_category ON f_Income_Transactions(CATEGORY_ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inc_currency ON f_Income_Transactions(CURRENCY_ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inc_asset ON f_Income_Transactions(ASSET_ID);")

        # Fact Table Indexes: Expenses
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_exp_date ON f_Expense_Transactions(DATE);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_exp_category ON f_Expense_Transactions(CATEGORY_ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_exp_currency ON f_Expense_Transactions(CURRENCY_ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_exp_asset ON f_Expense_Transactions(ASSET_ID);")

        # Fact Table Indexes: Transfers
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trans_date ON f_Transfer_Transactions(DATE);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trans_adj_date ON f_Transfer_Transactions(ADJUSTED_DATE_FOR_ANALYSIS);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trans_currency ON f_Transfer_Transactions(CURRENCY_ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_trans_asset ON f_Transfer_Transactions(ASSET_ID);")

        # Fact Table Indexes: Opening Balances
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_opbal_uid ON f_Opening_Balances(ZUID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_opbal_asset ON f_Opening_Balances(ZASSETUID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_opbal_currency ON f_Opening_Balances(ZCURRENCYUID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_opbal_category ON f_Opening_Balances(ZCATEGORYUID);")

        # Final Investment Benchmark & Market Data Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inv_bm_id ON f_Investment_Benchmark_Data(ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inv_bm_date ON f_Investment_Benchmark_Data(Date);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inv_mkt_isin ON f_Investment_Market_Data(ISIN);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inv_mkt_date ON f_Investment_Market_Data(Closing_Date);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_inv_buy_date ON f_Investment_Market_Data(Buy_Date);")

        # Investment Master Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_invmst_cat ON d_tf_Investment_Master(CATEGORY_ID);")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_invmst_class ON d_tf_Investment_Master(INSTRUMENT_CLASS);")

        cursor.execute("PRAGMA optimize;")


def generate_target_db_path(base_path):
    now = datetime.now()
    if now.month >= 4:
        fy_str = f"{now.year}-{str(now.year + 1)[-2:]}"
    else:
        fy_str = f"{now.year - 1}-{str(now.year)[-2:]}"

    month_year_str = now.strftime("%m-%Y")
    timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    file_name = f"Personal_Finance_DB_{timestamp_str}.db"

    full_dir_path = os.path.join(base_path, fy_str, month_year_str)
    os.makedirs(full_dir_path, exist_ok=True)

    return os.path.join(full_dir_path, file_name)


def batch_write_database(df, table_name, db_path, chunk_size=50000):
    """Writes a DataFrame to SQLite using the ultra-fast ADBC driver."""
    if df.height == 0:
        return

    # ADBC expects standard DB URIs
    db_uri = f"sqlite:///{db_path}"

    # ADBC writes native Arrow memory directly to SQLite
    df.write_database(
        table_name=table_name,
        connection=db_uri,
        if_table_exists="append",
        engine="adbc"
    )
