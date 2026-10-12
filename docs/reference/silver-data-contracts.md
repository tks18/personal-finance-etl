# Silver Data Contracts

Silver is the canonical analytical layer. It contains normalized household, currency, investment, Quant, reconciliation, and tax facts that downstream engines can consume without reinterpreting vendor/source layouts.

## Registry authority

The current registry contains **24 Silver contracts**. Publication order is explicit metadata, not an accidental consequence of dictionary iteration or filename sorting. The ETL validates the registry before publication and rejects missing or unregistered analytical outputs.

```mermaid
flowchart LR
    P[Engine output key] --> R[DataContract registry]
    R --> G[Grain + producer + order]
    R --> T[Physical table]
    T --> D[DDL schema]
    D --> V[Validated publication]
```

## Contract catalog

| Order | Contract ID | Physical table | Domain | Grain | Producer |
|---:|---|---|---|---|---|
| 10 | `df_d_calendar` | `silver.d_Calendar` | Common | Day | `CoreEngine` |
| 20 | `df_d_income_category` | `silver.d_Income_Category` | Wealth | Category | `CoreEngine` |
| 30 | `df_d_income_subcategory` | `silver.d_Income_Subcategory` | Wealth | Subcategory | `CoreEngine` |
| 40 | `df_d_expense_category` | `silver.d_Expense_Category` | Wealth | Category | `CoreEngine` |
| 50 | `df_d_expense_subcategory` | `silver.d_Expense_Subcategory` | Wealth | Subcategory | `CoreEngine` |
| 60 | `df_d_asset_category` | `silver.d_Asset_Category` | Wealth | Category | `CoreEngine` |
| 70 | `df_d_asset_subcategory` | `silver.d_Asset_SubCategory` | Wealth | Subcategory | `CoreEngine` |
| 80 | `df_d_currency` | `silver.d_Currency` | Common | Currency | `CoreEngine` |
| 90 | `df_d_benchmark_master` | `silver.d_Investment_Benchmark_Master` | Investments | Benchmark | `CoreEngine` |
| 95 | `df_f_currency_fx_rates` | `silver.f_Currency_FX_Rates` | Common | Date-Currency | `CoreEngine` |
| 100 | `df_d_investment_master` | `silver.d_Investment_Master` | Investments | ISIN | `CoreEngine` |
| 110 | `df_d_macro_parameters` | `silver.d_Macro_Parameters` | Investments | FinancialYear | `CoreEngine` |
| 120 | `df_f_income_transactions` | `silver.f_Income_Transactions` | Wealth | Transaction | `CoreEngine` |
| 130 | `df_f_expense_transactions` | `silver.f_Expense_Transactions` | Wealth | Transaction | `CoreEngine` |
| 140 | `df_f_transfer_transactions` | `silver.f_Transfer_Transactions` | Wealth | Transaction | `CoreEngine` |
| 150 | `df_f_opening_balances` | `silver.f_Opening_Balances` | Wealth | Balance | `CoreEngine` |
| 160 | `df_f_investment_market_data` | `silver.f_Investment_Market_Data` | Investments | Quote | `CoreEngine` |
| 170 | `df_f_tf_inv_purchase` | `silver.f_Investment_Purchase_Data` | Investments | Trade | `CoreEngine` |
| 180 | `df_f_tf_inv_sale` | `silver.f_Investment_Sale_Data` | Investments | Trade | `CoreEngine` |
| 190 | `df_f_investment_benchmark_data` | `silver.f_Investment_Benchmark_Data` | Investments | Quote | `CoreEngine` |
| 200 | `df_f_investment_analytics_lot` | `silver.f_Investment_Analytics_Lot` | Investments | ISIN-Lot | `InvestmentQuantEngine` |
| 205 | `df_f_investment_realized_events` | `silver.f_Investment_Realized_Events` | Investments | RealizedEvent | `InvestmentQuantEngine` |
| 206 | `df_f_investment_reconciliation_events` | `silver.f_Investment_Reconciliation_Events` | Investments | ReconEvent | `InvestmentQuantEngine` |
| 300 | `df_f_tax_events` | `silver.f_Tax_Events` | Taxes | TaxEvent | `TaxEngine` |

## Physical schemas

### `silver.d_Calendar`

**Contract ID:** `df_d_calendar`  
**Domain:** Common  
**Registry grain:** **Day**  
**Producer:** `CoreEngine`  
**Publication order:** `10`

