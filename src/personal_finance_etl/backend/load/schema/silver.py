SILVER_DDL = """
CREATE TABLE IF NOT EXISTS silver.d_Calendar (
    -- Base Date
    Date DATE PRIMARY KEY,
    
    -- Day Properties
    Day BIGINT,
    Day_Name TEXT,
    Day_Name_Short TEXT,
    Day_Ordinal BIGINT,
    Day_Ordinal_Name TEXT,
    Weekday BIGINT,
    IS_WEEKEND BIGINT,
    
    -- Week Properties
    Week BIGINT,
    Week_Ordinal BIGINT,
    Week_Ordinal_Name TEXT,
    Week_Name TEXT,
    Week_Year TEXT,
    Week_Name_Year TEXT,
    Start_of_Week DATE,
    End_of_Week DATE,
    
    -- Month Properties
    Month BIGINT,
    Month_Name TEXT,
    Month_Name_Short TEXT,
    Month_Year TEXT,
    Short_Month_Year TEXT,
    V_Short_Month_Year TEXT,
    Month_Ordinal BIGINT,
    Start_of_Month DATE,
    End_of_Month DATE,
    Days_in_Month BIGINT,
    Month_Progress_Pct DOUBLE,
    
    -- Quarter Properties
    Quarter BIGINT,
    Quarter_Name TEXT,
    Quarter_Year TEXT,
    Quarter_Ordinal BIGINT,
    Start_of_Quarter DATE,
    End_of_Quarter DATE,
    
    -- Year Properties
    Year BIGINT,
    Days_in_Year BIGINT,
    Year_Progress_Pct DOUBLE,
    
    -- Financial Year Properties
    Financial_Year TEXT,
    FY_Year BIGINT,
    FY_Month BIGINT,
    FY_Month_Ordinal BIGINT,
    FY_Quarter BIGINT,
    FY_Quarter_Name TEXT,
    FY_Quarter_Year TEXT,
    FY_Quarter_Ordinal BIGINT,
    FY_Start_of_Month DATE,
    FY_End_of_Month DATE,
    FY_Start_of_Quarter DATE,
    FY_End_of_Quarter DATE,
    
    -- Boolean / Snapshot Flags
    Is_Last_Day_Of_Month BOOLEAN,
    Is_Last_Day_Of_Quarter BOOLEAN,
    Is_Last_Day_Of_Year BOOLEAN,
    Is_Last_Day_Of_FY BOOLEAN,
    Is_Quarter_End_Month BOOLEAN,
    Is_Tax_Harvesting_Season BOOLEAN,
    Is_Current_Month BOOLEAN,
    Is_Previous_Month BOOLEAN,
    Is_Current_Quarter BOOLEAN,
    Is_Previous_Quarter BOOLEAN,
    Is_Current_Year BOOLEAN,
    Is_Previous_Year BOOLEAN,
    Is_Current_FY BOOLEAN,
    Is_YTD BOOLEAN,
    Is_FY_YTD BOOLEAN,
    Is_Future_Date BOOLEAN
);

CREATE TABLE IF NOT EXISTS silver.d_Income_Category (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    MODIFY_DATE BIGINT,
    UID TEXT PRIMARY KEY,
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE BIGINT,
    CATEGORY_NAME_SHORT TEXT
);

CREATE TABLE IF NOT EXISTS silver.d_Income_Subcategory (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    MODIFY_DATE BIGINT,
    UID TEXT PRIMARY KEY,
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE BIGINT,
    CATEGORY_ID TEXT,
    CATEGORY_GROUPS TEXT,
    Is_Active_Income BOOLEAN,
    Is_Passive_Income BOOLEAN,
    Is_Dividend_Income BOOLEAN,
    Is_Interest_Income BOOLEAN,
    FOREIGN KEY (CATEGORY_ID) REFERENCES silver.d_Income_Category(UID)
);

CREATE TABLE IF NOT EXISTS silver.d_Expense_Category (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    MODIFY_DATE BIGINT,
    UID TEXT PRIMARY KEY,
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE BIGINT
);

CREATE TABLE IF NOT EXISTS silver.d_Expense_Subcategory (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    MODIFY_DATE BIGINT,
    UID TEXT PRIMARY KEY,
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE BIGINT,
    CATEGORY_ID TEXT,
    Is_Core_Expense BOOLEAN,
    FOREIGN KEY(CATEGORY_ID) REFERENCES silver.d_Expense_Category(UID)
);

CREATE TABLE IF NOT EXISTS silver.d_Asset_Category (
    __file_name__ TEXT, __folder_path__ TEXT, DEVICE_ID BIGINT,
    UID TEXT PRIMARY KEY,
    USE_TIME BIGINT,
    ASSET_GROUP TEXT,
    TYPE BIGINT,
    ORDER_SEQUENCE BIGINT
);

CREATE TABLE IF NOT EXISTS silver.d_Asset_Subcategory (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    CARD_STATEMENT_DATE BIGINT,
    CARD_PAYMENT_DATE BIGINT,
    ASSET_NAME TEXT,
    ORDER_SEQUENCE BIGINT,
    ASSET_DESCRIPTION TEXT,
    NOTES TEXT,
    TRANSFER_EXPENSE BIGINT,
    CARD_AUTOPAY BIGINT,
    ADDED_TIME BIGINT,
    UID TEXT PRIMARY KEY,
    CURRENCY_ID TEXT,
    AUTOPAY_ASSET_ID TEXT,
    ASSET_GROUP_ID TEXT,
    Is_Liquid BOOLEAN,
    Is_Illiquid BOOLEAN,
    FOREIGN KEY(ASSET_GROUP_ID) REFERENCES silver.d_Asset_Category(UID)
);

CREATE TABLE IF NOT EXISTS silver.d_Currency (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    UID TEXT PRIMARY KEY,
    CURRENCY_NAME TEXT,
    ISO TEXT,
    MAIN_ISO TEXT,
    ORDER_SEQUENCE BIGINT,
    RATE DOUBLE,
    SYMBOL TEXT,
    INSERT_TYPE TEXT,
    SYMBOL_POSITION TEXT,
    IS_MAIN_CURRENCY BIGINT,
    IS_SHOW BIGINT,
    MODIFY_DATE BIGINT,
    DECIMAL_POINT BIGINT
);

CREATE TABLE IF NOT EXISTS silver.f_Income_Transactions (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    UID TEXT PRIMARY KEY,
    ASSET_ID TEXT NOT NULL,
    CARDDIVIDMONTH BIGINT,
    CATEGORY_ID TEXT NOT NULL,
    TO_ASSET_ID TEXT,
    DESCRIPTION TEXT,
    TIMESTAMP BIGINT,
    DATE DATE NOT NULL,
    TIME TEXT,
    PAID TEXT,
    TRANSACTION_TYPE BIGINT,
    BASE_AMOUNT DOUBLE,
    TRANSFER_UID TEXT,
    FEES_NOTES TEXT,
    LOCAL_AMOUNT DOUBLE,
    MARK TEXT,
    TRANSFER_FEES TEXT,
    UPDATED_TIME BIGINT,
    CURRENCY_ID TEXT,
    AMOUNT_ACCOUNT DOUBLE,
    EXCH_RATE DOUBLE,
    Is_Active_Income BOOLEAN,
    Is_Dividend_Income BOOLEAN,
    Is_Interest_Income BOOLEAN,
    FOREIGN KEY(CATEGORY_ID) REFERENCES silver.d_Income_Subcategory(UID),
    FOREIGN KEY(ASSET_ID) REFERENCES silver.d_Asset_Subcategory(UID),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID),
    FOREIGN KEY(DATE) REFERENCES silver.d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.f_Expense_Transactions (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    UID TEXT PRIMARY KEY,
    ASSET_ID TEXT NOT NULL,
    CARDDIVIDMONTH BIGINT,
    CATEGORY_ID TEXT NOT NULL,
    TO_ASSET_ID TEXT,
    DESCRIPTION TEXT,
    TIMESTAMP BIGINT,
    DATE DATE NOT NULL,
    TIME TEXT,
    PAID TEXT,
    TRANSACTION_TYPE BIGINT,
    BASE_AMOUNT DOUBLE,
    TRANSFER_UID TEXT,
    FEES_NOTES TEXT,
    LOCAL_AMOUNT DOUBLE,
    MARK TEXT,
    TRANSFER_FEES TEXT,
    UPDATED_TIME BIGINT,
    CURRENCY_ID TEXT,
    AMOUNT_ACCOUNT DOUBLE,
    EXCH_RATE DOUBLE,
    Is_Core_Expense BOOLEAN,
    FOREIGN KEY(CATEGORY_ID) REFERENCES silver.d_Expense_Subcategory(UID),
    FOREIGN KEY(ASSET_ID) REFERENCES silver.d_Asset_Subcategory(UID),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID),
    FOREIGN KEY(DATE) REFERENCES silver.d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.f_Transfer_Transactions (
    __file_name__ TEXT, __folder_path__ TEXT, S_NO BIGINT,
    UID TEXT PRIMARY KEY,
    ASSET_ID TEXT NOT NULL,
    CARDDIVIDMONTH BIGINT,
    CATEGORY_ID TEXT,
    TO_ASSET_ID TEXT,
    DESCRIPTION TEXT,
    TIMESTAMP BIGINT,
    DATE DATE NOT NULL,
    TIME TEXT,
    PAID TEXT,
    TRANSACTION_TYPE BIGINT,
    BASE_AMOUNT DOUBLE,
    TRANSFER_UID TEXT,
    FEES_NOTES TEXT,
    LOCAL_AMOUNT DOUBLE,
    MARK TEXT,
    TRANSFER_FEES TEXT,
    UPDATED_TIME BIGINT,
    CURRENCY_ID TEXT,
    AMOUNT_ACCOUNT DOUBLE,
    TRANSFER_TYPE TEXT,
    EXCH_RATE DOUBLE,
    AMOUNT_PROPER DOUBLE,
    ADJUSTED_DATE_FOR_ANALYSIS DATE,
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID),
    FOREIGN KEY(ASSET_ID) REFERENCES silver.d_Asset_Subcategory(UID),
    FOREIGN KEY(TO_ASSET_ID) REFERENCES silver.d_Asset_Subcategory(UID),
    FOREIGN KEY(DATE) REFERENCES silver.d_Calendar(Date),
    FOREIGN KEY(ADJUSTED_DATE_FOR_ANALYSIS) REFERENCES silver.d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.f_Opening_Balances (
    __file_name__ TEXT, __folder_path__ TEXT, Z_PK BIGINT PRIMARY KEY,
    ZUTIME BIGINT,
    ZDATE DOUBLE,
    ZAMOUNT DOUBLE,
    ZAMOUNTACCOUNT DOUBLE,
    ZAMOUNTSUB DOUBLE,
    ZCONTENT TEXT,
    ZDO_TYPE BIGINT,
    ZASSETUID TEXT,
    ZCATEGORYUID TEXT,
    ZCURRENCYUID TEXT,
    ZTOASSETUID TEXT,
    ZTXDATESTR DATE,
    ZTXUIDFEE TEXT,
    ZTXUIDTRANS TEXT,
    ZUID TEXT,
    FOREIGN KEY(ZCURRENCYUID) REFERENCES silver.d_Currency(UID),
    FOREIGN KEY(ZASSETUID) REFERENCES silver.d_Asset_Subcategory(UID),
    FOREIGN KEY(ZTXDATESTR) REFERENCES silver.d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.d_Investment_Benchmark_Master (
    __file_name__ TEXT,
    __folder_path__ TEXT,
    ID TEXT PRIMARY KEY,
    Benchmark_Name TEXT,
    yF_Ticker TEXT,
    Currency TEXT
);

CREATE TABLE IF NOT EXISTS silver.d_Investment_Master (
    ISIN TEXT PRIMARY KEY,
    INSTRUMENT_NAME TEXT,
    INSTRUMENT_HOUSE TEXT,
    INSTRUMENT_CLASS TEXT NOT NULL,
    INSTRUMENT_TYPE TEXT,
    INSTRUMENT_SUBTYPE TEXT,
    CATEGORY_ID TEXT,
    SECTOR TEXT,
    INDUSTRY TEXT,
    BENCHMARK_ID TEXT,
    TAX_TYPE TEXT NOT NULL,
    TAX_SUBTYPE TEXT,
    FOREIGN KEY(CATEGORY_ID) REFERENCES silver.d_Asset_Subcategory(UID),
    FOREIGN KEY(BENCHMARK_ID) REFERENCES silver.d_Investment_Benchmark_Master(ID)
);

CREATE TABLE IF NOT EXISTS silver.d_Macro_Parameters (
    -- Identifier
    FY TEXT PRIMARY KEY,
    -- Period
    FY_Start_Date DATE,
    FY_End_Date DATE,
    Debt_MF_Cutoff_Date DATE,
    -- Market Rate
    Inflation_Rate DOUBLE,
    Risk_Free_Rate DOUBLE,
    -- Equity Rates
    Equity_Listed_LTCG DOUBLE,
    Equity_Listed_STCG DOUBLE,
    Equity_Unlisted_LTCG DOUBLE,
    Equity_Unlisted_STCG DOUBLE,
    Equity_LTCG_Exemption BIGINT,
    -- Gold Rates
    Gold_LTCG DOUBLE,
    Gold_STCG DOUBLE,
    -- Debt MF Rates
    Debt_MF_Pre_Cutoff_LTCG DOUBLE,
    Debt_MF_Pre_Cutoff_STCG DOUBLE,
    Debt_MF_Post_Cutoff_LTCG DOUBLE,
    Debt_MF_Post_Cutoff_STCG DOUBLE,
    -- Other Debt
    Other_Debt_LTCG DOUBLE,
    Other_Debt_STCG DOUBLE,
    -- Default (fallback)
    Default_LTCG DOUBLE,
    Default_STCG DOUBLE,
    -- Income Tax
    Dividend_Income_Tax_Rate DOUBLE,
    -- Meta
    Remarks TEXT,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    FOREIGN KEY(FY_Start_Date) REFERENCES silver.d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.f_Investment_Market_Data (
    __file_name__ TEXT,
    __folder_path__ TEXT,
    Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    Quantity DOUBLE,
    Closing_Price DOUBLE,
    Buy_Price DOUBLE,
    Closing_Value DOUBLE,
    Buy_Value DOUBLE,
    Unit_PnL DOUBLE,
    Total_PnL DOUBLE,
    FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES silver.d_Investment_Master(ISIN)
);

CREATE TABLE IF NOT EXISTS silver.f_Investment_Purchase_Data (
    __file_name__ TEXT,
    __folder_path__ TEXT,
    ISIN TEXT NOT NULL,
    Date DATE NOT NULL,
    Price DOUBLE,
    Quantity DOUBLE,
    Value DOUBLE,
    CURRENCY_ID TEXT,
    FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES silver.d_Investment_Master(ISIN),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)
);

CREATE TABLE IF NOT EXISTS silver.f_Investment_Sale_Data (
    __file_name__ TEXT,
    __folder_path__ TEXT,
    ISIN TEXT NOT NULL,
    Date DATE NOT NULL,
    Quantity DOUBLE,
    Sell_Price DOUBLE,
    Sell_Value DOUBLE,
    Buy_Price DOUBLE,
    Buy_Value DOUBLE,
    Unit_PnL DOUBLE,
    Total_PnL DOUBLE,
    CURRENCY_ID TEXT,
    FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES silver.d_Investment_Master(ISIN),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)
);

CREATE TABLE IF NOT EXISTS silver.f_Investment_Benchmark_Data (
    Date DATE,
    ID TEXT,
    Benchmark_Name TEXT,
    yF_Ticker TEXT,
    Currency TEXT,
    Close DOUBLE,
    FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date),
    FOREIGN KEY(ID) REFERENCES silver.d_Investment_Benchmark_Master(ID)
);

CREATE TABLE IF NOT EXISTS silver.f_Investment_Analytics_Lot (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    Buy_Date DATE,
    -- Classification
    BENCHMARK_ID TEXT,
    TAX_TYPE TEXT,
    TAX_SUBTYPE TEXT,
    -- Holding Period
    Age_Days BIGINT,
    LTCG_Threshold_Days BIGINT,
    Days_To_LTCG BIGINT,
    Holding_Type TEXT,
    Dietz_Day_Weight DOUBLE,
    -- Position
    Quantity DOUBLE,
    Buy_Price DOUBLE,
    Market_Price DOUBLE,
    Buy_Value DOUBLE,
    Close_Value DOUBLE,
    -- Absolute Returns
    "P/L" DOUBLE,
    Absolute_Return DOUBLE,
    Lot_Weight DOUBLE,
    Lot_CAGR DOUBLE,
    -- Time-Range Returns
    Return_1D DOUBLE,
    Return_1W DOUBLE,
    Return_1M DOUBLE,
    Return_3M DOUBLE,
    Return_6M DOUBLE,
    Return_12M DOUBLE,
    Return_3Y DOUBLE,
    Return_5Y DOUBLE,
    Return_YTD DOUBLE,
    Return_FY_YTD DOUBLE,
    -- Time-Range Alphas
    Alpha_1D DOUBLE,
    Alpha_1W DOUBLE,
    Alpha_1M DOUBLE,
    Alpha_3M DOUBLE,
    Alpha_6M DOUBLE,
    Alpha_12M DOUBLE,
    Alpha_3Y DOUBLE,
    Alpha_5Y DOUBLE,
    Alpha_YTD DOUBLE,
    Alpha_FY_YTD DOUBLE,
    -- Drawdown Metadata
    Peak_Date DATE,
    Drawdown_Duration BIGINT,
    Underwater_Days BIGINT,
    -- Returns
    CAGR DOUBLE,
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparison
    BM_Buy_Price DOUBLE,
    BM_Market_Price DOUBLE,
    Lot_BM_Return DOUBLE,
    Lot_BM_CAGR DOUBLE,
    BM_CAGR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    Lot_Alpha DOUBLE,
    Is_Lagging_Benchmark BIGINT,
    -- Risk Metrics
    Beta DOUBLE,
    Tracking_Error DOUBLE,
    Information_Ratio DOUBLE,
    Upside_Capture DOUBLE,
    Downside_Capture DOUBLE,
    -- Per-ISIN Risk-Adjusted Ratios
    Sharpe_Ratio DOUBLE,
    Sortino_Ratio DOUBLE,
    Calmar_Ratio DOUBLE,
    Max_Drawdown DOUBLE,
    Historical_Max_DD DOUBLE,
    -- Benchmark Equivalents
    BM_Sharpe_Ratio DOUBLE,
    BM_Sortino_Ratio DOUBLE,
    BM_Calmar_Ratio DOUBLE,
    BM_Max_Drawdown DOUBLE,
    Historical_BM_Max_DD DOUBLE,
    -- Comparison Alphas (instrument minus benchmark)
    Sharpe_Alpha DOUBLE,
    Sortino_Alpha DOUBLE,
    Calmar_Alpha DOUBLE,
    -- Tax Exposure
    Tax_Rate DOUBLE,
    Unrealized_LTCG DOUBLE,
    Unrealized_STCG DOUBLE,
    Unrealized_Gain DOUBLE,
    Unrealized_LTCL DOUBLE,
    Unrealized_STCL DOUBLE,
    Unrealized_Loss DOUBLE,
    LTCG_Tax_If_Sold DOUBLE,
    STCG_Tax_If_Sold DOUBLE,
    After_Tax_PL DOUBLE,
    After_Tax_Close_Value DOUBLE,
    -- Portfolio Aggregates
    Portfolio_Weight DOUBLE,
    Outperformance_Probability DOUBLE,
    -- FY Tax Tracking
    FY TEXT,
    FY_Realized_LTCG DOUBLE,
    FY_Realized_STCG DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_LTCL DOUBLE,
    FY_Realized_STCL DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE,
    Equity_LTCG_Exemption BIGINT,
    -- Harvest Signals
    Stepup_Eligible BIGINT,
    Can_Harvest_Loss BOOLEAN,
    Harvest_Recommendation TEXT,
);
"""
