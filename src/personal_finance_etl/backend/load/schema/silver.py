SILVER_DDL = """
CREATE TABLE IF NOT EXISTS silver.d_Calendar (
    -- Identifiers
    Date DATE PRIMARY KEY,
    -- Descriptors/Classifications
    Day BIGINT,
    Day_Name TEXT,
    Day_Name_Short TEXT,
    Day_Ordinal BIGINT,
    Day_Ordinal_Name TEXT,
    Weekday BIGINT,
    IS_WEEKEND BIGINT,
    Week BIGINT,
    Week_Ordinal BIGINT,
    Week_Ordinal_Name TEXT,
    Week_Name TEXT,
    Week_Year TEXT,
    Week_Name_Year TEXT,
    Start_of_Week DATE,
    End_of_Week DATE,
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
    Quarter BIGINT,
    Quarter_Name TEXT,
    Quarter_Year TEXT,
    Quarter_Ordinal BIGINT,
    Start_of_Quarter DATE,
    End_of_Quarter DATE,
    Year BIGINT,
    Days_in_Year BIGINT,
    Year_Progress_Pct DOUBLE,
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
    -- Flags
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
    -- Identifiers
    UID TEXT PRIMARY KEY,
    -- Descriptors/Classifications
    CATEGORY_NAME TEXT,
    CATEGORY_NAME_SHORT TEXT,
    ORDER_SEQUENCE BIGINT,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    S_NO BIGINT,
    MODIFY_DATE BIGINT
);

CREATE TABLE IF NOT EXISTS silver.d_Income_Subcategory (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    CATEGORY_ID TEXT,
    -- Descriptors/Classifications
    CATEGORY_NAME TEXT,
    CATEGORY_GROUPS TEXT,
    ORDER_SEQUENCE BIGINT,
    Is_Active_Income BOOLEAN,
    Is_Passive_Income BOOLEAN,
    Is_Dividend_Income BOOLEAN,
    Is_Interest_Income BOOLEAN,
    Is_Non_Cash_Income BOOLEAN,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    S_NO BIGINT,
    MODIFY_DATE BIGINT,
    FOREIGN KEY (CATEGORY_ID) REFERENCES silver.d_Income_Category(UID)
);

CREATE TABLE IF NOT EXISTS silver.d_Expense_Category (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    -- Descriptors/Classifications
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE BIGINT,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    S_NO BIGINT,
    MODIFY_DATE BIGINT
);

CREATE TABLE IF NOT EXISTS silver.d_Expense_Subcategory (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    CATEGORY_ID TEXT,
    -- Descriptors/Classifications
    CATEGORY_NAME TEXT,
    ORDER_SEQUENCE BIGINT,
    Is_Core_Expense BOOLEAN,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    S_NO BIGINT,
    MODIFY_DATE BIGINT,
    FOREIGN KEY(CATEGORY_ID) REFERENCES silver.d_Expense_Category(UID)
);

CREATE TABLE IF NOT EXISTS silver.d_Asset_Category (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    -- Descriptors/Classifications
    ASSET_GROUP TEXT,
    TYPE BIGINT,
    ORDER_SEQUENCE BIGINT,
    ledger_role TEXT,
    cashflow_activity_type TEXT,
    settlement_timing TEXT,
    Is_Digital_Asset BOOLEAN,
    is_cash_pool BOOLEAN,
    is_non_cash_pnl BOOLEAN,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    DEVICE_ID BIGINT,
    USE_TIME BIGINT
);

CREATE TABLE IF NOT EXISTS silver.d_Asset_Subcategory (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    ASSET_GROUP_ID TEXT,
    CURRENCY_ID TEXT,
    AUTOPAY_ASSET_ID TEXT,
    -- Descriptors/Classifications
    ASSET_NAME TEXT,
    ASSET_DESCRIPTION TEXT,
    NOTES TEXT,
    ORDER_SEQUENCE BIGINT,
    ledger_role TEXT,
    cashflow_activity_type TEXT,
    settlement_timing TEXT,
    TRANSFER_EXPENSE BIGINT,
    CARD_AUTOPAY BIGINT,
    CARD_STATEMENT_DATE BIGINT,
    CARD_PAYMENT_DATE BIGINT,
    Is_Liquid BOOLEAN,
    Is_Illiquid BOOLEAN,
    Is_Digital_Asset BOOLEAN,
    is_cash_pool BOOLEAN,
    is_non_cash_pnl BOOLEAN,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    S_NO BIGINT,
    ADDED_TIME BIGINT,
    FOREIGN KEY(ASSET_GROUP_ID) REFERENCES silver.d_Asset_Category(UID)
);

CREATE TABLE IF NOT EXISTS silver.d_Currency (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    -- Descriptors/Classifications
    CURRENCY_NAME TEXT,
    ISO TEXT,
    MAIN_ISO TEXT,
    Target_Currency_Code TEXT,
    yF_Ticker TEXT,
    SYMBOL TEXT,
    SYMBOL_POSITION TEXT,
    ORDER_SEQUENCE BIGINT,
    RATE DOUBLE,
    DECIMAL_POINT BIGINT,
    IS_MAIN_CURRENCY BIGINT,
    IS_SHOW BIGINT,
    Is_Active BOOLEAN,
    INSERT_TYPE TEXT,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    S_NO BIGINT,
    MODIFY_DATE BIGINT
);

CREATE TABLE IF NOT EXISTS silver.f_Currency_FX_Rates (
    -- Identifiers
    Date DATE NOT NULL,
    Currency_ID TEXT NOT NULL,
    -- Descriptors/Classifications
    Currency_Code TEXT NOT NULL,
    Target_Currency_Code TEXT NOT NULL,
    yF_Ticker TEXT NOT NULL,
    -- Local/FX Values
    FX_Rate DOUBLE NOT NULL,
    FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date),
    FOREIGN KEY(Currency_ID) REFERENCES silver.d_Currency(UID)
);

CREATE TABLE IF NOT EXISTS silver.f_Income_Transactions (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    DATE DATE NOT NULL,
    ASSET_ID TEXT NOT NULL,
    CATEGORY_ID TEXT NOT NULL,
    CURRENCY_ID TEXT,
    TO_ASSET_ID TEXT,
    TRANSFER_UID TEXT,
    -- Descriptors/Classifications
    TIME TEXT,
    DESCRIPTION TEXT,
    PAID TEXT,
    TRANSACTION_TYPE BIGINT,
    FEES_NOTES TEXT,
    MARK TEXT,
    TRANSFER_FEES TEXT,
    CARDDIVIDMONTH BIGINT,
    Is_Active_Income BOOLEAN,
    Is_Dividend_Income BOOLEAN,
    Is_Interest_Income BOOLEAN,
    Is_Non_Cash_Income BOOLEAN,
    -- Position Values
    BASE_AMOUNT DOUBLE,
    AMOUNT_ACCOUNT DOUBLE,
    -- Local/FX Values
    LOCAL_AMOUNT DOUBLE,
    EXCH_RATE DOUBLE,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    S_NO BIGINT,
    TIMESTAMP BIGINT,
    UPDATED_TIME BIGINT,
    FOREIGN KEY(CATEGORY_ID) REFERENCES silver.d_Income_Subcategory(UID),
    FOREIGN KEY(ASSET_ID) REFERENCES silver.d_Asset_Subcategory(UID),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID),
    FOREIGN KEY(DATE) REFERENCES silver.d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.f_Expense_Transactions (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    DATE DATE NOT NULL,
    ASSET_ID TEXT NOT NULL,
    CATEGORY_ID TEXT NOT NULL,
    CURRENCY_ID TEXT,
    TO_ASSET_ID TEXT,
    TRANSFER_UID TEXT,
    -- Descriptors/Classifications
    TIME TEXT,
    DESCRIPTION TEXT,
    PAID TEXT,
    TRANSACTION_TYPE BIGINT,
    FEES_NOTES TEXT,
    MARK TEXT,
    TRANSFER_FEES TEXT,
    CARDDIVIDMONTH BIGINT,
    Is_Core_Expense BOOLEAN,
    -- Position Values
    BASE_AMOUNT DOUBLE,
    AMOUNT_ACCOUNT DOUBLE,
    -- Local/FX Values
    LOCAL_AMOUNT DOUBLE,
    EXCH_RATE DOUBLE,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    S_NO BIGINT,
    TIMESTAMP BIGINT,
    UPDATED_TIME BIGINT,
    FOREIGN KEY(CATEGORY_ID) REFERENCES silver.d_Expense_Subcategory(UID),
    FOREIGN KEY(ASSET_ID) REFERENCES silver.d_Asset_Subcategory(UID),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID),
    FOREIGN KEY(DATE) REFERENCES silver.d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.f_Transfer_Transactions (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    DATE DATE NOT NULL,
    ADJUSTED_DATE_FOR_ANALYSIS DATE,
    ASSET_ID TEXT NOT NULL,
    TO_ASSET_ID TEXT,
    CATEGORY_ID TEXT,
    CURRENCY_ID TEXT,
    TRANSFER_UID TEXT,
    -- Descriptors/Classifications
    TIME TEXT,
    DESCRIPTION TEXT,
    PAID TEXT,
    TRANSACTION_TYPE BIGINT,
    TRANSFER_TYPE TEXT,
    FEES_NOTES TEXT,
    MARK TEXT,
    TRANSFER_FEES TEXT,
    CARDDIVIDMONTH BIGINT,
    -- Position Values
    BASE_AMOUNT DOUBLE,
    AMOUNT_ACCOUNT DOUBLE,
    AMOUNT_PROPER DOUBLE,
    -- Local/FX Values
    LOCAL_AMOUNT DOUBLE,
    EXCH_RATE DOUBLE,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    S_NO BIGINT,
    TIMESTAMP BIGINT,
    UPDATED_TIME BIGINT,
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID),
    FOREIGN KEY(ASSET_ID) REFERENCES silver.d_Asset_Subcategory(UID),
    FOREIGN KEY(TO_ASSET_ID) REFERENCES silver.d_Asset_Subcategory(UID),
    FOREIGN KEY(DATE) REFERENCES silver.d_Calendar(Date),
    FOREIGN KEY(ADJUSTED_DATE_FOR_ANALYSIS) REFERENCES silver.d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.f_Opening_Balances (
    -- Identifiers
    Z_PK BIGINT PRIMARY KEY,
    ZTXDATESTR DATE,
    ZASSETUID TEXT,
    ZCATEGORYUID TEXT,
    ZCURRENCYUID TEXT,
    ZTOASSETUID TEXT,
    ZTXUIDFEE TEXT,
    ZTXUIDTRANS TEXT,
    ZUID TEXT,
    -- Descriptors/Classifications
    ZCONTENT TEXT,
    ZDO_TYPE BIGINT,
    -- Position Values
    ZAMOUNT DOUBLE,
    ZAMOUNTACCOUNT DOUBLE,
    ZAMOUNTSUB DOUBLE,
    ZDATE DOUBLE,
    ZUTIME BIGINT,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    FOREIGN KEY(ZCURRENCYUID) REFERENCES silver.d_Currency(UID),
    FOREIGN KEY(ZASSETUID) REFERENCES silver.d_Asset_Subcategory(UID),
    FOREIGN KEY(ZTXDATESTR) REFERENCES silver.d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.d_Investment_Benchmark_Master (
    -- Identifiers
    ID TEXT PRIMARY KEY,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    Benchmark_Name TEXT,
    yF_Ticker TEXT,
    __file_name__ TEXT,
    __folder_path__ TEXT
);

CREATE TABLE IF NOT EXISTS silver.d_Investment_Master (
    -- Identifiers
    ISIN TEXT PRIMARY KEY,
    CATEGORY_ID TEXT,
    BENCHMARK_ID TEXT,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    INSTRUMENT_NAME TEXT,
    INSTRUMENT_HOUSE TEXT,
    INSTRUMENT_CLASS TEXT NOT NULL,
    INSTRUMENT_TYPE TEXT,
    INSTRUMENT_SUBTYPE TEXT,
    SECTOR TEXT,
    INDUSTRY TEXT,
    COUNTRY TEXT,
    GEO TEXT,
    GEO_SUBTYPE TEXT,
    YAHOO_TICKER TEXT,
    -- Tax & Harvesting
    TAX_TYPE TEXT NOT NULL,
    TAX_SUBTYPE TEXT,
    FOREIGN KEY(CATEGORY_ID) REFERENCES silver.d_Asset_Subcategory(UID),
    FOREIGN KEY(BENCHMARK_ID) REFERENCES silver.d_Investment_Benchmark_Master(ID),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)
);

CREATE TABLE IF NOT EXISTS silver.d_Macro_Parameters (
    -- Identifiers
    FY TEXT PRIMARY KEY,
    FY_Start_Date DATE,
    FY_End_Date DATE,
    Debt_MF_Cutoff_Date DATE,
    -- Risk & Weights
    Inflation_Rate DOUBLE,
    Risk_Free_Rate DOUBLE,
    -- Tax & Harvesting
    Equity_Listed_LTCG DOUBLE,
    Equity_Listed_STCG DOUBLE,
    Equity_Unlisted_LTCG DOUBLE,
    Equity_Unlisted_STCG DOUBLE,
    Equity_LTCG_Exemption BIGINT,
    Gold_LTCG DOUBLE,
    Gold_STCG DOUBLE,
    Debt_MF_Pre_Cutoff_LTCG DOUBLE,
    Debt_MF_Pre_Cutoff_STCG DOUBLE,
    Debt_MF_Post_Cutoff_LTCG DOUBLE,
    Debt_MF_Post_Cutoff_STCG DOUBLE,
    Other_Debt_LTCG DOUBLE,
    Other_Debt_STCG DOUBLE,
    Default_LTCG DOUBLE,
    Default_STCG DOUBLE,
    Dividend_Income_Tax_Rate DOUBLE,
    -- Descriptors/Classifications
    Remarks TEXT,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    FOREIGN KEY(FY_Start_Date) REFERENCES silver.d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.f_Investment_Market_Data (
    -- Identifiers
    Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    FILE_CATEGORY TEXT,
    -- Position Values
    Quantity DOUBLE,
    Closing_Price DOUBLE,
    Buy_Price DOUBLE,
    Closing_Value DOUBLE,
    Buy_Value DOUBLE,
    -- Local/FX Values
    Closing_Price_Local DOUBLE,
    Buy_Price_Local DOUBLE,
    Closing_Value_Local DOUBLE,
    Buy_Value_Local DOUBLE,
    FX_Rate DOUBLE,
    -- Absolute Returns
    Unit_PnL DOUBLE,
    Total_PnL DOUBLE,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES silver.d_Investment_Master(ISIN),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)
);

CREATE TABLE IF NOT EXISTS silver.f_Investment_Purchase_Data (
    -- Identifiers
    Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    FILE_CATEGORY TEXT,
    -- Position Values
    Quantity DOUBLE,
    Price DOUBLE,
    Value DOUBLE,
    -- Local/FX Values
    Price_Local DOUBLE,
    Value_Local DOUBLE,
    FX_Rate DOUBLE,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES silver.d_Investment_Master(ISIN),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)
);

CREATE TABLE IF NOT EXISTS silver.f_Investment_Sale_Data (
    -- Identifiers
    Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    FILE_CATEGORY TEXT,
    -- Position Values
    Quantity DOUBLE,
    Sell_Price DOUBLE,
    Sell_Value DOUBLE,
    Buy_Price DOUBLE,
    Buy_Value DOUBLE,
    -- Local/FX Values
    Sell_Price_Local DOUBLE,
    Sell_Value_Local DOUBLE,
    Buy_Price_Local DOUBLE,
    Buy_Value_Local DOUBLE,
    FX_Rate DOUBLE,
    -- Absolute Returns
    Unit_PnL DOUBLE,
    Total_PnL DOUBLE,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES silver.d_Investment_Master(ISIN),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)
);

CREATE TABLE IF NOT EXISTS silver.f_Investment_Benchmark_Data (
    -- Identifiers
    Date DATE,
    ID TEXT,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    Benchmark_Name TEXT,
    yF_Ticker TEXT,
    -- Position Values
    Close DOUBLE,
    FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date),
    FOREIGN KEY(ID) REFERENCES silver.d_Investment_Benchmark_Master(ID)
);

CREATE TABLE IF NOT EXISTS silver.f_Investment_Analytics_Lot (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    CURRENCY_ID TEXT,
    Buy_Date DATE,
    -- Descriptors/Classifications
    BENCHMARK_ID TEXT,
    TAX_TYPE TEXT,
    TAX_SUBTYPE TEXT,
    -- Position Values
    Quantity DOUBLE,
    Buy_Price DOUBLE,
    Market_Price DOUBLE,
    Buy_Value DOUBLE,
    Close_Value DOUBLE,
    -- Local/FX Values
    Buy_Value_Local DOUBLE,
    Close_Value_Local DOUBLE,
    Blended_FX_Buy_Rate DOUBLE,
    Currency_Appreciation_Pct DOUBLE,
    -- Absolute Returns
    "P/L" DOUBLE,
    Absolute_Return DOUBLE,
    Absolute_Return_Local DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    Forex_Contribution_Pct DOUBLE,
    Asset_Return_Pct DOUBLE,
    Forex_Return_Pct DOUBLE,
    -- Performance Returns
    Lot_CAGR DOUBLE,
    Lot_CAGR_Local DOUBLE,
    CAGR DOUBLE,
    XIRR DOUBLE,
    XIRR_Local DOUBLE,
    FX_XIRR_Impact DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparisons
    BM_Buy_Price DOUBLE,
    BM_Market_Price DOUBLE,
    Lot_BM_Return DOUBLE,
    Lot_BM_CAGR DOUBLE,
    Lot_BM_CAGR_Local DOUBLE,
    BM_CAGR DOUBLE,
    BM_XIRR DOUBLE,
    BM_XIRR_Local DOUBLE,
    Active_Return DOUBLE,
    Active_Return_Local DOUBLE,
    Lot_Alpha DOUBLE,
    Is_Lagging_Benchmark BIGINT,
    -- Risk & Weights
    Max_Drawdown DOUBLE,
    Lot_Weight DOUBLE,
    Portfolio_Weight DOUBLE,
    Outperforming_Lot_Ratio DOUBLE,
    Dietz_Day_Weight DOUBLE,
    -- Tax & Harvesting
    Age_Days BIGINT,
    LTCG_Threshold_Days BIGINT,
    Days_To_LTCG BIGINT,
    Holding_Type TEXT,
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
    FY TEXT,
    FY_Realized_LTCG DOUBLE,
    FY_Realized_STCG DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_LTCL DOUBLE,
    FY_Realized_STCL DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE,
    Equity_LTCG_Exemption BIGINT,
    Stepup_Eligible BIGINT,
    Can_Harvest_Loss BOOLEAN,
    Harvest_Recommendation TEXT
);
"""