| Column | Physical type / constraint |
|---|---|
| `Date` | `DATE PRIMARY KEY` |
| `Day` | `BIGINT` |
| `Day_Name` | `TEXT` |
| `Day_Name_Short` | `TEXT` |
| `Day_Ordinal` | `BIGINT` |
| `Day_Ordinal_Name` | `TEXT` |
| `Weekday` | `BIGINT` |
| `IS_WEEKEND` | `BIGINT` |
| `Week` | `BIGINT` |
| `Week_Ordinal` | `BIGINT` |
| `Week_Ordinal_Name` | `TEXT` |
| `Week_Name` | `TEXT` |
| `Week_Year` | `TEXT` |
| `Week_Name_Year` | `TEXT` |
| `Start_of_Week` | `DATE` |
| `End_of_Week` | `DATE` |
| `Month` | `BIGINT` |
| `Month_Name` | `TEXT` |
| `Month_Name_Short` | `TEXT` |
| `Month_Year` | `TEXT` |
| `Short_Month_Year` | `TEXT` |
| `V_Short_Month_Year` | `TEXT` |
| `Month_Ordinal` | `BIGINT` |
| `Start_of_Month` | `DATE` |
| `End_of_Month` | `DATE` |
| `Days_in_Month` | `BIGINT` |
| `Month_Progress_Pct` | `DOUBLE` |
| `Quarter` | `BIGINT` |
| `Quarter_Name` | `TEXT` |
| `Quarter_Year` | `TEXT` |
| `Quarter_Ordinal` | `BIGINT` |
| `Start_of_Quarter` | `DATE` |
| `End_of_Quarter` | `DATE` |
| `Year` | `BIGINT` |
| `Days_in_Year` | `BIGINT` |
| `Year_Progress_Pct` | `DOUBLE` |
| `Financial_Year` | `TEXT` |
| `FY_Year` | `BIGINT` |
| `FY_Month` | `BIGINT` |
| `FY_Month_Ordinal` | `BIGINT` |
| `FY_Quarter` | `BIGINT` |
| `FY_Quarter_Name` | `TEXT` |
| `FY_Quarter_Year` | `TEXT` |
| `FY_Quarter_Ordinal` | `BIGINT` |
| `FY_Start_of_Month` | `DATE` |
| `FY_End_of_Month` | `DATE` |
| `FY_Start_of_Quarter` | `DATE` |
| `FY_End_of_Quarter` | `DATE` |
| `Is_Last_Day_Of_Month` | `BOOLEAN` |
| `Is_Last_Day_Of_Quarter` | `BOOLEAN` |
| `Is_Last_Day_Of_Year` | `BOOLEAN` |
| `Is_Last_Day_Of_FY` | `BOOLEAN` |
| `Is_Quarter_End_Month` | `BOOLEAN` |
| `Is_Tax_Harvesting_Season` | `BOOLEAN` |
| `Is_Current_Month` | `BOOLEAN` |
| `Is_Previous_Month` | `BOOLEAN` |
| `Is_Current_Quarter` | `BOOLEAN` |
| `Is_Previous_Quarter` | `BOOLEAN` |
| `Is_Current_Year` | `BOOLEAN` |
| `Is_Previous_Year` | `BOOLEAN` |
| `Is_Current_FY` | `BOOLEAN` |
| `Is_YTD` | `BOOLEAN` |
| `Is_FY_YTD` | `BOOLEAN` |
| `Is_Future_Date` | `BOOLEAN` |

The physical DDL defines **64 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.d_Income_Category`

**Contract ID:** `df_d_income_category`  
**Domain:** Wealth  
**Registry grain:** **Category**  
**Producer:** `CoreEngine`  
**Publication order:** `20`

| Column | Physical type / constraint |
|---|---|
| `UID` | `TEXT PRIMARY KEY` |
| `CATEGORY_NAME` | `TEXT` |
| `CATEGORY_NAME_SHORT` | `TEXT` |
| `ORDER_SEQUENCE` | `BIGINT` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |
| `S_NO` | `BIGINT` |
| `MODIFY_DATE` | `BIGINT` |
| `Tax_Income_Head` | `TEXT` |
| `Tax_Sub_Head` | `TEXT` |
| `Taxability` | `TEXT` |
| `Tax_Method` | `TEXT` |

The physical DDL defines **12 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.d_Income_Subcategory`

**Contract ID:** `df_d_income_subcategory`  
**Domain:** Wealth  
**Registry grain:** **Subcategory**  
**Producer:** `CoreEngine`  
**Publication order:** `30`

| Column | Physical type / constraint |
|---|---|
| `UID` | `TEXT PRIMARY KEY` |
| `CATEGORY_ID` | `TEXT` |
| `CATEGORY_NAME` | `TEXT` |
| `CATEGORY_GROUPS` | `TEXT` |
| `ORDER_SEQUENCE` | `BIGINT` |
| `Is_Active_Income` | `BOOLEAN` |
| `Is_Passive_Income` | `BOOLEAN` |
| `Is_Dividend_Income` | `BOOLEAN` |
| `Is_Interest_Income` | `BOOLEAN` |
| `Is_Non_Cash_Income` | `BOOLEAN` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |
| `S_NO` | `BIGINT` |
| `MODIFY_DATE` | `BIGINT` |
| `Tax_Income_Head` | `TEXT` |
| `Tax_Sub_Head` | `TEXT` |
| `Taxability` | `TEXT` |
| `Tax_Method` | `TEXT` |

