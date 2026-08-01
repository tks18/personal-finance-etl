PRESENTATION_DDL = """
CREATE TABLE IF NOT EXISTS p_tf_Net_Worth_Monthly_Summary (
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    ASSET_SUBCATEGORY_ID TEXT,
    Opening_Balance REAL,
    Income_Inflow REAL,
    Expense_Outflow REAL,
    Net_Transfers REAL,
    Net_Cashflow_Month REAL,
    Closing_Balance REAL,
    Organic_Growth_Value REAL,
    "Organic_Yield_%" REAL,
    "MoM_Balance_Growth_%" REAL,
    "Asset_Velocity_%" REAL,
    "3M_Avg_Expense" REAL,
    "3M_Avg_Income" REAL,
    "YoY_Balance_Growth_%" REAL,
    Months_of_Runway REAL,
    INFLATION_YOY_PCT REAL,
    Closing_Balance_Real REAL,
    "YoY_Balance_Growth_%_Real" REAL,
    Organic_Growth_Value_Real REAL,
    "Organic_Yield_%_Real" REAL,
    "MoM_Balance_Growth_%_Real" REAL,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(ASSET_SUBCATEGORY_ID) REFERENCES d_Asset_Subcategory(UID)
);

CREATE TABLE IF NOT EXISTS p_tf_Financial_Ratios_Monthly (
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    "Savings_Rate_%" REAL,
    Liquidity_Ratio_Months REAL,
    "Debt_to_Asset_Ratio_%" REAL,
    "FIRE_Progress_%" REAL,
    "YoY_Net_Worth_Growth_%" REAL,
    Total_Assets REAL,
    Total_Liabilities REAL,
    Total_Net_Worth REAL,
    "YoY_Net_Worth_Growth_%_Real" REAL,
    "FIRE_Progress_%_Real" REAL,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_category_spend_analytics (
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    CATEGORY_ID TEXT,
    CATEGORY_NAME TEXT,
    CATEGORY_GROUPS TEXT,
    Total_Monthly_Spend REAL,
    Average_Transaction_Value REAL,
    Trailing_3M_Avg_Spend REAL,
    Trailing_6M_Avg_Spend REAL,
    Spend_Share_Pct REAL,
    MoM_Variance_Pct REAL,
    YoY_Variance_Pct REAL,
    Spend_Intensity_Z_Score REAL,
    Is_Category_Creep BOOLEAN,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(CATEGORY_ID) REFERENCES d_Expense_Subcategory(UID)
);

CREATE TABLE IF NOT EXISTS p_tf_income_streams_monthly (
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    CATEGORY_ID TEXT,
    CATEGORY_NAME TEXT,
    CATEGORY_GROUPS TEXT,
    Total_Monthly_Income REAL,
    Average_Transaction_Value REAL,
    Trailing_3M_Avg_Income REAL,
    Trailing_6M_Avg_Income REAL,
    Income_Share_Pct REAL,
    MoM_Variance_Pct REAL,
    YoY_Variance_Pct REAL,
    Is_Passive_Income BOOLEAN,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(CATEGORY_ID) REFERENCES d_Income_Subcategory(UID)
);

CREATE TABLE IF NOT EXISTS p_tf_fire_forecasting_monthly (
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    Total_Net_Worth DOUBLE,
    Trailing_6M_Avg_Spend DOUBLE,
    Trailing_6M_Avg_Savings DOUBLE,
    Target_FI_Number DOUBLE,
    Current_FI_Coverage_Pct DOUBLE,
    Estimated_Months_To_FI_Linear DOUBLE,
    Months_To_FI_Conservative_P90 DOUBLE,
    Months_To_FI_Base_P50 DOUBLE,
    Months_To_FI_Aggressive_P10 DOUBLE,
    Runway_Months DOUBLE,
    INFLATION_YOY_PCT DOUBLE,
    Real_Return_Assumed_Pct DOUBLE,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_risk_metrics (
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    Total_Net_Worth DOUBLE,
    All_Time_High_NW DOUBLE,
    Drawdown_Pct DOUBLE,
    Monthly_Return DOUBLE,
    Annualized_Volatility_12M DOUBLE,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_sector_allocation_monthly (
    MONTH_START_DATE DATE,
    As_Of_Date DATE,
    INSTRUMENT_CLASS TEXT,
    INSTRUMENT_SUBTYPE TEXT,
    Class_Total_Value DOUBLE,
    Subtype_Total_Value DOUBLE,
    Total_Portfolio_Value DOUBLE,
    Class_Weight DOUBLE,
    Subtype_Weight DOUBLE,
    Class_HHI_Concentration_Index DOUBLE,
    Subtype_HHI_Concentration_Index DOUBLE,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_tax_harvesting (
    ISIN TEXT,
    "Instrument Name" TEXT,
    Holding_Type TEXT,
    Harvestable_Quantity DOUBLE,
    Total_Invested DOUBLE,
    Current_Value DOUBLE,
    Harvestable_Loss DOUBLE,
    Loss_Percentage DOUBLE,
    FOREIGN KEY(ISIN) REFERENCES d_tf_Investment_Master(ISIN)
);

CREATE TABLE IF NOT EXISTS _ETL_Metadata (
    Table_Name TEXT,
    Row_Count INTEGER,
    Generated_At TIMESTAMP
);

"""
