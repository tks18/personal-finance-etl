# Silver Data Contracts

Silver is the canonical analytical layer: dimensions, household facts, investment facts, reconstructed investment state, reconciliation events, and Tax events live here at explicit grains.

The registry answers **what the dataset means operationally**. The DDL answers **what the dataset physically contains**. Both are part of the contract.

## Registry authority

```python
@dataclass
class DataContract:
    contract_id: str
    layer: str
    physical_table: str
    domain: str
    grain: str
    producer: str
    publication_order: int
```

Source: `src/personal_finance_etl/infrastructure/warehouse/registry.py`

## Contract catalog

| Contract ID | Physical table | Domain | Grain | Producer | Order |
|---|---|---|---|---|---:|
| `df_d_calendar` | `silver.d_Calendar` | Common | `Day` | `CoreEngine` | 10 |
| `df_d_income_category` | `silver.d_Income_Category` | Wealth | `Category` | `CoreEngine` | 20 |
| `df_d_income_subcategory` | `silver.d_Income_Subcategory` | Wealth | `Subcategory` | `CoreEngine` | 30 |
| `df_d_expense_category` | `silver.d_Expense_Category` | Wealth | `Category` | `CoreEngine` | 40 |
| `df_d_expense_subcategory` | `silver.d_Expense_Subcategory` | Wealth | `Subcategory` | `CoreEngine` | 50 |
| `df_d_asset_category` | `silver.d_Asset_Category` | Wealth | `Category` | `CoreEngine` | 60 |
| `df_d_asset_subcategory` | `silver.d_Asset_SubCategory` | Wealth | `Subcategory` | `CoreEngine` | 70 |
| `df_d_currency` | `silver.d_Currency` | Common | `Currency` | `CoreEngine` | 80 |
| `df_d_benchmark_master` | `silver.d_Investment_Benchmark_Master` | Investments | `Benchmark` | `CoreEngine` | 90 |
| `df_f_currency_fx_rates` | `silver.f_Currency_FX_Rates` | Common | `Date-Currency` | `CoreEngine` | 95 |
| `df_d_investment_master` | `silver.d_Investment_Master` | Investments | `ISIN` | `CoreEngine` | 100 |
| `df_d_macro_parameters` | `silver.d_Macro_Parameters` | Investments | `FinancialYear` | `CoreEngine` | 110 |
| `df_f_income_transactions` | `silver.f_Income_Transactions` | Wealth | `Transaction` | `CoreEngine` | 120 |
| `df_f_expense_transactions` | `silver.f_Expense_Transactions` | Wealth | `Transaction` | `CoreEngine` | 130 |
| `df_f_transfer_transactions` | `silver.f_Transfer_Transactions` | Wealth | `Transaction` | `CoreEngine` | 140 |
| `df_f_opening_balances` | `silver.f_Opening_Balances` | Wealth | `Balance` | `CoreEngine` | 150 |
| `df_f_investment_market_data` | `silver.f_Investment_Market_Data` | Investments | `Quote` | `CoreEngine` | 160 |
| `df_f_tf_inv_purchase` | `silver.f_Investment_Purchase_Data` | Investments | `Trade` | `CoreEngine` | 170 |
| `df_f_tf_inv_sale` | `silver.f_Investment_Sale_Data` | Investments | `Trade` | `CoreEngine` | 180 |
| `df_f_investment_benchmark_data` | `silver.f_Investment_Benchmark_Data` | Investments | `Quote` | `CoreEngine` | 190 |
| `df_f_investment_analytics_lot` | `silver.f_Investment_Analytics_Lot` | Investments | `ISIN-Lot` | `InvestmentQuantEngine` | 200 |
| `df_f_investment_realized_events` | `silver.f_Investment_Realized_Events` | Investments | `RealizedEvent` | `InvestmentQuantEngine` | 205 |
| `df_f_investment_reconciliation_events` | `silver.f_Investment_Reconciliation_Events` | Investments | `ReconEvent` | `InvestmentQuantEngine` | 206 |
| `df_f_tax_events` | `silver.f_Tax_Events` | Taxes | `TaxEvent` | `TaxEngine` | 300 |


## Physical schemas

The following tables are generated directly from `schema/silver.py`. Column order therefore matches the declared warehouse contract.

### `silver.d_Calendar`