The physical DDL defines **18 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.d_Expense_Category`

**Contract ID:** `df_d_expense_category`  
**Domain:** Wealth  
**Registry grain:** **Category**  
**Producer:** `CoreEngine`  
**Publication order:** `40`

| Column | Physical type / constraint |
|---|---|
| `UID` | `TEXT PRIMARY KEY` |
| `CATEGORY_NAME` | `TEXT` |
| `ORDER_SEQUENCE` | `BIGINT` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |
| `S_NO` | `BIGINT` |
| `MODIFY_DATE` | `BIGINT` |

The physical DDL defines **7 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.d_Expense_Subcategory`

**Contract ID:** `df_d_expense_subcategory`  
**Domain:** Wealth  
**Registry grain:** **Subcategory**  
**Producer:** `CoreEngine`  
**Publication order:** `50`

| Column | Physical type / constraint |
|---|---|
| `UID` | `TEXT PRIMARY KEY` |
| `CATEGORY_ID` | `TEXT` |
| `CATEGORY_NAME` | `TEXT` |
| `ORDER_SEQUENCE` | `BIGINT` |
| `Is_Core_Expense` | `BOOLEAN` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |
| `S_NO` | `BIGINT` |
| `MODIFY_DATE` | `BIGINT` |

The physical DDL defines **9 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.d_Asset_Category`

**Contract ID:** `df_d_asset_category`  
**Domain:** Wealth  
**Registry grain:** **Category**  
**Producer:** `CoreEngine`  
**Publication order:** `60`

| Column | Physical type / constraint |
|---|---|
| `UID` | `TEXT PRIMARY KEY` |
| `ASSET_GROUP` | `TEXT` |
| `TYPE` | `BIGINT` |
| `ORDER_SEQUENCE` | `BIGINT` |
| `ledger_role` | `TEXT` |
| `cashflow_activity_type` | `TEXT` |
| `settlement_timing` | `TEXT` |
| `Is_Digital_Asset` | `BOOLEAN` |
| `is_cash_pool` | `BOOLEAN` |
| `is_non_cash_pnl` | `BOOLEAN` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |
| `DEVICE_ID` | `BIGINT` |
| `USE_TIME` | `BIGINT` |

The physical DDL defines **14 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.d_Asset_SubCategory`

**Contract ID:** `df_d_asset_subcategory`  
**Domain:** Wealth  
**Registry grain:** **Subcategory**  
**Producer:** `CoreEngine`  
**Publication order:** `70`

| Column | Physical type / constraint |
|---|---|

The physical DDL defines **0 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.d_Currency`

**Contract ID:** `df_d_currency`  
**Domain:** Common  
**Registry grain:** **Currency**  
**Producer:** `CoreEngine`  
**Publication order:** `80`

| Column | Physical type / constraint |
|---|---|
| `UID` | `TEXT PRIMARY KEY` |
| `CURRENCY_NAME` | `TEXT` |
| `ISO` | `TEXT` |
| `MAIN_ISO` | `TEXT` |
| `Target_Currency_Code` | `TEXT` |
| `yF_Ticker` | `TEXT` |
| `SYMBOL` | `TEXT` |
| `SYMBOL_POSITION` | `TEXT` |
| `ORDER_SEQUENCE` | `BIGINT` |
| `RATE` | `DOUBLE` |
| `DECIMAL_POINT` | `BIGINT` |
| `IS_MAIN_CURRENCY` | `BIGINT` |
| `IS_SHOW` | `BIGINT` |
| `Is_Active` | `BOOLEAN` |
| `INSERT_TYPE` | `TEXT` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |
| `S_NO` | `BIGINT` |
| `MODIFY_DATE` | `BIGINT` |

The physical DDL defines **19 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.d_Investment_Benchmark_Master`

**Contract ID:** `df_d_benchmark_master`  
**Domain:** Investments  
**Registry grain:** **Benchmark**  
**Producer:** `CoreEngine`  
**Publication order:** `90`

| Column | Physical type / constraint |
|---|---|
| `ID` | `TEXT PRIMARY KEY` |
| `CURRENCY_ID` | `TEXT` |
| `Benchmark_Name` | `TEXT` |
| `yF_Ticker` | `TEXT` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |

The physical DDL defines **6 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Currency_FX_Rates`

**Contract ID:** `df_f_currency_fx_rates`  
**Domain:** Common  
**Registry grain:** **Date-Currency**  
**Producer:** `CoreEngine`  
**Publication order:** `95`

| Column | Physical type / constraint |
|---|---|
| `Date` | `DATE NOT NULL` |
| `Currency_ID` | `TEXT NOT NULL` |
| `Currency_Code` | `TEXT NOT NULL` |
| `Target_Currency_Code` | `TEXT NOT NULL` |
| `yF_Ticker` | `TEXT NOT NULL` |
| `FX_Rate` | `DOUBLE NOT NULL` |
| `Data_Provider` | `TEXT` |
| `Extraction_Time` | `TEXT` |
| `Requested_Start` | `DATE` |
| `Requested_End` | `DATE` |
| `Is_Closure_Gap` | `BOOLEAN` |
| `Is_Imputed` | `BOOLEAN` |
| `First_Observation_Date` | `DATE` |

The physical DDL defines **13 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.d_Investment_Master`

