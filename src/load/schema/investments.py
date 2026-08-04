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
    INSTRUMENT_CLASS TEXT NOT NULL,
    INSTRUMENT_TYPE TEXT,
    INSTRUMENT_SUBTYPE TEXT,
    CATEGORY_ID TEXT,
    SECTOR TEXT,
    INDUSTRY TEXT,
    BENCHMARK_ID TEXT,
    TAX_TYPE TEXT NOT NULL,
    TAX_SUBTYPE TEXT,
    FOREIGN KEY(CATEGORY_ID) REFERENCES d_Asset_Subcategory(UID),
    FOREIGN KEY(BENCHMARK_ID) REFERENCES d_Investment_Benchmark_Master(ID)
);

-- DDL: d_Macro_Parameters
CREATE TABLE d_Macro_Parameters (
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
    -- Meta
    Remarks TEXT,
    __file_name__ TEXT,
    __folder_path__ TEXT,
    FOREIGN KEY(FY_Start_Date) REFERENCES d_Calendar(Date)
);

-- DDL: stg_InvestmentMarketData
CREATE TABLE stg_Investment_Market_Data (
    __file_name__ TEXT,
    __folder_path__ TEXT,
    Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
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
    ISIN TEXT NOT NULL,
    Date DATE NOT NULL,
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
    ISIN TEXT NOT NULL,
    Date DATE NOT NULL,
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

-- DDL: f_tf_Investment_Analytics_Lot
CREATE TABLE f_tf_Investment_Analytics_Lot (
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
    "Returns_%" DOUBLE,
    "Lot_Weight_%" DOUBLE,
    Lot_CAGR DOUBLE,
    -- Portfolio-Level Returns
    CAGR DOUBLE,
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparison
    BM_Buy_Price DOUBLE,
    BM_Market_Price DOUBLE,
    "Lot_BM_Returns_%" DOUBLE,
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
    "Portfolio_Weight_%" DOUBLE,
    Portfolio_XIRR DOUBLE,
    Portfolio_After_Tax_XIRR DOUBLE,
    Portfolio_BM_XIRR DOUBLE,
    Portfolio_Active_Return DOUBLE,
    Portfolio_Sharpe_Ratio DOUBLE,
    Portfolio_Sortino_Ratio DOUBLE,
    Portfolio_Max_Drawdown DOUBLE,
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
    FY_LTCG_Remaining_Exemption BIGINT,
    -- Harvest Signals
    Stepup_Eligible BIGINT,
    Can_Harvest_Loss BOOLEAN,
    Harvest_Recommendation TEXT,
    FOREIGN KEY(Closing_Date) REFERENCES d_Calendar(Date),
    FOREIGN KEY(Buy_Date) REFERENCES d_Calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES d_tf_Investment_Master(ISIN),
    FOREIGN KEY(BENCHMARK_ID) REFERENCES d_Investment_Benchmark_Master(ID)
);

-- DDL: f_tf_Investment_Analytics_ISIN
CREATE TABLE f_tf_Investment_Analytics_ISIN (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Unrealized_PL DOUBLE,
    "Absolute_Return_%" DOUBLE,
    "Weight_%" DOUBLE,
    -- Returns
    CAGR DOUBLE,
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_CAGR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    Is_Lagging_Benchmark BIGINT,
    -- Risk
    Beta DOUBLE,
    Tracking_Error DOUBLE,
    Information_Ratio DOUBLE,
    Upside_Capture DOUBLE,
    Downside_Capture DOUBLE,
    Outperformance_Probability DOUBLE,
    -- Tax Exposure
    Unrealized_LTCG DOUBLE,
    Unrealized_STCG DOUBLE,
    Unrealized_Gain DOUBLE,
    Unrealized_LTCL DOUBLE,
    Unrealized_STCL DOUBLE,
    Unrealized_Loss DOUBLE,
    LTCG_Tax_If_Sold DOUBLE,
    STCG_Tax_If_Sold DOUBLE,
    FY_Realized_LTCG DOUBLE,
    FY_Realized_STCG DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_LTCL DOUBLE,
    FY_Realized_STCL DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE,
    FOREIGN KEY(Closing_Date) REFERENCES d_Calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES d_tf_Investment_Master(ISIN)
);

-- DDL: f_tf_Investment_Analytics_Subtype
CREATE TABLE f_tf_Investment_Analytics_Subtype (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    INSTRUMENT_CLASS TEXT NOT NULL,
    INSTRUMENT_SUBTYPE TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Unrealized_PL DOUBLE,
    "Absolute_Return_%" DOUBLE,
    "Weight_%" DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    -- Risk-Adjusted
    Sharpe_Ratio DOUBLE,
    Sortino_Ratio DOUBLE,
    Max_Drawdown DOUBLE,
    -- Tax Exposure
    Unrealized_LTCG DOUBLE,
    Unrealized_STCG DOUBLE,
    Unrealized_Gain DOUBLE,
    Unrealized_LTCL DOUBLE,
    Unrealized_STCL DOUBLE,
    Unrealized_Loss DOUBLE,
    LTCG_Tax_If_Sold DOUBLE,
    STCG_Tax_If_Sold DOUBLE,
    FY_Realized_LTCG DOUBLE,
    FY_Realized_STCG DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_LTCL DOUBLE,
    FY_Realized_STCL DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE,
    FOREIGN KEY(Closing_Date) REFERENCES d_Calendar(Date)
);

-- DDL: f_tf_Investment_Analytics_Class
CREATE TABLE f_tf_Investment_Analytics_Class (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    INSTRUMENT_CLASS TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Unrealized_PL DOUBLE,
    "Absolute_Return_%" DOUBLE,
    "Weight_%" DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    -- Risk-Adjusted
    Sharpe_Ratio DOUBLE,
    Sortino_Ratio DOUBLE,
    Max_Drawdown DOUBLE,
    -- Tax Exposure
    Unrealized_LTCG DOUBLE,
    Unrealized_STCG DOUBLE,
    Unrealized_Gain DOUBLE,
    Unrealized_LTCL DOUBLE,
    Unrealized_STCL DOUBLE,
    Unrealized_Loss DOUBLE,
    LTCG_Tax_If_Sold DOUBLE,
    STCG_Tax_If_Sold DOUBLE,
    FY_Realized_LTCG DOUBLE,
    FY_Realized_STCG DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_LTCL DOUBLE,
    FY_Realized_STCL DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE,
    FOREIGN KEY(Closing_Date) REFERENCES d_Calendar(Date)
);

-- DDL: f_tf_Investment_Analytics_Portfolio
CREATE TABLE f_tf_Investment_Analytics_Portfolio (
    -- Identifier
    Closing_Date DATE NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Unrealized_PL DOUBLE,
    "Absolute_Return_%" DOUBLE,
    "Weight_%" DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    -- Risk-Adjusted
    Sharpe_Ratio DOUBLE,
    Sortino_Ratio DOUBLE,
    Max_Drawdown DOUBLE,
    -- Tax Exposure
    Unrealized_LTCG DOUBLE,
    Unrealized_STCG DOUBLE,
    Unrealized_Gain DOUBLE,
    Unrealized_LTCL DOUBLE,
    Unrealized_STCL DOUBLE,
    Unrealized_Loss DOUBLE,
    LTCG_Tax_If_Sold DOUBLE,
    STCG_Tax_If_Sold DOUBLE,
    FY_Realized_LTCG DOUBLE,
    FY_Realized_STCG DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_LTCL DOUBLE,
    FY_Realized_STCL DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE,
    FOREIGN KEY(Closing_Date) REFERENCES d_Calendar(Date)
);
"""
