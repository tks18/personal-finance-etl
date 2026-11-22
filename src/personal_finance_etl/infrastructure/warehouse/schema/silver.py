"""Declarative DuckDB Silver layer schema definitions.

Owns
----
- Declarative DuckDB DDL statements for analytical dimensions and facts in the Silver layer.
- Table schemas for calendar, categories, assets, currency FX, ledger facts, investment facts, and tax events.

Does not own
-------------
- Execution of DDL or warehouse loading (owned by infrastructure.warehouse.silver and connection).
- Control Plane SQLite schemas (owned by control_plane.py).
- Gold presentation layer schemas (owned by gold.py).
"""

from __future__ import annotations

SILVER_DDL = """
CREATE TABLE IF NOT EXISTS silver.dim_calendar (
    -- Identifiers
    Date DATE PRIMARY KEY,
    -- Descriptors/Classifications
    Day BIGINT,
    Day_Name TEXT,
    Day_Name_Short TEXT,
    Day_Ordinal BIGINT,
    Day_Ordinal_Name TEXT,
    Weekday BIGINT,
    IS_WEEKEND BIGINT,
    Week BIGINT,
    Week_Ordinal BIGINT,
    Week_Ordinal_Name TEXT,
    Week_Name TEXT,
    Week_Year TEXT,
    Week_Name_Year TEXT,
    Start_of_Week DATE,
    End_of_Week DATE,
    Month BIGINT,
    Month_Name TEXT,
    Month_Name_Short TEXT,
    Month_Year TEXT,
    Short_Month_Year TEXT,
    V_Short_Month_Year TEXT,
    Month_Ordinal BIGINT,
    Start_of_Month DATE,
    End_of_Month DATE,
    Days_in_Month BIGINT,
    Month_Progress_Pct DOUBLE,
    Quarter BIGINT,
    Quarter_Name TEXT,
    Quarter_Year TEXT,
    Quarter_Ordinal BIGINT,
    Start_of_Quarter DATE,
    End_of_Quarter DATE,
    Year BIGINT,
    Days_in_Year BIGINT,
    Year_Progress_Pct DOUBLE,
    Financial_Year TEXT,
    FY_Year BIGINT,
    FY_Month BIGINT,
    FY_Month_Ordinal BIGINT,
    FY_Quarter BIGINT,
    FY_Quarter_Name TEXT,
    FY_Quarter_Year TEXT,
    FY_Quarter_Ordinal BIGINT,
    FY_Start_of_Month DATE,
    FY_End_of_Month DATE,
    FY_Start_of_Quarter DATE,
    FY_End_of_Quarter DATE,
    -- Flags
    Is_Last_Day_Of_Month BOOLEAN,
    Is_Last_Day_Of_Quarter BOOLEAN,
    Is_Last_Day_Of_Year BOOLEAN,
    Is_Last_Day_Of_FY BOOLEAN,
    Is_Quarter_End_Month BOOLEAN,
    Is_Tax_Harvesting_Season BOOLEAN,
    Is_Current_Month BOOLEAN,
    Is_Previous_Month BOOLEAN,
    Is_Current_Quarter BOOLEAN,
    Is_Previous_Quarter BOOLEAN,
    Is_Current_Year BOOLEAN,
    Is_Previous_Year BOOLEAN,
    Is_Current_FY BOOLEAN,
    Is_YTD BOOLEAN,
    Is_FY_YTD BOOLEAN,
    Is_Future_Date BOOLEAN
);

CREATE TABLE IF NOT EXISTS silver.dim_income_category (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    -- Descriptors/Classifications
    CATEGORY_NAME TEXT,
    CATEGORY_NAME_SHORT TEXT
);

CREATE TABLE IF NOT EXISTS silver.dim_income_subcategory (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    CATEGORY_ID TEXT,
    -- Descriptors/Classifications
    CATEGORY_NAME TEXT,
    CATEGORY_GROUPS TEXT,
    Is_Active_Income BOOLEAN,
    Is_Passive_Income BOOLEAN,
    Is_Dividend_Income BOOLEAN,
    Is_Interest_Income BOOLEAN,
    Is_Non_Cash_Income BOOLEAN,
    Is_Investment_Exclusion BOOLEAN,
    Is_Tax_Credits BOOLEAN,
    Tax_Income_Head TEXT,
    Tax_Sub_Head TEXT,
    Taxability TEXT,
    Tax_Method TEXT,
    FOREIGN KEY (CATEGORY_ID) REFERENCES silver.dim_income_category(UID)
);

CREATE TABLE IF NOT EXISTS silver.dim_expense_category (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    -- Descriptors/Classifications
    CATEGORY_NAME TEXT
);

CREATE TABLE IF NOT EXISTS silver.dim_expense_subcategory (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    CATEGORY_ID TEXT,
    -- Descriptors/Classifications
    CATEGORY_NAME TEXT,
    Is_Core_Expense BOOLEAN,
    FOREIGN KEY(CATEGORY_ID) REFERENCES silver.dim_expense_category(UID)
);

CREATE TABLE IF NOT EXISTS silver.dim_asset_category (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    -- Descriptors/Classifications
    ASSET_GROUP TEXT,
    TYPE BIGINT,
    ledger_role TEXT,
    cashflow_activity_type TEXT,
    settlement_timing TEXT,
    Is_Digital_Asset BOOLEAN,
    is_cash_pool BOOLEAN,
    is_non_cash_pnl BOOLEAN
);

CREATE TABLE IF NOT EXISTS silver.dim_asset_subcategory (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    ASSET_GROUP_ID TEXT,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    ASSET_NAME TEXT,
    ASSET_DESCRIPTION TEXT,
    NOTES TEXT,
    ledger_role TEXT,
    cashflow_activity_type TEXT,
    settlement_timing TEXT,
    Is_Liquid BOOLEAN,
    Is_Illiquid BOOLEAN,
    Is_Digital_Asset BOOLEAN,
    is_cash_pool BOOLEAN,
    is_non_cash_pnl BOOLEAN,
    FOREIGN KEY(ASSET_GROUP_ID) REFERENCES silver.dim_asset_category(UID)
);

CREATE TABLE IF NOT EXISTS silver.dim_currency (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    -- Descriptors/Classifications
    CURRENCY_NAME TEXT,
    ISO TEXT,
    Target_Currency_Code TEXT,
    yF_Ticker TEXT,
    SYMBOL TEXT,
    Is_Active BOOLEAN
);

CREATE TABLE IF NOT EXISTS silver.fact_currency_fx_rates (
    -- Identifiers
    Date DATE NOT NULL,
    Currency_ID TEXT NOT NULL,
    -- Descriptors/Classifications
    Currency_Code TEXT NOT NULL,
    Target_Currency_Code TEXT NOT NULL,
    yF_Ticker TEXT NOT NULL,
    -- Local/FX Values
    FX_Rate DOUBLE NOT NULL,
    -- Provenance
    Data_Provider TEXT,
    Extraction_Time TEXT,
    Requested_Start DATE,
    Requested_End DATE,
    Is_Closure_Gap BOOLEAN,
    Is_Imputed BOOLEAN,
    First_Observation_Date DATE,
    FOREIGN KEY(Date) REFERENCES silver.dim_calendar(Date),
    FOREIGN KEY(Currency_ID) REFERENCES silver.dim_currency(UID)
);

CREATE TABLE IF NOT EXISTS silver.fact_income_transactions (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    DATE DATE NOT NULL,
    ASSET_ID TEXT NOT NULL,
    CATEGORY_ID TEXT NOT NULL,
    CURRENCY_ID TEXT,
    TO_ASSET_ID TEXT,
    TRANSFER_UID TEXT,
    -- Descriptors/Classifications
    TIME TEXT,
    DESCRIPTION TEXT,
    PAID TEXT,
    TRANSACTION_TYPE BIGINT,
    Is_Active_Income BOOLEAN,
    Is_Dividend_Income BOOLEAN,
    Is_Interest_Income BOOLEAN,
    Is_Non_Cash_Income BOOLEAN,
    -- Position Values
    BASE_AMOUNT DOUBLE,
    AMOUNT_ACCOUNT DOUBLE,
    -- Local/FX Values
    LOCAL_AMOUNT DOUBLE,
    EXCH_RATE DOUBLE,
    FOREIGN KEY(CATEGORY_ID) REFERENCES silver.dim_income_subcategory(UID),
    FOREIGN KEY(ASSET_ID) REFERENCES silver.dim_asset_subcategory(UID),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.dim_currency(UID),
    FOREIGN KEY(DATE) REFERENCES silver.dim_calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.fact_expense_transactions (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    DATE DATE NOT NULL,
    ASSET_ID TEXT NOT NULL,
    CATEGORY_ID TEXT NOT NULL,
    CURRENCY_ID TEXT,
    TO_ASSET_ID TEXT,
    TRANSFER_UID TEXT,
    -- Descriptors/Classifications
    TIME TEXT,
    DESCRIPTION TEXT,
    PAID TEXT,
    TRANSACTION_TYPE BIGINT,
    Is_Core_Expense BOOLEAN,
    -- Position Values
    BASE_AMOUNT DOUBLE,
    AMOUNT_ACCOUNT DOUBLE,
    -- Local/FX Values
    LOCAL_AMOUNT DOUBLE,
    EXCH_RATE DOUBLE,
    FOREIGN KEY(CATEGORY_ID) REFERENCES silver.dim_expense_subcategory(UID),
    FOREIGN KEY(ASSET_ID) REFERENCES silver.dim_asset_subcategory(UID),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.dim_currency(UID),
    FOREIGN KEY(DATE) REFERENCES silver.dim_calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.fact_transfer_transactions (
    -- Identifiers
    UID TEXT PRIMARY KEY,
    DATE DATE NOT NULL,
    ADJUSTED_DATE_FOR_ANALYSIS DATE,
    ASSET_ID TEXT NOT NULL,
    TO_ASSET_ID TEXT,
    CATEGORY_ID TEXT,
    CURRENCY_ID TEXT,
    TRANSFER_UID TEXT,
    -- Descriptors/Classifications
    TIME TEXT,
    DESCRIPTION TEXT,
    PAID TEXT,
    TRANSACTION_TYPE BIGINT,
    TRANSFER_TYPE TEXT,
    -- Position Values
    BASE_AMOUNT DOUBLE,
    AMOUNT_ACCOUNT DOUBLE,
    AMOUNT_PROPER DOUBLE,
    -- Local/FX Values
    LOCAL_AMOUNT DOUBLE,
    EXCH_RATE DOUBLE,
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.dim_currency(UID),
    FOREIGN KEY(ASSET_ID) REFERENCES silver.dim_asset_subcategory(UID),
    FOREIGN KEY(TO_ASSET_ID) REFERENCES silver.dim_asset_subcategory(UID),
    FOREIGN KEY(DATE) REFERENCES silver.dim_calendar(Date),
    FOREIGN KEY(ADJUSTED_DATE_FOR_ANALYSIS) REFERENCES silver.dim_calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.fact_opening_balances (
    -- Identifiers
    ZASSETUID TEXT PRIMARY KEY,
    -- Local/FX Values
    ZAMOUNTACCOUNT DOUBLE,
    -- Temporal
    ZTXDATESTR DATE,
    ZUTIME BIGINT,
    FOREIGN KEY(ZASSETUID) REFERENCES silver.dim_asset_subcategory(UID),
    FOREIGN KEY(ZTXDATESTR) REFERENCES silver.dim_calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.dim_benchmark_master (
    -- Identifiers
    ID TEXT PRIMARY KEY,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    Benchmark_Name TEXT,
    yF_Ticker TEXT
);

CREATE TABLE IF NOT EXISTS silver.dim_instrument_master (
    -- Identifiers
    ISIN TEXT PRIMARY KEY,
    CATEGORY_ID TEXT,
    BENCHMARK_ID TEXT,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    INSTRUMENT_NAME TEXT,
    INSTRUMENT_HOUSE TEXT,
    INSTRUMENT_CLASS TEXT NOT NULL,
    INSTRUMENT_TYPE TEXT,
    INSTRUMENT_SUBTYPE TEXT,
    SECTOR TEXT,
    INDUSTRY TEXT,
    COUNTRY TEXT,
    GEO TEXT,
    GEO_SUBTYPE TEXT,
    YAHOO_TICKER TEXT,
    -- Tax & Harvesting
    TAX_TYPE TEXT NOT NULL,
    TAX_SUBTYPE TEXT,
    FOREIGN KEY(CATEGORY_ID) REFERENCES silver.dim_asset_subcategory(UID),
    FOREIGN KEY(BENCHMARK_ID) REFERENCES silver.dim_benchmark_master(ID),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.dim_currency(UID)
);

CREATE TABLE IF NOT EXISTS silver.ref_financial_year_parameters (
    -- Identifiers
    FY TEXT PRIMARY KEY,
    FY_Start_Date DATE,
    FY_End_Date DATE,
    Debt_MF_Cutoff_Date DATE,
    -- Risk & Weights
    Inflation_Rate DOUBLE,
    Risk_Free_Rate DOUBLE,
    -- Tax & Harvesting
    Equity_Listed_LTCG DOUBLE,
    Equity_Listed_STCG DOUBLE,
    Equity_Unlisted_LTCG DOUBLE,
    Equity_Unlisted_STCG DOUBLE,
    Equity_LTCG_Exemption BIGINT,
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
    Estimated_Ordinary_Income_Tax_Rate DOUBLE,
    -- Descriptors/Classifications
    Remarks TEXT,
    FOREIGN KEY(FY_Start_Date) REFERENCES silver.dim_calendar(Date)
);

CREATE TABLE IF NOT EXISTS silver.fact_investment_market_data (
    -- Identifiers
    Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    __file_category__ TEXT,
    -- Position Values
    Quantity DOUBLE,
    Closing_Price DOUBLE,
    Buy_Price DOUBLE,
    Closing_Value DOUBLE,
    Buy_Value DOUBLE,
    -- Local/FX Values
    Closing_Price_Local DOUBLE,
    Buy_Price_Local DOUBLE,
    Closing_Value_Local DOUBLE,
    Buy_Value_Local DOUBLE,
    FX_Rate DOUBLE,
    -- Absolute Returns
    Unit_PnL DOUBLE,
    Total_PnL DOUBLE,
    -- Provenance
    Data_Provider TEXT,
    Extraction_Time TEXT,
    Requested_Start DATE,
    Requested_End DATE,
    Is_Closure_Gap BOOLEAN,
    Is_Imputed BOOLEAN,
    FOREIGN KEY(Date) REFERENCES silver.dim_calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES silver.dim_instrument_master(ISIN),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.dim_currency(UID)
);

CREATE TABLE IF NOT EXISTS silver.fact_investment_purchases (
    -- Identifiers
    Purchase_ID TEXT PRIMARY KEY,
    Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    __file_category__ TEXT,
    -- Position Values
    Quantity DOUBLE,
    Price DOUBLE,
    Value DOUBLE,
    -- Local/FX Values
    Price_Local DOUBLE,
    Value_Local DOUBLE,
    FX_Rate DOUBLE,
    FOREIGN KEY(Date) REFERENCES silver.dim_calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES silver.dim_instrument_master(ISIN),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.dim_currency(UID)
);

CREATE TABLE IF NOT EXISTS silver.fact_investment_sales (
    -- Identifiers
    Sale_ID TEXT PRIMARY KEY,
    Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    __file_category__ TEXT,
    -- Position Values
    Quantity DOUBLE,
    Sell_Price DOUBLE,
    Sell_Value DOUBLE,
    Buy_Price DOUBLE,
    Buy_Value DOUBLE,
    -- Local/FX Values
    Sell_Price_Local DOUBLE,
    Sell_Value_Local DOUBLE,
    Buy_Price_Local DOUBLE,
    Buy_Value_Local DOUBLE,
    FX_Rate DOUBLE,
    -- Absolute Returns
    Unit_PnL DOUBLE,
    Total_PnL DOUBLE,
    FOREIGN KEY(Date) REFERENCES silver.dim_calendar(Date),
    FOREIGN KEY(ISIN) REFERENCES silver.dim_instrument_master(ISIN),
    FOREIGN KEY(CURRENCY_ID) REFERENCES silver.dim_currency(UID)
);

CREATE TABLE IF NOT EXISTS silver.fact_investment_benchmark_data (
    -- Identifiers
    Date DATE,
    ID TEXT,
    CURRENCY_ID TEXT,
    -- Descriptors/Classifications
    Benchmark_Name TEXT,
    yF_Ticker TEXT,
    -- Position Values
    Close DOUBLE,
    -- Provenance
    Data_Provider TEXT,
    Extraction_Time TEXT,
    Requested_Start DATE,
    Requested_End DATE,
    Is_Closure_Gap BOOLEAN,
    Is_Imputed BOOLEAN,
    FOREIGN KEY(Date) REFERENCES silver.dim_calendar(Date),
    FOREIGN KEY(ID) REFERENCES silver.dim_benchmark_master(ID)
);

CREATE TABLE IF NOT EXISTS silver.fact_investment_lot_analytics (
    -- Identifiers
    Lot_ID TEXT NOT NULL,
    Closing_Date DATE NOT NULL,
    ISIN TEXT NOT NULL,
    CURRENCY_ID TEXT,
    Buy_Date DATE,
    Purchase_ID TEXT,
    -- Descriptors/Classifications
    Lot_Source_Type TEXT NOT NULL,
    BENCHMARK_ID TEXT,
    TAX_TYPE TEXT,
    TAX_SUBTYPE TEXT,
    -- Position Values
    Quantity DOUBLE,
    Execution_Residual DOUBLE,  -- Units ordered but not yet settled at this snapshot date
    Buy_Price DOUBLE,
    Market_Price DOUBLE,
    Buy_Value DOUBLE,
    Close_Value DOUBLE,
    -- Local/FX Values
    Buy_Value_Local DOUBLE,
    Close_Value_Local DOUBLE,
    Blended_FX_Buy_Rate DOUBLE,
    Buy_Price_Local DOUBLE,          -- Acquisition price in instrument native currency
    Market_Price_Local DOUBLE,       -- Market price in instrument native currency at snapshot
    FX_Rate_Buy DOUBLE,              -- FX rate (native → INR) at acquisition date
    FX_Rate_Snap DOUBLE,             -- FX rate (native → INR) at snapshot date
    Currency_Appreciation_Pct DOUBLE,
    -- Absolute Returns
    "P/L" DOUBLE,
    Absolute_Return DOUBLE,
    Absolute_Return_Local DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    Forex_Contribution_Pct DOUBLE,
    Asset_Return_Pct DOUBLE,
    Forex_Return_Pct DOUBLE,
    -- Performance Returns
    Lot_CAGR DOUBLE,
    Lot_CAGR_Status TEXT,       -- VALID | INVALID_INPUT | UNDEFINED | COMPUTATION_ERROR
    Lot_CAGR_Local DOUBLE,
    CAGR DOUBLE,
    CAGR_Status TEXT,           -- VALID | INVALID_INPUT | UNDEFINED | COMPUTATION_ERROR
    XIRR DOUBLE,
    XIRR_Status TEXT,           -- VALID | INVALID_INPUT | UNDEFINED | NON_CONVERGENT
    XIRR_Local DOUBLE,
    FX_XIRR_Impact DOUBLE,
    After_Tax_XIRR DOUBLE,
    -- Benchmark Comparisons
    BM_Buy_Price DOUBLE,
    BM_Market_Price DOUBLE,
    Lot_BM_Return DOUBLE,
    Lot_BM_CAGR DOUBLE,
    Lot_BM_CAGR_Status TEXT,    -- VALID | INVALID_INPUT | UNDEFINED | COMPUTATION_ERROR
    Lot_BM_CAGR_Local DOUBLE,
    BM_CAGR DOUBLE,
    BM_CAGR_Status TEXT,        -- VALID | INVALID_INPUT | UNDEFINED | COMPUTATION_ERROR
    BM_XIRR DOUBLE,
    BM_XIRR_Local DOUBLE,
    Active_Return DOUBLE,
    Active_Return_Local DOUBLE,
    Lot_Alpha DOUBLE,
    Is_Lagging_Benchmark BIGINT,
    -- Risk & Weights
    Max_Drawdown DOUBLE,
    Lot_Weight DOUBLE,
    Portfolio_Weight DOUBLE,
    Outperforming_Lot_Ratio DOUBLE,
    Dietz_Day_Weight DOUBLE,
    -- Tax & Harvesting
    Age_Days BIGINT,
    LTCG_Threshold_Days BIGINT,
    Days_To_LTCG BIGINT,
    Holding_Type TEXT,
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
    FY TEXT,
    FY_Realized_LTCG DOUBLE,
    FY_Realized_STCG DOUBLE,
    FY_Realized_Gain DOUBLE,
    FY_Realized_LTCL DOUBLE,
    FY_Realized_STCL DOUBLE,
    FY_Realized_Loss DOUBLE,
    FY_Realized_Net_PnL DOUBLE,
    Equity_LTCG_Exemption BIGINT,
    Stepup_Eligible BIGINT,
    Can_Harvest_Loss BOOLEAN,
    Harvest_Recommendation TEXT,
    PRIMARY KEY (Lot_ID, Closing_Date)
);

CREATE TABLE IF NOT EXISTS silver.fact_investment_realized_events (
    Realized_Event_ID TEXT PRIMARY KEY,
    Sale_ID TEXT NOT NULL,
    Lot_ID TEXT NOT NULL,
    Purchase_ID TEXT,
    ISIN TEXT,
    Acquisition_Date DATE,
    Disposal_Date DATE,
    FY TEXT,
    Quantity_Disposed DOUBLE,
    Acquisition_Price DOUBLE,
    Disposed_Cost_Basis DOUBLE,
    Sale_Price DOUBLE,
    Sale_Proceeds DOUBLE,
    Realized_Gain_Loss DOUBLE,
    Holding_Type TEXT,
    Tax_Type TEXT,
    Tax_Subtype TEXT,
    Lot_Source_Type TEXT,
    Currency_ID TEXT,
    Asset_PnL_Local DOUBLE,
    Asset_PnL DOUBLE,
    Forex_PnL DOUBLE,
    -- Rate resolved from macro CSV at disposal time (same source as snapshot.py LTCG_Tax_If_Sold).
    -- NULL for CHECK_REQUIRED (RECONCILIATION) lots — no reliable rate can be assigned.
    Applied_Rate DOUBLE,
    Estimated_Tax DOUBLE,
    UNIQUE(Sale_ID, Lot_ID)
);

CREATE TABLE IF NOT EXISTS silver.fact_investment_reconciliation_events (
    Reconciliation_Group_ID TEXT NOT NULL,
    Reconciliation_Event_ID TEXT PRIMARY KEY,
    Run_ID TEXT,
    ISIN TEXT NOT NULL,
    Reconciliation_Date DATE NOT NULL,
    Lot_ID TEXT,
    Purchase_ID TEXT,
    Adjustment_Type TEXT,
    Reason TEXT,
    Broker_Quantity DOUBLE,
    Reconstructed_Quantity DOUBLE,
    Quantity_Adjustment DOUBLE,
    Broker_Cost_Basis DOUBLE,
    Reconstructed_Cost_Basis DOUBLE,
    Cost_Basis_Adjustment DOUBLE,
    Original_Unit_Cost DOUBLE,
    Adjusted_Unit_Cost DOUBLE
);

CREATE TABLE IF NOT EXISTS silver.fact_tax_events (
    Tax_Event_ID TEXT PRIMARY KEY,
    FY TEXT NOT NULL,
    Event_Date DATE NOT NULL,
    Source_Type TEXT NOT NULL,
    Source_ID TEXT NOT NULL,
    Income_Head TEXT NOT NULL,
    Tax_Sub_Head TEXT NOT NULL,
    Amount_INR DOUBLE NOT NULL,
    Applied_Rate DOUBLE,
    Estimated_Tax DOUBLE,
    CURRENCY_ID TEXT,
    Tax_Status TEXT NOT NULL,
    Tax_Status_Reason TEXT,
    ISIN TEXT,
    Lot_ID TEXT,
    UNIQUE(Source_Type, Source_ID, Tax_Sub_Head)
);
"""