**Contract ID:** `df_d_investment_master`  
**Domain:** Investments  
**Registry grain:** **ISIN**  
**Producer:** `CoreEngine`  
**Publication order:** `100`

| Column | Physical type / constraint |
|---|---|
| `ISIN` | `TEXT PRIMARY KEY` |
| `CATEGORY_ID` | `TEXT` |
| `BENCHMARK_ID` | `TEXT` |
| `CURRENCY_ID` | `TEXT` |
| `INSTRUMENT_NAME` | `TEXT` |
| `INSTRUMENT_HOUSE` | `TEXT` |
| `INSTRUMENT_CLASS` | `TEXT NOT NULL` |
| `INSTRUMENT_TYPE` | `TEXT` |
| `INSTRUMENT_SUBTYPE` | `TEXT` |
| `SECTOR` | `TEXT` |
| `INDUSTRY` | `TEXT` |
| `COUNTRY` | `TEXT` |
| `GEO` | `TEXT` |
| `GEO_SUBTYPE` | `TEXT` |
| `YAHOO_TICKER` | `TEXT` |
| `TAX_TYPE` | `TEXT NOT NULL` |
| `TAX_SUBTYPE` | `TEXT` |

The physical DDL defines **17 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.d_Macro_Parameters`

**Contract ID:** `df_d_macro_parameters`  
**Domain:** Investments  
**Registry grain:** **FinancialYear**  
**Producer:** `CoreEngine`  
**Publication order:** `110`

| Column | Physical type / constraint |
|---|---|
| `FY` | `TEXT PRIMARY KEY` |
| `FY_Start_Date` | `DATE` |
| `FY_End_Date` | `DATE` |
| `Debt_MF_Cutoff_Date` | `DATE` |
| `Inflation_Rate` | `DOUBLE` |
| `Risk_Free_Rate` | `DOUBLE` |
| `Equity_Listed_LTCG` | `DOUBLE` |
| `Equity_Listed_STCG` | `DOUBLE` |
| `Equity_Unlisted_LTCG` | `DOUBLE` |
| `Equity_Unlisted_STCG` | `DOUBLE` |
| `Equity_LTCG_Exemption` | `BIGINT` |
| `Gold_LTCG` | `DOUBLE` |
| `Gold_STCG` | `DOUBLE` |
| `Debt_MF_Pre_Cutoff_LTCG` | `DOUBLE` |
| `Debt_MF_Pre_Cutoff_STCG` | `DOUBLE` |
| `Debt_MF_Post_Cutoff_LTCG` | `DOUBLE` |
| `Debt_MF_Post_Cutoff_STCG` | `DOUBLE` |
| `Other_Debt_LTCG` | `DOUBLE` |
| `Other_Debt_STCG` | `DOUBLE` |
| `Default_LTCG` | `DOUBLE` |
| `Default_STCG` | `DOUBLE` |
| `Estimated_Ordinary_Income_Tax_Rate` | `DOUBLE` |
| `Remarks` | `TEXT` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |

The physical DDL defines **25 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Income_Transactions`

**Contract ID:** `df_f_income_transactions`  
**Domain:** Wealth  
**Registry grain:** **Transaction**  
**Producer:** `CoreEngine`  
**Publication order:** `120`

| Column | Physical type / constraint |
|---|---|
| `UID` | `TEXT PRIMARY KEY` |
| `DATE` | `DATE NOT NULL` |
| `ASSET_ID` | `TEXT NOT NULL` |
| `CATEGORY_ID` | `TEXT NOT NULL` |
| `CURRENCY_ID` | `TEXT` |
| `TO_ASSET_ID` | `TEXT` |
| `TRANSFER_UID` | `TEXT` |
| `TIME` | `TEXT` |
| `DESCRIPTION` | `TEXT` |
| `PAID` | `TEXT` |
| `TRANSACTION_TYPE` | `BIGINT` |
| `FEES_NOTES` | `TEXT` |
| `MARK` | `TEXT` |
| `TRANSFER_FEES` | `TEXT` |
| `CARDDIVIDMONTH` | `BIGINT` |
| `Is_Active_Income` | `BOOLEAN` |
| `Is_Dividend_Income` | `BOOLEAN` |
| `Is_Interest_Income` | `BOOLEAN` |
| `Is_Non_Cash_Income` | `BOOLEAN` |
| `BASE_AMOUNT` | `DOUBLE` |
| `AMOUNT_ACCOUNT` | `DOUBLE` |
| `LOCAL_AMOUNT` | `DOUBLE` |
| `EXCH_RATE` | `DOUBLE` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |
| `S_NO` | `BIGINT` |
| `TIMESTAMP` | `BIGINT` |
| `UPDATED_TIME` | `BIGINT` |