**Contract ID:** `df_d_calendar`  
**Grain:** `Day`  
**Domain:** `Common`  
**Producer:** `CoreEngine`  
**Publication order:** `10`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Date` | `DATE PRIMARY KEY` | Identifiers |
| `Day` | `BIGINT` | Descriptors/Classifications |
| `Day_Name` | `TEXT` | Descriptors/Classifications |
| `Day_Name_Short` | `TEXT` | Descriptors/Classifications |
| `Day_Ordinal` | `BIGINT` | Descriptors/Classifications |
| `Day_Ordinal_Name` | `TEXT` | Descriptors/Classifications |
| `Weekday` | `BIGINT` | Descriptors/Classifications |
| `IS_WEEKEND` | `BIGINT` | Descriptors/Classifications |
| `Week` | `BIGINT` | Descriptors/Classifications |
| `Week_Ordinal` | `BIGINT` | Descriptors/Classifications |
| `Week_Ordinal_Name` | `TEXT` | Descriptors/Classifications |
| `Week_Name` | `TEXT` | Descriptors/Classifications |
| `Week_Year` | `TEXT` | Descriptors/Classifications |
| `Week_Name_Year` | `TEXT` | Descriptors/Classifications |
| `Start_of_Week` | `DATE` | Descriptors/Classifications |
| `End_of_Week` | `DATE` | Descriptors/Classifications |
| `Month` | `BIGINT` | Descriptors/Classifications |
| `Month_Name` | `TEXT` | Descriptors/Classifications |
| `Month_Name_Short` | `TEXT` | Descriptors/Classifications |
| `Month_Year` | `TEXT` | Descriptors/Classifications |
| `Short_Month_Year` | `TEXT` | Descriptors/Classifications |
| `V_Short_Month_Year` | `TEXT` | Descriptors/Classifications |
| `Month_Ordinal` | `BIGINT` | Descriptors/Classifications |
| `Start_of_Month` | `DATE` | Descriptors/Classifications |
| `End_of_Month` | `DATE` | Descriptors/Classifications |
| `Days_in_Month` | `BIGINT` | Descriptors/Classifications |
| `Month_Progress_Pct` | `DOUBLE` | Descriptors/Classifications |
| `Quarter` | `BIGINT` | Descriptors/Classifications |
| `Quarter_Name` | `TEXT` | Descriptors/Classifications |
| `Quarter_Year` | `TEXT` | Descriptors/Classifications |
| `Quarter_Ordinal` | `BIGINT` | Descriptors/Classifications |
| `Start_of_Quarter` | `DATE` | Descriptors/Classifications |
| `End_of_Quarter` | `DATE` | Descriptors/Classifications |
| `Year` | `BIGINT` | Descriptors/Classifications |
| `Days_in_Year` | `BIGINT` | Descriptors/Classifications |
| `Year_Progress_Pct` | `DOUBLE` | Descriptors/Classifications |
| `Financial_Year` | `TEXT` | Descriptors/Classifications |
| `FY_Year` | `BIGINT` | Descriptors/Classifications |
| `FY_Month` | `BIGINT` | Descriptors/Classifications |
| `FY_Month_Ordinal` | `BIGINT` | Descriptors/Classifications |
| `FY_Quarter` | `BIGINT` | Descriptors/Classifications |
| `FY_Quarter_Name` | `TEXT` | Descriptors/Classifications |
| `FY_Quarter_Year` | `TEXT` | Descriptors/Classifications |
| `FY_Quarter_Ordinal` | `BIGINT` | Descriptors/Classifications |
| `FY_Start_of_Month` | `DATE` | Descriptors/Classifications |
| `FY_End_of_Month` | `DATE` | Descriptors/Classifications |
| `FY_Start_of_Quarter` | `DATE` | Descriptors/Classifications |
| `FY_End_of_Quarter` | `DATE` | Descriptors/Classifications |
| `Is_Last_Day_Of_Month` | `BOOLEAN` | Flags |
| `Is_Last_Day_Of_Quarter` | `BOOLEAN` | Flags |
| `Is_Last_Day_Of_Year` | `BOOLEAN` | Flags |
| `Is_Last_Day_Of_FY` | `BOOLEAN` | Flags |
| `Is_Quarter_End_Month` | `BOOLEAN` | Flags |
| `Is_Tax_Harvesting_Season` | `BOOLEAN` | Flags |
| `Is_Current_Month` | `BOOLEAN` | Flags |
| `Is_Previous_Month` | `BOOLEAN` | Flags |
| `Is_Current_Quarter` | `BOOLEAN` | Flags |
| `Is_Previous_Quarter` | `BOOLEAN` | Flags |
| `Is_Current_Year` | `BOOLEAN` | Flags |
| `Is_Previous_Year` | `BOOLEAN` | Flags |
| `Is_Current_FY` | `BOOLEAN` | Flags |
| `Is_YTD` | `BOOLEAN` | Flags |
| `Is_FY_YTD` | `BOOLEAN` | Flags |
| `Is_Future_Date` | `BOOLEAN` | Flags |

### `silver.d_Income_Category`

**Contract ID:** `df_d_income_category`  
**Grain:** `Category`  
**Domain:** `Wealth`  
**Producer:** `CoreEngine`  
**Publication order:** `20`

| Column | Physical type / constraint | Role |
|---|---|---|
| `UID` | `TEXT PRIMARY KEY` | Identifiers |
| `CATEGORY_NAME` | `TEXT` | Descriptors/Classifications |
| `CATEGORY_NAME_SHORT` | `TEXT` | Descriptors/Classifications |
| `ORDER_SEQUENCE` | `BIGINT` | Descriptors/Classifications |
| `__file_name__` | `TEXT` | Descriptors/Classifications |
| `__folder_path__` | `TEXT` | Descriptors/Classifications |
| `S_NO` | `BIGINT` | Descriptors/Classifications |
| `MODIFY_DATE` | `BIGINT` | Descriptors/Classifications |

### `silver.d_Income_Subcategory`

**Contract ID:** `df_d_income_subcategory`  
**Grain:** `Subcategory`  
**Domain:** `Wealth`  
**Producer:** `CoreEngine`  
**Publication order:** `30`

| Column | Physical type / constraint | Role |
|---|---|---|
| `UID` | `TEXT PRIMARY KEY` | Identifiers |
| `CATEGORY_ID` | `TEXT` | Identifiers |
| `CATEGORY_NAME` | `TEXT` | Descriptors/Classifications |
| `CATEGORY_GROUPS` | `TEXT` | Descriptors/Classifications |
| `ORDER_SEQUENCE` | `BIGINT` | Descriptors/Classifications |
| `Is_Active_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Passive_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Dividend_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Interest_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Non_Cash_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Investment_Exclusion` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Tax_Credits` | `BOOLEAN` | Descriptors/Classifications |
| `__file_name__` | `TEXT` | Descriptors/Classifications |
| `__folder_path__` | `TEXT` | Descriptors/Classifications |
| `S_NO` | `BIGINT` | Descriptors/Classifications |
| `MODIFY_DATE` | `BIGINT` | Descriptors/Classifications |
| `Tax_Income_Head` | `TEXT` | Descriptors/Classifications |
| `Tax_Sub_Head` | `TEXT` | Descriptors/Classifications |
| `Taxability` | `TEXT` | Descriptors/Classifications |
| `Tax_Method` | `TEXT` | Descriptors/Classifications |

**Table constraints**

- `FOREIGN KEY (CATEGORY_ID) REFERENCES silver.d_Income_Category(UID)`

### `silver.d_Expense_Category`

**Contract ID:** `df_d_expense_category`  
**Grain:** `Category`  
**Domain:** `Wealth`  
**Producer:** `CoreEngine`  
**Publication order:** `40`

| Column | Physical type / constraint | Role |
|---|---|---|
| `UID` | `TEXT PRIMARY KEY` | Identifiers |
| `CATEGORY_NAME` | `TEXT` | Descriptors/Classifications |
| `ORDER_SEQUENCE` | `BIGINT` | Descriptors/Classifications |
| `__file_name__` | `TEXT` | Descriptors/Classifications |
| `__folder_path__` | `TEXT` | Descriptors/Classifications |
| `S_NO` | `BIGINT` | Descriptors/Classifications |
| `MODIFY_DATE` | `BIGINT` | Descriptors/Classifications |

### `silver.d_Expense_Subcategory`

**Contract ID:** `df_d_expense_subcategory`  
**Grain:** `Subcategory`  
**Domain:** `Wealth`  
**Producer:** `CoreEngine`  
**Publication order:** `50`

