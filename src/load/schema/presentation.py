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
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(ASSET_SUBCATEGORY_ID) REFERENCES d_Asset_SubCategory(UID)
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
    Total_Net_Worth REAL,
    Trailing_6M_Avg_Spend REAL,
    Trailing_6M_Avg_Savings REAL,
    Target_FI_Number REAL,
    Current_FI_Coverage_Pct REAL,
    Estimated_Months_To_FI REAL,
    Runway_Months REAL,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date)
);

"""