The physical DDL defines **28 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Expense_Transactions`

**Contract ID:** `df_f_expense_transactions`  
**Domain:** Wealth  
**Registry grain:** **Transaction**  
**Producer:** `CoreEngine`  
**Publication order:** `130`

| Column | Physical type / constraint |
|---|---|
| `UID` | `TEXT PRIMARY KEY` |
| `DATE` | `DATE NOT NULL` |
| `ASSET_ID` | `TEXT NOT NULL` |
| `CATEGORY_ID` | `TEXT NOT NULL` |
| `CURRENCY_ID` | `TEXT` |
| `TO_ASSET_ID` | `TEXT` |
| `TRANSFER_UID` | `TEXT` |
| `TIME` | `TEXT` |
| `DESCRIPTION` | `TEXT` |
| `PAID` | `TEXT` |
| `TRANSACTION_TYPE` | `BIGINT` |
| `FEES_NOTES` | `TEXT` |
| `MARK` | `TEXT` |
| `TRANSFER_FEES` | `TEXT` |
| `CARDDIVIDMONTH` | `BIGINT` |
| `Is_Core_Expense` | `BOOLEAN` |
| `BASE_AMOUNT` | `DOUBLE` |
| `AMOUNT_ACCOUNT` | `DOUBLE` |
| `LOCAL_AMOUNT` | `DOUBLE` |
| `EXCH_RATE` | `DOUBLE` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |
| `S_NO` | `BIGINT` |
| `TIMESTAMP` | `BIGINT` |
| `UPDATED_TIME` | `BIGINT` |

The physical DDL defines **25 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Transfer_Transactions`

**Contract ID:** `df_f_transfer_transactions`  
**Domain:** Wealth  
**Registry grain:** **Transaction**  
**Producer:** `CoreEngine`  
**Publication order:** `140`

| Column | Physical type / constraint |
|---|---|
| `UID` | `TEXT PRIMARY KEY` |
| `DATE` | `DATE NOT NULL` |
| `ADJUSTED_DATE_FOR_ANALYSIS` | `DATE` |
| `ASSET_ID` | `TEXT NOT NULL` |
| `TO_ASSET_ID` | `TEXT` |
| `CATEGORY_ID` | `TEXT` |
| `CURRENCY_ID` | `TEXT` |
| `TRANSFER_UID` | `TEXT` |
| `TIME` | `TEXT` |
| `DESCRIPTION` | `TEXT` |
| `PAID` | `TEXT` |
| `TRANSACTION_TYPE` | `BIGINT` |
| `TRANSFER_TYPE` | `TEXT` |
| `FEES_NOTES` | `TEXT` |
| `MARK` | `TEXT` |
| `TRANSFER_FEES` | `TEXT` |
| `CARDDIVIDMONTH` | `BIGINT` |
| `BASE_AMOUNT` | `DOUBLE` |
| `AMOUNT_ACCOUNT` | `DOUBLE` |
| `AMOUNT_PROPER` | `DOUBLE` |
| `LOCAL_AMOUNT` | `DOUBLE` |
| `EXCH_RATE` | `DOUBLE` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |
| `S_NO` | `BIGINT` |
| `TIMESTAMP` | `BIGINT` |
| `UPDATED_TIME` | `BIGINT` |

The physical DDL defines **27 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Opening_Balances`

**Contract ID:** `df_f_opening_balances`  
**Domain:** Wealth  
**Registry grain:** **Balance**  
**Producer:** `CoreEngine`  
**Publication order:** `150`

| Column | Physical type / constraint |
|---|---|
| `Z_PK` | `BIGINT PRIMARY KEY` |
| `ZTXDATESTR` | `DATE` |
| `ZASSETUID` | `TEXT` |
| `ZCATEGORYUID` | `TEXT` |
| `ZCURRENCYUID` | `TEXT` |
| `ZTOASSETUID` | `TEXT` |
| `ZTXUIDFEE` | `TEXT` |
| `ZTXUIDTRANS` | `TEXT` |
| `ZUID` | `TEXT` |
| `ZCONTENT` | `TEXT` |
| `ZDO_TYPE` | `BIGINT` |
| `ZAMOUNT` | `DOUBLE` |
| `ZAMOUNTACCOUNT` | `DOUBLE` |
| `ZAMOUNTSUB` | `DOUBLE` |
| `ZDATE` | `DOUBLE` |
| `ZUTIME` | `BIGINT` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |

The physical DDL defines **18 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Investment_Market_Data`

**Contract ID:** `df_f_investment_market_data`  
**Domain:** Investments  
**Registry grain:** **Quote**  
**Producer:** `CoreEngine`  
**Publication order:** `160`