| Column | Physical type / constraint | Role |
|---|---|---|
| `UID` | `TEXT PRIMARY KEY` | Identifiers |
| `CATEGORY_ID` | `TEXT` | Identifiers |
| `CATEGORY_NAME` | `TEXT` | Descriptors/Classifications |
| `ORDER_SEQUENCE` | `BIGINT` | Descriptors/Classifications |
| `Is_Core_Expense` | `BOOLEAN` | Descriptors/Classifications |
| `__file_name__` | `TEXT` | Descriptors/Classifications |
| `__folder_path__` | `TEXT` | Descriptors/Classifications |
| `S_NO` | `BIGINT` | Descriptors/Classifications |
| `MODIFY_DATE` | `BIGINT` | Descriptors/Classifications |

**Table constraints**

- `FOREIGN KEY(CATEGORY_ID) REFERENCES silver.d_Expense_Category(UID)`

### `silver.d_Asset_Category`

**Contract ID:** `df_d_asset_category`  
**Grain:** `Category`  
**Domain:** `Wealth`  
**Producer:** `CoreEngine`  
**Publication order:** `60`

| Column | Physical type / constraint | Role |
|---|---|---|
| `UID` | `TEXT PRIMARY KEY` | Identifiers |
| `ASSET_GROUP` | `TEXT` | Descriptors/Classifications |
| `TYPE` | `BIGINT` | Descriptors/Classifications |
| `ORDER_SEQUENCE` | `BIGINT` | Descriptors/Classifications |
| `ledger_role` | `TEXT` | Descriptors/Classifications |
| `cashflow_activity_type` | `TEXT` | Descriptors/Classifications |
| `settlement_timing` | `TEXT` | Descriptors/Classifications |
| `Is_Digital_Asset` | `BOOLEAN` | Descriptors/Classifications |
| `is_cash_pool` | `BOOLEAN` | Descriptors/Classifications |
| `is_non_cash_pnl` | `BOOLEAN` | Descriptors/Classifications |
| `__file_name__` | `TEXT` | Descriptors/Classifications |
| `__folder_path__` | `TEXT` | Descriptors/Classifications |
| `DEVICE_ID` | `BIGINT` | Descriptors/Classifications |
| `USE_TIME` | `BIGINT` | Descriptors/Classifications |

### `silver.d_Asset_Subcategory`

| Column | Physical type / constraint | Role |
|---|---|---|
| `UID` | `TEXT PRIMARY KEY` | Identifiers |
| `ASSET_GROUP_ID` | `TEXT` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `AUTOPAY_ASSET_ID` | `TEXT` | Identifiers |
| `ASSET_NAME` | `TEXT` | Descriptors/Classifications |
| `ASSET_DESCRIPTION` | `TEXT` | Descriptors/Classifications |
| `NOTES` | `TEXT` | Descriptors/Classifications |
| `ORDER_SEQUENCE` | `BIGINT` | Descriptors/Classifications |
| `ledger_role` | `TEXT` | Descriptors/Classifications |
| `cashflow_activity_type` | `TEXT` | Descriptors/Classifications |
| `settlement_timing` | `TEXT` | Descriptors/Classifications |
| `TRANSFER_EXPENSE` | `BIGINT` | Descriptors/Classifications |
| `CARD_AUTOPAY` | `BIGINT` | Descriptors/Classifications |
| `CARD_STATEMENT_DATE` | `BIGINT` | Descriptors/Classifications |
| `CARD_PAYMENT_DATE` | `BIGINT` | Descriptors/Classifications |
| `Is_Liquid` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Illiquid` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Digital_Asset` | `BOOLEAN` | Descriptors/Classifications |
| `is_cash_pool` | `BOOLEAN` | Descriptors/Classifications |
| `is_non_cash_pnl` | `BOOLEAN` | Descriptors/Classifications |
| `__file_name__` | `TEXT` | Descriptors/Classifications |
| `__folder_path__` | `TEXT` | Descriptors/Classifications |
| `S_NO` | `BIGINT` | Descriptors/Classifications |
| `ADDED_TIME` | `BIGINT` | Descriptors/Classifications |

**Table constraints**

- `FOREIGN KEY(ASSET_GROUP_ID) REFERENCES silver.d_Asset_Category(UID)`

### `silver.d_Currency`

**Contract ID:** `df_d_currency`  
**Grain:** `Currency`  
**Domain:** `Common`  
**Producer:** `CoreEngine`  
**Publication order:** `80`

| Column | Physical type / constraint | Role |
|---|---|---|
| `UID` | `TEXT PRIMARY KEY` | Identifiers |
| `CURRENCY_NAME` | `TEXT` | Descriptors/Classifications |
| `ISO` | `TEXT` | Descriptors/Classifications |
| `MAIN_ISO` | `TEXT` | Descriptors/Classifications |
| `Target_Currency_Code` | `TEXT` | Descriptors/Classifications |
| `yF_Ticker` | `TEXT` | Descriptors/Classifications |
| `SYMBOL` | `TEXT` | Descriptors/Classifications |
| `SYMBOL_POSITION` | `TEXT` | Descriptors/Classifications |
| `ORDER_SEQUENCE` | `BIGINT` | Descriptors/Classifications |
| `RATE` | `DOUBLE` | Descriptors/Classifications |
| `DECIMAL_POINT` | `BIGINT` | Descriptors/Classifications |
| `IS_MAIN_CURRENCY` | `BIGINT` | Descriptors/Classifications |
| `IS_SHOW` | `BIGINT` | Descriptors/Classifications |
| `Is_Active` | `BOOLEAN` | Descriptors/Classifications |
| `INSERT_TYPE` | `TEXT` | Descriptors/Classifications |
| `__file_name__` | `TEXT` | Descriptors/Classifications |
| `__folder_path__` | `TEXT` | Descriptors/Classifications |
| `S_NO` | `BIGINT` | Descriptors/Classifications |
| `MODIFY_DATE` | `BIGINT` | Descriptors/Classifications |

### `silver.f_Currency_FX_Rates`

