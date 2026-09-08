GOLD_DDL = """
CREATE TABLE IF NOT EXISTS gold.Wealth_Net_Worth_Monthly (
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
    Investment_Contribution_Pct REAL,
    Savings_to_NW_Ratio REAL,
    -- Trailing Averages
    "3M_Avg_Expense" REAL,
    "3M_Avg_Core_Expense" REAL,
    "3M_Avg_Income" REAL,
    Months_of_Runway REAL,
    -- Inflation-Adjusted (Real)
);

CREATE TABLE IF NOT EXISTS gold.Cashflow_Spend_Monthly (
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
    -- Trailing Averages
    Trailing_3M_Avg_Spend REAL,
    Cumulative_YTD_Spend REAL,
    -- Variance & Share
    -- Inflation-Adjusted
    -- Flags
    Is_Core_Expense BOOLEAN,
    Is_Investment BOOLEAN,
    Is_Discretionary BOOLEAN
);

CREATE TABLE IF NOT EXISTS gold.Cashflow_Income_Monthly (
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
    -- Trailing Averages
    Trailing_3M_Avg_Income REAL,
    Cumulative_YTD_Income REAL,
    -- Variance & Share
    -- Growth
    -- Activity
    -- Flags
    Is_Active_Income BOOLEAN,
    Is_Passive_Income BOOLEAN,
    Is_Dividend_Income BOOLEAN,
    Is_Interest_Income BOOLEAN
);

CREATE TABLE IF NOT EXISTS gold.Wealth_Risk_Metrics (
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
    INFLATION_YOY_PCT DOUBLE,
    CPI_INDEX DOUBLE,
    -- Spending & Savings
    Trailing_6M_Avg_Spend DOUBLE,
    Trailing_12M_Avg_Spend DOUBLE,
    Trailing_6M_Avg_Savings DOUBLE,
    Trailing_12M_Avg_Savings DOUBLE,
    Trailing_6M_Avg_Total_Spend DOUBLE,
    Trailing_6M_Avg_Total_Savings DOUBLE,
    Trailing_12M_Avg_Total_Spend DOUBLE,
    Trailing_12M_Avg_Total_Savings DOUBLE,
    Real_Return_Assumed_Pct DOUBLE,
    -- FI Numbers (Today's Money)
    Target_FI_Today DOUBLE,
    Target_FI_Today_Total DOUBLE,
    -- FI Future Nominal Values
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
    Months_To_FI_Base_P50 DOUBLE,
    Months_To_FI_Aggressive_P10 DOUBLE,
    Probability_Of_Success_Pct DOUBLE,
    Years_To_FI_P50 DOUBLE,
    Projected_FI_Date_P50 DATE,
    -- Sustainability
    Runway_Months_Linear DOUBLE,
    Runway_Months_Total_Linear DOUBLE,
    Runway_Months_Stressed_P10 DOUBLE,
    Runway_Months_Base_P50 DOUBLE,
    Withdrawal_Rate_If_Retired_Now DOUBLE,
    Withdrawal_Rate_If_Retired_Now_Total DOUBLE,
    Savings_Rate_Required DOUBLE,
    Savings_Rate_Required_Total DOUBLE,
    -- Decumulation & Velocity (GOAT Metrics)
    -- Savings & FI Progress Metrics
    Savings_Rate_Actual DOUBLE,
    Savings_Rate_Actual_Total DOUBLE,
    FI_Velocity DOUBLE,
    FI_Velocity_Total DOUBLE,
    -- Advanced Monte Carlo Outputs
    Terminal_Wealth_Nominal_P50 DOUBLE,
    -- Risk Metrics natively merged
    -- Risk-Adjusted Return Ratios
);

CREATE TABLE IF NOT EXISTS gold.Forecast_Tax_Liability_Annual (
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
    Tax_Harvesting_Capacity DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Forecast_Budget_Monthly (
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
    -- Actual Percentages of Income
    -- Variance Accounting
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

CREATE TABLE IF NOT EXISTS gold.Cashflow_Summary_Monthly (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    -- Asset Balances
    Opening_Balance_Asset DOUBLE,
    Closing_Balance_Asset DOUBLE,
    Closing_Balance_Asset_Market DOUBLE,
    -- Income bifurcation
    Total_Income DOUBLE,
    Active_Income DOUBLE,
    Passive_Income DOUBLE,
    Dividend_Income DOUBLE,
    Interest_Income DOUBLE,
    -- Expense bifurcation
    Total_Expense DOUBLE,
    Total_Core_Expense DOUBLE,
    NonCore_Expense DOUBLE,
    -- Investments deployed (buys)
    Total_Investment_Deployed DOUBLE,
    Equity_Deployed DOUBLE,
    Stocks_Deployed DOUBLE,
    ETFs_Deployed DOUBLE,
    MF_Deployed DOUBLE,
    Other_Deployed DOUBLE,
    -- Redemptions & net flow
    Total_Investment_Redeemed DOUBLE,
    Redemption_Gain_Loss_Value DOUBLE,
    Net_Investment_Flow DOUBLE,
    -- Surplus & rates
    Gross_Surplus DOUBLE,
    Net_Surplus_After_Invest DOUBLE,
    Savings_Rate_Pct DOUBLE,
    Investment_Rate_Pct DOUBLE,
    -- MoM deltas
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
    Expense_to_NW_Ratio DOUBLE,
    Emergency_Fund_Coverage DOUBLE,
        );
CREATE TABLE IF NOT EXISTS gold.Investment_By_ISIN (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
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
    -- Time-Range Returns
    -- Time-Range Alphas
    -- Risk
    Outperformance_Probability DOUBLE,
    -- Per-ISIN Risk-Adjusted Ratios
    Max_Drawdown DOUBLE,
    -- Benchmark Equivalents
    -- Comparison Alphas
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
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,

    -- Time-Range Returns
    -- Time-Range Alphas
    -- Risk-Adjusted (Portfolio)
    Max_Drawdown DOUBLE,
    -- Benchmark Equivalents
    -- Comparison Alphas
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
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,

    -- Time-Range Returns
    -- Time-Range Alphas
    -- Risk-Adjusted (Portfolio)
    Max_Drawdown DOUBLE,
    -- Benchmark Equivalents
    -- Comparison Alphas
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
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,

    -- Time-Range Returns
    -- Time-Range Alphas
    -- Risk-Adjusted (Portfolio)
    Max_Drawdown DOUBLE,
    -- Benchmark Equivalents
    -- Comparison Alphas
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
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,

    -- Time-Range Returns
    -- Time-Range Alphas
    -- Risk-Adjusted (Portfolio)
    Max_Drawdown DOUBLE,
    -- Benchmark Equivalents
    -- Comparison Alphas
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
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,

    -- Time-Range Returns
    -- Time-Range Alphas
    -- Risk-Adjusted (Portfolio)
    Max_Drawdown DOUBLE,
    -- Benchmark Equivalents
    -- Comparison Alphas
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
    Unrealized_PL DOUBLE,
    Absolute_Return DOUBLE,
    Weight DOUBLE,
    -- Returns
    XIRR DOUBLE,
    After_Tax_XIRR DOUBLE,
    BM_XIRR DOUBLE,
    Active_Return DOUBLE,
        
    -- Time-Range Returns
    -- Time-Range Alphas
    -- Risk-Adjusted (Portfolio)
    Max_Drawdown DOUBLE,
    -- Benchmark Equivalents
    -- Comparison Alphas
    -- Tax Exposure
    Unrealized_Gain DOUBLE,
    Unrealized_Loss DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE
);

"""
