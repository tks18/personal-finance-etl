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
    FOREIGN KEY(CATEGORY_ID) REFERENCES d_AssetSubCategory(UID),
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

-- DDL: stg_InvestmentMarketData
CREATE TABLE stg_Investment_Market_Data (
    __file_name__ TEXT,
    __folder_path__ TEXT,
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
    __file_name__ TEXT,
    __folder_path__ TEXT,
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
    __file_name__ TEXT,
    __folder_path__ TEXT,
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
CREATE TABLE f_Investment_Market_Data (
    Closing_Date DATE, 
    ISIN TEXT, 
    BENCHMARK_ID TEXT, 
    TAX_TYPE TEXT, 
    TAX_SUBTYPE TEXT, 
    Buy_Date DATE, 
    Age_Days INTEGER, 
    LTCG_Threshold_Days INTEGER, 
    Days_To_LTCG INTEGER, 
    Holding_Type TEXT, 
    Quantity REAL, 
    Buy_Price REAL, 
    Market_Price REAL, 
    Buy_Value REAL, 
    Close_Value REAL, 
    "P/L" REAL, 
    "Returns_%" REAL, 
    "Lot_Weight_%" REAL, 
    Lot_CAGR REAL, 
    CAGR REAL, 
    XIRR REAL, 
    BM_Buy_Price REAL, 
    BM_Market_Price REAL, 
    "Lot_BM_Returns_%" REAL, 
    Lot_BM_CAGR REAL, 
    BM_CAGR REAL, 
    BM_XIRR REAL, 
    Active_Return REAL, 
    Lot_Alpha REAL, 
    Is_Lagging_Benchmark INTEGER, 
    Beta REAL, 
    Tracking_Error REAL, 
    Information_Ratio REAL, 
    Upside_Capture REAL, 
    Downside_Capture REAL, 
    Tax_Rate REAL, 
    Unrealized_LTCG REAL, 
    Unrealized_STCG REAL, 
    Unrealized_Loss REAL, 
    LTCG_Tax_If_Sold REAL, 
    STCG_Tax_If_Sold REAL, 
    After_Tax_PL REAL, 
    After_Tax_Close_Value REAL, 
    Outperformance_Probability REAL, 
    Portfolio_XIRR REAL, 
    Portfolio_BM_XIRR REAL, 
    Portfolio_Active_Return REAL, 
    "Portfolio_Weight_%" REAL, 
    Portfolio_Sharpe_Ratio REAL, 
    Portfolio_Sortino_Ratio REAL, 
    Portfolio_Max_Drawdown REAL,
    FY TEXT, 
    FY_Realized_LTCG REAL, 
    FY_Realized_STCG REAL, 
    FY_Realized_Loss REAL, 
    FY_LTCG_Remaining_Exemption INTEGER, 
    Stepup_Eligible INTEGER, 
    Harvest_Recommendation TEXT, 
    FOREIGN KEY(Closing_Date) REFERENCES d_Calendar(Date),
    FOREIGN KEY(BENCHMARK_ID) REFERENCES d_Investment_Benchmark_Master(ID),
    FOREIGN KEY(ISIN) REFERENCES d_tf_InvestmentMaster(ISIN),
    FOREIGN KEY(Buy_Date) REFERENCES d_Calendar(Date)
);
"""
