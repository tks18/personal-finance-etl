INVESTMENTS_DDL = """
-- DDL: d_Investment_Benchmark_Master
CREATE TABLE d_Investment_Benchmark_Master (
    __file_name__ TEXT,
    __folder_path__ TEXT,
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
    FOREIGN KEY(CATEGORY_ID) REFERENCES d_Asset_Subcategory(UID),
    FOREIGN KEY(BENCHMARK_ID) REFERENCES d_Investment_Benchmark_Master(ID)
);

-- DDL: d_Tax_Rates
CREATE TABLE d_Tax_Rates (
    __file_name__ TEXT,
    __folder_path__ TEXT,
    FY TEXT PRIMARY KEY,
    FY_Start_Date DATE,
    FY_End_Date DATE,
    Debt_MF_Cutoff_Date DATE,
    Equity_Listed_LTCG DOUBLE,
    Equity_Listed_STCG DOUBLE,
    Equity_Unlisted_LTCG DOUBLE,
    Equity_Unlisted_STCG DOUBLE,
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
    Equity_LTCG_Exemption BIGINT,
    Remarks TEXT,
    FOREIGN KEY(FY_Start_Date) REFERENCES d_Calendar(Date)
);

-- DDL: stg_InvestmentMarketData
CREATE TABLE stg_Investment_Market_Data (
    __file_name__ TEXT,
    __folder_path__ TEXT,
    Date DATE,
    ISIN TEXT,
    Quantity DOUBLE,
    "Closing Price" DOUBLE,
    "Buy Price" DOUBLE,
    "Closing Value" DOUBLE,
    "Buy Value" DOUBLE,
    "Unit P/L" DOUBLE,
    "Total P/L" DOUBLE,
    FOREIGN KEY(Date) REFERENCES d_Calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES d_tf_Investment_Master(ISIN)
);

-- DDL: f_tf_InvestmentPurchaseData
CREATE TABLE f_tf_Investment_Purchase_Data (
    __file_name__ TEXT,
    __folder_path__ TEXT,
    ISIN TEXT,
    Date DATE,
    Price DOUBLE,
    Quantity DOUBLE,
    Value DOUBLE,
    CURRENCY_ID TEXT,
    FOREIGN KEY(Date) REFERENCES d_Calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES d_tf_Investment_Master(ISIN),
    FOREIGN KEY(CURRENCY_ID) REFERENCES d_Currency(UID)
);

-- DDL: f_tf_InvestmentSaleData
CREATE TABLE f_tf_Investment_Sale_Data (
    __file_name__ TEXT,
    __folder_path__ TEXT,
    ISIN TEXT,
    Date DATE,
    Quantity DOUBLE,
    "Sell Price" DOUBLE,
    "Sell Value" DOUBLE,
    "Buy Price" DOUBLE,
    "Buy Value" DOUBLE,
    "Unit P/L" DOUBLE,
    "Total P/L" DOUBLE,
    CURRENCY_ID TEXT,
    FOREIGN KEY(Date) REFERENCES d_Calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES d_tf_Investment_Master(ISIN),
    FOREIGN KEY(CURRENCY_ID) REFERENCES d_Currency(UID)
);

-- DDL: f_Investment_Benchmark_Data
CREATE TABLE f_Investment_Benchmark_Data (
    Date DATE,
    ID TEXT,
    Benchmark_Name TEXT,
    yF_Ticker TEXT,
    Currency TEXT,
    Close DOUBLE,
    FOREIGN KEY(Date) REFERENCES d_Calendar(Date),
    FOREIGN KEY(ID) REFERENCES d_Investment_Benchmark_Master(ID)
);

-- DDL: f_Investment_Market_Data
CREATE TABLE f_Investment_Market_Data (
    Closing_Date DATE, 
    ISIN TEXT, 
    BENCHMARK_ID TEXT, 
    TAX_TYPE TEXT, 
    TAX_SUBTYPE TEXT, 
    Buy_Date DATE, 
    Age_Days BIGINT, 
    LTCG_Threshold_Days BIGINT, 
    Days_To_LTCG BIGINT, 
    Holding_Type TEXT, 
    Quantity DOUBLE, 
    Buy_Price DOUBLE, 
    Market_Price DOUBLE, 
    Buy_Value DOUBLE, 
    Close_Value DOUBLE, 
    "P/L" DOUBLE, 
    "Returns_%" DOUBLE, 
    "Lot_Weight_%" DOUBLE, 
    Lot_CAGR DOUBLE, 
    CAGR DOUBLE, 
    XIRR DOUBLE, 
    BM_Buy_Price DOUBLE, 
    BM_Market_Price DOUBLE, 
    "Lot_BM_Returns_%" DOUBLE, 
    Lot_BM_CAGR DOUBLE, 
    BM_CAGR DOUBLE, 
    BM_XIRR DOUBLE, 
    Active_Return DOUBLE, 
    Lot_Alpha DOUBLE, 
    Is_Lagging_Benchmark BIGINT, 
    Beta DOUBLE, 
    Tracking_Error DOUBLE, 
    Information_Ratio DOUBLE, 
    Upside_Capture DOUBLE, 
    Downside_Capture DOUBLE, 
    Tax_Rate DOUBLE, 
    Unrealized_LTCG DOUBLE, 
    Unrealized_STCG DOUBLE, 
    Unrealized_Loss DOUBLE, 
    LTCG_Tax_If_Sold DOUBLE, 
    STCG_Tax_If_Sold DOUBLE, 
    After_Tax_PL DOUBLE, 
    After_Tax_Close_Value DOUBLE, 
    Outperformance_Probability DOUBLE, 
    Portfolio_XIRR DOUBLE, 
    Portfolio_BM_XIRR DOUBLE, 
    Portfolio_Active_Return DOUBLE, 
    "Portfolio_Weight_%" DOUBLE, 
    Portfolio_Sharpe_Ratio DOUBLE, 
    Portfolio_Sortino_Ratio DOUBLE, 
    Portfolio_Max_Drawdown DOUBLE,
    FY TEXT, 
    FY_Realized_LTCG DOUBLE, 
    FY_Realized_STCG DOUBLE, 
    FY_Realized_Loss DOUBLE, 
    FY_LTCG_Remaining_Exemption BIGINT, 
    Stepup_Eligible BIGINT, 
    Harvest_Recommendation TEXT, 
    FOREIGN KEY(Closing_Date) REFERENCES d_Calendar(Date),
    FOREIGN KEY(BENCHMARK_ID) REFERENCES d_Investment_Benchmark_Master(ID),
    FOREIGN KEY(ISIN) REFERENCES d_tf_Investment_Master(ISIN),
    FOREIGN KEY(Buy_Date) REFERENCES d_Calendar(Date)
);
"""
