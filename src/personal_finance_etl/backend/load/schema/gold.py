GOLD_DDL = """
CREATE TABLE IF NOT EXISTS gold.Wealth_Asset_Breakdown (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    ASSET_SUBCATEGORY_ID TEXT,
    -- Position Values
    Opening_Balance DOUBLE,
    Closing_Balance DOUBLE,
    Closing_Balance_Market DOUBLE,
    All_Time_High_Balance DOUBLE,
    Liquid_Assets DOUBLE,
    Liquid_Assets_Market DOUBLE,
    -- Local/FX Values
    Closing_Investment_Market_Value_Local DOUBLE,
    Closing_Investment_Book_Value_Local DOUBLE,
    -- Absolute Returns
    Closing_Asset_PnL DOUBLE,
    Closing_Forex_PnL DOUBLE,
    -- Performance Returns
    "MoM_Balance_Growth_%" DOUBLE,
    "YoY_Balance_Growth_%" DOUBLE,
    Organic_Growth_Value DOUBLE,
    "Organic_Yield_%" DOUBLE,
    -- Risk & Weights
    Drawdown_From_Peak DOUBLE,
    Investment_Contribution_Pct DOUBLE,
    Savings_to_NW_Ratio DOUBLE,
    -- Cashflow
    Income_Inflow DOUBLE,
    Cash_Income_Inflow DOUBLE,
    Non_Cash_Income_Inflow DOUBLE,
    Expense_Outflow DOUBLE,
    Core_Expense_Outflow DOUBLE,
    Cash_Expense_Outflow DOUBLE,
    Non_Cash_Expense_Outflow DOUBLE,
    Net_Transfers DOUBLE,
    Net_Cashflow_Month DOUBLE,
    Surplus_Deficit_Month DOUBLE,
    Cumulative_Net_Savings DOUBLE,
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
    -- Descriptors/Classifications
    Months_Elapsed BIGINT,
    -- Position Values
    Total_Income DOUBLE,
    Total_Cash_Income DOUBLE,
    Total_Non_Cash_Income DOUBLE,
    Total_Expense DOUBLE,
    Total_Core_Expense DOUBLE,
    Total_Cash_Expense DOUBLE,
    Total_Non_Cash_Expense DOUBLE,
    Net_Cashflow_Month DOUBLE,
    Opening_Balance_Asset DOUBLE,
    Opening_Balance_Asset_Market DOUBLE,
    Closing_Balance_Asset DOUBLE,
    Closing_Balance_Asset_Market DOUBLE,
    Asset_Delta DOUBLE,
    Asset_Market_Delta DOUBLE,
    Total_Assets DOUBLE,
    Total_Assets_Market DOUBLE,
    Opening_Investment_Book_Value DOUBLE,
    Closing_Investment_Book_Value DOUBLE,
    Investment_Book_Value_Delta DOUBLE,
    Opening_Investment_Market_Value DOUBLE,
    Closing_Investment_Market_Value DOUBLE,
    Investment_Market_Value_Delta DOUBLE,
    Liquid_Assets DOUBLE,
    Liquid_Assets_Market DOUBLE,
    Total_Liabilities DOUBLE,
    Total_Net_Worth DOUBLE,
    Total_Net_Worth_Market DOUBLE,
    -- Local/FX Values
    Closing_Investment_Market_Value_Local DOUBLE,
    Closing_Investment_Book_Value_Local DOUBLE,
    Total_Foreign_Currency_Exposure DOUBLE,
    -- Absolute Returns
    Opening_Unrealized_PL DOUBLE,
    Closing_Unrealized_PL DOUBLE,
    Closing_Asset_PnL DOUBLE,
    Closing_Forex_PnL DOUBLE,
    -- Performance Returns
    Opening_Investment_XIRR DOUBLE,
    Closing_Investment_XIRR DOUBLE,
    -- Risk & Weights
    Foreign_Exposure_Pct DOUBLE,
    CPI_INDEX DOUBLE,
    INFLATION_YOY_PCT DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Cashflow_Expense_Breakdown (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    CATEGORY_ID TEXT,
    -- Descriptors/Classifications
    CATEGORY_NAME TEXT,
    CATEGORY_GROUPS TEXT,
    Spend_Type TEXT,
    Is_Core_Expense BOOLEAN,
    Is_Investment BOOLEAN,
    Is_Discretionary BOOLEAN,
    -- Position Values
    Total_Monthly_Spend DOUBLE,
    Cash_Spend DOUBLE,
    Non_Cash_Spend DOUBLE,
    Trailing_3M_Avg_Spend DOUBLE,
    Cumulative_YTD_Spend DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Cashflow_Income_Breakdown (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    CATEGORY_ID TEXT,
    -- Descriptors/Classifications
    CATEGORY_NAME TEXT,
    CATEGORY_GROUPS TEXT,
    Is_Active_Income BOOLEAN,
    Is_Passive_Income BOOLEAN,
    Is_Dividend_Income BOOLEAN,
    Is_Interest_Income BOOLEAN,
    Is_Non_Cash_Income BOOLEAN,
    -- Position Values
    Total_Monthly_Income DOUBLE,
    Trailing_3M_Avg_Income DOUBLE,
    Cumulative_YTD_Income DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Wealth_FIRE_Analytics (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    -- Descriptors/Classifications
    Projected_FI_Date_P50 DATE,
    -- Position Values
    Total_Income DOUBLE,
    Total_Cash_Income DOUBLE,
    Trailing_6M_Avg_Spend DOUBLE,
    Trailing_12M_Avg_Spend DOUBLE,
    Trailing_6M_Avg_Savings DOUBLE,
    Trailing_12M_Avg_Savings DOUBLE,
    Target_FI_Today DOUBLE,
    Coast_FI_Today DOUBLE,
    Lean_FI_Today DOUBLE,
    Target_FI_Total_Future_Nominal DOUBLE,
    FI_Gap DOUBLE,
    FI_Gap_Monthly_Trend DOUBLE,
    Terminal_Wealth_Nominal_P50 DOUBLE,
    -- Performance Returns
    Real_Return_Assumed_Pct DOUBLE,
    Wealth_Velocity DOUBLE,
    Wealth_Acceleration DOUBLE,
    Real_NW_CAGR_3Y DOUBLE,
    -- Risk & Weights
    Current_FI_Coverage_Pct DOUBLE,
    Estimated_Months_To_FI_Linear DOUBLE,
    Months_To_FI_Conservative_P90 DOUBLE,
    Months_To_FI_Base_P50 DOUBLE,
    Months_To_FI_Aggressive_P10 DOUBLE,
    Probability_Of_Success_Pct DOUBLE,
    Years_To_FI_P50 DOUBLE,
    Runway_Months_Linear DOUBLE,
    Runway_Months_Stressed_P10 DOUBLE,
    Runway_Months_Base_P50 DOUBLE,
    Withdrawal_Rate_If_Retired_Now DOUBLE,
    Savings_Rate_Required DOUBLE,
    Savings_Rate_Actual DOUBLE,
    FI_Velocity DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Forecast_Tax_Liability (
    -- Identifiers
    MONTH_START_DATE DATE,
    Financial_Year TEXT,
    -- Absolute Returns
    Realized_STCG DOUBLE,
    Realized_LTCG DOUBLE,
    Realized_Gain DOUBLE,
    Realized_STCL DOUBLE,
    Realized_LTCL DOUBLE,
    Realized_Loss DOUBLE,
    Realized_Net_PnL DOUBLE,
    Taxable_Dividends DOUBLE,
    Taxable_Interest DOUBLE,
    -- Tax & Harvesting
    LTCG_Exemption_Used DOUBLE,
    LTCG_Exemption_Remaining DOUBLE,
    Projected_Tax_Bill DOUBLE,
    Effective_Tax_Rate_Pct DOUBLE,
    Harvesting_Offset_Remaining DOUBLE,
    Tax_Harvesting_Capacity DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Forecast_Budget_Variance (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    -- Descriptors/Classifications
    Is_Core_Overspent BOOLEAN,
    Is_NonCore_Overspent BOOLEAN,
    Is_Investment_Underfunded BOOLEAN,
    Is_Income_Volatile BOOLEAN,
    Is_Budget_Month_Healthy BOOLEAN,
    -- Position Values
    Total_Income DOUBLE,
    Actual_Income DOUBLE,
    Budget_Income DOUBLE,
    Budget_Core_Expense_Target DOUBLE,
    Budget_NonCore_Expense_Target DOUBLE,
    Budget_Investment_Target DOUBLE,
    Budget_Surplus_Buffer DOUBLE,
    Budget_Total_Expense_Target DOUBLE,
    Actual_Core_Expense DOUBLE,
    Actual_NonCore_Expense DOUBLE,
    Investment_Deployed DOUBLE,
    Investment_Redeemed DOUBLE,
    Actual_Investment DOUBLE,
    Actual_Savings DOUBLE,
    Emergency_Fund_Gap DOUBLE,
    -- Risk & Weights
    Rule_Core_Pct_Budget DOUBLE,
    Rule_NonCore_Pct_Budget DOUBLE,
    Rule_Investment_Pct_Budget DOUBLE,
    Zero_Income_Runway_Months DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Investment_Portfolio_Summary (
    -- Identifiers
    MONTH_START_DATE DATE,
    Max_Closing_Date DATE,
    ISIN TEXT,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    INSTRUMENT_NAME TEXT,
    INSTRUMENT_CLASS TEXT,
    INSTRUMENT_TYPE TEXT,
    INSTRUMENT_SUBTYPE TEXT,
    SECTOR TEXT,
    Rebalance_Required BOOLEAN,
    -- Position Values
    ISIN_Market_Value DOUBLE,
    ISIN_Book_Value DOUBLE,
    -- Local/FX Values
    ISIN_Market_Value_Local DOUBLE,
    ISIN_Book_Value_Local DOUBLE,
    -- Absolute Returns
    ISIN_Unrealized_PnL DOUBLE,
    ISIN_Asset_PnL DOUBLE,
    ISIN_Forex_PnL DOUBLE,
    ISIN_Forex_Contribution_Pct DOUBLE,
    -- Performance Returns
    ISIN_XIRR_Local DOUBLE,
    ISIN_FX_XIRR_Impact DOUBLE,
    -- Benchmark Comparisons
    ISIN_BM_XIRR DOUBLE,
    ISIN_BM_XIRR_Local DOUBLE,
    ISIN_Active_Return DOUBLE,
    ISIN_Active_Return_Local DOUBLE,
    -- Risk & Weights
    ISIN_Weight DOUBLE,
    Class_Weight DOUBLE,
    Class_Target_Weight DOUBLE,
    Class_Drift DOUBLE,
    Sector_Weight DOUBLE,
    Monthly_Market_Value_Change_Pct DOUBLE,
    -- Tax & Harvesting
    ISIN_Harvestable_Loss DOUBLE,
    Tax_Harvesting_Priority_Score DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Cashflow_Efficiency_Analytics (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    -- Descriptors/Classifications
    Is_Surplus_Month BOOLEAN,
    Is_Investment_Target_Met BOOLEAN,
    -- Position Values
    Total_Income DOUBLE,
    Total_Cash_Income DOUBLE,
    Total_Non_Cash_Income DOUBLE,
    Total_Expense DOUBLE,
    Active_Income DOUBLE,
    Passive_Income DOUBLE,
    Dividend_Income DOUBLE,
    Interest_Income DOUBLE,
    Core_Expense DOUBLE,
    NonCore_Expense DOUBLE,
    Total_Cash_Expense DOUBLE,
    Total_Non_Cash_Expense DOUBLE,
    Total_Investment_Deployed DOUBLE,
    Total_Investment_Redeemed DOUBLE,
    Redemption_Gain_Loss_Value DOUBLE,
    Net_Investment_Flow DOUBLE,
    Gross_Surplus DOUBLE,
    Net_Surplus_After_Invest DOUBLE,
    Income_MoM_Delta DOUBLE,
    Expense_MoM_Delta DOUBLE,
    Investment_MoM_Delta DOUBLE,
    Trailing_3M_Avg_Income DOUBLE,
    Trailing_3M_Avg_Expense DOUBLE,
    Trailing_3M_Avg_Investment DOUBLE,
    -- Risk & Weights
    Savings_Rate_Pct DOUBLE,
    Investment_Rate_Pct DOUBLE,
    Active_Income_Share_Pct DOUBLE,
    Passive_Income_Share_Pct DOUBLE,
    Core_Expense_Share_Pct DOUBLE,
    NonCore_Expense_Share_Pct DOUBLE,
    Income_MoM_Pct DOUBLE,
    Expense_MoM_Pct DOUBLE,
    Trailing_3M_Avg_Savings_Rate DOUBLE,
    Trailing_3M_Avg_Investment_Rate DOUBLE,
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
    CURRENCY_ID TEXT,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Total_Quantity DOUBLE,
    Total_Stocks DOUBLE,
    -- Local/FX Values
    Total_Invested_Value_Local DOUBLE,
    Total_Current_Value_Local DOUBLE,
    Current_FX_Rate DOUBLE,
    Blended_FX_Buy_Rate DOUBLE,
    Currency_Appreciation_Pct DOUBLE,
    -- Absolute Returns
    Unrealized_PL DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    Forex_Contribution_Pct DOUBLE,
    Absolute_Return DOUBLE,
    -- Performance Returns
    CAGR DOUBLE,
    XIRR DOUBLE,
    XIRR_Local DOUBLE,
    FX_XIRR_Impact DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparisons
    BM_CAGR DOUBLE,
    BM_XIRR DOUBLE,
    BM_XIRR_Local DOUBLE,
    Active_Return DOUBLE,
    Active_Return_Local DOUBLE,
    Is_Lagging_Benchmark BIGINT,
    Outperforming_Lot_Ratio DOUBLE,
    -- Risk & Weights
    Max_Drawdown DOUBLE,
    Weight DOUBLE,
    -- Tax & Harvesting
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
    -- Descriptors/Classifications
    INSTRUMENT_CLASS TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Total_Quantity DOUBLE,
    Total_Stocks DOUBLE,
    -- Local/FX Values
    Total_Invested_Value_Local DOUBLE,
    Total_Current_Value_Local DOUBLE,
    Current_FX_Rate DOUBLE,
    Blended_FX_Buy_Rate DOUBLE,
    Currency_Appreciation_Pct DOUBLE,
    -- Absolute Returns
    Unrealized_PL DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    Forex_Contribution_Pct DOUBLE,
    Absolute_Return DOUBLE,
    -- Performance Returns
    XIRR DOUBLE,
    XIRR_Local DOUBLE,
    FX_XIRR_Impact DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparisons
    BM_XIRR DOUBLE,
    BM_XIRR_Local DOUBLE,
    Active_Return DOUBLE,
    Active_Return_Local DOUBLE,
    -- Risk & Weights
    Max_Drawdown DOUBLE,
    Weight DOUBLE,
    -- Tax & Harvesting
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
    -- Local/FX Values
    Total_Invested_Value_Local DOUBLE,
    Total_Current_Value_Local DOUBLE,
    Current_FX_Rate DOUBLE,
    Blended_FX_Buy_Rate DOUBLE,
    Currency_Appreciation_Pct DOUBLE,
    -- Absolute Returns
    Unrealized_PL DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    Forex_Contribution_Pct DOUBLE,
    Absolute_Return DOUBLE,
    -- Performance Returns
    XIRR DOUBLE,
    XIRR_Local DOUBLE,
    FX_XIRR_Impact DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparisons
    BM_XIRR DOUBLE,
    BM_XIRR_Local DOUBLE,
    Active_Return DOUBLE,
    Active_Return_Local DOUBLE,
    -- Risk & Weights
    Max_Drawdown DOUBLE,
    Weight DOUBLE,
    -- Tax & Harvesting
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
    -- Local/FX Values
    Total_Invested_Value_Local DOUBLE,
    Total_Current_Value_Local DOUBLE,
    Current_FX_Rate DOUBLE,
    Blended_FX_Buy_Rate DOUBLE,
    Currency_Appreciation_Pct DOUBLE,
    -- Absolute Returns
    Unrealized_PL DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    Forex_Contribution_Pct DOUBLE,
    Absolute_Return DOUBLE,
    -- Performance Returns
    XIRR DOUBLE,
    XIRR_Local DOUBLE,
    FX_XIRR_Impact DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparisons
    BM_XIRR DOUBLE,
    BM_XIRR_Local DOUBLE,
    Active_Return DOUBLE,
    Active_Return_Local DOUBLE,
    -- Risk & Weights
    Max_Drawdown DOUBLE,
    Weight DOUBLE,
    -- Tax & Harvesting
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
    -- Local/FX Values
    Total_Invested_Value_Local DOUBLE,
    Total_Current_Value_Local DOUBLE,
    Current_FX_Rate DOUBLE,
    Blended_FX_Buy_Rate DOUBLE,
    Currency_Appreciation_Pct DOUBLE,
    -- Absolute Returns
    Unrealized_PL DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    Forex_Contribution_Pct DOUBLE,
    Absolute_Return DOUBLE,
    -- Performance Returns
    XIRR DOUBLE,
    XIRR_Local DOUBLE,
    FX_XIRR_Impact DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparisons
    BM_XIRR DOUBLE,
    BM_XIRR_Local DOUBLE,
    Active_Return DOUBLE,
    Active_Return_Local DOUBLE,
    -- Risk & Weights
    Max_Drawdown DOUBLE,
    Weight DOUBLE,
    -- Tax & Harvesting
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
    -- Local/FX Values
    Total_Invested_Value_Local DOUBLE,
    Total_Current_Value_Local DOUBLE,
    Current_FX_Rate DOUBLE,
    Blended_FX_Buy_Rate DOUBLE,
    Currency_Appreciation_Pct DOUBLE,
    -- Absolute Returns
    Unrealized_PL DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    Forex_Contribution_Pct DOUBLE,
    Absolute_Return DOUBLE,
    -- Performance Returns
    XIRR DOUBLE,
    XIRR_Local DOUBLE,
    FX_XIRR_Impact DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparisons
    BM_XIRR DOUBLE,
    BM_XIRR_Local DOUBLE,
    Active_Return DOUBLE,
    Active_Return_Local DOUBLE,
    -- Risk & Weights
    Max_Drawdown DOUBLE,
    Weight DOUBLE,
    -- Tax & Harvesting
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
    -- Local/FX Values
    Total_Invested_Value_Local DOUBLE,
    Total_Current_Value_Local DOUBLE,
    Current_FX_Rate DOUBLE,
    Blended_FX_Buy_Rate DOUBLE,
    Currency_Appreciation_Pct DOUBLE,
    -- Absolute Returns
    Unrealized_PL DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    Forex_Contribution_Pct DOUBLE,
    Absolute_Return DOUBLE,
    -- Performance Returns
    XIRR DOUBLE,
    XIRR_Local DOUBLE,
    FX_XIRR_Impact DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparisons
    BM_XIRR DOUBLE,
    BM_XIRR_Local DOUBLE,
    Active_Return DOUBLE,
    Active_Return_Local DOUBLE,
    -- Risk & Weights
    Max_Drawdown DOUBLE,
    Weight DOUBLE,
    -- Tax & Harvesting
    Unrealized_Gain DOUBLE,
    Unrealized_Loss DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Investment_By_Geo (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    GEO TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Total_Quantity DOUBLE,
    Total_Stocks DOUBLE,
    -- Local/FX Values
    Total_Invested_Value_Local DOUBLE,
    Total_Current_Value_Local DOUBLE,
    Current_FX_Rate DOUBLE,
    Blended_FX_Buy_Rate DOUBLE,
    Currency_Appreciation_Pct DOUBLE,
    -- Absolute Returns
    Unrealized_PL DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    Forex_Contribution_Pct DOUBLE,
    Absolute_Return DOUBLE,
    -- Performance Returns
    XIRR DOUBLE,
    XIRR_Local DOUBLE,
    FX_XIRR_Impact DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparisons
    BM_XIRR DOUBLE,
    BM_XIRR_Local DOUBLE,
    Active_Return DOUBLE,
    Active_Return_Local DOUBLE,
    -- Risk & Weights
    Max_Drawdown DOUBLE,
    Weight DOUBLE,
    -- Tax & Harvesting
    Unrealized_Gain DOUBLE,
    Unrealized_Loss DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Investment_By_Country (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    COUNTRY TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Total_Quantity DOUBLE,
    Total_Stocks DOUBLE,
    -- Local/FX Values
    Total_Invested_Value_Local DOUBLE,
    Total_Current_Value_Local DOUBLE,
    Current_FX_Rate DOUBLE,
    Blended_FX_Buy_Rate DOUBLE,
    Currency_Appreciation_Pct DOUBLE,
    -- Absolute Returns
    Unrealized_PL DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    Forex_Contribution_Pct DOUBLE,
    Absolute_Return DOUBLE,
    -- Performance Returns
    XIRR DOUBLE,
    XIRR_Local DOUBLE,
    FX_XIRR_Impact DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparisons
    BM_XIRR DOUBLE,
    BM_XIRR_Local DOUBLE,
    Active_Return DOUBLE,
    Active_Return_Local DOUBLE,
    -- Risk & Weights
    Max_Drawdown DOUBLE,
    Weight DOUBLE,
    -- Tax & Harvesting
    Unrealized_Gain DOUBLE,
    Unrealized_Loss DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Investment_By_Currency (
    -- Identifiers
    Closing_Date DATE NOT NULL,
    CURRENCY_ID TEXT NOT NULL,
    -- Position Values
    Total_Invested_Value DOUBLE,
    Total_Current_Value DOUBLE,
    Total_Quantity DOUBLE,
    Total_Stocks DOUBLE,
    -- Local/FX Values
    Total_Invested_Value_Local DOUBLE,
    Total_Current_Value_Local DOUBLE,
    Current_FX_Rate DOUBLE,
    Blended_FX_Buy_Rate DOUBLE,
    Currency_Appreciation_Pct DOUBLE,
    -- Absolute Returns
    Unrealized_PL DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    Forex_Contribution_Pct DOUBLE,
    Absolute_Return DOUBLE,
    -- Performance Returns
    XIRR DOUBLE,
    XIRR_Local DOUBLE,
    FX_XIRR_Impact DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparisons
    BM_XIRR DOUBLE,
    BM_XIRR_Local DOUBLE,
    Active_Return DOUBLE,
    Active_Return_Local DOUBLE,
    -- Risk & Weights
    Max_Drawdown DOUBLE,
    Weight DOUBLE,
    -- Tax & Harvesting
    Unrealized_Gain DOUBLE,
    Unrealized_Loss DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE
);

CREATE TABLE IF NOT EXISTS gold.Cashflow_Activity_Summary (
    -- Identifiers
    MONTH_START_DATE DATE,
    MONTH_END_DATE DATE,
    YEAR_MONTH TEXT,
    -- Position Values
    Opening_Cash_Balance DOUBLE,
    Closing_Cash_Balance DOUBLE,
    Net_Cash_Movement DOUBLE,
    Cash_Inflow_Operating DOUBLE,
    Cash_Outflow_Operating DOUBLE,
    Net_Cashflow_Operating DOUBLE,
    Cash_Inflow_Investing DOUBLE,
    Cash_Outflow_Investing DOUBLE,
    Net_Cashflow_Investing DOUBLE,
    Cash_Inflow_Financing DOUBLE,
    Cash_Outflow_Financing DOUBLE,
    Net_Cashflow_Financing DOUBLE,
    Internal_Transfer_Inflow DOUBLE,
    Internal_Transfer_Outflow DOUBLE,
    Net_Internal_Transfers DOUBLE,
    Total_Cash_Expenses DOUBLE,
    Total_Non_Cash_Expenses DOUBLE,
    Total_Cash_Inflow DOUBLE,
    Total_Cash_Outflow DOUBLE,
    Calculated_Net_Cashflow DOUBLE,
    Unreconciled_Difference DOUBLE
);
"""