**Contract ID:** `df_f_currency_fx_rates`  
**Grain:** `Date-Currency`  
**Domain:** `Common`  
**Producer:** `CoreEngine`  
**Publication order:** `95`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Date` | `DATE NOT NULL` | Identifiers |
| `Currency_ID` | `TEXT NOT NULL` | Identifiers |
| `Currency_Code` | `TEXT NOT NULL` | Descriptors/Classifications |
| `Target_Currency_Code` | `TEXT NOT NULL` | Descriptors/Classifications |
| `yF_Ticker` | `TEXT NOT NULL` | Descriptors/Classifications |
| `FX_Rate` | `DOUBLE NOT NULL` | Local/FX Values |
| `Data_Provider` | `TEXT` | Provenance |
| `Extraction_Time` | `TEXT` | Provenance |
| `Requested_Start` | `DATE` | Provenance |
| `Requested_End` | `DATE` | Provenance |
| `Is_Closure_Gap` | `BOOLEAN` | Provenance |
| `Is_Imputed` | `BOOLEAN` | Provenance |
| `First_Observation_Date` | `DATE` | Provenance |

**Table constraints**

- `FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date)`
- `FOREIGN KEY(Currency_ID) REFERENCES silver.d_Currency(UID)`

### `silver.f_Income_Transactions`

**Contract ID:** `df_f_income_transactions`  
**Grain:** `Transaction`  
**Domain:** `Wealth`  
**Producer:** `CoreEngine`  
**Publication order:** `120`

| Column | Physical type / constraint | Role |
|---|---|---|
| `UID` | `TEXT PRIMARY KEY` | Identifiers |
| `DATE` | `DATE NOT NULL` | Identifiers |
| `ASSET_ID` | `TEXT NOT NULL` | Identifiers |
| `CATEGORY_ID` | `TEXT NOT NULL` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `TO_ASSET_ID` | `TEXT` | Identifiers |
| `TRANSFER_UID` | `TEXT` | Identifiers |
| `TIME` | `TEXT` | Descriptors/Classifications |
| `DESCRIPTION` | `TEXT` | Descriptors/Classifications |
| `PAID` | `TEXT` | Descriptors/Classifications |
| `TRANSACTION_TYPE` | `BIGINT` | Descriptors/Classifications |
| `FEES_NOTES` | `TEXT` | Descriptors/Classifications |
| `MARK` | `TEXT` | Descriptors/Classifications |
| `TRANSFER_FEES` | `TEXT` | Descriptors/Classifications |
| `CARDDIVIDMONTH` | `BIGINT` | Descriptors/Classifications |
| `Is_Active_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Dividend_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Interest_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Non_Cash_Income` | `BOOLEAN` | Descriptors/Classifications |
| `BASE_AMOUNT` | `DOUBLE` | Position Values |
| `AMOUNT_ACCOUNT` | `DOUBLE` | Position Values |
| `LOCAL_AMOUNT` | `DOUBLE` | Local/FX Values |
| `EXCH_RATE` | `DOUBLE` | Local/FX Values |
| `__file_name__` | `TEXT` | Local/FX Values |
| `__folder_path__` | `TEXT` | Local/FX Values |
| `S_NO` | `BIGINT` | Local/FX Values |
| `TIMESTAMP` | `BIGINT` | Local/FX Values |
| `UPDATED_TIME` | `BIGINT` | Local/FX Values |

**Table constraints**

- `FOREIGN KEY(CATEGORY_ID) REFERENCES silver.d_Income_Subcategory(UID)`
- `FOREIGN KEY(ASSET_ID) REFERENCES silver.d_Asset_Subcategory(UID)`
- `FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)`
- `FOREIGN KEY(DATE) REFERENCES silver.d_Calendar(Date)`

### `silver.f_Expense_Transactions`

**Contract ID:** `df_f_expense_transactions`  
**Grain:** `Transaction`  
**Domain:** `Wealth`  
**Producer:** `CoreEngine`  
**Publication order:** `130`

| Column | Physical type / constraint | Role |
|---|---|---|
| `UID` | `TEXT PRIMARY KEY` | Identifiers |
| `DATE` | `DATE NOT NULL` | Identifiers |
| `ASSET_ID` | `TEXT NOT NULL` | Identifiers |
| `CATEGORY_ID` | `TEXT NOT NULL` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `TO_ASSET_ID` | `TEXT` | Identifiers |
| `TRANSFER_UID` | `TEXT` | Identifiers |
| `TIME` | `TEXT` | Descriptors/Classifications |
| `DESCRIPTION` | `TEXT` | Descriptors/Classifications |
| `PAID` | `TEXT` | Descriptors/Classifications |
| `TRANSACTION_TYPE` | `BIGINT` | Descriptors/Classifications |
| `FEES_NOTES` | `TEXT` | Descriptors/Classifications |
| `MARK` | `TEXT` | Descriptors/Classifications |
| `TRANSFER_FEES` | `TEXT` | Descriptors/Classifications |
| `CARDDIVIDMONTH` | `BIGINT` | Descriptors/Classifications |
| `Is_Core_Expense` | `BOOLEAN` | Descriptors/Classifications |
| `BASE_AMOUNT` | `DOUBLE` | Position Values |
| `AMOUNT_ACCOUNT` | `DOUBLE` | Position Values |
| `LOCAL_AMOUNT` | `DOUBLE` | Local/FX Values |
| `EXCH_RATE` | `DOUBLE` | Local/FX Values |
| `__file_name__` | `TEXT` | Local/FX Values |
| `__folder_path__` | `TEXT` | Local/FX Values |
| `S_NO` | `BIGINT` | Local/FX Values |
| `TIMESTAMP` | `BIGINT` | Local/FX Values |
| `UPDATED_TIME` | `BIGINT` | Local/FX Values |

**Table constraints**

- `FOREIGN KEY(CATEGORY_ID) REFERENCES silver.d_Expense_Subcategory(UID)`
- `FOREIGN KEY(ASSET_ID) REFERENCES silver.d_Asset_Subcategory(UID)`
- `FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)`
- `FOREIGN KEY(DATE) REFERENCES silver.d_Calendar(Date)`

### `silver.f_Transfer_Transactions`

**Contract ID:** `df_f_transfer_transactions`  
**Grain:** `Transaction`  
**Domain:** `Wealth`  
**Producer:** `CoreEngine`  
**Publication order:** `140`

| Column | Physical type / constraint | Role |
|---|---|---|
| `UID` | `TEXT PRIMARY KEY` | Identifiers |
| `DATE` | `DATE NOT NULL` | Identifiers |
| `ADJUSTED_DATE_FOR_ANALYSIS` | `DATE` | Identifiers |
| `ASSET_ID` | `TEXT NOT NULL` | Identifiers |
| `TO_ASSET_ID` | `TEXT` | Identifiers |
| `CATEGORY_ID` | `TEXT` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `TRANSFER_UID` | `TEXT` | Identifiers |
| `TIME` | `TEXT` | Descriptors/Classifications |
| `DESCRIPTION` | `TEXT` | Descriptors/Classifications |
| `PAID` | `TEXT` | Descriptors/Classifications |
| `TRANSACTION_TYPE` | `BIGINT` | Descriptors/Classifications |
| `TRANSFER_TYPE` | `TEXT` | Descriptors/Classifications |
| `FEES_NOTES` | `TEXT` | Descriptors/Classifications |
| `MARK` | `TEXT` | Descriptors/Classifications |
| `TRANSFER_FEES` | `TEXT` | Descriptors/Classifications |
| `CARDDIVIDMONTH` | `BIGINT` | Descriptors/Classifications |
| `BASE_AMOUNT` | `DOUBLE` | Position Values |
| `AMOUNT_ACCOUNT` | `DOUBLE` | Position Values |
| `AMOUNT_PROPER` | `DOUBLE` | Position Values |
| `LOCAL_AMOUNT` | `DOUBLE` | Local/FX Values |
| `EXCH_RATE` | `DOUBLE` | Local/FX Values |
| `__file_name__` | `TEXT` | Local/FX Values |
| `__folder_path__` | `TEXT` | Local/FX Values |
| `S_NO` | `BIGINT` | Local/FX Values |
| `TIMESTAMP` | `BIGINT` | Local/FX Values |
| `UPDATED_TIME` | `BIGINT` | Local/FX Values |

**Table constraints**

- `FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)`
- `FOREIGN KEY(ASSET_ID) REFERENCES silver.d_Asset_Subcategory(UID)`
- `FOREIGN KEY(TO_ASSET_ID) REFERENCES silver.d_Asset_Subcategory(UID)`
- `FOREIGN KEY(DATE) REFERENCES silver.d_Calendar(Date)`
- `FOREIGN KEY(ADJUSTED_DATE_FOR_ANALYSIS) REFERENCES silver.d_Calendar(Date)`

### `silver.f_Opening_Balances`

**Contract ID:** `df_f_opening_balances`  
**Grain:** `Balance`  
**Domain:** `Wealth`  
**Producer:** `CoreEngine`  
**Publication order:** `150`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Z_PK` | `BIGINT PRIMARY KEY` | Identifiers |
| `ZTXDATESTR` | `DATE` | Identifiers |
| `ZASSETUID` | `TEXT` | Identifiers |
| `ZCATEGORYUID` | `TEXT` | Identifiers |
| `ZCURRENCYUID` | `TEXT` | Identifiers |
| `ZTOASSETUID` | `TEXT` | Identifiers |
| `ZTXUIDFEE` | `TEXT` | Identifiers |
| `ZTXUIDTRANS` | `TEXT` | Identifiers |
| `ZUID` | `TEXT` | Identifiers |
| `ZCONTENT` | `TEXT` | Descriptors/Classifications |
| `ZDO_TYPE` | `BIGINT` | Descriptors/Classifications |
| `ZAMOUNT` | `DOUBLE` | Position Values |
| `ZAMOUNTACCOUNT` | `DOUBLE` | Position Values |
| `ZAMOUNTSUB` | `DOUBLE` | Position Values |
| `ZDATE` | `DOUBLE` | Position Values |
| `ZUTIME` | `BIGINT` | Position Values |
| `__file_name__` | `TEXT` | Position Values |
| `__folder_path__` | `TEXT` | Position Values |

