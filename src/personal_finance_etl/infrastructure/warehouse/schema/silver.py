"""Declarative DuckDB Silver layer schema definitions and plan-aware DDL generator.

Owns
----
- Declarative column specifications for all 24 analytical dimensions and facts in the Silver layer.
- Plan-aware DDL generator dynamically creating active tables with active column subsets.
- Column pruning engine omitting inactive capability columns from physical Silver tables.

Does not own
-------------
- Execution of DDL or warehouse loading (owned by infrastructure.warehouse.silver and connection).
- Control Plane SQLite schemas (owned by control_plane.py).
- Gold presentation layer schemas (owned by gold.py).
"""

from __future__ import annotations

from personal_finance_etl.contracts.capabilities import (
    CAPABILITY_COLUMN_INVENTORY,
    CapabilityId,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.infrastructure.warehouse.contracts import DATA_CONTRACT_REGISTRY

__all__ = ["SILVER_DDL", "SILVER_TABLE_SCHEMAS", "generate_silver_ddl"]

_SILVER_COLUMN_CAPABILITY_MAP: dict[tuple[DatasetId, str], CapabilityId] = {}
for _cap_id, _ds_map in CAPABILITY_COLUMN_INVENTORY.items():
    for _ds_id, _cols in _ds_map.items():
        for _col in _cols:
            _SILVER_COLUMN_CAPABILITY_MAP[(_ds_id, _col)] = _cap_id

SILVER_TABLE_SCHEMAS: dict[
    DatasetId,
    tuple[tuple[tuple[str, str], ...], tuple[tuple[str, DatasetId | None], ...]],
] = {
    DatasetId.COMMON_CALENDAR: (
        (
            ("Date", "Date DATE PRIMARY KEY"),
            ("Day", "Day BIGINT"),
            ("Day_Name", "Day_Name TEXT"),
            ("Day_Name_Short", "Day_Name_Short TEXT"),
            ("Day_Ordinal", "Day_Ordinal BIGINT"),
            ("Day_Ordinal_Name", "Day_Ordinal_Name TEXT"),
            ("Weekday", "Weekday BIGINT"),
            ("IS_WEEKEND", "IS_WEEKEND BIGINT"),
            ("Week", "Week BIGINT"),
            ("Week_Ordinal", "Week_Ordinal BIGINT"),
            ("Week_Ordinal_Name", "Week_Ordinal_Name TEXT"),
            ("Week_Name", "Week_Name TEXT"),
            ("Week_Year", "Week_Year TEXT"),
            ("Week_Name_Year", "Week_Name_Year TEXT"),
            ("Start_of_Week", "Start_of_Week DATE"),
            ("End_of_Week", "End_of_Week DATE"),
            ("Month", "Month BIGINT"),
            ("Month_Name", "Month_Name TEXT"),
            ("Month_Name_Short", "Month_Name_Short TEXT"),
            ("Month_Year", "Month_Year TEXT"),
            ("Short_Month_Year", "Short_Month_Year TEXT"),
            ("V_Short_Month_Year", "V_Short_Month_Year TEXT"),
            ("Month_Ordinal", "Month_Ordinal BIGINT"),
            ("Start_of_Month", "Start_of_Month DATE"),
            ("End_of_Month", "End_of_Month DATE"),
            ("Days_in_Month", "Days_in_Month BIGINT"),
            ("Month_Progress_Pct", "Month_Progress_Pct DOUBLE"),
            ("Quarter", "Quarter BIGINT"),
            ("Quarter_Name", "Quarter_Name TEXT"),
            ("Quarter_Year", "Quarter_Year TEXT"),
            ("Quarter_Ordinal", "Quarter_Ordinal BIGINT"),
            ("Start_of_Quarter", "Start_of_Quarter DATE"),
            ("End_of_Quarter", "End_of_Quarter DATE"),
            ("Year", "Year BIGINT"),
            ("Days_in_Year", "Days_in_Year BIGINT"),
            ("Year_Progress_Pct", "Year_Progress_Pct DOUBLE"),
            ("Financial_Year", "Financial_Year TEXT"),
            ("FY_Year", "FY_Year BIGINT"),
            ("FY_Month", "FY_Month BIGINT"),
            ("FY_Month_Ordinal", "FY_Month_Ordinal BIGINT"),
            ("FY_Quarter", "FY_Quarter BIGINT"),
            ("FY_Quarter_Name", "FY_Quarter_Name TEXT"),
            ("FY_Quarter_Year", "FY_Quarter_Year TEXT"),
            ("FY_Quarter_Ordinal", "FY_Quarter_Ordinal BIGINT"),
            ("FY_Start_of_Month", "FY_Start_of_Month DATE"),
            ("FY_End_of_Month", "FY_End_of_Month DATE"),
            ("FY_Start_of_Quarter", "FY_Start_of_Quarter DATE"),
            ("FY_End_of_Quarter", "FY_End_of_Quarter DATE"),
            ("Is_Last_Day_Of_Month", "Is_Last_Day_Of_Month BOOLEAN"),
            ("Is_Last_Day_Of_Quarter", "Is_Last_Day_Of_Quarter BOOLEAN"),
            ("Is_Last_Day_Of_Year", "Is_Last_Day_Of_Year BOOLEAN"),
            ("Is_Last_Day_Of_FY", "Is_Last_Day_Of_FY BOOLEAN"),
            ("Is_Quarter_End_Month", "Is_Quarter_End_Month BOOLEAN"),
            ("Is_Tax_Harvesting_Season", "Is_Tax_Harvesting_Season BOOLEAN"),
            ("Is_Current_Month", "Is_Current_Month BOOLEAN"),
            ("Is_Previous_Month", "Is_Previous_Month BOOLEAN"),
            ("Is_Current_Quarter", "Is_Current_Quarter BOOLEAN"),
            ("Is_Previous_Quarter", "Is_Previous_Quarter BOOLEAN"),
            ("Is_Current_Year", "Is_Current_Year BOOLEAN"),
            ("Is_Previous_Year", "Is_Previous_Year BOOLEAN"),
            ("Is_Current_FY", "Is_Current_FY BOOLEAN"),
            ("Is_YTD", "Is_YTD BOOLEAN"),
            ("Is_FY_YTD", "Is_FY_YTD BOOLEAN"),
            ("Is_Future_Date", "Is_Future_Date BOOLEAN"),
        ),
        (),
    ),
    DatasetId.WEALTH_INCOME_CATEGORY: (
        (
            ("UID", "UID TEXT PRIMARY KEY"),
            ("CATEGORY_NAME", "CATEGORY_NAME TEXT"),
            ("CATEGORY_NAME_SHORT", "CATEGORY_NAME_SHORT TEXT"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (),
    ),
    DatasetId.WEALTH_INCOME_SUBCATEGORY: (
        (
            ("UID", "UID TEXT PRIMARY KEY"),
            ("CATEGORY_ID", "CATEGORY_ID TEXT"),
            ("CATEGORY_NAME", "CATEGORY_NAME TEXT"),
            ("Is_Active_Income", "Is_Active_Income BOOLEAN"),
            ("Is_Passive_Income", "Is_Passive_Income BOOLEAN"),
            ("Is_Dividend_Income", "Is_Dividend_Income BOOLEAN"),
            ("Is_Interest_Income", "Is_Interest_Income BOOLEAN"),
            ("Is_Non_Cash_Income", "Is_Non_Cash_Income BOOLEAN"),
            ("Is_Investment_Exclusion", "Is_Investment_Exclusion BOOLEAN"),
            ("Is_Tax_Credits", "Is_Tax_Credits BOOLEAN"),
            ("artifact_id", "artifact_id TEXT"),
            ("Tax_Income_Head", "Tax_Income_Head TEXT"),
            ("Tax_Sub_Head", "Tax_Sub_Head TEXT"),
            ("Taxability", "Taxability TEXT"),
            ("Tax_Method", "Tax_Method TEXT"),
        ),
        (
            (
                "FOREIGN KEY (CATEGORY_ID) REFERENCES silver.wealth_income_category(UID)",
                DatasetId.WEALTH_INCOME_CATEGORY,
            ),
        ),
    ),
    DatasetId.WEALTH_EXPENSE_CATEGORY: (
        (
            ("UID", "UID TEXT PRIMARY KEY"),
            ("CATEGORY_NAME", "CATEGORY_NAME TEXT"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (),
    ),
    DatasetId.WEALTH_EXPENSE_SUBCATEGORY: (
        (
            ("UID", "UID TEXT PRIMARY KEY"),
            ("CATEGORY_ID", "CATEGORY_ID TEXT"),
            ("CATEGORY_NAME", "CATEGORY_NAME TEXT"),
            ("Is_Core_Expense", "Is_Core_Expense BOOLEAN"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (
            (
                "FOREIGN KEY(CATEGORY_ID) REFERENCES silver.wealth_expense_category(UID)",
                DatasetId.WEALTH_EXPENSE_CATEGORY,
            ),
        ),
    ),
    DatasetId.WEALTH_ASSET_CATEGORY: (
        (
            ("UID", "UID TEXT PRIMARY KEY"),
            ("ASSET_GROUP", "ASSET_GROUP TEXT"),
            ("ledger_role", "ledger_role TEXT"),
            ("cashflow_activity_type", "cashflow_activity_type TEXT"),
            ("settlement_timing", "settlement_timing TEXT"),
            ("Is_Digital_Asset", "Is_Digital_Asset BOOLEAN"),
            ("is_cash_pool", "is_cash_pool BOOLEAN"),
            ("is_non_cash_pnl", "is_non_cash_pnl BOOLEAN"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (),
    ),
    DatasetId.WEALTH_ASSET_SUBCATEGORY: (
        (
            ("UID", "UID TEXT PRIMARY KEY"),
            ("ASSET_GROUP_ID", "ASSET_GROUP_ID TEXT"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("ASSET_NAME", "ASSET_NAME TEXT"),
            ("ASSET_DESCRIPTION", "ASSET_DESCRIPTION TEXT"),
            ("NOTES", "NOTES TEXT"),
            ("ledger_role", "ledger_role TEXT"),
            ("cashflow_activity_type", "cashflow_activity_type TEXT"),
            ("settlement_timing", "settlement_timing TEXT"),
            ("Is_Liquid", "Is_Liquid BOOLEAN"),
            ("Is_Illiquid", "Is_Illiquid BOOLEAN"),
            ("Is_Digital_Asset", "Is_Digital_Asset BOOLEAN"),
            ("is_cash_pool", "is_cash_pool BOOLEAN"),
            ("is_non_cash_pnl", "is_non_cash_pnl BOOLEAN"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (
            (
                "FOREIGN KEY(ASSET_GROUP_ID) REFERENCES silver.wealth_asset_category(UID)",
                DatasetId.WEALTH_ASSET_CATEGORY,
            ),
        ),
    ),
    DatasetId.COMMON_CURRENCY: (
        (
            ("UID", "UID TEXT PRIMARY KEY"),
            ("CURRENCY_NAME", "CURRENCY_NAME TEXT"),
            ("ISO", "ISO TEXT"),
            ("Target_Currency_Code", "Target_Currency_Code TEXT"),
            ("SYMBOL", "SYMBOL TEXT"),
            ("Is_Active", "Is_Active BOOLEAN"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (),
    ),
    DatasetId.COMMON_CURRENCY_FX_RATES: (
        (
            ("Date", "Date DATE NOT NULL"),
            ("Currency_ID", "Currency_ID TEXT NOT NULL"),
            ("Currency_Code", "Currency_Code TEXT NOT NULL"),
            ("Target_Currency_Code", "Target_Currency_Code TEXT NOT NULL"),
            ("FX_Rate", "FX_Rate DOUBLE NOT NULL"),
            ("Is_Closure_Gap", "Is_Closure_Gap BOOLEAN"),
            ("Is_Imputed", "Is_Imputed BOOLEAN"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (
            (
                "FOREIGN KEY(Date) REFERENCES silver.common_calendar(Date)",
                DatasetId.COMMON_CALENDAR,
            ),
            (
                "FOREIGN KEY(Currency_ID) REFERENCES silver.common_currency(UID)",
                DatasetId.COMMON_CURRENCY,
            ),
        ),
    ),
    DatasetId.WEALTH_INCOME_TRANSACTIONS: (
        (
            ("UID", "UID TEXT PRIMARY KEY"),
            ("DATE", "DATE DATE NOT NULL"),
            ("ASSET_ID", "ASSET_ID TEXT NOT NULL"),
            ("CATEGORY_ID", "CATEGORY_ID TEXT NOT NULL"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("TO_ASSET_ID", "TO_ASSET_ID TEXT"),
            ("TRANSFER_UID", "TRANSFER_UID TEXT"),
            ("TIME", "TIME TEXT"),
            ("DESCRIPTION", "DESCRIPTION TEXT"),
            ("Is_Active_Income", "Is_Active_Income BOOLEAN"),
            ("Is_Dividend_Income", "Is_Dividend_Income BOOLEAN"),
            ("Is_Interest_Income", "Is_Interest_Income BOOLEAN"),
            ("Is_Non_Cash_Income", "Is_Non_Cash_Income BOOLEAN"),
            ("BASE_AMOUNT", "BASE_AMOUNT DOUBLE"),
            ("AMOUNT_ACCOUNT", "AMOUNT_ACCOUNT DOUBLE"),
            ("LOCAL_AMOUNT", "LOCAL_AMOUNT DOUBLE"),
            ("EXCH_RATE", "EXCH_RATE DOUBLE"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (
            (
                "FOREIGN KEY(CATEGORY_ID) REFERENCES silver.wealth_income_subcategory(UID)",
                DatasetId.WEALTH_INCOME_SUBCATEGORY,
            ),
            (
                "FOREIGN KEY(ASSET_ID) REFERENCES silver.wealth_asset_subcategory(UID)",
                DatasetId.WEALTH_ASSET_SUBCATEGORY,
            ),
            (
                "FOREIGN KEY(CURRENCY_ID) REFERENCES silver.common_currency(UID)",
                DatasetId.COMMON_CURRENCY,
            ),
            (
                "FOREIGN KEY(DATE) REFERENCES silver.common_calendar(Date)",
                DatasetId.COMMON_CALENDAR,
            ),
        ),
    ),
    DatasetId.WEALTH_EXPENSE_TRANSACTIONS: (
        (
            ("UID", "UID TEXT PRIMARY KEY"),
            ("DATE", "DATE DATE NOT NULL"),
            ("ASSET_ID", "ASSET_ID TEXT NOT NULL"),
            ("CATEGORY_ID", "CATEGORY_ID TEXT NOT NULL"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("TO_ASSET_ID", "TO_ASSET_ID TEXT"),
            ("TRANSFER_UID", "TRANSFER_UID TEXT"),
            ("TIME", "TIME TEXT"),
            ("DESCRIPTION", "DESCRIPTION TEXT"),
            ("Is_Core_Expense", "Is_Core_Expense BOOLEAN"),
            ("BASE_AMOUNT", "BASE_AMOUNT DOUBLE"),
            ("AMOUNT_ACCOUNT", "AMOUNT_ACCOUNT DOUBLE"),
            ("LOCAL_AMOUNT", "LOCAL_AMOUNT DOUBLE"),
            ("EXCH_RATE", "EXCH_RATE DOUBLE"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (
            (
                "FOREIGN KEY(CATEGORY_ID) REFERENCES silver.wealth_expense_subcategory(UID)",
                DatasetId.WEALTH_EXPENSE_SUBCATEGORY,
            ),
            (
                "FOREIGN KEY(ASSET_ID) REFERENCES silver.wealth_asset_subcategory(UID)",
                DatasetId.WEALTH_ASSET_SUBCATEGORY,
            ),
            (
                "FOREIGN KEY(CURRENCY_ID) REFERENCES silver.common_currency(UID)",
                DatasetId.COMMON_CURRENCY,
            ),
            (
                "FOREIGN KEY(DATE) REFERENCES silver.common_calendar(Date)",
                DatasetId.COMMON_CALENDAR,
            ),
        ),
    ),
    DatasetId.WEALTH_TRANSFER_TRANSACTIONS: (
        (
            ("UID", "UID TEXT PRIMARY KEY"),
            ("DATE", "DATE DATE NOT NULL"),
            ("ADJUSTED_DATE_FOR_ANALYSIS", "ADJUSTED_DATE_FOR_ANALYSIS DATE"),
            ("ASSET_ID", "ASSET_ID TEXT NOT NULL"),
            ("TO_ASSET_ID", "TO_ASSET_ID TEXT"),
            ("CATEGORY_ID", "CATEGORY_ID TEXT"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("TRANSFER_UID", "TRANSFER_UID TEXT"),
            ("TIME", "TIME TEXT"),
            ("DESCRIPTION", "DESCRIPTION TEXT"),
            ("BASE_AMOUNT", "BASE_AMOUNT DOUBLE"),
            ("AMOUNT_ACCOUNT", "AMOUNT_ACCOUNT DOUBLE"),
            ("AMOUNT_PROPER", "AMOUNT_PROPER DOUBLE"),
            ("LOCAL_AMOUNT", "LOCAL_AMOUNT DOUBLE"),
            ("EXCH_RATE", "EXCH_RATE DOUBLE"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (
            (
                "FOREIGN KEY(CURRENCY_ID) REFERENCES silver.common_currency(UID)",
                DatasetId.COMMON_CURRENCY,
            ),
            (
                "FOREIGN KEY(ASSET_ID) REFERENCES silver.wealth_asset_subcategory(UID)",
                DatasetId.WEALTH_ASSET_SUBCATEGORY,
            ),
            (
                "FOREIGN KEY(TO_ASSET_ID) REFERENCES silver.wealth_asset_subcategory(UID)",
                DatasetId.WEALTH_ASSET_SUBCATEGORY,
            ),
            (
                "FOREIGN KEY(DATE) REFERENCES silver.common_calendar(Date)",
                DatasetId.COMMON_CALENDAR,
            ),
            (
                "FOREIGN KEY(ADJUSTED_DATE_FOR_ANALYSIS) REFERENCES silver.common_calendar(Date)",
                DatasetId.COMMON_CALENDAR,
            ),
        ),
    ),
    DatasetId.WEALTH_OPENING_BALANCES: (
        (
            ("Z_PK", "Z_PK BIGINT PRIMARY KEY"),
            ("Date", "Date DATE NOT NULL"),
            ("ASSET_SUBCATEGORY_ID", "ASSET_SUBCATEGORY_ID TEXT NOT NULL"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("Opening_Amount", "Opening_Amount DOUBLE"),
            ("Opening_Amount_Account", "Opening_Amount_Account DOUBLE"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (
            (
                "FOREIGN KEY(CURRENCY_ID) REFERENCES silver.common_currency(UID)",
                DatasetId.COMMON_CURRENCY,
            ),
            (
                "FOREIGN KEY(ASSET_SUBCATEGORY_ID) REFERENCES silver.wealth_asset_subcategory(UID)",
                DatasetId.WEALTH_ASSET_SUBCATEGORY,
            ),
            (
                "FOREIGN KEY(Date) REFERENCES silver.common_calendar(Date)",
                DatasetId.COMMON_CALENDAR,
            ),
        ),
    ),
    DatasetId.INVESTMENT_BENCHMARK_MASTER_DIM: (
        (
            ("ID", "ID TEXT PRIMARY KEY"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("Benchmark_Name", "Benchmark_Name TEXT"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (),
    ),
    DatasetId.INVESTMENT_MASTER: (
        (
            ("ISIN", "ISIN TEXT PRIMARY KEY"),
            ("CATEGORY_ID", "CATEGORY_ID TEXT"),
            ("BENCHMARK_ID", "BENCHMARK_ID TEXT"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("INSTRUMENT_NAME", "INSTRUMENT_NAME TEXT"),
            ("INSTRUMENT_HOUSE", "INSTRUMENT_HOUSE TEXT"),
            ("INSTRUMENT_CLASS", "INSTRUMENT_CLASS TEXT NOT NULL"),
            ("INSTRUMENT_TYPE", "INSTRUMENT_TYPE TEXT"),
            ("INSTRUMENT_SUBTYPE", "INSTRUMENT_SUBTYPE TEXT"),
            ("SECTOR", "SECTOR TEXT"),
            ("INDUSTRY", "INDUSTRY TEXT"),
            ("COUNTRY", "COUNTRY TEXT"),
            ("GEO", "GEO TEXT"),
            ("GEO_SUBTYPE", "GEO_SUBTYPE TEXT"),
            ("TAX_TYPE", "TAX_TYPE TEXT NOT NULL"),
            ("TAX_SUBTYPE", "TAX_SUBTYPE TEXT"),
        ),
        (
            (
                "FOREIGN KEY(CATEGORY_ID) REFERENCES silver.wealth_asset_subcategory(UID)",
                DatasetId.WEALTH_ASSET_SUBCATEGORY,
            ),
            (
                "FOREIGN KEY(BENCHMARK_ID) REFERENCES silver.investment_benchmark_master_dim(ID)",
                DatasetId.INVESTMENT_BENCHMARK_MASTER_DIM,
            ),
            (
                "FOREIGN KEY(CURRENCY_ID) REFERENCES silver.common_currency(UID)",
                DatasetId.COMMON_CURRENCY,
            ),
        ),
    ),
    DatasetId.INVESTMENT_MACRO_PARAMETERS_DIM: (
        (
            ("FY", "FY TEXT PRIMARY KEY"),
            ("FY_Start_Date", "FY_Start_Date DATE"),
            ("FY_End_Date", "FY_End_Date DATE"),
            ("Debt_MF_Cutoff_Date", "Debt_MF_Cutoff_Date DATE"),
            ("Inflation_Rate", "Inflation_Rate DOUBLE"),
            ("Risk_Free_Rate", "Risk_Free_Rate DOUBLE"),
            ("Equity_Listed_LTCG", "Equity_Listed_LTCG DOUBLE"),
            ("Equity_Listed_STCG", "Equity_Listed_STCG DOUBLE"),
            ("Equity_Unlisted_LTCG", "Equity_Unlisted_LTCG DOUBLE"),
            ("Equity_Unlisted_STCG", "Equity_Unlisted_STCG DOUBLE"),
            ("Equity_LTCG_Exemption", "Equity_LTCG_Exemption BIGINT"),
            ("Gold_LTCG", "Gold_LTCG DOUBLE"),
            ("Gold_STCG", "Gold_STCG DOUBLE"),
            ("Debt_MF_Pre_Cutoff_LTCG", "Debt_MF_Pre_Cutoff_LTCG DOUBLE"),
            ("Debt_MF_Pre_Cutoff_STCG", "Debt_MF_Pre_Cutoff_STCG DOUBLE"),
            ("Debt_MF_Post_Cutoff_LTCG", "Debt_MF_Post_Cutoff_LTCG DOUBLE"),
            ("Debt_MF_Post_Cutoff_STCG", "Debt_MF_Post_Cutoff_STCG DOUBLE"),
            ("Other_Debt_LTCG", "Other_Debt_LTCG DOUBLE"),
            ("Other_Debt_STCG", "Other_Debt_STCG DOUBLE"),
            ("Default_LTCG", "Default_LTCG DOUBLE"),
            ("Default_STCG", "Default_STCG DOUBLE"),
            ("Estimated_Ordinary_Income_Tax_Rate", "Estimated_Ordinary_Income_Tax_Rate DOUBLE"),
            ("Remarks", "Remarks TEXT"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (),
    ),
    DatasetId.INVESTMENT_MARKET_DATA: (
        (
            ("Date", "Date DATE NOT NULL"),
            ("ISIN", "ISIN TEXT NOT NULL"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("Quantity", "Quantity DOUBLE"),
            ("Closing_Price", "Closing_Price DOUBLE"),
            ("Buy_Price", "Buy_Price DOUBLE"),
            ("Closing_Value", "Closing_Value DOUBLE"),
            ("Buy_Value", "Buy_Value DOUBLE"),
            ("Closing_Price_Local", "Closing_Price_Local DOUBLE"),
            ("Buy_Price_Local", "Buy_Price_Local DOUBLE"),
            ("Closing_Value_Local", "Closing_Value_Local DOUBLE"),
            ("Buy_Value_Local", "Buy_Value_Local DOUBLE"),
            ("FX_Rate", "FX_Rate DOUBLE"),
            ("Unit_PnL", "Unit_PnL DOUBLE"),
            ("Total_PnL", "Total_PnL DOUBLE"),
            ("Is_Closure_Gap", "Is_Closure_Gap BOOLEAN"),
            ("Is_Imputed", "Is_Imputed BOOLEAN"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (
            (
                "FOREIGN KEY(Date) REFERENCES silver.common_calendar(Date)",
                DatasetId.COMMON_CALENDAR,
            ),
            (
                "FOREIGN KEY(ISIN) REFERENCES silver.investment_master(ISIN)",
                DatasetId.INVESTMENT_MASTER,
            ),
            (
                "FOREIGN KEY(CURRENCY_ID) REFERENCES silver.common_currency(UID)",
                DatasetId.COMMON_CURRENCY,
            ),
        ),
    ),
    DatasetId.INVESTMENT_PURCHASE_DATA: (
        (
            ("Purchase_ID", "Purchase_ID TEXT PRIMARY KEY"),
            ("Date", "Date DATE NOT NULL"),
            ("ISIN", "ISIN TEXT NOT NULL"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("Quantity", "Quantity DOUBLE"),
            ("Price", "Price DOUBLE"),
            ("Value", "Value DOUBLE"),
            ("Price_Local", "Price_Local DOUBLE"),
            ("Value_Local", "Value_Local DOUBLE"),
            ("FX_Rate", "FX_Rate DOUBLE"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (
            (
                "FOREIGN KEY(Date) REFERENCES silver.common_calendar(Date)",
                DatasetId.COMMON_CALENDAR,
            ),
            (
                "FOREIGN KEY(ISIN) REFERENCES silver.investment_master(ISIN)",
                DatasetId.INVESTMENT_MASTER,
            ),
            (
                "FOREIGN KEY(CURRENCY_ID) REFERENCES silver.common_currency(UID)",
                DatasetId.COMMON_CURRENCY,
            ),
        ),
    ),
    DatasetId.INVESTMENT_SALE_DATA: (
        (
            ("Sale_ID", "Sale_ID TEXT PRIMARY KEY"),
            ("Date", "Date DATE NOT NULL"),
            ("ISIN", "ISIN TEXT NOT NULL"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("Quantity", "Quantity DOUBLE"),
            ("Sell_Price", "Sell_Price DOUBLE"),
            ("Sell_Value", "Sell_Value DOUBLE"),
            ("Buy_Price", "Buy_Price DOUBLE"),
            ("Buy_Value", "Buy_Value DOUBLE"),
            ("Sell_Price_Local", "Sell_Price_Local DOUBLE"),
            ("Sell_Value_Local", "Sell_Value_Local DOUBLE"),
            ("Buy_Price_Local", "Buy_Price_Local DOUBLE"),
            ("Buy_Value_Local", "Buy_Value_Local DOUBLE"),
            ("FX_Rate", "FX_Rate DOUBLE"),
            ("Unit_PnL", "Unit_PnL DOUBLE"),
            ("Total_PnL", "Total_PnL DOUBLE"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (
            (
                "FOREIGN KEY(Date) REFERENCES silver.common_calendar(Date)",
                DatasetId.COMMON_CALENDAR,
            ),
            (
                "FOREIGN KEY(ISIN) REFERENCES silver.investment_master(ISIN)",
                DatasetId.INVESTMENT_MASTER,
            ),
            (
                "FOREIGN KEY(CURRENCY_ID) REFERENCES silver.common_currency(UID)",
                DatasetId.COMMON_CURRENCY,
            ),
        ),
    ),
    DatasetId.INVESTMENT_BENCHMARK_DATA: (
        (
            ("Date", "Date DATE"),
            ("ID", "ID TEXT"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("Benchmark_Name", "Benchmark_Name TEXT"),
            ("Close", "Close DOUBLE"),
            ("Is_Closure_Gap", "Is_Closure_Gap BOOLEAN"),
            ("Is_Imputed", "Is_Imputed BOOLEAN"),
            ("artifact_id", "artifact_id TEXT"),
        ),
        (
            (
                "FOREIGN KEY(Date) REFERENCES silver.common_calendar(Date)",
                DatasetId.COMMON_CALENDAR,
            ),
            (
                "FOREIGN KEY(ID) REFERENCES silver.investment_benchmark_master_dim(ID)",
                DatasetId.INVESTMENT_BENCHMARK_MASTER_DIM,
            ),
        ),
    ),
    DatasetId.INVESTMENT_LOT_ANALYTICS: (
        (
            ("Lot_ID", "Lot_ID TEXT NOT NULL"),
            ("Closing_Date", "Closing_Date DATE NOT NULL"),
            ("ISIN", "ISIN TEXT NOT NULL"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("Buy_Date", "Buy_Date DATE"),
            ("Purchase_ID", "Purchase_ID TEXT"),
            ("Lot_Source_Type", "Lot_Source_Type TEXT NOT NULL"),
            ("BENCHMARK_ID", "BENCHMARK_ID TEXT"),
            ("TAX_TYPE", "TAX_TYPE TEXT"),
            ("TAX_SUBTYPE", "TAX_SUBTYPE TEXT"),
            ("Quantity", "Quantity DOUBLE"),
            (
                "Execution_Residual",
                "Execution_Residual DOUBLE,  -- Units ordered but not yet settled at this snapshot date",
            ),
            ("Buy_Price", "Buy_Price DOUBLE"),
            ("Market_Price", "Market_Price DOUBLE"),
            ("Buy_Value", "Buy_Value DOUBLE"),
            ("Close_Value", "Close_Value DOUBLE"),
            ("Buy_Value_Local", "Buy_Value_Local DOUBLE"),
            ("Close_Value_Local", "Close_Value_Local DOUBLE"),
            ("Blended_FX_Buy_Rate", "Blended_FX_Buy_Rate DOUBLE"),
            (
                "Buy_Price_Local",
                "Buy_Price_Local DOUBLE,          -- Acquisition price in instrument native currency",
            ),
            (
                "Market_Price_Local",
                "Market_Price_Local DOUBLE,       -- Market price in instrument native currency at snapshot",
            ),
            (
                "FX_Rate_Buy",
                "FX_Rate_Buy DOUBLE,              -- FX rate (native → INR) at acquisition date",
            ),
            (
                "FX_Rate_Snap",
                "FX_Rate_Snap DOUBLE,             -- FX rate (native → INR) at snapshot date",
            ),
            ("Currency_Appreciation_Pct", "Currency_Appreciation_Pct DOUBLE"),
            ("P/L", '"P/L" DOUBLE'),
            ("Absolute_Return", "Absolute_Return DOUBLE"),
            ("Absolute_Return_Local", "Absolute_Return_Local DOUBLE"),
            ("Asset_PnL", "Asset_PnL DOUBLE"),
            ("Forex_PnL", "Forex_PnL DOUBLE"),
            ("Forex_Contribution_Pct", "Forex_Contribution_Pct DOUBLE"),
            ("Asset_Return_Pct", "Asset_Return_Pct DOUBLE"),
            ("Forex_Return_Pct", "Forex_Return_Pct DOUBLE"),
            ("Lot_CAGR", "Lot_CAGR DOUBLE"),
            (
                "Lot_CAGR_Status",
                "Lot_CAGR_Status TEXT,       -- VALID | INVALID_INPUT | UNDEFINED | COMPUTATION_ERROR",
            ),
            ("Lot_CAGR_Local", "Lot_CAGR_Local DOUBLE"),
            ("CAGR", "CAGR DOUBLE"),
            (
                "CAGR_Status",
                "CAGR_Status TEXT,           -- VALID | INVALID_INPUT | UNDEFINED | COMPUTATION_ERROR",
            ),
            ("XIRR", "XIRR DOUBLE"),
            (
                "XIRR_Status",
                "XIRR_Status TEXT,           -- VALID | INVALID_INPUT | UNDEFINED | NON_CONVERGENT",
            ),
            ("XIRR_Local", "XIRR_Local DOUBLE"),
            ("FX_XIRR_Impact", "FX_XIRR_Impact DOUBLE"),
            ("After_Tax_XIRR", "After_Tax_XIRR DOUBLE"),
            ("BM_Buy_Price", "BM_Buy_Price DOUBLE"),
            ("BM_Market_Price", "BM_Market_Price DOUBLE"),
            ("Lot_BM_Return", "Lot_BM_Return DOUBLE"),
            ("Lot_BM_CAGR", "Lot_BM_CAGR DOUBLE"),
            (
                "Lot_BM_CAGR_Status",
                "Lot_BM_CAGR_Status TEXT,    -- VALID | INVALID_INPUT | UNDEFINED | COMPUTATION_ERROR",
            ),
            ("Lot_BM_CAGR_Local", "Lot_BM_CAGR_Local DOUBLE"),
            ("BM_CAGR", "BM_CAGR DOUBLE"),
            (
                "BM_CAGR_Status",
                "BM_CAGR_Status TEXT,        -- VALID | INVALID_INPUT | UNDEFINED | COMPUTATION_ERROR",
            ),
            ("BM_XIRR", "BM_XIRR DOUBLE"),
            ("BM_XIRR_Local", "BM_XIRR_Local DOUBLE"),
            ("Active_Return", "Active_Return DOUBLE"),
            ("Active_Return_Local", "Active_Return_Local DOUBLE"),
            ("Lot_Alpha", "Lot_Alpha DOUBLE"),
            ("Is_Lagging_Benchmark", "Is_Lagging_Benchmark BIGINT"),
            ("Max_Drawdown", "Max_Drawdown DOUBLE"),
            ("Lot_Weight", "Lot_Weight DOUBLE"),
            ("Portfolio_Weight", "Portfolio_Weight DOUBLE"),
            ("Outperforming_Lot_Ratio", "Outperforming_Lot_Ratio DOUBLE"),
            ("Dietz_Day_Weight", "Dietz_Day_Weight DOUBLE"),
            ("Age_Days", "Age_Days BIGINT"),
            ("LTCG_Threshold_Days", "LTCG_Threshold_Days BIGINT"),
            ("Days_To_LTCG", "Days_To_LTCG BIGINT"),
            ("Holding_Type", "Holding_Type TEXT"),
            ("Tax_Rate", "Tax_Rate DOUBLE"),
            ("Unrealized_LTCG", "Unrealized_LTCG DOUBLE"),
            ("Unrealized_STCG", "Unrealized_STCG DOUBLE"),
            ("Unrealized_Gain", "Unrealized_Gain DOUBLE"),
            ("Unrealized_LTCL", "Unrealized_LTCL DOUBLE"),
            ("Unrealized_STCL", "Unrealized_STCL DOUBLE"),
            ("Unrealized_Loss", "Unrealized_Loss DOUBLE"),
            ("LTCG_Tax_If_Sold", "LTCG_Tax_If_Sold DOUBLE"),
            ("STCG_Tax_If_Sold", "STCG_Tax_If_Sold DOUBLE"),
            ("After_Tax_PL", "After_Tax_PL DOUBLE"),
            ("After_Tax_Close_Value", "After_Tax_Close_Value DOUBLE"),
            ("FY", "FY TEXT"),
            ("FY_Realized_LTCG", "FY_Realized_LTCG DOUBLE"),
            ("FY_Realized_STCG", "FY_Realized_STCG DOUBLE"),
            ("FY_Realized_Gain", "FY_Realized_Gain DOUBLE"),
            ("FY_Realized_LTCL", "FY_Realized_LTCL DOUBLE"),
            ("FY_Realized_STCL", "FY_Realized_STCL DOUBLE"),
            ("FY_Realized_Loss", "FY_Realized_Loss DOUBLE"),
            ("FY_Realized_Net_PnL", "FY_Realized_Net_PnL DOUBLE"),
            ("Equity_LTCG_Exemption", "Equity_LTCG_Exemption BIGINT"),
            ("Stepup_Eligible", "Stepup_Eligible BIGINT"),
            ("Can_Harvest_Loss", "Can_Harvest_Loss BOOLEAN"),
            ("Harvest_Recommendation", "Harvest_Recommendation TEXT"),
        ),
        (("PRIMARY KEY (Lot_ID, Closing_Date)", None),),
    ),
    DatasetId.INVESTMENT_REALIZED_EVENTS: (
        (
            ("Realized_Event_ID", "Realized_Event_ID TEXT PRIMARY KEY"),
            ("Sale_ID", "Sale_ID TEXT NOT NULL"),
            ("Lot_ID", "Lot_ID TEXT NOT NULL"),
            ("Purchase_ID", "Purchase_ID TEXT"),
            ("ISIN", "ISIN TEXT"),
            ("Acquisition_Date", "Acquisition_Date DATE"),
            ("Disposal_Date", "Disposal_Date DATE"),
            ("FY", "FY TEXT"),
            ("Quantity_Disposed", "Quantity_Disposed DOUBLE"),
            ("Acquisition_Price", "Acquisition_Price DOUBLE"),
            ("Disposed_Cost_Basis", "Disposed_Cost_Basis DOUBLE"),
            ("Sale_Price", "Sale_Price DOUBLE"),
            ("Sale_Proceeds", "Sale_Proceeds DOUBLE"),
            ("Realized_Gain_Loss", "Realized_Gain_Loss DOUBLE"),
            ("Holding_Type", "Holding_Type TEXT"),
            ("Tax_Type", "Tax_Type TEXT"),
            ("Tax_Subtype", "Tax_Subtype TEXT"),
            ("Lot_Source_Type", "Lot_Source_Type TEXT"),
            ("Currency_ID", "Currency_ID TEXT"),
            ("Asset_PnL_Local", "Asset_PnL_Local DOUBLE"),
            ("Asset_PnL", "Asset_PnL DOUBLE"),
            ("Forex_PnL", "Forex_PnL DOUBLE"),
            ("Applied_Rate", "Applied_Rate DOUBLE"),
            ("Estimated_Tax", "Estimated_Tax DOUBLE"),
        ),
        (("UNIQUE(Sale_ID, Lot_ID)", None),),
    ),
    DatasetId.INVESTMENT_RECONCILIATION_EVENTS: (
        (
            ("Reconciliation_Group_ID", "Reconciliation_Group_ID TEXT NOT NULL"),
            ("Reconciliation_Event_ID", "Reconciliation_Event_ID TEXT PRIMARY KEY"),
            ("Run_ID", "Run_ID TEXT"),
            ("ISIN", "ISIN TEXT NOT NULL"),
            ("Reconciliation_Date", "Reconciliation_Date DATE NOT NULL"),
            ("Lot_ID", "Lot_ID TEXT"),
            ("Purchase_ID", "Purchase_ID TEXT"),
            ("Adjustment_Type", "Adjustment_Type TEXT"),
            ("Reason", "Reason TEXT"),
            ("Broker_Quantity", "Broker_Quantity DOUBLE"),
            ("Reconstructed_Quantity", "Reconstructed_Quantity DOUBLE"),
            ("Quantity_Adjustment", "Quantity_Adjustment DOUBLE"),
            ("Broker_Cost_Basis", "Broker_Cost_Basis DOUBLE"),
            ("Reconstructed_Cost_Basis", "Reconstructed_Cost_Basis DOUBLE"),
            ("Cost_Basis_Adjustment", "Cost_Basis_Adjustment DOUBLE"),
            ("Original_Unit_Cost", "Original_Unit_Cost DOUBLE"),
            ("Adjusted_Unit_Cost", "Adjusted_Unit_Cost DOUBLE"),
        ),
        (),
    ),
    DatasetId.TAX_EVENTS: (
        (
            ("Tax_Event_ID", "Tax_Event_ID TEXT PRIMARY KEY"),
            ("FY", "FY TEXT NOT NULL"),
            ("Event_Date", "Event_Date DATE NOT NULL"),
            ("Source_Type", "Source_Type TEXT NOT NULL"),
            ("Source_ID", "Source_ID TEXT NOT NULL"),
            ("Income_Head", "Income_Head TEXT NOT NULL"),
            ("Tax_Sub_Head", "Tax_Sub_Head TEXT NOT NULL"),
            ("Amount_INR", "Amount_INR DOUBLE NOT NULL"),
            ("Applied_Rate", "Applied_Rate DOUBLE"),
            ("Estimated_Tax", "Estimated_Tax DOUBLE"),
            ("CURRENCY_ID", "CURRENCY_ID TEXT"),
            ("Tax_Status", "Tax_Status TEXT NOT NULL"),
            ("Tax_Status_Reason", "Tax_Status_Reason TEXT"),
            ("ISIN", "ISIN TEXT"),
            ("Lot_ID", "Lot_ID TEXT"),
        ),
        (("UNIQUE(Source_Type, Source_ID, Tax_Sub_Head)", None),),
    ),
}


def generate_silver_ddl(plan: ExecutionPlan | None = None) -> str:
    """Generate dynamic DDL statements for active Silver tables with physical column pruning.

    Parameters
    ----------
    plan : ExecutionPlan | None, optional
        Active execution plan. If None, generates DDL for all 24 Silver tables with all columns.

    Returns
    -------
    str
        Concatenated SQL DDL string initializing active Silver tables.
    """
    ddl_statements: list[str] = []
    contracts = sorted(
        (c for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"),
        key=lambda c: c.publication_order,
    )
    for contract in contracts:
        ds_id = contract.dataset_id
        if plan is not None and not plan.is_silver_dataset_active(ds_id):
            continue

        schema = SILVER_TABLE_SCHEMAS.get(ds_id)
        if schema is None:
            continue

        cols, constrs = schema
        active_elements: list[str] = []

        for col_name, col_sql in cols:
            cap_id = _SILVER_COLUMN_CAPABILITY_MAP.get((ds_id, col_name))
            if cap_id is not None and plan is not None:
                if not plan.is_capability_active(cap_id):
                    continue
            active_elements.append(f"    {col_sql}")

        for constr_sql, target_ds in constrs:
            if target_ds is not None and plan is not None:
                if not plan.is_silver_dataset_active(target_ds):
                    continue
            active_elements.append(f"    {constr_sql}")

        body = ",\n".join(active_elements)
        ddl_statements.append(f"CREATE TABLE IF NOT EXISTS {contract.physical_table} (\n{body}\n);")

    return "\n\n".join(ddl_statements)


SILVER_DDL: str = generate_silver_ddl(plan=None)
