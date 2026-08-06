PRESENTATION_DDL = """
CREATE TABLE IF NOT EXISTS p_tf_Net_Worth_Monthly_Summary (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    ASSET_SUBCATEGORY_ID TEXT,
    -- Core Balances
    Opening_Balance REAL,
    Closing_Balance REAL,
    Closing_Balance_Market REAL,
    All_Time_High_Balance REAL,
    Drawdown_From_Peak REAL,
    Liquid_Assets REAL,
    Liquid_Assets_Market REAL,
    -- Cashflow
    Income_Inflow REAL,
    Expense_Outflow REAL,
    Core_Expense_Outflow REAL,
    Net_Transfers REAL,
    Net_Cashflow_Month REAL,
    Surplus_Deficit_Month REAL,
    Cumulative_Net_Savings REAL,
    -- Growth & Performance
    "MoM_Balance_Growth_%" REAL,
    "YoY_Balance_Growth_%" REAL,
    Organic_Growth_Value REAL,
    "Organic_Yield_%" REAL,
    "Asset_Velocity_%" REAL,
    "Balance_Concentration_%" REAL,
    Investment_Contribution_Pct REAL,
    Savings_to_NW_Ratio REAL,
    -- Trailing Averages
    "3M_Avg_Expense" REAL,
    "3M_Avg_Core_Expense" REAL,
    "3M_Avg_Income" REAL,
    Months_of_Runway REAL,
    -- Inflation-Adjusted (Real)
    INFLATION_YOY_PCT REAL,
    Closing_Balance_Real REAL,
    Closing_Balance_Market_Real REAL,
    Balance_MoM_Real REAL,
    Real_Income_Inflow REAL,
    Real_Expense_Outflow REAL,
    "3M_Avg_Core_Expense_Real" REAL,
    Months_of_Runway_Real REAL,
    "YoY_Balance_Growth_%_Real" REAL,
    Organic_Growth_Value_Real REAL,
    "Organic_Yield_%_Real" REAL,
    "MoM_Balance_Growth_%_Real" REAL,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(ASSET_SUBCATEGORY_ID) REFERENCES d_Asset_Subcategory(UID)
);

CREATE TABLE IF NOT EXISTS p_tf_Financial_Ratios_Monthly (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    -- Net Worth Summary
    Total_Assets REAL,
    Total_Assets_Market REAL,
    Total_Liabilities REAL,
    Total_Net_Worth REAL,
    Total_Net_Worth_Market REAL,
    -- Core Ratios
    "Savings_Rate_%" REAL,
    "Real_Savings_Rate_%" REAL,
    "Income_Surplus_Rate_%" REAL,
    Liquidity_Ratio_Months REAL,
    Emergency_Fund_Coverage REAL,
    Net_Worth_to_Annual_Expense_Ratio REAL,
    Net_Worth_per_Month_Age REAL,
    -- Debt Ratios
    "Debt_to_Asset_Ratio_%" REAL,
    Debt_Service_Coverage REAL,
    Liability_Coverage_Ratio REAL,
    Liquid_Liability_Coverage_Ratio REAL,
    Expense_to_NW_Ratio REAL,
    -- Growth
    "YoY_Net_Worth_Growth_%" REAL,
    "YoY_Net_Worth_Growth_%_Real" REAL,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_Category_Spend_Analytics (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    CATEGORY_ID TEXT,
    -- Descriptors
    CATEGORY_NAME TEXT,
    CATEGORY_GROUPS TEXT,
    Spend_Type TEXT,
    -- Core Metrics
    Total_Monthly_Spend REAL,
    Average_Transaction_Value REAL,
    Avg_Days_Between_Transactions REAL,
    -- Trailing Averages
    Trailing_3M_Avg_Spend REAL,
    Trailing_6M_Avg_Spend REAL,
    Trailing_12M_Avg_Spend REAL,
    Trailing_12M_Total_Spend REAL,
    Cumulative_YTD_Spend REAL,
    -- Variance & Share
    Spend_Share_Pct REAL,
    MoM_Variance_Pct REAL,
    YoY_Variance_Pct REAL,
    Budget_Variance_Pct REAL,
    Spend_Consistency_Score REAL,
    Rank_by_Spend BIGINT,
    -- Inflation-Adjusted
    Real_Monthly_Spend REAL,
    YoY_Real_Variance_Pct REAL,
    Category_Inflation_Contribution REAL,
    -- Flags
    Is_Core_Expense BOOLEAN,
    Is_Investment BOOLEAN,
    Is_Discretionary BOOLEAN,
    Is_Category_Creep BOOLEAN,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(CATEGORY_ID) REFERENCES d_Expense_Subcategory(UID)
);

CREATE TABLE IF NOT EXISTS p_tf_Income_Streams_Monthly (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    CATEGORY_ID TEXT,
    -- Descriptors
    CATEGORY_NAME TEXT,
    CATEGORY_GROUPS TEXT,
    -- Core Metrics
    Total_Monthly_Income REAL,
    Average_Transaction_Value REAL,
    -- Trailing Averages
    Trailing_3M_Avg_Income REAL,
    Trailing_6M_Avg_Income REAL,
    Trailing_12M_Avg_Income REAL,
    Trailing_12M_Total_Income REAL,
    Cumulative_YTD_Income REAL,
    -- Variance & Share
    Income_Share_Pct REAL,
    MoM_Variance_Pct REAL,
    YoY_Variance_Pct REAL,
    Income_Stability_Score REAL,
    Income_Diversification_Score REAL,
    -- Growth
    Income_CAGR REAL,
    Real_Monthly_Income REAL,
    Real_YoY_Income_Growth REAL,
    -- Activity
    Months_Active_TTM REAL,
    Months_Since_Last_Received BIGINT,
    -- Flags
    Is_Active_Income BOOLEAN,
    Is_Passive_Income BOOLEAN,
    Is_Dividend_Income BOOLEAN,
    Is_Interest_Income BOOLEAN,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(CATEGORY_ID) REFERENCES d_Income_Subcategory(UID)
);

CREATE TABLE IF NOT EXISTS p_tf_Fire_Forecasting_Monthly (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    Total_Income DOUBLE,
    Total_Core_Expense DOUBLE,
    Total_Expense DOUBLE,
    Net_Savings DOUBLE,
    Net_Savings_Total DOUBLE,
    -- Wealth Snapshot
    Total_Net_Worth DOUBLE,
    Total_Net_Worth_Market DOUBLE,
    Total_Net_Worth_Market_Af_Tax DOUBLE,
    -- Spending & Savings
    Trailing_6M_Avg_Spend DOUBLE,
    Trailing_6M_Avg_Savings DOUBLE,
    Trailing_6M_Avg_Total_Spend DOUBLE,
    Trailing_6M_Avg_Total_Savings DOUBLE,
    INFLATION_YOY_PCT DOUBLE,
    Real_Return_Assumed_Pct DOUBLE,
    -- FI Numbers (Today's Money)
    Target_FI_Today DOUBLE,
    Target_FI_Today_Total DOUBLE,
    Coast_FI_Today DOUBLE,
    Coast_FI_Today_Total DOUBLE,
    Lean_FI_Today DOUBLE,
    Lean_FI_Today_Total DOUBLE,
    -- FI Future Nominal Values
    Target_FI_Future_Nominal DOUBLE,
    Target_FI_Total_Future_Nominal DOUBLE,
    -- FI Progress
    Current_FI_Coverage_Pct DOUBLE,
    Current_FI_Coverage_Pct_Total DOUBLE,
    NW_Percentile_of_FI DOUBLE,
    NW_Percentile_of_FI_Total DOUBLE,
    FI_Gap DOUBLE,
    FI_Gap_Total DOUBLE,
    FI_Gap_Monthly_Trend DOUBLE,
    FI_Gap_Total_Monthly_Trend DOUBLE,
    -- Time to FI
    Estimated_Months_To_FI_Linear DOUBLE,
    Estimated_Months_To_FI_Total_Linear DOUBLE,
    Months_To_FI_Conservative_P90 DOUBLE,
    Months_To_FI_Total_Conservative_P90 DOUBLE,
    Months_To_FI_Base_P50 DOUBLE,
    Months_To_FI_Total_Base_P50 DOUBLE,
    Months_To_FI_Aggressive_P10 DOUBLE,
    Months_To_FI_Total_Aggressive_P10 DOUBLE,
    Probability_Of_Success_Pct DOUBLE,
    Probability_Of_Success_Total_Pct DOUBLE,
    Years_To_FI_P50 DOUBLE,
    Years_To_FI_Total_P50 DOUBLE,
    Projected_FI_Date_P50 DATE,
    Projected_FI_Date_Total_P50 DATE,
    -- Sustainability
    Runway_Months_Linear DOUBLE,
    Runway_Months_Stressed_P10 DOUBLE,
    Runway_Months_Base_P50 DOUBLE,
    Runway_Months_Total_Linear DOUBLE,
    Runway_Months_Total_Stressed_P10 DOUBLE,
    Runway_Months_Total_Base_P50 DOUBLE,
    Withdrawal_Rate_If_Retired_Now DOUBLE,
    Withdrawal_Rate_If_Retired_Now_Total DOUBLE,
    Savings_Rate_Required DOUBLE,
    Savings_Rate_Required_Total DOUBLE,
    -- Decumulation & Velocity (GOAT Metrics)
    Wealth_Velocity DOUBLE,
    Wealth_Acceleration DOUBLE,
    CAPE_Adjusted_SWR DOUBLE,
    Guyton_Klinger_Floor DOUBLE,
    Guyton_Klinger_Ceiling DOUBLE,
    Human_Capital_Value DOUBLE,
    Human_to_Financial_Capital_Ratio DOUBLE,
    Velocity_vs_Savings_Ratio DOUBLE,
    Model_Error_Months_To_FI DOUBLE,
    Net_Worth_Post_Tax_Delta_Pct DOUBLE,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_Risk_Metrics (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    -- Wealth Snapshot
    Total_Net_Worth DOUBLE,
    Total_Net_Worth_Market DOUBLE,
    -- Returns
    Monthly_Return DOUBLE,
    Rolling_12M_Return DOUBLE,
    -- Drawdown
    All_Time_High_NW DOUBLE,
    NW_Drawdown_Pct DOUBLE,
    Real_Drawdown_Pct DOUBLE,
    Drawdown_Pct DOUBLE,
    "Recovery_From_Drawdown_%" DOUBLE,
    Max_Drawdown_12M DOUBLE,
    -- Volatility & Risk
    Annualized_Volatility_12M DOUBLE,
    NW_Volatility_12M DOUBLE,
    Downside_Deviation_12M DOUBLE,
    VaR_95_Monthly DOUBLE,
    Expected_Shortfall_95 DOUBLE,
    -- Risk-Adjusted Ratios
    Sharpe_Ratio_Monthly DOUBLE,
    Sortino_Ratio_Monthly DOUBLE,
    Calmar_Ratio DOUBLE,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_Sector_Allocation_Monthly (
    -- Identifiers
    MONTH_START_DATE DATE,
    As_Of_Date DATE,
    -- Dimensions
    INSTRUMENT_CLASS TEXT,
    INSTRUMENT_TYPE TEXT,
    INSTRUMENT_SUBTYPE TEXT,
    SECTOR TEXT,
    -- Values
    Total_Portfolio_Value DOUBLE,
    Class_Total_Value DOUBLE,
    Sector_Total_Value DOUBLE,
    -- Weights
    Class_Target_Weight DOUBLE,
    Class_Weight DOUBLE,
    Weight_In_Class DOUBLE,
    Portfolio_Weight DOUBLE,
    Weight_Change_MoM DOUBLE,
    -- Concentration
    Class_HHI_Concentration_Index DOUBLE,
    Sector_HHI_Concentration_Index REAL,
    Effective_Diversification REAL,
    Marginal_Risk_Contribution DOUBLE,
    -- Performance
    Class_CAGR REAL,
    Benchmark_Deviation REAL,
    -- Flags
    Is_Overweight BOOLEAN,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_Tax_Liability_Forecast (
    -- Identifiers
    MONTH_START_DATE DATE,
    Financial_Year TEXT,
    -- Realized Gains/Income
    Realized_STCG DOUBLE,
    Realized_LTCG DOUBLE,
    Realized_Gain DOUBLE,
    Realized_STCL DOUBLE,
    Realized_LTCL DOUBLE,
    Realized_Loss DOUBLE,
    Realized_Net_PnL DOUBLE,
    Taxable_Dividends DOUBLE,
    Taxable_Interest DOUBLE,
    -- Tax Exemptions
    LTCG_Exemption_Used DOUBLE,
    LTCG_Exemption_Remaining DOUBLE,
    -- Projections
    Projected_Tax_Bill DOUBLE,
    Harvesting_Offset_Remaining DOUBLE,
    -- Efficiency
    Tax_Drag_Pct DOUBLE,
    Tax_Alpha_Pct DOUBLE,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_Performance_Attribution (
    -- Identifiers
    MONTH_START_DATE DATE,
    INSTRUMENT_CLASS TEXT,
    INSTRUMENT_TYPE TEXT,
    INSTRUMENT_SUBTYPE TEXT,
    SECTOR TEXT,
    -- Macro Weights (Class Level)
    Class_Target_Weight DOUBLE,
    Class_Actual_Weight DOUBLE,
    -- Returns
    Sector_Return DOUBLE,
    Class_Benchmark_Return DOUBLE,
    -- Brinson-Fachler Attribution
    Allocation_Effect DOUBLE,
    Selection_Effect DOUBLE,
    Interaction_Effect DOUBLE,
    Total_Active_Return DOUBLE,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_Portfolio_Rebalancing_Plan (
    -- Identifiers
    MONTH_START_DATE DATE,
    INSTRUMENT_CLASS TEXT,
    INSTRUMENT_TYPE TEXT,
    INSTRUMENT_SUBTYPE TEXT,
    SECTOR TEXT,
    -- Macro Status (Class Level)
    Class_Target_Weight DOUBLE,
    Class_Actual_Weight DOUBLE,
    Class_Deviation DOUBLE,
    Class_Rebalance_Action TEXT,
    Class_Order_Value DOUBLE,
    -- Micro Component (Sector Level)
    Sector_Value DOUBLE,
    Sector_Unrealized_Loss DOUBLE,
    -- Status
    Is_Rebalance_Required BOOLEAN,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_Tax_Harvesting (
    -- Identifiers
    ISIN TEXT,
    "Instrument Name" TEXT,
    -- Position
    Holding_Type TEXT,
    Max_Days_Held BIGINT,
    Harvestable_Quantity DOUBLE,
    -- Values
    Total_Invested DOUBLE,
    Current_Value DOUBLE,
    Harvestable_Loss DOUBLE,
    Loss_Percentage DOUBLE,
    -- Tax Benefit
    LTCG_Exemption_Remaining REAL,
    Tax_Savings_If_Harvested REAL,
    Net_Tax_Benefit REAL,
    -- Scoring
    Offset_Potential REAL,
    Substitute_Asset_Available BOOLEAN,
    Priority_Score REAL,
    FOREIGN KEY(ISIN) REFERENCES d_tf_Investment_Master(ISIN)
);

CREATE TABLE IF NOT EXISTS p_tf_Budget_Forecast_Monthly (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    -- Income Anchor
    Actual_Income DOUBLE,
    Budget_Income DOUBLE,
    Income_Volatility_Pct DOUBLE,
    Income_Regime TEXT,
    -- Rule Targets (from config: 40/20/30+10)
    Rule_Core_Pct_Budget DOUBLE,
    Rule_NonCore_Pct_Budget DOUBLE,
    Rule_Investment_Pct_Budget DOUBLE,
    Budget_Core_Expense_Target DOUBLE,
    Budget_NonCore_Expense_Target DOUBLE,
    Budget_Investment_Target DOUBLE,
    Budget_Surplus_Buffer DOUBLE,
    Budget_Total_Expense_Target DOUBLE,
    -- Actuals
    Actual_Core_Expense DOUBLE,
    Actual_NonCore_Expense DOUBLE,
    Actual_Investment DOUBLE,
    Actual_Savings DOUBLE,
    -- Actual Percentages of Income
    Actual_Core_Pct_of_Income DOUBLE,
    Actual_NonCore_Pct_of_Income DOUBLE,
    Actual_Investment_Pct_of_Income DOUBLE,
    Actual_Savings_Pct_of_Income DOUBLE,
    -- Variance Accounting
    Core_Expense_Variance DOUBLE,
    NonCore_Expense_Variance DOUBLE,
    Investment_Shortfall DOUBLE,
    Total_Budget_Variance DOUBLE,
    -- Trend & Momentum Signals
    Core_Expense_3M_Trend DOUBLE,
    NonCore_Expense_3M_Trend DOUBLE,
    Income_3M_Trend DOUBLE,
    -- Z-Score Anomaly Detection (6M rolling baseline)
    Core_Expense_ZScore DOUBLE,
    NonCore_Expense_ZScore DOUBLE,
    Income_ZScore DOUBLE,
    Savings_Rate_Trend_Signal TEXT,
    -- Composite Health Score
    Savings_Rate_Health_Score DOUBLE,
    Savings_Rate_Grade TEXT,
    Budget_Stress_Score DOUBLE,
    -- Lifestyle & Efficiency Metrics
    Marginal_Core_Efficiency DOUBLE,
    Lifestyle_Creep_Index DOUBLE,
    Budget_Elasticity DOUBLE,
    -- Runway
    Zero_Income_Runway_Months DOUBLE,
    Emergency_Fund_Gap DOUBLE,
    -- M+1 Forward Budget Plan
    NextMonth_Budget_Income_Forecast DOUBLE,
    NextMonth_Core_Budget DOUBLE,
    NextMonth_NonCore_Budget DOUBLE,
    NextMonth_Investment_Budget DOUBLE,
    NextMonth_Discretionary_Pool DOUBLE,
    NextMonth_Recommended_Savings DOUBLE,
    -- M+2 Forward Budget Plan
    Next2Month_Budget_Income_Forecast DOUBLE,
    Next2Month_Core_Budget DOUBLE,
    Next2Month_NonCore_Budget DOUBLE,
    Next2Month_Investment_Budget DOUBLE,
    Next2Month_Discretionary_Pool DOUBLE,
    Next2Month_Recommended_Savings DOUBLE,
    -- M+3 Forward Budget Plan
    Next3Month_Budget_Income_Forecast DOUBLE,
    Next3Month_Core_Budget DOUBLE,
    Next3Month_NonCore_Budget DOUBLE,
    Next3Month_Investment_Budget DOUBLE,
    Next3Month_Discretionary_Pool DOUBLE,
    Next3Month_Recommended_Savings DOUBLE,
    -- Flags
    Is_Core_Overspent BOOLEAN,
    Is_NonCore_Overspent BOOLEAN,
    Is_Investment_Underfunded BOOLEAN,
    Is_Income_Volatile BOOLEAN,
    Is_Budget_Month_Healthy BOOLEAN,
    Is_Lifestyle_Creep BOOLEAN,
    Is_Expense_Anomaly BOOLEAN,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_Investment_Snapshot_ISIN (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    ISIN TEXT,
    INSTRUMENT_NAME TEXT,
    INSTRUMENT_CLASS TEXT,
    INSTRUMENT_TYPE TEXT,
    INSTRUMENT_SUBTYPE TEXT,
    SECTOR TEXT,
    -- Position Values
    Invested_Value DOUBLE,
    Market_Value DOUBLE,
    Unrealized_PL DOUBLE,
    Absolute_Return_Pct DOUBLE,
    Portfolio_Weight_Pct DOUBLE,
    -- MoM Return
    Prev_Month_Market_Value DOUBLE,
    Monthly_Value_Change DOUBLE,
    Monthly_Deployed DOUBLE,
    Monthly_Redeemed DOUBLE,
    Net_Monthly_Flow DOUBLE,
    MoM_Return_Pct DOUBLE,
    MoM_Return_Pct_Simple DOUBLE,
    -- Trailing Returns
    Rolling_3M_Return_Pct DOUBLE,
    Rolling_6M_Return_Pct DOUBLE,
    Rolling_12M_Return_Pct DOUBLE,
    -- Benchmark MoM
    BM_MoM_Return_Pct DOUBLE,
    MoM_Alpha DOUBLE,
    -- Snapshot Metrics (cumulative)
    CAGR DOUBLE,
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    Active_Return DOUBLE,
    Beta DOUBLE,
    Tracking_Error DOUBLE,
    Information_Ratio DOUBLE,
    -- Tax Context
    Unrealized_LTCG DOUBLE,
    Unrealized_STCG DOUBLE,
    Unrealized_LTCL DOUBLE,
    Unrealized_STCL DOUBLE,
    LTCG_Tax_If_Sold DOUBLE,
    STCG_Tax_If_Sold DOUBLE,
    -- Flags
    Is_New_Position BOOLEAN,
    Is_Closed_Position BOOLEAN,
    Is_Active_Month BOOLEAN,
    Is_MoM_Positive BOOLEAN,
    Is_Beating_BM_MoM BOOLEAN,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES d_tf_Investment_Master(ISIN)
);

CREATE TABLE IF NOT EXISTS p_tf_Investment_Snapshot_Portfolio (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    -- Portfolio Valuation
    Total_Invested_Value DOUBLE,
    Total_Market_Value DOUBLE,
    Total_Unrealized_PL DOUBLE,
    Absolute_Return_Pct DOUBLE,
    -- MoM Return
    Prev_Month_Market_Value DOUBLE,
    Portfolio_MoM_Return_Pct DOUBLE,
    Portfolio_MoM_Return_Pct_Simple DOUBLE,
    Portfolio_MoM_Value_Change DOUBLE,
    Monthly_Deployed_Total DOUBLE,
    Monthly_Redeemed_Total DOUBLE,
    -- Rolling Returns
    Rolling_3M_Return_Pct DOUBLE,
    Rolling_6M_Return_Pct DOUBLE,
    Rolling_12M_Return_Pct DOUBLE,
    Rolling_3M_Annualized_Return DOUBLE,
    -- Quant Metrics
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    Sharpe_Ratio DOUBLE,
    Sortino_Ratio DOUBLE,
    Max_Drawdown DOUBLE,
    -- Cashflow Context
    Total_Income DOUBLE,
    Total_Expense DOUBLE,
    Total_Core_Expense DOUBLE,
    Surplus_For_Investment DOUBLE,
    Deployment_Efficiency_Pct DOUBLE,
    -- Tax Summary
    Total_Unrealized_LTCG DOUBLE,
    Total_Unrealized_STCG DOUBLE,
    Total_Unrealized_LTCL DOUBLE,
    Total_Unrealized_STCL DOUBLE,
    Total_LTCG_Tax_If_Sold DOUBLE,
    Total_STCG_Tax_If_Sold DOUBLE,
    FY_Realized_Net_PnL DOUBLE,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS p_tf_Monthly_Cashflow_Summary (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    -- Income bifurcation
    Total_Income DOUBLE,
    Active_Income DOUBLE,
    Passive_Income DOUBLE,
    Dividend_Income DOUBLE,
    Interest_Income DOUBLE,
    Active_Income_Share_Pct DOUBLE,
    Passive_Income_Share_Pct DOUBLE,
    -- Expense bifurcation
    Total_Expense DOUBLE,
    Total_Core_Expense DOUBLE,
    NonCore_Expense DOUBLE,
    Core_Expense_Share_Pct DOUBLE,
    -- Investments deployed (buys)
    Total_Investment_Deployed DOUBLE,
    Equity_Deployed DOUBLE,
    Stocks_Deployed DOUBLE,
    ETFs_Deployed DOUBLE,
    MF_Deployed DOUBLE,
    Other_Deployed DOUBLE,
    Equity_Pct_of_Deployed DOUBLE,
    MF_Pct_of_Deployed DOUBLE,
    -- Redemptions & net flow
    Total_Investment_Redeemed DOUBLE,
    Net_Investment_Flow DOUBLE,
    -- Surplus & rates
    Gross_Surplus DOUBLE,
    Net_Surplus_After_Invest DOUBLE,
    Savings_Rate_Pct DOUBLE,
    Investment_Rate_Pct DOUBLE,
    -- MoM deltas
    Income_MoM_Delta DOUBLE,
    Expense_MoM_Delta DOUBLE,
    Investment_MoM_Delta DOUBLE,
    Income_MoM_Pct DOUBLE,
    Expense_MoM_Pct DOUBLE,
    -- Trailing averages
    Trailing_3M_Avg_Income DOUBLE,
    Trailing_3M_Avg_Expense DOUBLE,
    Trailing_3M_Avg_Investment DOUBLE,
    Trailing_3M_Avg_Savings_Rate DOUBLE,
    -- Flags
    Is_Surplus_Month BOOLEAN,
    Is_Investment_Target_Met BOOLEAN,
    FOREIGN KEY(MONTH_START_DATE) REFERENCES d_Calendar(Date),
    FOREIGN KEY(MONTH_END_DATE) REFERENCES d_Calendar(Date)
);

CREATE TABLE IF NOT EXISTS _ETL_Metadata (
    Table_Name TEXT,
    Row_Count INTEGER,
    Generated_At TIMESTAMP
);

"""