| Column | Physical type / constraint |
|---|---|
| `Date` | `DATE NOT NULL` |
| `ISIN` | `TEXT NOT NULL` |
| `CURRENCY_ID` | `TEXT` |
| `__file_category__` | `TEXT` |
| `Quantity` | `DOUBLE` |
| `Closing_Price` | `DOUBLE` |
| `Buy_Price` | `DOUBLE` |
| `Closing_Value` | `DOUBLE` |
| `Buy_Value` | `DOUBLE` |
| `Closing_Price_Local` | `DOUBLE` |
| `Buy_Price_Local` | `DOUBLE` |
| `Closing_Value_Local` | `DOUBLE` |
| `Buy_Value_Local` | `DOUBLE` |
| `FX_Rate` | `DOUBLE` |
| `Unit_PnL` | `DOUBLE` |
| `Total_PnL` | `DOUBLE` |
| `Data_Provider` | `TEXT` |
| `Extraction_Time` | `TEXT` |
| `Requested_Start` | `DATE` |
| `Requested_End` | `DATE` |
| `Is_Closure_Gap` | `BOOLEAN` |
| `Is_Imputed` | `BOOLEAN` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |

The physical DDL defines **24 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Investment_Purchase_Data`

**Contract ID:** `df_f_tf_inv_purchase`  
**Domain:** Investments  
**Registry grain:** **Trade**  
**Producer:** `CoreEngine`  
**Publication order:** `170`

| Column | Physical type / constraint |
|---|---|
| `Purchase_ID` | `TEXT PRIMARY KEY` |
| `Date` | `DATE NOT NULL` |
| `ISIN` | `TEXT NOT NULL` |
| `CURRENCY_ID` | `TEXT` |
| `__file_category__` | `TEXT` |
| `Quantity` | `DOUBLE` |
| `Price` | `DOUBLE` |
| `Value` | `DOUBLE` |
| `Price_Local` | `DOUBLE` |
| `Value_Local` | `DOUBLE` |
| `FX_Rate` | `DOUBLE` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |

The physical DDL defines **13 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Investment_Sale_Data`

**Contract ID:** `df_f_tf_inv_sale`  
**Domain:** Investments  
**Registry grain:** **Trade**  
**Producer:** `CoreEngine`  
**Publication order:** `180`

| Column | Physical type / constraint |
|---|---|
| `Sale_ID` | `TEXT PRIMARY KEY` |
| `Date` | `DATE NOT NULL` |
| `ISIN` | `TEXT NOT NULL` |
| `CURRENCY_ID` | `TEXT` |
| `__file_category__` | `TEXT` |
| `Quantity` | `DOUBLE` |
| `Sell_Price` | `DOUBLE` |
| `Sell_Value` | `DOUBLE` |
| `Buy_Price` | `DOUBLE` |
| `Buy_Value` | `DOUBLE` |
| `Sell_Price_Local` | `DOUBLE` |
| `Sell_Value_Local` | `DOUBLE` |
| `Buy_Price_Local` | `DOUBLE` |
| `Buy_Value_Local` | `DOUBLE` |
| `FX_Rate` | `DOUBLE` |
| `Unit_PnL` | `DOUBLE` |
| `Total_PnL` | `DOUBLE` |
| `__file_name__` | `TEXT` |
| `__folder_path__` | `TEXT` |

The physical DDL defines **19 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Investment_Benchmark_Data`

**Contract ID:** `df_f_investment_benchmark_data`  
**Domain:** Investments  
**Registry grain:** **Quote**  
**Producer:** `CoreEngine`  
**Publication order:** `190`

| Column | Physical type / constraint |
|---|---|
| `Date` | `DATE` |
| `ID` | `TEXT` |
| `CURRENCY_ID` | `TEXT` |
| `Benchmark_Name` | `TEXT` |
| `yF_Ticker` | `TEXT` |
| `Close` | `DOUBLE` |
| `Data_Provider` | `TEXT` |
| `Extraction_Time` | `TEXT` |
| `Requested_Start` | `DATE` |
| `Requested_End` | `DATE` |
| `Is_Closure_Gap` | `BOOLEAN` |
| `Is_Imputed` | `BOOLEAN` |

The physical DDL defines **12 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Investment_Analytics_Lot`

**Contract ID:** `df_f_investment_analytics_lot`  
**Domain:** Investments  
**Registry grain:** **ISIN-Lot**  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `200`

Canonical Quant lot/snapshot output. Grain is registry-defined as ISIN-Lot; fields carry reconstructed holdings, valuation, performance, benchmark, FX, and tax-relevant state.