**Table constraints**

- `FOREIGN KEY(ZCURRENCYUID) REFERENCES silver.d_Currency(UID)`
- `FOREIGN KEY(ZASSETUID) REFERENCES silver.d_Asset_Subcategory(UID)`
- `FOREIGN KEY(ZTXDATESTR) REFERENCES silver.d_Calendar(Date)`

### `silver.d_Investment_Benchmark_Master`

**Contract ID:** `df_d_benchmark_master`  
**Grain:** `Benchmark`  
**Domain:** `Investments`  
**Producer:** `CoreEngine`  
**Publication order:** `90`

| Column | Physical type / constraint | Role |
|---|---|---|
| `ID` | `TEXT PRIMARY KEY` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `Benchmark_Name` | `TEXT` | Descriptors/Classifications |
| `yF_Ticker` | `TEXT` | Descriptors/Classifications |
| `__file_name__` | `TEXT` | Descriptors/Classifications |
| `__folder_path__` | `TEXT` | Descriptors/Classifications |

### `silver.d_Investment_Master`

**Contract ID:** `df_d_investment_master`  
**Grain:** `ISIN`  
**Domain:** `Investments`  
**Producer:** `CoreEngine`  
**Publication order:** `100`

| Column | Physical type / constraint | Role |
|---|---|---|
| `ISIN` | `TEXT PRIMARY KEY` | Identifiers |
| `CATEGORY_ID` | `TEXT` | Identifiers |
| `BENCHMARK_ID` | `TEXT` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `INSTRUMENT_NAME` | `TEXT` | Descriptors/Classifications |
| `INSTRUMENT_HOUSE` | `TEXT` | Descriptors/Classifications |
| `INSTRUMENT_CLASS` | `TEXT NOT NULL` | Descriptors/Classifications |
| `INSTRUMENT_TYPE` | `TEXT` | Descriptors/Classifications |
| `INSTRUMENT_SUBTYPE` | `TEXT` | Descriptors/Classifications |
| `SECTOR` | `TEXT` | Descriptors/Classifications |
| `INDUSTRY` | `TEXT` | Descriptors/Classifications |
| `COUNTRY` | `TEXT` | Descriptors/Classifications |
| `GEO` | `TEXT` | Descriptors/Classifications |
| `GEO_SUBTYPE` | `TEXT` | Descriptors/Classifications |
| `YAHOO_TICKER` | `TEXT` | Descriptors/Classifications |
| `TAX_TYPE` | `TEXT NOT NULL` | Tax & Harvesting |
| `TAX_SUBTYPE` | `TEXT` | Tax & Harvesting |

**Table constraints**

- `FOREIGN KEY(CATEGORY_ID) REFERENCES silver.d_Asset_Subcategory(UID)`
- `FOREIGN KEY(BENCHMARK_ID) REFERENCES silver.d_Investment_Benchmark_Master(ID)`
- `FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)`

### `silver.d_Macro_Parameters`

**Contract ID:** `df_d_macro_parameters`  
**Grain:** `FinancialYear`  
**Domain:** `Investments`  
**Producer:** `CoreEngine`  
**Publication order:** `110`

