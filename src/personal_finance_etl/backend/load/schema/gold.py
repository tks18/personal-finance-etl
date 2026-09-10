GOLD_DDL = """
CREATE TABLE IF NOT EXISTS gold.Wealth_Asset_Breakdown (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    ASSET_SUBCATEGORY_ID TEXT,
    -- Core Balances
    Opening_Balance DOUBLE,
    Closing_Balance DOUBLE,
    Closing_Balance_Market DOUBLE,
    All_Time_High_Balance DOUBLE,
    Drawdown_From_Peak DOUBLE,
    Liquid_Assets DOUBLE,
    Liquid_Assets_Market DOUBLE,
    -- Cashflow
    Income_Inflow DOUBLE,
    Expense_Outflow DOUBLE,
    Core_Expense_Outflow DOUBLE,
    Net_Transfers DOUBLE,
    Net_Cashflow_Month DOUBLE,
    Surplus_Deficit_Month DOUBLE,
    Cumulative_Net_Savings DOUBLE,
    -- Growth & Performance
    "MoM_Balance_Growth_%" DOUBLE,
    "YoY_Balance_Growth_%" DOUBLE,
    Organic_Growth_Value DOUBLE,
    "Organic_Yield_%" DOUBLE,
    Investment_Contribution_Pct DOUBLE,
    Savings_to_NW_Ratio DOUBLE,
    -- Trailing Averages
    "3M_Avg_Expense" DOUBLE,
    "3M_Avg_Core_Expense" DOUBLE,
    "3M_Avg_Income" DOUBLE,
    Months_of_Runway DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Core_Monthly_Fact (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    -- Core Metrics
    Total_Income DOUBLE,
    Total_Expense DOUBLE,
    Total_Core_Expense DOUBLE,
    Net_Cashflow_Month DOUBLE,
    -- Asset Balances
    Opening_Balance_Asset DOUBLE,
    Opening_Balance_Asset_Market DOUBLE,
    Closing_Balance_Asset DOUBLE,
    Closing_Balance_Asset_Market DOUBLE,
    Asset_Delta DOUBLE,
    Asset_Market_Delta DOUBLE,
    Total_Assets DOUBLE,
    Total_Assets_Market DOUBLE,
    -- Investment Balances (Book)
    Opening_Investment_Book_Value DOUBLE,
    Closing_Investment_Book_Value DOUBLE,
    Investment_Book_Value_Delta DOUBLE,
    -- Investment Balances (Market)
    Opening_Investment_Market_Value DOUBLE,
    Closing_Investment_Market_Value DOUBLE,
    Investment_Market_Value_Delta DOUBLE,
    -- Investment Performance
    Opening_Investment_XIRR DOUBLE,
    Closing_Investment_XIRR DOUBLE,
    Opening_Unrealized_PL DOUBLE,
    Closing_Unrealized_PL DOUBLE,
    -- Liabilities & Wealth
    Liquid_Assets DOUBLE,
    Liquid_Assets_Market DOUBLE,
    Total_Liabilities DOUBLE,
    Total_Net_Worth DOUBLE,
    Total_Net_Worth_Market DOUBLE,
    Months_Elapsed BIGINT,
    -- Inflation & CPI
    CPI_INDEX DOUBLE,
    INFLATION_YOY_PCT DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Cashflow_Expense_Breakdown (
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
    Total_Monthly_Spend DOUBLE,
    -- Trailing Averages
    Trailing_3M_Avg_Spend DOUBLE,
    Cumulative_YTD_Spend DOUBLE,
    -- Flags
    Is_Core_Expense BOOLEAN,
    Is_Investment BOOLEAN,
    Is_Discretionary BOOLEAN
);

CREATE TABLE IF NOT EXISTS gold.Cashflow_Income_Breakdown (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    CATEGORY_ID TEXT,
    -- Descriptors
    CATEGORY_NAME TEXT,
    CATEGORY_GROUPS TEXT,
    -- Core Metrics
    Total_Monthly_Income DOUBLE,
    -- Trailing Averages
    Trailing_3M_Avg_Income DOUBLE,
    Cumulative_YTD_Income DOUBLE,
    -- Flags
    Is_Active_Income BOOLEAN,
    Is_Passive_Income BOOLEAN,
    Is_Dividend_Income BOOLEAN,
    Is_Interest_Income BOOLEAN
);

CREATE TABLE IF NOT EXISTS gold.Wealth_FIRE_Analytics (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    -- Spending & Savings
    Trailing_6M_Avg_Spend DOUBLE,
    Trailing_12M_Avg_Spend DOUBLE,
    Trailing_6M_Avg_Savings DOUBLE,
    Trailing_12M_Avg_Savings DOUBLE,
    Real_Return_Assumed_Pct DOUBLE,
    -- FI Numbers (Today's Money)
    Target_FI_Today DOUBLE,
    Coast_FI_Today DOUBLE,
    Lean_FI_Today DOUBLE,
    -- FI Future Nominal Values
    Target_FI_Total_Future_Nominal DOUBLE,
    -- FI Progress
    Current_FI_Coverage_Pct DOUBLE,
    FI_Gap DOUBLE,
    FI_Gap_Monthly_Trend DOUBLE,
    -- Time to FI
    Estimated_Months_To_FI_Linear DOUBLE,
    Months_To_FI_Conservative_P90 DOUBLE,
    Months_To_FI_Base_P50 DOUBLE,
    Months_To_FI_Aggressive_P10 DOUBLE,
    Probability_Of_Success_Pct DOUBLE,
    Years_To_FI_P50 DOUBLE,
    Projected_FI_Date_P50 DATE,
    -- Sustainability
    Runway_Months_Linear DOUBLE,
    Runway_Months_Stressed_P10 DOUBLE,
    Runway_Months_Base_P50 DOUBLE,
    Withdrawal_Rate_If_Retired_Now DOUBLE,
    Savings_Rate_Required DOUBLE,
    -- Savings & FI Progress Metrics
    Savings_Rate_Actual DOUBLE,
    FI_Velocity DOUBLE,
    -- Decumulation & Velocity
    Wealth_Velocity DOUBLE,
    Wealth_Acceleration DOUBLE,
    Real_NW_CAGR_3Y DOUBLE,
    -- Advanced Monte Carlo Outputs
    Terminal_Wealth_Nominal_P50 DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Forecast_Tax_Liability (
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
    Effective_Tax_Rate_Pct DOUBLE,
    Harvesting_Offset_Remaining DOUBLE,
    -- Efficiency
    Tax_Harvesting_Capacity DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Forecast_Budget_Variance (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    -- Income Anchor
    Actual_Income DOUBLE,
    Budget_Income DOUBLE,
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
    Investment_Deployed DOUBLE,
    Investment_Redeemed DOUBLE,
    Actual_Investment DOUBLE,
    Actual_Savings DOUBLE,
    -- Runway
    Zero_Income_Runway_Months DOUBLE,
    Emergency_Fund_Gap DOUBLE,
    -- Flags
    Is_Core_Overspent BOOLEAN,
    Is_NonCore_Overspent BOOLEAN,
    Is_Investment_Underfunded BOOLEAN,
    Is_Income_Volatile BOOLEAN,
    Is_Budget_Month_Healthy BOOLEAN
);

CREATE TABLE IF NOT EXISTS gold.Investment_Portfolio_Summary (
    MONTH_START_DATE DATE,
    Max_Closing_Date DATE,
    ISIN TEXT,
    INSTRUMENT_NAME TEXT,
    INSTRUMENT_CLASS TEXT,
    INSTRUMENT_TYPE TEXT,
    INSTRUMENT_SUBTYPE TEXT,
    SECTOR TEXT,
    ISIN_Market_Value DOUBLE,
    ISIN_Book_Value DOUBLE,
    ISIN_Unrealized_PnL DOUBLE,
    ISIN_Harvestable_Loss DOUBLE,
    ISIN_Weight DOUBLE,
    Class_Weight DOUBLE,
    Class_Target_Weight DOUBLE,
    Class_Drift DOUBLE,
    Rebalance_Required BOOLEAN,
    Sector_Weight DOUBLE,
    ISIN_Monthly_Return DOUBLE,
    Tax_Harvesting_Priority_Score DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Cashflow_Efficiency_Analytics (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    -- Income bifurcation
    Active_Income DOUBLE,
    Passive_Income DOUBLE,
    Dividend_Income DOUBLE,
    Interest_Income DOUBLE,
    -- Expense bifurcation
    Core_Expense DOUBLE,
    NonCore_Expense DOUBLE,
    -- Investments
    Total_Investment_Deployed DOUBLE,
    Total_Investment_Redeemed DOUBLE,
    Redemption_Gain_Loss_Value DOUBLE,
    Net_Investment_Flow DOUBLE,
    -- Surplus & rates
    Gross_Surplus DOUBLE,
    Net_Surplus_After_Invest DOUBLE,
    Savings_Rate_Pct DOUBLE,
    Investment_Rate_Pct DOUBLE,
    Active_Income_Share_Pct DOUBLE,
    Passive_Income_Share_Pct DOUBLE,
    Core_Expense_Share_Pct DOUBLE,
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
    -- Financial Ratios
    Liquidity_Ratio_Months DOUBLE,
    Debt_to_Asset_Ratio_Pct DOUBLE,
    YoY_Net_Worth_Growth_Pct DOUBLE,
    YoY_Net_Worth_Growth_Pct_Real DOUBLE,
    Expense_to_NW_Ratio DOUBLE,
    Emergency_Fund_Coverage DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Investment_By_ISIN (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Total_Quantity DOUBLE,
    Total_Stocks DOUBLE,
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    CAGR DOUBLE,
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_CAGR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    Is_Lagging_Benchmark BIGINT,
    -- Risk
    Outperformance_Probability DOUBLE,
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
    FY_Realized_Net_PnL DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Investment_By_Subtype (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    INSTRUMENT_SUBTYPE TEXT NOT NULL,
    INSTRUMENT_CLASS TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Total_Quantity DOUBLE,
    Total_Stocks DOUBLE,
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    -- Risk-Adjusted (Portfolio)
    Max_Drawdown DOUBLE,
    -- Tax Exposure
    Unrealized_Gain DOUBLE,
    Unrealized_Loss DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Investment_By_Class (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    INSTRUMENT_CLASS TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Total_Quantity DOUBLE,
    Total_Stocks DOUBLE,
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    -- Risk-Adjusted (Portfolio)
    Max_Drawdown DOUBLE,
    -- Tax Exposure
    Unrealized_Gain DOUBLE,
    Unrealized_Loss DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Investment_By_Instrument_Type (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    INSTRUMENT_TYPE TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Total_Quantity DOUBLE,
    Total_Stocks DOUBLE,
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    -- Risk-Adjusted (Portfolio)
    Max_Drawdown DOUBLE,
    -- Tax Exposure
    Unrealized_Gain DOUBLE,
    Unrealized_Loss DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Investment_By_Sector (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    SECTOR TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Total_Quantity DOUBLE,
    Total_Stocks DOUBLE,
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    -- Risk-Adjusted (Portfolio)
    Max_Drawdown DOUBLE,
    -- Tax Exposure
    Unrealized_Gain DOUBLE,
    Unrealized_Loss DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Investment_By_Industry (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    INDUSTRY TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Total_Quantity DOUBLE,
    Total_Stocks DOUBLE,
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    -- Risk-Adjusted (Portfolio)
    Max_Drawdown DOUBLE,
    -- Tax Exposure
    Unrealized_Gain DOUBLE,
    Unrealized_Loss DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Investment_By_Portfolio (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Total_Quantity DOUBLE,
    Total_Stocks DOUBLE,
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
    -- Risk-Adjusted (Portfolio)
    Max_Drawdown DOUBLE,
    -- Tax Exposure
    Unrealized_Gain DOUBLE,
    Unrealized_Loss DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE
);

"""
