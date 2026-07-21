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

CREATE TABLE IF NOT EXISTS p_tf_Category_Inflation_Trends (
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    CATEGORY_ID TEXT,
    Total_Monthly_Spend REAL,
    Average_Transaction_Value REAL,
    "MoM_Spend_Growth_%" REAL,
    "YoY_Spend_Growth_%" REAL,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(CATEGORY_ID) REFERENCES d_Expense_Category(UID)
);

"""