| Column | Physical type / constraint | Role |
|---|---|---|
| `FY` | `TEXT PRIMARY KEY` | Identifiers |
| `FY_Start_Date` | `DATE` | Identifiers |
| `FY_End_Date` | `DATE` | Identifiers |
| `Debt_MF_Cutoff_Date` | `DATE` | Identifiers |
| `Inflation_Rate` | `DOUBLE` | Risk & Weights |
| `Risk_Free_Rate` | `DOUBLE` | Risk & Weights |
| `Equity_Listed_LTCG` | `DOUBLE` | Tax & Harvesting |
| `Equity_Listed_STCG` | `DOUBLE` | Tax & Harvesting |
| `Equity_Unlisted_LTCG` | `DOUBLE` | Tax & Harvesting |
| `Equity_Unlisted_STCG` | `DOUBLE` | Tax & Harvesting |
| `Equity_LTCG_Exemption` | `BIGINT` | Tax & Harvesting |
| `Gold_LTCG` | `DOUBLE` | Tax & Harvesting |
| `Gold_STCG` | `DOUBLE` | Tax & Harvesting |
| `Debt_MF_Pre_Cutoff_LTCG` | `DOUBLE` | Tax & Harvesting |
| `Debt_MF_Pre_Cutoff_STCG` | `DOUBLE` | Tax & Harvesting |
| `Debt_MF_Post_Cutoff_LTCG` | `DOUBLE` | Tax & Harvesting |
| `Debt_MF_Post_Cutoff_STCG` | `DOUBLE` | Tax & Harvesting |
| `Other_Debt_LTCG` | `DOUBLE` | Tax & Harvesting |
| `Other_Debt_STCG` | `DOUBLE` | Tax & Harvesting |
| `Default_LTCG` | `DOUBLE` | Tax & Harvesting |
| `Default_STCG` | `DOUBLE` | Tax & Harvesting |
| `Estimated_Ordinary_Income_Tax_Rate` | `DOUBLE` | Tax & Harvesting |
| `Remarks` | `TEXT` | Descriptors/Classifications |
| `__file_name__` | `TEXT` | Descriptors/Classifications |
| `__folder_path__` | `TEXT` | Descriptors/Classifications |

**Table constraints**

- `FOREIGN KEY(FY_Start_Date) REFERENCES silver.d_Calendar(Date)`

### `silver.f_Investment_Market_Data`

**Contract ID:** `df_f_investment_market_data`  
**Grain:** `Quote`  
**Domain:** `Investments`  
**Producer:** `CoreEngine`  
**Publication order:** `160`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Date` | `DATE NOT NULL` | Identifiers |
| `ISIN` | `TEXT NOT NULL` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `__file_category__` | `TEXT` | Descriptors/Classifications |
| `Quantity` | `DOUBLE` | Position Values |
| `Closing_Price` | `DOUBLE` | Position Values |
| `Buy_Price` | `DOUBLE` | Position Values |
| `Closing_Value` | `DOUBLE` | Position Values |
| `Buy_Value` | `DOUBLE` | Position Values |
| `Closing_Price_Local` | `DOUBLE` | Local/FX Values |
| `Buy_Price_Local` | `DOUBLE` | Local/FX Values |
| `Closing_Value_Local` | `DOUBLE` | Local/FX Values |
| `Buy_Value_Local` | `DOUBLE` | Local/FX Values |
| `FX_Rate` | `DOUBLE` | Local/FX Values |
| `Unit_PnL` | `DOUBLE` | Absolute Returns |
| `Total_PnL` | `DOUBLE` | Absolute Returns |
| `Data_Provider` | `TEXT` | Provenance |
| `Extraction_Time` | `TEXT` | Provenance |
| `Requested_Start` | `DATE` | Provenance |
| `Requested_End` | `DATE` | Provenance |
| `Is_Closure_Gap` | `BOOLEAN` | Provenance |
| `Is_Imputed` | `BOOLEAN` | Provenance |

**Table constraints**

- `FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date)`
- `FOREIGN KEY(ISIN) REFERENCES silver.d_Investment_Master(ISIN)`
- `FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)`

### `silver.f_Investment_Purchase_Data`

**Contract ID:** `df_f_tf_inv_purchase`  
**Grain:** `Trade`  
**Domain:** `Investments`  
**Producer:** `CoreEngine`  
**Publication order:** `170`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Purchase_ID` | `TEXT PRIMARY KEY` | Identifiers |
| `Date` | `DATE NOT NULL` | Identifiers |
| `ISIN` | `TEXT NOT NULL` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `__file_category__` | `TEXT` | Descriptors/Classifications |
| `Quantity` | `DOUBLE` | Position Values |
| `Price` | `DOUBLE` | Position Values |
| `Value` | `DOUBLE` | Position Values |
| `Price_Local` | `DOUBLE` | Local/FX Values |
| `Value_Local` | `DOUBLE` | Local/FX Values |
| `FX_Rate` | `DOUBLE` | Local/FX Values |
| `__file_name__` | `TEXT` | Local/FX Values |
| `__folder_path__` | `TEXT` | Local/FX Values |

**Table constraints**

- `FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date)`
- `FOREIGN KEY(ISIN) REFERENCES silver.d_Investment_Master(ISIN)`
- `FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)`

### `silver.f_Investment_Sale_Data`

**Contract ID:** `df_f_tf_inv_sale`  
**Grain:** `Trade`  
**Domain:** `Investments`  
**Producer:** `CoreEngine`  
**Publication order:** `180`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Sale_ID` | `TEXT PRIMARY KEY` | Identifiers |
| `Date` | `DATE NOT NULL` | Identifiers |
| `ISIN` | `TEXT NOT NULL` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `__file_category__` | `TEXT` | Descriptors/Classifications |
| `Quantity` | `DOUBLE` | Position Values |
| `Sell_Price` | `DOUBLE` | Position Values |
| `Sell_Value` | `DOUBLE` | Position Values |
| `Buy_Price` | `DOUBLE` | Position Values |
| `Buy_Value` | `DOUBLE` | Position Values |
| `Sell_Price_Local` | `DOUBLE` | Local/FX Values |
| `Sell_Value_Local` | `DOUBLE` | Local/FX Values |
| `Buy_Price_Local` | `DOUBLE` | Local/FX Values |
| `Buy_Value_Local` | `DOUBLE` | Local/FX Values |
| `FX_Rate` | `DOUBLE` | Local/FX Values |
| `Unit_PnL` | `DOUBLE` | Absolute Returns |
| `Total_PnL` | `DOUBLE` | Absolute Returns |
| `__file_name__` | `TEXT` | Absolute Returns |
| `__folder_path__` | `TEXT` | Absolute Returns |

**Table constraints**

- `FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date)`
- `FOREIGN KEY(ISIN) REFERENCES silver.d_Investment_Master(ISIN)`
- `FOREIGN KEY(CURRENCY_ID) REFERENCES silver.d_Currency(UID)`

### `silver.f_Investment_Benchmark_Data`

**Contract ID:** `df_f_investment_benchmark_data`  
**Grain:** `Quote`  
**Domain:** `Investments`  
**Producer:** `CoreEngine`  
**Publication order:** `190`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Date` | `DATE` | Identifiers |
| `ID` | `TEXT` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `Benchmark_Name` | `TEXT` | Descriptors/Classifications |
| `yF_Ticker` | `TEXT` | Descriptors/Classifications |
| `Close` | `DOUBLE` | Position Values |
| `Data_Provider` | `TEXT` | Provenance |
| `Extraction_Time` | `TEXT` | Provenance |
| `Requested_Start` | `DATE` | Provenance |
| `Requested_End` | `DATE` | Provenance |
| `Is_Closure_Gap` | `BOOLEAN` | Provenance |
| `Is_Imputed` | `BOOLEAN` | Provenance |