| Column | Physical type / constraint |
|---|---|
| `Lot_ID` | `TEXT NOT NULL` |
| `Closing_Date` | `DATE NOT NULL` |
| `ISIN` | `TEXT NOT NULL` |
| `CURRENCY_ID` | `TEXT` |
| `Buy_Date` | `DATE` |
| `Purchase_ID` | `TEXT` |
| `Lot_Source_Type` | `TEXT NOT NULL` |
| `BENCHMARK_ID` | `TEXT` |
| `TAX_TYPE` | `TEXT` |
| `TAX_SUBTYPE` | `TEXT` |
| `Quantity` | `DOUBLE` |
| `Execution_Residual` | `DOUBLE` |
| `Buy_Price` | `DOUBLE` |
| `Market_Price` | `DOUBLE` |
| `Buy_Value` | `DOUBLE` |
| `Close_Value` | `DOUBLE` |
| `Buy_Value_Local` | `DOUBLE` |
| `Close_Value_Local` | `DOUBLE` |
| `Blended_FX_Buy_Rate` | `DOUBLE` |
| `Buy_Price_Local` | `DOUBLE` |
| `Market_Price_Local` | `DOUBLE` |
| `FX_Rate_Buy` | `DOUBLE` |
| `FX_Rate_Snap` | `DOUBLE` |
| `Currency_Appreciation_Pct` | `DOUBLE` |
| `Absolute_Return` | `DOUBLE` |
| `Absolute_Return_Local` | `DOUBLE` |
| `Asset_PnL` | `DOUBLE` |
| `Forex_PnL` | `DOUBLE` |
| `Forex_Contribution_Pct` | `DOUBLE` |
| `Asset_Return_Pct` | `DOUBLE` |
| `Forex_Return_Pct` | `DOUBLE` |
| `Lot_CAGR` | `DOUBLE` |
| `Lot_CAGR_Local` | `DOUBLE` |
| `CAGR` | `DOUBLE` |
| `XIRR` | `DOUBLE` |
| `XIRR_Status` | `TEXT` |
| `XIRR_Local` | `DOUBLE` |
| `FX_XIRR_Impact` | `DOUBLE` |
| `After_Tax_XIRR` | `DOUBLE` |
| `BM_Buy_Price` | `DOUBLE` |
| `BM_Market_Price` | `DOUBLE` |
| `Lot_BM_Return` | `DOUBLE` |
| `Lot_BM_CAGR` | `DOUBLE` |
| `Lot_BM_CAGR_Local` | `DOUBLE` |
| `BM_CAGR` | `DOUBLE` |
| `BM_XIRR` | `DOUBLE` |
| `BM_XIRR_Local` | `DOUBLE` |
| `Active_Return` | `DOUBLE` |
| `Active_Return_Local` | `DOUBLE` |
| `Lot_Alpha` | `DOUBLE` |
| `Is_Lagging_Benchmark` | `BIGINT` |
| `Max_Drawdown` | `DOUBLE` |
| `Lot_Weight` | `DOUBLE` |
| `Portfolio_Weight` | `DOUBLE` |
| `Outperforming_Lot_Ratio` | `DOUBLE` |
| `Dietz_Day_Weight` | `DOUBLE` |
| `Age_Days` | `BIGINT` |
| `LTCG_Threshold_Days` | `BIGINT` |
| `Days_To_LTCG` | `BIGINT` |
| `Holding_Type` | `TEXT` |
| `Tax_Rate` | `DOUBLE` |
| `Unrealized_LTCG` | `DOUBLE` |
| `Unrealized_STCG` | `DOUBLE` |
| `Unrealized_Gain` | `DOUBLE` |
| `Unrealized_LTCL` | `DOUBLE` |
| `Unrealized_STCL` | `DOUBLE` |
| `Unrealized_Loss` | `DOUBLE` |
| `LTCG_Tax_If_Sold` | `DOUBLE` |
| `STCG_Tax_If_Sold` | `DOUBLE` |
| `After_Tax_PL` | `DOUBLE` |
| `After_Tax_Close_Value` | `DOUBLE` |
| `FY` | `TEXT` |
| `FY_Realized_LTCG` | `DOUBLE` |
| `FY_Realized_STCG` | `DOUBLE` |
| `FY_Realized_Gain` | `DOUBLE` |
| `FY_Realized_LTCL` | `DOUBLE` |
| `FY_Realized_STCL` | `DOUBLE` |
| `FY_Realized_Loss` | `DOUBLE` |
| `FY_Realized_Net_PnL` | `DOUBLE` |
| `Equity_LTCG_Exemption` | `BIGINT` |
| `Stepup_Eligible` | `BIGINT` |
| `Can_Harvest_Loss` | `BOOLEAN` |
| `Harvest_Recommendation` | `TEXT` |