**Table constraints**

- `FOREIGN KEY(Date) REFERENCES silver.d_Calendar(Date)`
- `FOREIGN KEY(ID) REFERENCES silver.d_Investment_Benchmark_Master(ID)`

### `silver.f_Investment_Analytics_Lot`

**Contract ID:** `df_f_investment_analytics_lot`  
**Grain:** `ISIN-Lot`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `200`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Lot_ID` | `TEXT NOT NULL` | Identifiers |
| `Closing_Date` | `DATE NOT NULL` | Identifiers |
| `ISIN` | `TEXT NOT NULL` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `Buy_Date` | `DATE` | Identifiers |
| `Purchase_ID` | `TEXT` | Identifiers |
| `Lot_Source_Type` | `TEXT NOT NULL` | Descriptors/Classifications |
| `BENCHMARK_ID` | `TEXT` | Descriptors/Classifications |
| `TAX_TYPE` | `TEXT` | Descriptors/Classifications |
| `TAX_SUBTYPE` | `TEXT` | Descriptors/Classifications |
| `Quantity` | `DOUBLE` | Position Values |
| `Execution_Residual` | `DOUBLE,  -- Units ordered but not yet settled at this snapshot date` | Position Values |
| `Buy_Price` | `DOUBLE` | Position Values |
| `Market_Price` | `DOUBLE` | Position Values |
| `Buy_Value` | `DOUBLE` | Position Values |
| `Close_Value` | `DOUBLE` | Position Values |
| `Buy_Value_Local` | `DOUBLE` | Local/FX Values |
| `Close_Value_Local` | `DOUBLE` | Local/FX Values |
| `Blended_FX_Buy_Rate` | `DOUBLE` | Local/FX Values |
| `Buy_Price_Local` | `DOUBLE,          -- Acquisition price in instrument native currency` | Local/FX Values |
| `Market_Price_Local` | `DOUBLE,       -- Market price in instrument native currency at snapshot` | Local/FX Values |
| `FX_Rate_Buy` | `DOUBLE,              -- FX rate (native → INR) at acquisition date` | Local/FX Values |
| `FX_Rate_Snap` | `DOUBLE,             -- FX rate (native → INR) at snapshot date` | Local/FX Values |
| `Currency_Appreciation_Pct` | `DOUBLE` | Local/FX Values |
| `"P/L"` | `DOUBLE` | Absolute Returns |
| `Absolute_Return` | `DOUBLE` | Absolute Returns |
| `Absolute_Return_Local` | `DOUBLE` | Absolute Returns |
| `Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_Contribution_Pct` | `DOUBLE` | Absolute Returns |
| `Asset_Return_Pct` | `DOUBLE` | Absolute Returns |
| `Forex_Return_Pct` | `DOUBLE` | Absolute Returns |
| `Lot_CAGR` | `DOUBLE` | Performance Returns |
| `Lot_CAGR_Status` | `TEXT,       -- VALID \| INVALID_INPUT \| UNDEFINED \| COMPUTATION_ERROR` | Performance Returns |
| `Lot_CAGR_Local` | `DOUBLE` | Performance Returns |
| `CAGR` | `DOUBLE` | Performance Returns |
| `CAGR_Status` | `TEXT,           -- VALID \| INVALID_INPUT \| UNDEFINED \| COMPUTATION_ERROR` | Performance Returns |
| `XIRR` | `DOUBLE` | Performance Returns |
| `XIRR_Status` | `TEXT,           -- VALID \| INVALID_INPUT \| UNDEFINED \| NON_CONVERGENT` | Performance Returns |
| `XIRR_Local` | `DOUBLE` | Performance Returns |
| `FX_XIRR_Impact` | `DOUBLE` | Performance Returns |
| `After_Tax_XIRR` | `DOUBLE` | Performance Returns |
| `BM_Buy_Price` | `DOUBLE` | Benchmark Comparisons |
| `BM_Market_Price` | `DOUBLE` | Benchmark Comparisons |
| `Lot_BM_Return` | `DOUBLE` | Benchmark Comparisons |
| `Lot_BM_CAGR` | `DOUBLE` | Benchmark Comparisons |
| `Lot_BM_CAGR_Status` | `TEXT,    -- VALID \| INVALID_INPUT \| UNDEFINED \| COMPUTATION_ERROR` | Benchmark Comparisons |
| `Lot_BM_CAGR_Local` | `DOUBLE` | Benchmark Comparisons |
| `BM_CAGR` | `DOUBLE` | Benchmark Comparisons |
| `BM_CAGR_Status` | `TEXT,        -- VALID \| INVALID_INPUT \| UNDEFINED \| COMPUTATION_ERROR` | Benchmark Comparisons |
| `BM_XIRR` | `DOUBLE` | Benchmark Comparisons |
| `BM_XIRR_Local` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return_Local` | `DOUBLE` | Benchmark Comparisons |
| `Lot_Alpha` | `DOUBLE` | Benchmark Comparisons |
| `Is_Lagging_Benchmark` | `BIGINT` | Benchmark Comparisons |
| `Max_Drawdown` | `DOUBLE` | Risk & Weights |
| `Lot_Weight` | `DOUBLE` | Risk & Weights |
| `Portfolio_Weight` | `DOUBLE` | Risk & Weights |
| `Outperforming_Lot_Ratio` | `DOUBLE` | Risk & Weights |
| `Dietz_Day_Weight` | `DOUBLE` | Risk & Weights |
| `Age_Days` | `BIGINT` | Tax & Harvesting |
| `LTCG_Threshold_Days` | `BIGINT` | Tax & Harvesting |
| `Days_To_LTCG` | `BIGINT` | Tax & Harvesting |
| `Holding_Type` | `TEXT` | Tax & Harvesting |
| `Tax_Rate` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_LTCG` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_STCG` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Gain` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_LTCL` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_STCL` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Loss` | `DOUBLE` | Tax & Harvesting |
| `LTCG_Tax_If_Sold` | `DOUBLE` | Tax & Harvesting |
| `STCG_Tax_If_Sold` | `DOUBLE` | Tax & Harvesting |
| `After_Tax_PL` | `DOUBLE` | Tax & Harvesting |
| `After_Tax_Close_Value` | `DOUBLE` | Tax & Harvesting |
| `FY` | `TEXT` | Tax & Harvesting |
| `FY_Realized_LTCG` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_STCG` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Gain` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_LTCL` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_STCL` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Net_PnL` | `DOUBLE` | Tax & Harvesting |
| `Equity_LTCG_Exemption` | `BIGINT` | Tax & Harvesting |
| `Stepup_Eligible` | `BIGINT` | Tax & Harvesting |
| `Can_Harvest_Loss` | `BOOLEAN` | Tax & Harvesting |
| `Harvest_Recommendation` | `TEXT` | Tax & Harvesting |

**Table constraints**

- `PRIMARY KEY (Lot_ID, Closing_Date)`

### `silver.f_Investment_Realized_Events`

**Contract ID:** `df_f_investment_realized_events`  
**Grain:** `RealizedEvent`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `205`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Realized_Event_ID` | `TEXT PRIMARY KEY` | Field |
| `Sale_ID` | `TEXT NOT NULL` | Field |
| `Lot_ID` | `TEXT NOT NULL` | Field |
| `Purchase_ID` | `TEXT` | Field |
| `ISIN` | `TEXT` | Field |
| `Acquisition_Date` | `DATE` | Field |
| `Disposal_Date` | `DATE` | Field |
| `FY` | `TEXT` | Field |
| `Quantity_Disposed` | `DOUBLE` | Field |
| `Acquisition_Price` | `DOUBLE` | Field |
| `Disposed_Cost_Basis` | `DOUBLE` | Field |
| `Sale_Price` | `DOUBLE` | Field |
| `Sale_Proceeds` | `DOUBLE` | Field |
| `Realized_Gain_Loss` | `DOUBLE` | Field |
| `Holding_Type` | `TEXT` | Field |
| `Tax_Type` | `TEXT` | Field |
| `Tax_Subtype` | `TEXT` | Field |
| `Lot_Source_Type` | `TEXT` | Field |
| `Currency_ID` | `TEXT` | Field |
| `Asset_PnL_Local` | `DOUBLE` | Field |
| `Asset_PnL` | `DOUBLE` | Field |
| `Forex_PnL` | `DOUBLE` | Field |
| `Applied_Rate` | `DOUBLE` | NULL for CHECK_REQUIRED (RECONCILIATION) lots — no reliable rate can be assigned. |
| `Estimated_Tax` | `DOUBLE` | NULL for CHECK_REQUIRED (RECONCILIATION) lots — no reliable rate can be assigned. |

**Table constraints**

- `UNIQUE(Sale_ID, Lot_ID)`

### `silver.f_Investment_Reconciliation_Events`

**Contract ID:** `df_f_investment_reconciliation_events`  
**Grain:** `ReconEvent`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `206`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Reconciliation_Group_ID` | `TEXT NOT NULL` | Field |
| `Reconciliation_Event_ID` | `TEXT PRIMARY KEY` | Field |
| `Run_ID` | `TEXT` | Field |
| `ISIN` | `TEXT NOT NULL` | Field |
| `Reconciliation_Date` | `DATE NOT NULL` | Field |
| `Lot_ID` | `TEXT` | Field |
| `Purchase_ID` | `TEXT` | Field |
| `Adjustment_Type` | `TEXT` | Field |
| `Reason` | `TEXT` | Field |
| `Broker_Quantity` | `DOUBLE` | Field |
| `Reconstructed_Quantity` | `DOUBLE` | Field |
| `Quantity_Adjustment` | `DOUBLE` | Field |
| `Broker_Cost_Basis` | `DOUBLE` | Field |
| `Reconstructed_Cost_Basis` | `DOUBLE` | Field |
| `Cost_Basis_Adjustment` | `DOUBLE` | Field |
| `Original_Unit_Cost` | `DOUBLE` | Field |
| `Adjusted_Unit_Cost` | `DOUBLE` | Field |

### `silver.f_Tax_Events`

**Contract ID:** `df_f_tax_events`  
**Grain:** `TaxEvent`  
**Domain:** `Taxes`  
**Producer:** `TaxEngine`  
**Publication order:** `300`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Tax_Event_ID` | `TEXT PRIMARY KEY` | Field |
| `FY` | `TEXT NOT NULL` | Field |
| `Event_Date` | `DATE NOT NULL` | Field |
| `Source_Type` | `TEXT NOT NULL` | Field |
| `Source_ID` | `TEXT NOT NULL` | Field |
| `Income_Head` | `TEXT NOT NULL` | Field |
| `Tax_Sub_Head` | `TEXT NOT NULL` | Field |
| `Amount_INR` | `DOUBLE NOT NULL` | Field |
| `Applied_Rate` | `DOUBLE` | Field |
| `Estimated_Tax` | `DOUBLE` | Field |
| `CURRENCY_ID` | `TEXT` | Field |
| `Tax_Status` | `TEXT NOT NULL` | Field |
| `Tax_Status_Reason` | `TEXT` | Field |
| `ISIN` | `TEXT` | Field |
| `Lot_ID` | `TEXT` | Field |

**Table constraints**

- `UNIQUE(Source_Type, Source_ID, Tax_Sub_Head)`


## Publication invariants

The Silver catalog depends on several invariants:

1. registry contract IDs are unique;
2. physical table names are unique within Silver/Gold registry scope;
3. each contract has a declared grain and producer;
4. physical schemas match the producer output;
5. identity-bearing facts preserve deterministic identity semantics;
6. publication order respects dependency.

`validate_registry()` checks structural registry integrity. Runtime schema/publication validation protects the physical side.

## Ownership boundary

Silver is canonical analytical state. It may contain reconstructed state such as lots and reconciliation events, but the financial logic that produces that state remains owned by the relevant domain/application service, not by the table definition.

## Related specifications

- [Financial Model](../finance/financial-model.md)
- [Investment Data Model](../finance/investment-data-model.md)
- [Identity & Grain Contracts](identity-and-grain-contracts.md)
- [Gold Data Contracts](gold-data-contracts.md)