The physical DDL defines **83 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Investment_Realized_Events`

**Contract ID:** `df_f_investment_realized_events`  
**Domain:** Investments  
**Registry grain:** **RealizedEvent**  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `205`

One realized disposal component produced by canonical FIFO processing. A single sale may produce multiple rows when it consumes multiple acquisition lots.

| Column | Physical type / constraint |
|---|---|
| `Realized_Event_ID` | `TEXT PRIMARY KEY` |
| `Sale_ID` | `TEXT NOT NULL` |
| `Lot_ID` | `TEXT NOT NULL` |
| `Purchase_ID` | `TEXT` |
| `ISIN` | `TEXT` |
| `Acquisition_Date` | `DATE` |
| `Disposal_Date` | `DATE` |
| `FY` | `TEXT` |
| `Quantity_Disposed` | `DOUBLE` |
| `Acquisition_Price` | `DOUBLE` |
| `Disposed_Cost_Basis` | `DOUBLE` |
| `Sale_Price` | `DOUBLE` |
| `Sale_Proceeds` | `DOUBLE` |
| `Realized_Gain_Loss` | `DOUBLE` |
| `Holding_Type` | `TEXT` |
| `Tax_Type` | `TEXT` |
| `Tax_Subtype` | `TEXT` |
| `Lot_Source_Type` | `TEXT` |
| `Currency_ID` | `TEXT` |
| `Asset_PnL_Local` | `DOUBLE` |
| `Asset_PnL` | `DOUBLE` |
| `Forex_PnL` | `DOUBLE` |
| `Applied_Rate` | `DOUBLE` |
| `Estimated_Tax` | `DOUBLE` |

The physical DDL defines **24 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Investment_Reconciliation_Events`

**Contract ID:** `df_f_investment_reconciliation_events`  
**Domain:** Investments  
**Registry grain:** **ReconEvent**  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `206`

Explicit provenance for quantity or cost-basis reconciliation between reconstructed and observed investment state.

| Column | Physical type / constraint |
|---|---|
| `Reconciliation_Group_ID` | `TEXT NOT NULL` |
| `Reconciliation_Event_ID` | `TEXT PRIMARY KEY` |
| `Run_ID` | `TEXT` |
| `ISIN` | `TEXT NOT NULL` |
| `Reconciliation_Date` | `DATE NOT NULL` |
| `Lot_ID` | `TEXT` |
| `Purchase_ID` | `TEXT` |
| `Adjustment_Type` | `TEXT` |
| `Reason` | `TEXT` |
| `Broker_Quantity` | `DOUBLE` |
| `Reconstructed_Quantity` | `DOUBLE` |
| `Quantity_Adjustment` | `DOUBLE` |
| `Broker_Cost_Basis` | `DOUBLE` |
| `Reconstructed_Cost_Basis` | `DOUBLE` |
| `Cost_Basis_Adjustment` | `DOUBLE` |
| `Original_Unit_Cost` | `DOUBLE` |
| `Adjusted_Unit_Cost` | `DOUBLE` |

The physical DDL defines **17 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

### `silver.f_Tax_Events`

**Contract ID:** `df_f_tax_events`  
**Domain:** Taxes  
**Registry grain:** **TaxEvent**  
**Producer:** `TaxEngine`  
**Publication order:** `300`

Canonical tax-preparation evidence normalized from household ledger income and Quant realized events.

| Column | Physical type / constraint |
|---|---|
| `Tax_Event_ID` | `TEXT PRIMARY KEY` |
| `FY` | `TEXT NOT NULL` |
| `Event_Date` | `DATE NOT NULL` |
| `Source_Type` | `TEXT NOT NULL` |
| `Source_ID` | `TEXT NOT NULL` |
| `Income_Head` | `TEXT NOT NULL` |
| `Tax_Sub_Head` | `TEXT NOT NULL` |
| `Amount_INR` | `DOUBLE NOT NULL` |
| `Applied_Rate` | `DOUBLE` |
| `Estimated_Tax` | `DOUBLE` |
| `CURRENCY_ID` | `TEXT` |
| `Tax_Status` | `TEXT NOT NULL` |
| `Tax_Status_Reason` | `TEXT` |
| `ISIN` | `TEXT` |
| `Lot_ID` | `TEXT` |

The physical DDL defines **15 columns** for this table. The registry grain is the semantic row contract; it should be used when reasoning about joins and uniqueness rather than assuming the first ID-looking column is automatically the grain.

## Publication invariants

- Every registered contract has a non-empty ID, physical table, grain, producer, and supported layer.
- Contract IDs and physical table mappings are unique.
- Engine output keys must match registered contract IDs.
- Registered outputs must be produced before publication; unregistered outputs are rejected.
- Physical DDL and producer output must remain compatible with `INSERT ... BY NAME`/loader behavior.
- Schema changes are contract changes even when the database engine can technically coerce them.

## Ownership boundary

Reference specifies the physical contract, not the full financial derivation. Financial formulas and interpretation live in the Finance specifications; orchestration and persistence behavior live in Architecture. This separation keeps the contract pages useful during implementation work instead of turning them into duplicate textbooks.

## Related specifications

- [Warehouse Architecture](../architecture/warehouse-architecture.md)
- [Data Model](../architecture/data-model.md)
- [Identity and Grain Contracts](identity-and-grain-contracts.md)
- [Data Contract and Schema Evolution](../developer/data-contract-and-schema-evolution.md)
