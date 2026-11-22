# Silver Warehouse Column Disposition and Consumer Archaeology Manifest

> **Authority:** PFETL v11 Shan-First Architecture — Phase 005 Governance Artifact  
> **Scope:** Authoritative classification and consumer mapping across all 24 Silver tables (534 columns)  
> **Release Target:** v11.2.0  
> **Operational Constraint:** Strictly Non-Destructive — schema alterations execute in Phase 006 (Household/Ref) and Phase 007 (Investments/Tax)  

---

## 1. Executive Summary & Disposition Statistics

The Silver analytical layer serves as the normalized canonical truth for Shan's personal finances.
In accordance with v11 program principles, column drops and renames are strictly consumer-proven.
This manifest freezes the disposition of every single physical column definition in DuckDB Silver schema.

| Metric | Count | Governance Policy |
| :--- | :---: | :--- |
| **Total Silver Tables** | **24** | Proven 24-table topology preserved 1:1 (No merge / split) |
| **Total Silver Columns** | **534** | 100% cataloged and assigned explicit migration targets |
| 🛡️ `PROTECTED` Columns | **126** | Business keys, financial identities & formula inputs; strict equality required |
| 🏷️ `RENAME` Columns | **299** | Canonical naming alignment (`pnl`, `fx`, `financial_year`, lowercase snake_case) |
| 📦 `KEEP` Columns | **13** | Active dimensions and metrics already conforming to canonical vocabulary |
| 🗑️ `REMOVE_CANDIDATE` Columns | **96** | Proven dead source/UI residues with zero downstream consumers in analytical marts |

---

## 2. Frozen 24-Table Topology & Renaming Matrix

All 24 Silver tables transition to dimensional warehouse nomenclature (`silver.dim_*`, `silver.fact_*`, `silver.ref_*`):

| # | Current Physical Table | Target Physical Table | Domain | Split Sprint | Grains & Identity | Columns |
| :---: | :--- | :--- | :--- | :---: | :--- | :---: |
| 1 | `silver.d_Calendar` | `silver.dim_calendar` | Common | Phase 006 | Daily Calendar Date (Date) | 64 |
| 2 | `silver.d_Income_Category` | `silver.dim_income_category` | Household | Phase 006 | Income Category (UID) | 8 |
| 3 | `silver.d_Income_Subcategory` | `silver.dim_income_subcategory` | Household | Phase 006 | Income Subcategory (UID) | 20 |
| 4 | `silver.d_Expense_Category` | `silver.dim_expense_category` | Household | Phase 006 | Expense Category (UID) | 7 |
| 5 | `silver.d_Expense_Subcategory` | `silver.dim_expense_subcategory` | Household | Phase 006 | Expense Subcategory (UID) | 9 |
| 6 | `silver.d_Asset_Category` | `silver.dim_asset_category` | Household | Phase 006 | Asset Group / Category (UID) | 14 |
| 7 | `silver.d_Asset_Subcategory` | `silver.dim_asset_subcategory` | Household | Phase 006 | Asset Subcategory / Account (UID) | 24 |
| 8 | `silver.d_Currency` | `silver.dim_currency` | Common | Phase 006 | Currency Code (UID) | 19 |
| 9 | `silver.f_Currency_FX_Rates` | `silver.fact_currency_fx_rates` | Common | Phase 006 | Currency Exchange Observation (Currency_ID, Date) | 13 |
| 10 | `silver.f_Income_Transactions` | `silver.fact_income_transactions` | Household | Phase 006 | Income Transaction (UID) | 28 |
| 11 | `silver.f_Expense_Transactions` | `silver.fact_expense_transactions` | Household | Phase 006 | Expense Transaction (UID) | 25 |
| 12 | `silver.f_Transfer_Transactions` | `silver.fact_transfer_transactions` | Household | Phase 006 | Transfer Transaction (UID) | 27 |
| 13 | `silver.f_Opening_Balances` | `silver.fact_opening_balances` | Household | Phase 006 | Opening Balance Snapshot (ZASSETUID) | 18 |
| 14 | `silver.d_Investment_Benchmark_Master` | `silver.dim_benchmark_master` | Investments | Phase 006 | Benchmark Security (ID) | 6 |
| 15 | `silver.d_Investment_Master` | `silver.dim_instrument_master` | Investments | Phase 007 | Instrument / Security (ISIN) | 17 |
| 16 | `silver.d_Macro_Parameters` | `silver.ref_financial_year_parameters` | Common | Phase 006 | Financial Year Parameters (FY) | 25 |
| 17 | `silver.f_Investment_Market_Data` | `silver.fact_investment_market_data` | Investments | Phase 007 | Daily Market Price (Date, ISIN) | 22 |
| 18 | `silver.f_Investment_Purchase_Data` | `silver.fact_investment_purchases` | Investments | Phase 007 | Purchase Execution (Purchase_ID) | 13 |
| 19 | `silver.f_Investment_Sale_Data` | `silver.fact_investment_sales` | Investments | Phase 007 | Sale Execution (Sale_ID) | 19 |
| 20 | `silver.f_Investment_Benchmark_Data` | `silver.fact_investment_benchmark_data` | Investments | Phase 007 | Daily Benchmark Close (Date, ID) | 12 |
| 21 | `silver.f_Investment_Analytics_Lot` | `silver.fact_investment_lot_analytics` | Investments | Phase 007 | Tax Lot Snapshot (Lot_ID, Closing_Date) | 88 |
| 22 | `silver.f_Investment_Realized_Events` | `silver.fact_investment_realized_events` | Investments | Phase 007 | Lot Realized Gain/Loss Disposal (Realized_Event_ID) | 24 |
| 23 | `silver.f_Investment_Reconciliation_Events` | `silver.fact_investment_reconciliation_events` | Investments | Phase 007 | Reconciliation Adjustment (Reconciliation_Event_ID) | 17 |
| 24 | `silver.f_Tax_Events` | `silver.fact_tax_events` | Tax | Phase 007 | Taxable Event (Tax_Event_ID) | 15 |

---

## 3. Canonical Vocabulary Governance Rules

1. **`instrument` vs `investment`:** Security definitions belong in `dim_instrument_master`. Shan's trades, holdings, and lots belong in `fact_investment_*`.
2. **`fx` Standard:** Eliminate `Forex_` and mixed `FX_` prefixes; standardize on `fx_pnl`, `fx_rate`, `fx_return_pct`, `fx_xirr_impact`.
3. **`pnl` Standard:** Eliminate SQL special characters (`/`, `&`). Replace `P/L` with `pnl`, `Asset_PnL` with `asset_pnl`, `Unit_PnL` with `unit_pnl`.
4. **`financial_year` Standard:** Replace uppercase `FY` with `financial_year` across all temporal and macro schemas.
5. **Base vs Local Clarity:** Explicitly qualify local currency measurements (`*_local`) vs base INR measurements (`*_base` or base-implicit).

---

## 4. Household & Reference Dispositions (15 Tables) (Phase 006 Scope)

### `silver.d_Calendar` -> `silver.dim_calendar`
**Domain:** Common | **Grain:** Daily Calendar Date (Date) | **Columns:** 64
*Master temporal dimension providing rich calendar, fiscal, and operational date attributes.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Date` | DATE | `date` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/control_plane/simulation_fingerprint.py, infrastructure/warehouse/contracts.py, infrastructure/providers/files/csv.py (+49 more)] |
| `Day` | BIGINT | `day` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: day). [Consumers: infrastructure/warehouse/contracts.py, domain/household/transforms/calendar.py] |
| `Day_Name` | TEXT | `day_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: day_name). [Consumers: domain/household/transforms/calendar.py] |
| `Day_Name_Short` | TEXT | `day_name_short` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: day_name_short). [Consumers: domain/household/transforms/calendar.py] |
| `Day_Ordinal` | BIGINT | `day_ordinal` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: day_ordinal). [Consumers: domain/household/transforms/calendar.py] |
| `Day_Ordinal_Name` | TEXT | `day_ordinal_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: day_ordinal_name). [Consumers: domain/household/transforms/calendar.py] |
| `Weekday` | BIGINT | `weekday` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: weekday). [Consumers: domain/household/transforms/calendar.py] |
| `IS_WEEKEND` | BIGINT | `is_weekend` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: is_weekend). [Consumers: domain/household/transforms/calendar.py] |
| `Week` | BIGINT | `week` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: week). [Consumers: domain/household/transforms/calendar.py] |
| `Week_Ordinal` | BIGINT | `week_ordinal` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: week_ordinal). [Consumers: domain/household/transforms/calendar.py] |
| `Week_Ordinal_Name` | TEXT | `week_ordinal_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: week_ordinal_name). [Consumers: domain/household/transforms/calendar.py] |
| `Week_Name` | TEXT | `week_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: week_name). [Consumers: domain/household/transforms/calendar.py] |
| `Week_Year` | TEXT | `week_year` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: week_year). [Consumers: domain/household/transforms/calendar.py] |
| `Week_Name_Year` | TEXT | `week_name_year` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: week_name_year). [Consumers: domain/household/transforms/calendar.py] |
| `Start_of_Week` | DATE | `start_of_week` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: start_of_week). [Consumers: domain/household/transforms/calendar.py] |
| `End_of_Week` | DATE | `end_of_week` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: end_of_week). [Consumers: domain/household/transforms/calendar.py] |
| `Month` | BIGINT | `month` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: month). [Consumers: infrastructure/warehouse/contracts.py, infrastructure/providers/files/excel.py, domain/fire/inflation.py (+4 more)] |
| `Month_Name` | TEXT | `month_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: month_name). [Consumers: domain/household/transforms/calendar.py] |
| `Month_Name_Short` | TEXT | `month_name_short` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: month_name_short). [Consumers: domain/household/transforms/calendar.py] |
| `Month_Year` | TEXT | `month_year` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: month_year). [Consumers: domain/household/transforms/calendar.py] |
| `Short_Month_Year` | TEXT | `short_month_year` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: short_month_year). [Consumers: domain/household/transforms/calendar.py] |
| `V_Short_Month_Year` | TEXT | `v_short_month_year` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: v_short_month_year). [Consumers: domain/household/transforms/calendar.py] |
| `Month_Ordinal` | BIGINT | `month_ordinal` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: month_ordinal). [Consumers: domain/household/transforms/calendar.py] |
| `Start_of_Month` | DATE | `start_of_month` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: start_of_month). [Consumers: domain/household/transforms/calendar.py] |
| `End_of_Month` | DATE | `end_of_month` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: end_of_month). [Consumers: domain/household/transforms/calendar.py] |
| `Days_in_Month` | BIGINT | `days_in_month` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: days_in_month). [Consumers: domain/household/transforms/calendar.py] |
| `Month_Progress_Pct` | DOUBLE | `month_progress_pct` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: month_progress_pct). [Consumers: domain/household/transforms/calendar.py] |
| `Quarter` | BIGINT | `quarter` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: quarter). [Consumers: domain/household/transforms/calendar.py] |
| `Quarter_Name` | TEXT | `quarter_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: quarter_name). [Consumers: domain/household/transforms/calendar.py] |
| `Quarter_Year` | TEXT | `quarter_year` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: quarter_year). [Consumers: domain/household/transforms/calendar.py] |
| `Quarter_Ordinal` | BIGINT | `quarter_ordinal` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: quarter_ordinal). [Consumers: domain/household/transforms/calendar.py] |
| `Start_of_Quarter` | DATE | `start_of_quarter` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: start_of_quarter). [Consumers: domain/household/transforms/calendar.py] |
| `End_of_Quarter` | DATE | `end_of_quarter` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: end_of_quarter). [Consumers: domain/household/transforms/calendar.py] |
| `Year` | BIGINT | `year` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: year). [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/common.py, domain/common/dates.py (+5 more)] |
| `Days_in_Year` | BIGINT | `days_in_year` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: days_in_year). [Consumers: domain/household/transforms/calendar.py] |
| `Year_Progress_Pct` | DOUBLE | `year_progress_pct` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: year_progress_pct). [Consumers: domain/household/transforms/calendar.py] |
| `Financial_Year` | TEXT | `financial_year` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: financial_year). [Consumers: domain/household/transforms/calendar.py] |
| `FY_Year` | BIGINT | `fy_year` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_year). [Consumers: domain/common/dates.py, domain/household/transforms/calendar.py] |
| `FY_Month` | BIGINT | `fy_month` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_month). [Consumers: domain/household/transforms/calendar.py] |
| `FY_Month_Ordinal` | BIGINT | `fy_month_ordinal` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_month_ordinal). [Consumers: domain/household/transforms/calendar.py] |
| `FY_Quarter` | BIGINT | `fy_quarter` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_quarter). [Consumers: domain/household/transforms/calendar.py] |
| `FY_Quarter_Name` | TEXT | `fy_quarter_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_quarter_name). [Consumers: domain/household/transforms/calendar.py] |
| `FY_Quarter_Year` | TEXT | `fy_quarter_year` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_quarter_year). [Consumers: domain/household/transforms/calendar.py] |
| `FY_Quarter_Ordinal` | BIGINT | `fy_quarter_ordinal` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_quarter_ordinal). [Consumers: domain/household/transforms/calendar.py] |
| `FY_Start_of_Month` | DATE | `fy_start_of_month` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_start_of_month). [Consumers: domain/household/transforms/calendar.py] |
| `FY_End_of_Month` | DATE | `fy_end_of_month` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_end_of_month). [Consumers: domain/household/transforms/calendar.py] |
| `FY_Start_of_Quarter` | DATE | `fy_start_of_quarter` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_start_of_quarter). [Consumers: domain/household/transforms/calendar.py] |
| `FY_End_of_Quarter` | DATE | `fy_end_of_quarter` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_end_of_quarter). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Last_Day_Of_Month` | BOOLEAN | `is_last_day_of_month` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_last_day_of_month). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Last_Day_Of_Quarter` | BOOLEAN | `is_last_day_of_quarter` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_last_day_of_quarter). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Last_Day_Of_Year` | BOOLEAN | `is_last_day_of_year` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_last_day_of_year). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Last_Day_Of_FY` | BOOLEAN | `is_last_day_of_fy` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_last_day_of_fy). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Quarter_End_Month` | BOOLEAN | `is_quarter_end_month` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_quarter_end_month). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Tax_Harvesting_Season` | BOOLEAN | `is_tax_harvesting_season` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_tax_harvesting_season). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Current_Month` | BOOLEAN | `is_current_month` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_current_month). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Previous_Month` | BOOLEAN | `is_previous_month` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_previous_month). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Current_Quarter` | BOOLEAN | `is_current_quarter` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_current_quarter). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Previous_Quarter` | BOOLEAN | `is_previous_quarter` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_previous_quarter). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Current_Year` | BOOLEAN | `is_current_year` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_current_year). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Previous_Year` | BOOLEAN | `is_previous_year` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_previous_year). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Current_FY` | BOOLEAN | `is_current_fy` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_current_fy). [Consumers: domain/household/transforms/calendar.py] |
| `Is_YTD` | BOOLEAN | `is_ytd` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_ytd). [Consumers: domain/household/transforms/calendar.py] |
| `Is_FY_YTD` | BOOLEAN | `is_fy_ytd` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_fy_ytd). [Consumers: domain/household/transforms/calendar.py] |
| `Is_Future_Date` | BOOLEAN | `is_future_date` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_future_date). [Consumers: domain/household/transforms/calendar.py] |

### `silver.d_Income_Category` -> `silver.dim_income_category`
**Domain:** Household | **Grain:** Income Category (UID) | **Columns:** 8
*Top-level income classifications (e.g., Salary, Investment Income, Business).*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `UID` | TEXT | `uid` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/household/expense.py (+18 more)] |
| `CATEGORY_NAME` | TEXT | `category_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: category_name). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/income.py (+3 more)] |
| `CATEGORY_NAME_SHORT` | TEXT | `category_name_short` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: category_name_short). [Consumers: domain/household/transforms/income_dimensions.py] |
| `ORDER_SEQUENCE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+1 more)] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |
| `S_NO` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+2 more)] |
| `MODIFY_DATE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py, domain/household/transforms/reference_dimensions.py] |

### `silver.d_Income_Subcategory` -> `silver.dim_income_subcategory`
**Domain:** Household | **Grain:** Income Subcategory (UID) | **Columns:** 20
*Detailed income streams with tax head, method, and cashflow classifications.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `UID` | TEXT | `uid` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/household/expense.py (+18 more)] |
| `CATEGORY_ID` | TEXT | `category_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/income.py (+11 more)] |
| `CATEGORY_NAME` | TEXT | `category_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: category_name). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/income.py (+3 more)] |
| `CATEGORY_GROUPS` | TEXT | `category_groups` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: category_groups). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/income.py (+2 more)] |
| `ORDER_SEQUENCE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+1 more)] |
| `Is_Active_Income` | BOOLEAN | `is_active_income` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_active_income). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/income.py, domain/household/ledger.py (+3 more)] |
| `Is_Passive_Income` | BOOLEAN | `is_passive_income` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_passive_income). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/income.py, domain/household/transforms/income_dimensions.py] |
| `Is_Dividend_Income` | BOOLEAN | `is_dividend_income` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_dividend_income). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/income.py, domain/household/ledger.py (+3 more)] |
| `Is_Interest_Income` | BOOLEAN | `is_interest_income` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_interest_income). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/income.py, domain/household/ledger.py (+3 more)] |
| `Is_Non_Cash_Income` | BOOLEAN | `is_non_cash_income` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_non_cash_income). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/income.py, domain/household/ledger.py (+2 more)] |
| `Is_Investment_Exclusion` | BOOLEAN | `is_investment_exclusion` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_investment_exclusion). [Consumers: domain/tax/events/builder.py, domain/household/transforms/income_dimensions.py] |
| `Is_Tax_Credits` | BOOLEAN | `is_tax_credits` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_tax_credits). [Consumers: domain/tax/events/builder.py, domain/household/transforms/income_dimensions.py] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |
| `S_NO` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+2 more)] |
| `MODIFY_DATE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py, domain/household/transforms/reference_dimensions.py] |
| `Tax_Income_Head` | TEXT | `tax_income_head` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: tax_income_head). [Consumers: domain/tax/events/builder.py, domain/household/transforms/income_dimensions.py] |
| `Tax_Sub_Head` | TEXT | `tax_sub_head` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: tax_sub_head). [Consumers: infrastructure/warehouse/schema/gold.py, domain/common/identity.py, domain/tax/events/builder.py (+6 more)] |
| `Taxability` | TEXT | `taxability` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: taxability). [Consumers: domain/tax/events/builder.py, domain/tax/reconciliation/reconciler.py, domain/household/transforms/income_dimensions.py] |
| `Tax_Method` | TEXT | `tax_method` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: tax_method). [Consumers: domain/tax/events/builder.py, domain/household/transforms/income_dimensions.py] |

### `silver.d_Expense_Category` -> `silver.dim_expense_category`
**Domain:** Household | **Grain:** Expense Category (UID) | **Columns:** 7
*Top-level household expense classifications.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `UID` | TEXT | `uid` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/household/expense.py (+18 more)] |
| `CATEGORY_NAME` | TEXT | `category_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: category_name). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/income.py (+3 more)] |
| `ORDER_SEQUENCE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+1 more)] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |
| `S_NO` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+2 more)] |
| `MODIFY_DATE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py, domain/household/transforms/reference_dimensions.py] |

### `silver.d_Expense_Subcategory` -> `silver.dim_expense_subcategory`
**Domain:** Household | **Grain:** Expense Subcategory (UID) | **Columns:** 9
*Granular expense categories with core vs non-core lifestyle tagging.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `UID` | TEXT | `uid` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/household/expense.py (+18 more)] |
| `CATEGORY_ID` | TEXT | `category_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/income.py (+11 more)] |
| `CATEGORY_NAME` | TEXT | `category_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: category_name). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/income.py (+3 more)] |
| `ORDER_SEQUENCE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+1 more)] |
| `Is_Core_Expense` | BOOLEAN | `is_core_expense` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_core_expense). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/ledger.py (+2 more)] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |
| `S_NO` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+2 more)] |
| `MODIFY_DATE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py, domain/household/transforms/reference_dimensions.py] |

### `silver.d_Asset_Category` -> `silver.dim_asset_category`
**Domain:** Household | **Grain:** Asset Group / Category (UID) | **Columns:** 14
*Asset groupings (Bank Accounts, Real Estate, Vehicles, Cash Pools).*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `UID` | TEXT | `uid` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/household/expense.py (+18 more)] |
| `ASSET_GROUP` | TEXT | `asset_group` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: asset_group). [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/transactions.py] |
| `TYPE` | BIGINT | `type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: type). [Consumers: domain/household/ledger.py, domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py (+2 more)] |
| `ORDER_SEQUENCE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+1 more)] |
| `ledger_role` | TEXT | `ledger_role` | 📦 KEEP | `source_taxonomy` | Active analytical dimension or metric (canonical target: ledger_role). [Consumers: domain/household/transforms/asset_dimensions.py] |
| `cashflow_activity_type` | TEXT | `cashflow_activity_type` | 📦 KEEP | `source_taxonomy` | Active analytical dimension or metric (canonical target: cashflow_activity_type). [Consumers: domain/household/cashflow/statement.py, domain/household/transforms/asset_dimensions.py] |
| `settlement_timing` | TEXT | `settlement_timing` | 📦 KEEP | `source_taxonomy` | Active analytical dimension or metric (canonical target: settlement_timing). [Consumers: domain/household/transforms/asset_dimensions.py] |
| `Is_Digital_Asset` | BOOLEAN | `is_digital_asset` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_digital_asset). [Consumers: domain/household/transforms/asset_dimensions.py] |
| `is_cash_pool` | BOOLEAN | `is_cash_pool` | 📦 KEEP | `source_taxonomy` | Active analytical dimension or metric (canonical target: is_cash_pool). [Consumers: domain/household/cashflow/statement.py, domain/household/transforms/asset_dimensions.py] |
| `is_non_cash_pnl` | BOOLEAN | `is_non_cash_pnl` | 📦 KEEP | `source_taxonomy` | Active analytical dimension or metric (canonical target: is_non_cash_pnl). [Consumers: domain/household/expense.py, domain/household/ledger.py, domain/household/cashflow/statement.py (+1 more)] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |
| `DEVICE_ID` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py] |
| `USE_TIME` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py] |

### `silver.d_Asset_Subcategory` -> `silver.dim_asset_subcategory`
**Domain:** Household | **Grain:** Asset Subcategory / Account (UID) | **Columns:** 24
*Individual financial accounts, liquidity profiles, and payment instruments.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `UID` | TEXT | `uid` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/household/expense.py (+18 more)] |
| `ASSET_GROUP_ID` | TEXT | `asset_group_id` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: asset_group_id). [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/transactions.py] |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/market/benchmark.py, domain/common/identity.py (+21 more)] |
| `AUTOPAY_ASSET_ID` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py] |
| `ASSET_NAME` | TEXT | `asset_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: asset_name). [Consumers: domain/investments/transforms/indian_equity.py, domain/investments/transforms/mutual_funds.py, domain/investments/transforms/us_equity.py (+1 more)] |
| `ASSET_DESCRIPTION` | TEXT | `asset_description` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: asset_description). [Consumers: domain/household/transforms/asset_dimensions.py] |
| `NOTES` | TEXT | `notes` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: notes). [Consumers: domain/household/transforms/asset_dimensions.py] |
| `ORDER_SEQUENCE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+1 more)] |
| `ledger_role` | TEXT | `ledger_role` | 📦 KEEP | `source_taxonomy` | Active analytical dimension or metric (canonical target: ledger_role). [Consumers: domain/household/transforms/asset_dimensions.py] |
| `cashflow_activity_type` | TEXT | `cashflow_activity_type` | 📦 KEEP | `source_taxonomy` | Active analytical dimension or metric (canonical target: cashflow_activity_type). [Consumers: domain/household/cashflow/statement.py, domain/household/transforms/asset_dimensions.py] |
| `settlement_timing` | TEXT | `settlement_timing` | 📦 KEEP | `source_taxonomy` | Active analytical dimension or metric (canonical target: settlement_timing). [Consumers: domain/household/transforms/asset_dimensions.py] |
| `TRANSFER_EXPENSE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py] |
| `CARD_AUTOPAY` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py] |
| `CARD_STATEMENT_DATE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py] |
| `CARD_PAYMENT_DATE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py] |
| `Is_Liquid` | BOOLEAN | `is_liquid` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_liquid). [Consumers: domain/wealth/net_worth.py, domain/household/transforms/asset_dimensions.py] |
| `Is_Illiquid` | BOOLEAN | `is_illiquid` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_illiquid). [Consumers: domain/household/transforms/asset_dimensions.py] |
| `Is_Digital_Asset` | BOOLEAN | `is_digital_asset` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_digital_asset). [Consumers: domain/household/transforms/asset_dimensions.py] |
| `is_cash_pool` | BOOLEAN | `is_cash_pool` | 📦 KEEP | `source_taxonomy` | Active analytical dimension or metric (canonical target: is_cash_pool). [Consumers: domain/household/cashflow/statement.py, domain/household/transforms/asset_dimensions.py] |
| `is_non_cash_pnl` | BOOLEAN | `is_non_cash_pnl` | 📦 KEEP | `source_taxonomy` | Active analytical dimension or metric (canonical target: is_non_cash_pnl). [Consumers: domain/household/expense.py, domain/household/ledger.py, domain/household/cashflow/statement.py (+1 more)] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |
| `S_NO` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+2 more)] |
| `ADDED_TIME` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py] |

### `silver.d_Currency` -> `silver.dim_currency`
**Domain:** Common | **Grain:** Currency Code (UID) | **Columns:** 19
*Supported ISO currencies, active status, and Yahoo Finance tickers.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `UID` | TEXT | `uid` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/household/expense.py (+18 more)] |
| `CURRENCY_NAME` | TEXT | `currency_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: currency_name). [Consumers: infrastructure/providers/market/currency.py, domain/household/transforms/reference_dimensions.py] |
| `ISO` | TEXT | `iso` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: iso). [Consumers: infrastructure/control_plane/artifact_repository.py, infrastructure/control_plane/run_repository.py, infrastructure/control_plane/simulation_fingerprint.py (+3 more)] |
| `MAIN_ISO` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/reference_dimensions.py] |
| `Target_Currency_Code` | TEXT | `target_currency_code` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: target_currency_code). [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/market/fx.py (+2 more)] |
| `yF_Ticker` | TEXT | `y_f_ticker` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: y_f_ticker). [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/benchmark.py, infrastructure/providers/market/common.py (+7 more)] |
| `SYMBOL` | TEXT | `symbol` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: symbol). [Consumers: domain/investments/contracts/types.py, domain/household/transforms/reference_dimensions.py] |
| `SYMBOL_POSITION` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/reference_dimensions.py] |
| `ORDER_SEQUENCE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+1 more)] |
| `RATE` | DOUBLE | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/reference_dimensions.py] |
| `DECIMAL_POINT` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/reference_dimensions.py] |
| `IS_MAIN_CURRENCY` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/reference_dimensions.py] |
| `IS_SHOW` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/reference_dimensions.py] |
| `Is_Active` | BOOLEAN | `is_active` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_active). [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/market/fx.py (+1 more)] |
| `INSERT_TYPE` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/reference_dimensions.py] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |
| `S_NO` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+2 more)] |
| `MODIFY_DATE` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py, domain/household/transforms/reference_dimensions.py] |

### `silver.f_Currency_FX_Rates` -> `silver.fact_currency_fx_rates`
**Domain:** Common | **Grain:** Currency Exchange Observation (Currency_ID, Date) | **Columns:** 13
*Continuous daily FX conversion rates to base currency (INR).*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Date` | DATE | `date` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/control_plane/simulation_fingerprint.py, infrastructure/warehouse/contracts.py, infrastructure/providers/files/csv.py (+49 more)] |
| `Currency_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/providers/market/currency.py, domain/market/fx.py, domain/tax/events/quant.py (+6 more)] |
| `Currency_Code` | TEXT | `currency_code` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: currency_code). [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/market/fx.py (+1 more)] |
| `Target_Currency_Code` | TEXT | `target_currency_code` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: target_currency_code). [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/market/fx.py (+2 more)] |
| `yF_Ticker` | TEXT | `y_f_ticker` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: y_f_ticker). [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/benchmark.py, infrastructure/providers/market/common.py (+7 more)] |
| `FX_Rate` | DOUBLE | `fx_rate` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: fx_rate). [Consumers: infrastructure/providers/market/currency.py, domain/market/fx.py, domain/investments/transforms/common.py (+5 more)] |
| `Data_Provider` | TEXT | `data_provider` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: data_provider). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+4 more)] |
| `Extraction_Time` | TEXT | `extraction_time` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: extraction_time). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+4 more)] |
| `Requested_Start` | DATE | `requested_start` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: requested_start). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+3 more)] |
| `Requested_End` | DATE | `requested_end` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: requested_end). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+3 more)] |
| `Is_Closure_Gap` | BOOLEAN | `is_closure_gap` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_closure_gap). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+5 more)] |
| `Is_Imputed` | BOOLEAN | `is_imputed` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_imputed). [Consumers: domain/market/benchmarks.py, domain/market/fx.py, domain/investments/transforms/common.py (+1 more)] |
| `First_Observation_Date` | DATE | `first_observation_date` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: first_observation_date). [Consumers: domain/market/fx.py] |

### `silver.f_Income_Transactions` -> `silver.fact_income_transactions`
**Domain:** Household | **Grain:** Income Transaction (UID) | **Columns:** 28
*Recorded household income receipts with multi-currency amounts and tax flags.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `UID` | TEXT | `uid` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/household/expense.py (+18 more)] |
| `DATE` | DATE | `date` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/control_plane/schema.py, infrastructure/control_plane/simulation_fingerprint.py, infrastructure/warehouse/schema/gold.py (+12 more)] |
| `ASSET_ID` | TEXT | `asset_id` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: asset_id). [Consumers: domain/household/ledger.py, domain/household/cashflow/statement.py, domain/household/transforms/transactions.py] |
| `CATEGORY_ID` | TEXT | `category_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/income.py (+11 more)] |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/market/benchmark.py, domain/common/identity.py (+21 more)] |
| `TO_ASSET_ID` | TEXT | `to_asset_id` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: to_asset_id). [Consumers: domain/household/cashflow/statement.py, domain/household/transforms/transactions.py] |
| `TRANSFER_UID` | TEXT | `transfer_uid` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: transfer_uid). [Consumers: domain/household/transforms/transactions.py] |
| `TIME` | TEXT | `time` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: time). [Consumers: domain/household/transforms/transactions.py] |
| `DESCRIPTION` | TEXT | `description` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: description). [Consumers: domain/household/transforms/transactions.py] |
| `PAID` | TEXT | `paid` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: paid). [Consumers: domain/household/transforms/transactions.py] |
| `TRANSACTION_TYPE` | BIGINT | `transaction_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: transaction_type). [Consumers: domain/household/transforms/transactions.py] |
| `FEES_NOTES` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `MARK` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `TRANSFER_FEES` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `CARDDIVIDMONTH` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `Is_Active_Income` | BOOLEAN | `is_active_income` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_active_income). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/income.py, domain/household/ledger.py (+3 more)] |
| `Is_Dividend_Income` | BOOLEAN | `is_dividend_income` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_dividend_income). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/income.py, domain/household/ledger.py (+3 more)] |
| `Is_Interest_Income` | BOOLEAN | `is_interest_income` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_interest_income). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/income.py, domain/household/ledger.py (+3 more)] |
| `Is_Non_Cash_Income` | BOOLEAN | `is_non_cash_income` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_non_cash_income). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/income.py, domain/household/ledger.py (+2 more)] |
| `BASE_AMOUNT` | DOUBLE | `base_amount` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/ledger.py, domain/tax/events/builder.py, domain/tax/reconciliation/reconciler.py (+2 more)] |
| `AMOUNT_ACCOUNT` | DOUBLE | `amount_account` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/transforms/transactions.py] |
| `LOCAL_AMOUNT` | DOUBLE | `local_amount` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/transforms/transactions.py] |
| `EXCH_RATE` | DOUBLE | `exch_rate` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: exch_rate). [Consumers: domain/household/transforms/transactions.py] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |
| `S_NO` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+2 more)] |
| `TIMESTAMP` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: infrastructure/control_plane/schema.py, infrastructure/warehouse/schema/meta.py, domain/household/transforms/transactions.py] |
| `UPDATED_TIME` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |

### `silver.f_Expense_Transactions` -> `silver.fact_expense_transactions`
**Domain:** Household | **Grain:** Expense Transaction (UID) | **Columns:** 25
*Recorded household expense outlays with core lifestyle classifications.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `UID` | TEXT | `uid` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/household/expense.py (+18 more)] |
| `DATE` | DATE | `date` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/control_plane/schema.py, infrastructure/control_plane/simulation_fingerprint.py, infrastructure/warehouse/schema/gold.py (+12 more)] |
| `ASSET_ID` | TEXT | `asset_id` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: asset_id). [Consumers: domain/household/ledger.py, domain/household/cashflow/statement.py, domain/household/transforms/transactions.py] |
| `CATEGORY_ID` | TEXT | `category_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/income.py (+11 more)] |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/market/benchmark.py, domain/common/identity.py (+21 more)] |
| `TO_ASSET_ID` | TEXT | `to_asset_id` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: to_asset_id). [Consumers: domain/household/cashflow/statement.py, domain/household/transforms/transactions.py] |
| `TRANSFER_UID` | TEXT | `transfer_uid` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: transfer_uid). [Consumers: domain/household/transforms/transactions.py] |
| `TIME` | TEXT | `time` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: time). [Consumers: domain/household/transforms/transactions.py] |
| `DESCRIPTION` | TEXT | `description` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: description). [Consumers: domain/household/transforms/transactions.py] |
| `PAID` | TEXT | `paid` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: paid). [Consumers: domain/household/transforms/transactions.py] |
| `TRANSACTION_TYPE` | BIGINT | `transaction_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: transaction_type). [Consumers: domain/household/transforms/transactions.py] |
| `FEES_NOTES` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `MARK` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `TRANSFER_FEES` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `CARDDIVIDMONTH` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `Is_Core_Expense` | BOOLEAN | `is_core_expense` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_core_expense). [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/ledger.py (+2 more)] |
| `BASE_AMOUNT` | DOUBLE | `base_amount` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/ledger.py, domain/tax/events/builder.py, domain/tax/reconciliation/reconciler.py (+2 more)] |
| `AMOUNT_ACCOUNT` | DOUBLE | `amount_account` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/transforms/transactions.py] |
| `LOCAL_AMOUNT` | DOUBLE | `local_amount` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/transforms/transactions.py] |
| `EXCH_RATE` | DOUBLE | `exch_rate` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: exch_rate). [Consumers: domain/household/transforms/transactions.py] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |
| `S_NO` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+2 more)] |
| `TIMESTAMP` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: infrastructure/control_plane/schema.py, infrastructure/warehouse/schema/meta.py, domain/household/transforms/transactions.py] |
| `UPDATED_TIME` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |

### `silver.f_Transfer_Transactions` -> `silver.fact_transfer_transactions`
**Domain:** Household | **Grain:** Transfer Transaction (UID) | **Columns:** 27
*Inter-account transfers, credit card payments, and balance adjustments.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `UID` | TEXT | `uid` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/currency.py, domain/household/expense.py (+18 more)] |
| `DATE` | DATE | `date` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/control_plane/schema.py, infrastructure/control_plane/simulation_fingerprint.py, infrastructure/warehouse/schema/gold.py (+12 more)] |
| `ADJUSTED_DATE_FOR_ANALYSIS` | DATE | `adjusted_date_for_analysis` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: adjusted_date_for_analysis). [Consumers: domain/household/transforms/transactions.py] |
| `ASSET_ID` | TEXT | `asset_id` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: asset_id). [Consumers: domain/household/ledger.py, domain/household/cashflow/statement.py, domain/household/transforms/transactions.py] |
| `TO_ASSET_ID` | TEXT | `to_asset_id` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: to_asset_id). [Consumers: domain/household/cashflow/statement.py, domain/household/transforms/transactions.py] |
| `CATEGORY_ID` | TEXT | `category_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/income.py (+11 more)] |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/market/benchmark.py, domain/common/identity.py (+21 more)] |
| `TRANSFER_UID` | TEXT | `transfer_uid` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: transfer_uid). [Consumers: domain/household/transforms/transactions.py] |
| `TIME` | TEXT | `time` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: time). [Consumers: domain/household/transforms/transactions.py] |
| `DESCRIPTION` | TEXT | `description` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: description). [Consumers: domain/household/transforms/transactions.py] |
| `PAID` | TEXT | `paid` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: paid). [Consumers: domain/household/transforms/transactions.py] |
| `TRANSACTION_TYPE` | BIGINT | `transaction_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: transaction_type). [Consumers: domain/household/transforms/transactions.py] |
| `TRANSFER_TYPE` | TEXT | `transfer_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: transfer_type). [Consumers: domain/household/transforms/transactions.py] |
| `FEES_NOTES` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `MARK` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `TRANSFER_FEES` | TEXT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `CARDDIVIDMONTH` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `BASE_AMOUNT` | DOUBLE | `base_amount` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/ledger.py, domain/tax/events/builder.py, domain/tax/reconciliation/reconciler.py (+2 more)] |
| `AMOUNT_ACCOUNT` | DOUBLE | `amount_account` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/transforms/transactions.py] |
| `AMOUNT_PROPER` | DOUBLE | `proper_amount` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/ledger.py, domain/household/cashflow/statement.py, domain/household/transforms/transactions.py] |
| `LOCAL_AMOUNT` | DOUBLE | `local_amount` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/transforms/transactions.py] |
| `EXCH_RATE` | DOUBLE | `exch_rate` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: exch_rate). [Consumers: domain/household/transforms/transactions.py] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |
| `S_NO` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/asset_dimensions.py, domain/household/transforms/expense_dimensions.py, domain/household/transforms/income_dimensions.py (+2 more)] |
| `TIMESTAMP` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: infrastructure/control_plane/schema.py, infrastructure/warehouse/schema/meta.py, domain/household/transforms/transactions.py] |
| `UPDATED_TIME` | BIGINT | *(drop)* | 🗑️ REMOVE | `source_taxonomy` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |

### `silver.f_Opening_Balances` -> `silver.fact_opening_balances`
**Domain:** Household | **Grain:** Opening Balance Snapshot (ZASSETUID) | **Columns:** 18
*Account opening balance anchor points for cumulative ledger calculation.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Z_PK` | BIGINT | *(drop)* | 🗑️ REMOVE | `implementation_residue` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `ZTXDATESTR` | DATE | `date` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/fire/inflation.py, domain/household/ledger.py, domain/household/transforms/calendar.py (+1 more)] |
| `ZASSETUID` | TEXT | `asset_subcategory_id` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/ledger.py, domain/household/transforms/transactions.py] |
| `ZCATEGORYUID` | TEXT | *(drop)* | 🗑️ REMOVE | `implementation_residue` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `ZCURRENCYUID` | TEXT | *(drop)* | 🗑️ REMOVE | `implementation_residue` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `ZTOASSETUID` | TEXT | *(drop)* | 🗑️ REMOVE | `implementation_residue` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `ZTXUIDFEE` | TEXT | *(drop)* | 🗑️ REMOVE | `implementation_residue` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `ZTXUIDTRANS` | TEXT | *(drop)* | 🗑️ REMOVE | `implementation_residue` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `ZUID` | TEXT | *(drop)* | 🗑️ REMOVE | `implementation_residue` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `ZCONTENT` | TEXT | *(drop)* | 🗑️ REMOVE | `implementation_residue` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `ZDO_TYPE` | BIGINT | *(drop)* | 🗑️ REMOVE | `implementation_residue` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `ZAMOUNT` | DOUBLE | *(drop)* | 🗑️ REMOVE | `implementation_residue` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `ZAMOUNTACCOUNT` | DOUBLE | `opening_amount` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/ledger.py, domain/household/transforms/transactions.py] |
| `ZAMOUNTSUB` | DOUBLE | *(drop)* | 🗑️ REMOVE | `implementation_residue` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `ZDATE` | DOUBLE | *(drop)* | 🗑️ REMOVE | `implementation_residue` | Upstream source/UI residue with zero required downstream consumers in analytical marts. [Consumers: domain/household/transforms/transactions.py] |
| `ZUTIME` | BIGINT | `snapshot_timestamp` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/ledger.py, domain/household/transforms/transactions.py] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |

### `silver.d_Investment_Benchmark_Master` -> `silver.dim_benchmark_master`
**Domain:** Investments | **Grain:** Benchmark Security (ID) | **Columns:** 6
*Master index benchmarks (Nifty 50, S&P 500, Gold, CRISIL).*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `ID` | TEXT | `id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: presentation/desktop/base_tab.py, presentation/observability/desktop_sink.py, infrastructure/control_plane/artifact_repository.py (+23 more)] |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/market/benchmark.py, domain/common/identity.py (+21 more)] |
| `Benchmark_Name` | TEXT | `benchmark_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: benchmark_name). [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/benchmark.py, domain/household/transforms/reference_dimensions.py] |
| `yF_Ticker` | TEXT | `y_f_ticker` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: y_f_ticker). [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/benchmark.py, infrastructure/providers/market/common.py (+7 more)] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |

### `silver.d_Macro_Parameters` -> `silver.ref_financial_year_parameters`
**Domain:** Common | **Grain:** Financial Year Parameters (FY) | **Columns:** 25
*Annual macroeconomic, tax regime, and indexation rates by financial year.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `FY` | TEXT | `financial_year` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (financial_year) conforming to v11 vocabulary standard. [Consumers: infrastructure/warehouse/contracts.py, infrastructure/warehouse/schema/gold.py, infrastructure/providers/files/csv.py (+15 more)] |
| `FY_Start_Date` | DATE | `fy_start_date` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_start_date). [Consumers: infrastructure/providers/files/csv.py, domain/fire/inflation.py, domain/market/macro.py (+1 more)] |
| `FY_End_Date` | DATE | `fy_end_date` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_end_date). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Debt_MF_Cutoff_Date` | DATE | `debt_mf_cutoff_date` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: debt_mf_cutoff_date). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Inflation_Rate` | DOUBLE | `inflation_rate` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: inflation_rate). [Consumers: infrastructure/providers/files/csv.py, domain/fire/inflation.py, domain/market/macro.py (+1 more)] |
| `Risk_Free_Rate` | DOUBLE | `risk_free_rate` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: risk_free_rate). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Equity_Listed_LTCG` | DOUBLE | `equity_listed_ltcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: equity_listed_ltcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Equity_Listed_STCG` | DOUBLE | `equity_listed_stcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: equity_listed_stcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Equity_Unlisted_LTCG` | DOUBLE | `equity_unlisted_ltcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: equity_unlisted_ltcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Equity_Unlisted_STCG` | DOUBLE | `equity_unlisted_stcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: equity_unlisted_stcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Equity_LTCG_Exemption` | BIGINT | `equity_ltcg_exemption` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: equity_ltcg_exemption). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/investments/contracts/types.py (+5 more)] |
| `Gold_LTCG` | DOUBLE | `gold_ltcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: gold_ltcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Gold_STCG` | DOUBLE | `gold_stcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: gold_stcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Debt_MF_Pre_Cutoff_LTCG` | DOUBLE | `debt_mf_pre_cutoff_ltcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: debt_mf_pre_cutoff_ltcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Debt_MF_Pre_Cutoff_STCG` | DOUBLE | `debt_mf_pre_cutoff_stcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: debt_mf_pre_cutoff_stcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Debt_MF_Post_Cutoff_LTCG` | DOUBLE | `debt_mf_post_cutoff_ltcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: debt_mf_post_cutoff_ltcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Debt_MF_Post_Cutoff_STCG` | DOUBLE | `debt_mf_post_cutoff_stcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: debt_mf_post_cutoff_stcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Other_Debt_LTCG` | DOUBLE | `other_debt_ltcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: other_debt_ltcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Other_Debt_STCG` | DOUBLE | `other_debt_stcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: other_debt_stcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Default_LTCG` | DOUBLE | `default_ltcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: default_ltcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py (+1 more)] |
| `Default_STCG` | DOUBLE | `default_stcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: default_stcg). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py (+1 more)] |
| `Estimated_Ordinary_Income_Tax_Rate` | DOUBLE | `estimated_ordinary_income_tax_rate` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: estimated_ordinary_income_tax_rate). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/household/transforms/reference_dimensions.py] |
| `Remarks` | TEXT | `remarks` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: remarks). [Consumers: infrastructure/providers/files/csv.py, domain/household/transforms/reference_dimensions.py] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |

---

## 5. Investment, Event & Tax Dispositions (9 Tables) (Phase 007 Scope)

### `silver.d_Investment_Master` -> `silver.dim_instrument_master`
**Domain:** Investments | **Grain:** Instrument / Security (ISIN) | **Columns:** 17
*Master security master containing taxonomy, class, sector, geography, and tax rules.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `ISIN` | TEXT | `isin` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: application/__init__.py, contracts/observability.py, infrastructure/control_plane/run_repository.py (+44 more)] |
| `CATEGORY_ID` | TEXT | `category_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/household/expense.py, domain/household/income.py (+11 more)] |
| `BENCHMARK_ID` | TEXT | `benchmark_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/portfolio/snapshots.py (+4 more)] |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/market/benchmark.py, domain/common/identity.py (+21 more)] |
| `INSTRUMENT_NAME` | TEXT | `instrument_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: instrument_name). [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/files/csv.py, domain/wealth/analytics.py (+4 more)] |
| `INSTRUMENT_HOUSE` | TEXT | `instrument_house` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: instrument_house). [Consumers: domain/investments/transforms/common.py, domain/investments/transforms/indian_equity.py, domain/investments/transforms/mutual_funds.py (+1 more)] |
| `INSTRUMENT_CLASS` | TEXT | `instrument_class` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: instrument_class). [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/investments/contracts/types.py (+7 more)] |
| `INSTRUMENT_TYPE` | TEXT | `instrument_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: instrument_type). [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/investments/contracts/types.py (+7 more)] |
| `INSTRUMENT_SUBTYPE` | TEXT | `instrument_subtype` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: instrument_subtype). [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/investments/contracts/types.py (+6 more)] |
| `SECTOR` | TEXT | `sector` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: sector). [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/investments/contracts/types.py (+3 more)] |
| `INDUSTRY` | TEXT | `industry` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: industry). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/types.py, domain/investments/transforms/common.py (+2 more)] |
| `COUNTRY` | TEXT | `country` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: country). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/types.py, domain/investments/transforms/common.py (+2 more)] |
| `GEO` | TEXT | `geo` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: geo). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/types.py, domain/investments/transforms/common.py (+2 more)] |
| `GEO_SUBTYPE` | TEXT | `geo_subtype` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: geo_subtype). [Consumers: domain/investments/transforms/common.py] |
| `YAHOO_TICKER` | TEXT | `yahoo_ticker` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: yahoo_ticker). [Consumers: domain/investments/transforms/common.py, application/ingestion/market_sync.py] |
| `TAX_TYPE` | TEXT | `tax_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: tax_type). [Consumers: infrastructure/warehouse/silver.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+4 more)] |
| `TAX_SUBTYPE` | TEXT | `tax_subtype` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: tax_subtype). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/portfolio/analytics.py (+3 more)] |

### `silver.f_Investment_Market_Data` -> `silver.fact_investment_market_data`
**Domain:** Investments | **Grain:** Daily Market Price (Date, ISIN) | **Columns:** 22
*Continuous daily closing prices, valuations, and unrealized returns per instrument.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Date` | DATE | `date` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/control_plane/simulation_fingerprint.py, infrastructure/warehouse/contracts.py, infrastructure/providers/files/csv.py (+49 more)] |
| `ISIN` | TEXT | `isin` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: application/__init__.py, contracts/observability.py, infrastructure/control_plane/run_repository.py (+44 more)] |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/market/benchmark.py, domain/common/identity.py (+21 more)] |
| `__file_category__` | TEXT | `__file_category__` | 📦 KEEP | `source_taxonomy` | Required for US stock filtering in market_sync/market_state; must migrate to CURRENCY_ID/COUNTRY in Phase 007 before removal. [Consumers: infrastructure/providers/files/excel.py, domain/investments/transforms/common.py, domain/investments/transforms/indian_equity.py (+6 more)] |
| `Quantity` | DOUBLE | `quantity` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+16 more)] |
| `Closing_Price` | DOUBLE | `closing_price` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: closing_price). [Consumers: domain/investments/contracts/types.py, domain/investments/transforms/common.py, domain/investments/transforms/indian_equity.py (+6 more)] |
| `Buy_Price` | DOUBLE | `buy_price` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py, domain/investments/transforms/common.py (+4 more)] |
| `Closing_Value` | DOUBLE | `closing_value` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: closing_value). [Consumers: domain/investments/transforms/common.py, domain/investments/transforms/indian_equity.py, domain/investments/transforms/mutual_funds.py (+2 more)] |
| `Buy_Value` | DOUBLE | `buy_value` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/wealth/analytics.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+10 more)] |
| `Closing_Price_Local` | DOUBLE | `closing_price_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: closing_price_local). [Consumers: infrastructure/providers/market/us_market.py, domain/investments/transforms/common.py, domain/investments/valuation/market_state.py (+2 more)] |
| `Buy_Price_Local` | DOUBLE | `buy_price_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: buy_price_local). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/lots/ordering.py (+4 more)] |
| `Closing_Value_Local` | DOUBLE | `closing_value_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: closing_value_local). [Consumers: domain/investments/transforms/common.py, domain/investments/valuation/market_state.py, application/ingestion/asset_strategies.py] |
| `Buy_Value_Local` | DOUBLE | `buy_value_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: buy_value_local). [Consumers: domain/wealth/analytics.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+7 more)] |
| `FX_Rate` | DOUBLE | `fx_rate` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: fx_rate). [Consumers: infrastructure/providers/market/currency.py, domain/market/fx.py, domain/investments/transforms/common.py (+5 more)] |
| `Unit_PnL` | DOUBLE | `unit_pn_l` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (unit_pn_l) conforming to v11 vocabulary standard. [Consumers: domain/investments/transforms/common.py, domain/investments/transforms/indian_equity.py, domain/investments/transforms/mutual_funds.py (+2 more)] |
| `Total_PnL` | DOUBLE | `total_pn_l` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (total_pn_l) conforming to v11 vocabulary standard. [Consumers: domain/investments/transforms/common.py, domain/investments/transforms/indian_equity.py, domain/investments/transforms/mutual_funds.py (+3 more)] |
| `Data_Provider` | TEXT | `data_provider` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: data_provider). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+4 more)] |
| `Extraction_Time` | TEXT | `extraction_time` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: extraction_time). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+4 more)] |
| `Requested_Start` | DATE | `requested_start` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: requested_start). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+3 more)] |
| `Requested_End` | DATE | `requested_end` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: requested_end). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+3 more)] |
| `Is_Closure_Gap` | BOOLEAN | `is_closure_gap` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_closure_gap). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+5 more)] |
| `Is_Imputed` | BOOLEAN | `is_imputed` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_imputed). [Consumers: domain/market/benchmarks.py, domain/market/fx.py, domain/investments/transforms/common.py (+1 more)] |

### `silver.f_Investment_Purchase_Data` -> `silver.fact_investment_purchases`
**Domain:** Investments | **Grain:** Purchase Execution (Purchase_ID) | **Columns:** 13
*Execution records for security acquisitions across mutual funds and equities.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Purchase_ID` | TEXT | `purchase_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+8 more)] |
| `Date` | DATE | `date` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/control_plane/simulation_fingerprint.py, infrastructure/warehouse/contracts.py, infrastructure/providers/files/csv.py (+49 more)] |
| `ISIN` | TEXT | `isin` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: application/__init__.py, contracts/observability.py, infrastructure/control_plane/run_repository.py (+44 more)] |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/market/benchmark.py, domain/common/identity.py (+21 more)] |
| `__file_category__` | TEXT | `__file_category__` | 📦 KEEP | `source_taxonomy` | Required for US stock filtering in market_sync/market_state; must migrate to CURRENCY_ID/COUNTRY in Phase 007 before removal. [Consumers: infrastructure/providers/files/excel.py, domain/investments/transforms/common.py, domain/investments/transforms/indian_equity.py (+6 more)] |
| `Quantity` | DOUBLE | `quantity` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+16 more)] |
| `Price` | DOUBLE | `price` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: price). [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+8 more)] |
| `Value` | DOUBLE | `value` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: value). [Consumers: domain/household/budget.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+8 more)] |
| `Price_Local` | DOUBLE | `price_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: price_local). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/transforms/common.py (+3 more)] |
| `Value_Local` | DOUBLE | `value_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: value_local). [Consumers: domain/investments/contracts/types.py, domain/investments/transforms/common.py, domain/investments/transforms/us_equity.py (+2 more)] |
| `FX_Rate` | DOUBLE | `fx_rate` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: fx_rate). [Consumers: infrastructure/providers/market/currency.py, domain/market/fx.py, domain/investments/transforms/common.py (+5 more)] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |

### `silver.f_Investment_Sale_Data` -> `silver.fact_investment_sales`
**Domain:** Investments | **Grain:** Sale Execution (Sale_ID) | **Columns:** 19
*Execution records for security disposals with proceeds and transaction P&L.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Sale_ID` | TEXT | `sale_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+5 more)] |
| `Date` | DATE | `date` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/control_plane/simulation_fingerprint.py, infrastructure/warehouse/contracts.py, infrastructure/providers/files/csv.py (+49 more)] |
| `ISIN` | TEXT | `isin` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: application/__init__.py, contracts/observability.py, infrastructure/control_plane/run_repository.py (+44 more)] |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/market/benchmark.py, domain/common/identity.py (+21 more)] |
| `__file_category__` | TEXT | `__file_category__` | 📦 KEEP | `source_taxonomy` | Required for US stock filtering in market_sync/market_state; must migrate to CURRENCY_ID/COUNTRY in Phase 007 before removal. [Consumers: infrastructure/providers/files/excel.py, domain/investments/transforms/common.py, domain/investments/transforms/indian_equity.py (+6 more)] |
| `Quantity` | DOUBLE | `quantity` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+16 more)] |
| `Sell_Price` | DOUBLE | `sell_price` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/common/identity.py, domain/investments/contracts/types.py, domain/investments/lots/ordering.py (+2 more)] |
| `Sell_Value` | DOUBLE | `sell_value` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/household/budget.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+4 more)] |
| `Buy_Price` | DOUBLE | `buy_price` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py, domain/investments/transforms/common.py (+4 more)] |
| `Buy_Value` | DOUBLE | `buy_value` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/wealth/analytics.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+10 more)] |
| `Sell_Price_Local` | DOUBLE | `sell_price_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: sell_price_local). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/transforms/common.py (+2 more)] |
| `Sell_Value_Local` | DOUBLE | `sell_value_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: sell_value_local). [Consumers: domain/investments/contracts/types.py, domain/investments/transforms/common.py, application/ingestion/asset_strategies.py] |
| `Buy_Price_Local` | DOUBLE | `buy_price_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: buy_price_local). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/lots/ordering.py (+4 more)] |
| `Buy_Value_Local` | DOUBLE | `buy_value_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: buy_value_local). [Consumers: domain/wealth/analytics.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+7 more)] |
| `FX_Rate` | DOUBLE | `fx_rate` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: fx_rate). [Consumers: infrastructure/providers/market/currency.py, domain/market/fx.py, domain/investments/transforms/common.py (+5 more)] |
| `Unit_PnL` | DOUBLE | `unit_pn_l` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (unit_pn_l) conforming to v11 vocabulary standard. [Consumers: domain/investments/transforms/common.py, domain/investments/transforms/indian_equity.py, domain/investments/transforms/mutual_funds.py (+2 more)] |
| `Total_PnL` | DOUBLE | `total_pn_l` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (total_pn_l) conforming to v11 vocabulary standard. [Consumers: domain/investments/transforms/common.py, domain/investments/transforms/indian_equity.py, domain/investments/transforms/mutual_funds.py (+3 more)] |
| `__file_name__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/warehouse/bronze.py, infrastructure/warehouse/meta/healing.py, infrastructure/providers/files/csv.py (+16 more)] |
| `__folder_path__` | TEXT | *(drop)* | 🗑️ REMOVE | `provenance_reference` | Bronze lakehouse provenance residue; unreferenced in Silver/Gold full replacements. [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/files/excel.py, infrastructure/providers/files/sqlite.py (+12 more)] |

### `silver.f_Investment_Benchmark_Data` -> `silver.fact_investment_benchmark_data`
**Domain:** Investments | **Grain:** Daily Benchmark Close (Date, ID) | **Columns:** 12
*Continuous historical price series for index benchmarks.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Date` | DATE | `date` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/control_plane/simulation_fingerprint.py, infrastructure/warehouse/contracts.py, infrastructure/providers/files/csv.py (+49 more)] |
| `ID` | TEXT | `id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: presentation/desktop/base_tab.py, presentation/observability/desktop_sink.py, infrastructure/control_plane/artifact_repository.py (+23 more)] |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/market/benchmark.py, domain/common/identity.py (+21 more)] |
| `Benchmark_Name` | TEXT | `benchmark_name` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: benchmark_name). [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/benchmark.py, domain/household/transforms/reference_dimensions.py] |
| `yF_Ticker` | TEXT | `y_f_ticker` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: y_f_ticker). [Consumers: infrastructure/providers/files/csv.py, infrastructure/providers/market/benchmark.py, infrastructure/providers/market/common.py (+7 more)] |
| `Close` | DOUBLE | `close` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/control_plane/facade.py, infrastructure/recovery/restore.py, infrastructure/providers/market/benchmark.py (+5 more)] |
| `Data_Provider` | TEXT | `data_provider` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: data_provider). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+4 more)] |
| `Extraction_Time` | TEXT | `extraction_time` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: extraction_time). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+4 more)] |
| `Requested_Start` | DATE | `requested_start` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: requested_start). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+3 more)] |
| `Requested_End` | DATE | `requested_end` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: requested_end). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+3 more)] |
| `Is_Closure_Gap` | BOOLEAN | `is_closure_gap` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_closure_gap). [Consumers: infrastructure/providers/market/benchmark.py, infrastructure/providers/market/currency.py, infrastructure/providers/market/us_market.py (+5 more)] |
| `Is_Imputed` | BOOLEAN | `is_imputed` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_imputed). [Consumers: domain/market/benchmarks.py, domain/market/fx.py, domain/investments/transforms/common.py (+1 more)] |

### `silver.f_Investment_Analytics_Lot` -> `silver.fact_investment_lot_analytics`
**Domain:** Investments | **Grain:** Tax Lot Snapshot (Lot_ID, Closing_Date) | **Columns:** 88
*Comprehensive daily tax lot positions, FIFO tracking, XIRR, CAGR, and harvesting status.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Lot_ID` | TEXT | `lot_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/common/identity.py, domain/tax/events/builder.py, domain/tax/events/quant.py (+8 more)] |
| `Closing_Date` | DATE | `closing_date` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/control_plane/simulation_fingerprint.py, infrastructure/warehouse/schema/gold.py, domain/fire/deterministic.py (+12 more)] |
| `ISIN` | TEXT | `isin` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: application/__init__.py, contracts/observability.py, infrastructure/control_plane/run_repository.py (+44 more)] |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/market/benchmark.py, domain/common/identity.py (+21 more)] |
| `Buy_Date` | DATE | `buy_date` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py, application/investments/isin_service/metrics.py] |
| `Purchase_ID` | TEXT | `purchase_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+8 more)] |
| `Lot_Source_Type` | TEXT | `lot_source_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: lot_source_type). [Consumers: domain/tax/events/quant.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+4 more)] |
| `BENCHMARK_ID` | TEXT | `benchmark_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/portfolio/snapshots.py (+4 more)] |
| `TAX_TYPE` | TEXT | `tax_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: tax_type). [Consumers: infrastructure/warehouse/silver.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+4 more)] |
| `TAX_SUBTYPE` | TEXT | `tax_subtype` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: tax_subtype). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/portfolio/analytics.py (+3 more)] |
| `Quantity` | DOUBLE | `quantity` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+16 more)] |
| `Execution_Residual` | DOUBLE | `execution_residual` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: execution_residual). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `Buy_Price` | DOUBLE | `buy_price` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py, domain/investments/transforms/common.py (+4 more)] |
| `Market_Price` | DOUBLE | `market_price` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `Buy_Value` | DOUBLE | `buy_value` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/wealth/analytics.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+10 more)] |
| `Close_Value` | DOUBLE | `close_value` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/wealth/analytics.py, domain/investments/contracts/models.py, domain/investments/portfolio/aggregation.py (+2 more)] |
| `Buy_Value_Local` | DOUBLE | `buy_value_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: buy_value_local). [Consumers: domain/wealth/analytics.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+7 more)] |
| `Close_Value_Local` | DOUBLE | `close_value_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: close_value_local). [Consumers: domain/wealth/analytics.py, domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `Blended_FX_Buy_Rate` | DOUBLE | `fx_rate_buy_blended` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (fx_rate_buy_blended) conforming to v11 vocabulary standard. [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `Buy_Price_Local` | DOUBLE | `buy_price_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: buy_price_local). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/lots/ordering.py (+4 more)] |
| `Market_Price_Local` | DOUBLE | `market_price_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: market_price_local). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `FX_Rate_Buy` | DOUBLE | `fx_rate_buy` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: fx_rate_buy). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `FX_Rate_Snap` | DOUBLE | `fx_rate_snapshot` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: fx_rate_snapshot). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `Currency_Appreciation_Pct` | DOUBLE | `currency_appreciation_pct` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: currency_appreciation_pct). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `P/L` | DOUBLE | `pnl` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (pnl) conforming to v11 vocabulary standard. [Consumers: domain/wealth/analytics.py, domain/investments/contracts/models.py, domain/investments/portfolio/analytics.py (+1 more)] |
| `Absolute_Return` | DOUBLE | `absolute_return` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `Absolute_Return_Local` | DOUBLE | `absolute_return_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: absolute_return_local). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `Asset_PnL` | DOUBLE | `asset_pn_l` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/wealth/market_valuation.py (+7 more)] |
| `Forex_PnL` | DOUBLE | `fx_pnl` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/wealth/market_valuation.py (+7 more)] |
| `Forex_Contribution_Pct` | DOUBLE | `fx_contribution_pct` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (fx_contribution_pct) conforming to v11 vocabulary standard. [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `Asset_Return_Pct` | DOUBLE | `asset_return_pct` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (asset_return_pct) conforming to v11 vocabulary standard. [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `Forex_Return_Pct` | DOUBLE | `fx_return_pct` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (fx_return_pct) conforming to v11 vocabulary standard. [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `Lot_CAGR` | DOUBLE | `lot_cagr` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: lot_cagr). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py, application/investments/isin_service/metrics.py] |
| `Lot_CAGR_Status` | TEXT | `lot_cagr_status` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: lot_cagr_status). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py, application/investments/isin_service/metrics.py] |
| `Lot_CAGR_Local` | DOUBLE | `lot_cagr_local` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: lot_cagr_local). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py, application/investments/isin_service/metrics.py] |
| `CAGR` | DOUBLE | `cagr` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/common/calculation.py, domain/investments/__init__.py (+10 more)] |
| `CAGR_Status` | TEXT | `cagr_status` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: cagr_status). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `XIRR` | DOUBLE | `xirr` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/common/calculation.py, domain/investments/__init__.py (+13 more)] |
| `XIRR_Status` | TEXT | `xirr_status` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: xirr_status). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/portfolio/snapshots.py] |
| `XIRR_Local` | DOUBLE | `xirr_local` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: xirr_local). [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/investments/contracts/models.py (+5 more)] |
| `FX_XIRR_Impact` | DOUBLE | `fx_xirr_impact` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fx_xirr_impact). [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/investments/contracts/models.py (+5 more)] |
| `After_Tax_XIRR` | DOUBLE | `after_tax_xirr` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: after_tax_xirr). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+4 more)] |
| `BM_Buy_Price` | DOUBLE | `bm_buy_price` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: bm_buy_price). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py, application/investments/isin_service/metrics.py] |
| `BM_Market_Price` | DOUBLE | `bm_market_price` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: bm_market_price). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `Lot_BM_Return` | DOUBLE | `lot_bm_return` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: lot_bm_return). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `Lot_BM_CAGR` | DOUBLE | `lot_bm_cagr` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: lot_bm_cagr). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py, application/investments/isin_service/metrics.py] |
| `Lot_BM_CAGR_Status` | TEXT | `lot_bm_cagr_status` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: lot_bm_cagr_status). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py, application/investments/isin_service/metrics.py] |
| `Lot_BM_CAGR_Local` | DOUBLE | `lot_bm_cagr_local` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: lot_bm_cagr_local). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py, application/investments/isin_service/metrics.py] |
| `BM_CAGR` | DOUBLE | `bm_cagr` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: bm_cagr). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+3 more)] |
| `BM_CAGR_Status` | TEXT | `bm_cagr_status` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: bm_cagr_status). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `BM_XIRR` | DOUBLE | `bm_xirr` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: bm_xirr). [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/investments/contracts/models.py (+5 more)] |
| `BM_XIRR_Local` | DOUBLE | `bm_xirr_local` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: bm_xirr_local). [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/investments/contracts/models.py (+4 more)] |
| `Active_Return` | DOUBLE | `active_return` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: active_return). [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/investments/contracts/models.py (+5 more)] |
| `Active_Return_Local` | DOUBLE | `active_return_local` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: active_return_local). [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/investments/contracts/models.py (+5 more)] |
| `Lot_Alpha` | DOUBLE | `lot_alpha` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: lot_alpha). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py, application/investments/isin_service/metrics.py] |
| `Is_Lagging_Benchmark` | BIGINT | `is_lagging_benchmark` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: is_lagging_benchmark). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+3 more)] |
| `Max_Drawdown` | DOUBLE | `max_drawdown` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: max_drawdown). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+2 more)] |
| `Lot_Weight` | DOUBLE | `lot_weight` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: lot_weight). [Consumers: domain/investments/contracts/models.py, domain/investments/performance/attribution.py, domain/investments/portfolio/aggregation.py] |
| `Portfolio_Weight` | DOUBLE | `portfolio_weight` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: portfolio_weight). [Consumers: domain/investments/portfolio/aggregation.py] |
| `Outperforming_Lot_Ratio` | DOUBLE | `outperforming_lot_ratio` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: outperforming_lot_ratio). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `Dietz_Day_Weight` | DOUBLE | `dietz_day_weight` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: dietz_day_weight). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `Age_Days` | BIGINT | `age_days` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: age_days). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `LTCG_Threshold_Days` | BIGINT | `ltcg_threshold_days` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: ltcg_threshold_days). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `Days_To_LTCG` | BIGINT | `days_to_ltcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: days_to_ltcg). [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/analytics.py, domain/investments/portfolio/snapshots.py] |
| `Holding_Type` | TEXT | `holding_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: holding_type). [Consumers: domain/tax/classification.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+5 more)] |
| `Tax_Rate` | DOUBLE | `tax_rate` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `Unrealized_LTCG` | DOUBLE | `unrealized_ltcg` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/analytics.py (+2 more)] |
| `Unrealized_STCG` | DOUBLE | `unrealized_stcg` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `Unrealized_Gain` | DOUBLE | `unrealized_gain` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `Unrealized_LTCL` | DOUBLE | `unrealized_ltcl` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `Unrealized_STCL` | DOUBLE | `unrealized_stcl` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `Unrealized_Loss` | DOUBLE | `unrealized_loss` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/analytics.py (+2 more)] |
| `LTCG_Tax_If_Sold` | DOUBLE | `ltcg_tax_if_sold` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `STCG_Tax_If_Sold` | DOUBLE | `stcg_tax_if_sold` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py (+1 more)] |
| `After_Tax_PL` | DOUBLE | `after_tax_pl` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `After_Tax_Close_Value` | DOUBLE | `after_tax_close_value` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/investments/contracts/models.py, domain/investments/portfolio/snapshots.py] |
| `FY` | TEXT | `financial_year` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (financial_year) conforming to v11 vocabulary standard. [Consumers: infrastructure/warehouse/contracts.py, infrastructure/warehouse/schema/gold.py, infrastructure/providers/files/csv.py (+15 more)] |
| `FY_Realized_LTCG` | DOUBLE | `fy_realized_ltcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_realized_ltcg). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/performance/attribution.py] |
| `FY_Realized_STCG` | DOUBLE | `fy_realized_stcg` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_realized_stcg). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/performance/attribution.py] |
| `FY_Realized_Gain` | DOUBLE | `fy_realized_gain` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_realized_gain). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/performance/attribution.py, application/investments/aggregation_service/service.py] |
| `FY_Realized_LTCL` | DOUBLE | `fy_realized_ltcl` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_realized_ltcl). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/performance/attribution.py] |
| `FY_Realized_STCL` | DOUBLE | `fy_realized_stcl` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_realized_stcl). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/performance/attribution.py] |
| `FY_Realized_Loss` | DOUBLE | `fy_realized_loss` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_realized_loss). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/performance/attribution.py, application/investments/aggregation_service/service.py] |
| `FY_Realized_Net_PnL` | DOUBLE | `fy_realized_net_pn_l` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: fy_realized_net_pn_l). [Consumers: infrastructure/warehouse/schema/gold.py, domain/investments/performance/attribution.py, application/investments/aggregation_service/service.py] |
| `Equity_LTCG_Exemption` | BIGINT | `equity_ltcg_exemption` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: equity_ltcg_exemption). [Consumers: infrastructure/providers/files/csv.py, domain/market/macro.py, domain/investments/contracts/types.py (+5 more)] |
| `Stepup_Eligible` | BIGINT | `stepup_eligible` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: stepup_eligible). [Consumers: domain/investments/portfolio/analytics.py] |
| `Can_Harvest_Loss` | BOOLEAN | `can_harvest_loss` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: can_harvest_loss). [Consumers: domain/investments/portfolio/analytics.py] |
| `Harvest_Recommendation` | TEXT | `harvest_recommendation` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: harvest_recommendation). [Consumers: domain/investments/portfolio/analytics.py] |

### `silver.f_Investment_Realized_Events` -> `silver.fact_investment_realized_events`
**Domain:** Investments | **Grain:** Lot Realized Gain/Loss Disposal (Realized_Event_ID) | **Columns:** 24
*Realized capital gains/losses matched to specific tax lots and sales.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Realized_Event_ID` | TEXT | `realized_event_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/tax/events/quant.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+2 more)] |
| `Sale_ID` | TEXT | `sale_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+5 more)] |
| `Lot_ID` | TEXT | `lot_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/common/identity.py, domain/tax/events/builder.py, domain/tax/events/quant.py (+8 more)] |
| `Purchase_ID` | TEXT | `purchase_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+8 more)] |
| `ISIN` | TEXT | `isin` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: application/__init__.py, contracts/observability.py, infrastructure/control_plane/run_repository.py (+44 more)] |
| `Acquisition_Date` | DATE | `acquisition_date` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/tax/classification.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+2 more)] |
| `Disposal_Date` | DATE | `disposal_date` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/tax/events/quant.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+3 more)] |
| `FY` | TEXT | `financial_year` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (financial_year) conforming to v11 vocabulary standard. [Consumers: infrastructure/warehouse/contracts.py, infrastructure/warehouse/schema/gold.py, infrastructure/providers/files/csv.py (+15 more)] |
| `Quantity_Disposed` | DOUBLE | `quantity_disposed` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/lots/fifo.py (+1 more)] |
| `Acquisition_Price` | DOUBLE | `acquisition_price` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: acquisition_price). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/lots/fifo.py (+1 more)] |
| `Disposed_Cost_Basis` | DOUBLE | `disposed_cost_basis` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: disposed_cost_basis). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/lots/fifo.py (+1 more)] |
| `Sale_Price` | DOUBLE | `sale_price` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: sale_price). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/lots/fifo.py (+1 more)] |
| `Sale_Proceeds` | DOUBLE | `sale_proceeds` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: sale_proceeds). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/lots/fifo.py (+1 more)] |
| `Realized_Gain_Loss` | DOUBLE | `realized_gain_loss` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/tax/events/quant.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+3 more)] |
| `Holding_Type` | TEXT | `holding_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: holding_type). [Consumers: domain/tax/classification.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+5 more)] |
| `Tax_Type` | TEXT | `tax_type` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: tax_type). [Consumers: domain/tax/classification.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+3 more)] |
| `Tax_Subtype` | TEXT | `tax_subtype` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: tax_subtype). [Consumers: domain/tax/classification.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+3 more)] |
| `Lot_Source_Type` | TEXT | `lot_source_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: lot_source_type). [Consumers: domain/tax/events/quant.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+4 more)] |
| `Currency_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/providers/market/currency.py, domain/market/fx.py, domain/tax/events/quant.py (+6 more)] |
| `Asset_PnL_Local` | DOUBLE | `asset_pn_l_local` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: asset_pn_l_local). [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, domain/investments/lots/fifo.py (+1 more)] |
| `Asset_PnL` | DOUBLE | `asset_pn_l` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/wealth/market_valuation.py (+7 more)] |
| `Forex_PnL` | DOUBLE | `fx_pnl` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: infrastructure/warehouse/schema/gold.py, domain/wealth/analytics.py, domain/wealth/market_valuation.py (+7 more)] |
| `Applied_Rate` | DOUBLE | `applied_rate` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/tax/events/builder.py, domain/tax/events/quant.py, domain/tax/events/schema.py (+4 more)] |
| `Estimated_Tax` | DOUBLE | `estimated_tax` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/tax/events/builder.py, domain/tax/events/quant.py, domain/tax/events/schema.py (+5 more)] |

### `silver.f_Investment_Reconciliation_Events` -> `silver.fact_investment_reconciliation_events`
**Domain:** Investments | **Grain:** Reconciliation Adjustment (Reconciliation_Event_ID) | **Columns:** 17
*Audit trail of unit and cost basis adjustments reconciling broker statements to engine truth.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Reconciliation_Group_ID` | TEXT | `reconciliation_group_id` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+1 more)] |
| `Reconciliation_Event_ID` | TEXT | `reconciliation_event_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/investments/contracts/models.py, domain/investments/contracts/types.py, application/investments/aggregation_service/events.py] |
| `Run_ID` | TEXT | `run_id` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/investments/contracts/types.py, application/investments/aggregation_service/events.py] |
| `ISIN` | TEXT | `isin` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: application/__init__.py, contracts/observability.py, infrastructure/control_plane/run_repository.py (+44 more)] |
| `Reconciliation_Date` | DATE | `reconciliation_date` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+2 more)] |
| `Lot_ID` | TEXT | `lot_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/common/identity.py, domain/tax/events/builder.py, domain/tax/events/quant.py (+8 more)] |
| `Purchase_ID` | TEXT | `purchase_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+8 more)] |
| `Adjustment_Type` | TEXT | `adjustment_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: adjustment_type). [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+2 more)] |
| `Reason` | TEXT | `reason` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: reason). [Consumers: domain/investments/contracts/types.py, domain/investments/lots/reconciliation.py, application/investments/aggregation_service/events.py] |
| `Broker_Quantity` | DOUBLE | `broker_quantity` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: broker_quantity). [Consumers: domain/common/identity.py, domain/investments/contracts/types.py, domain/investments/lots/reconciliation.py (+1 more)] |
| `Reconstructed_Quantity` | DOUBLE | `reconstructed_quantity` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: reconstructed_quantity). [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+2 more)] |
| `Quantity_Adjustment` | DOUBLE | `quantity_adjustment` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: quantity_adjustment). [Consumers: domain/investments/contracts/types.py, domain/investments/lots/reconciliation.py, application/investments/aggregation_service/events.py] |
| `Broker_Cost_Basis` | DOUBLE | `broker_cost_basis` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: broker_cost_basis). [Consumers: domain/common/identity.py, domain/investments/contracts/types.py, domain/investments/lots/reconciliation.py (+1 more)] |
| `Reconstructed_Cost_Basis` | DOUBLE | `reconstructed_cost_basis` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: reconstructed_cost_basis). [Consumers: domain/common/identity.py, domain/investments/contracts/models.py, domain/investments/contracts/types.py (+2 more)] |
| `Cost_Basis_Adjustment` | DOUBLE | `cost_basis_adjustment` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: cost_basis_adjustment). [Consumers: domain/investments/contracts/types.py, domain/investments/lots/reconciliation.py, application/investments/aggregation_service/events.py] |
| `Original_Unit_Cost` | DOUBLE | `original_unit_cost` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: original_unit_cost). [Consumers: domain/investments/contracts/types.py, domain/investments/lots/reconciliation.py, application/investments/aggregation_service/events.py] |
| `Adjusted_Unit_Cost` | DOUBLE | `adjusted_unit_cost` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: adjusted_unit_cost). [Consumers: domain/investments/contracts/types.py, domain/investments/lots/reconciliation.py, application/investments/aggregation_service/events.py] |

### `silver.f_Tax_Events` -> `silver.fact_tax_events`
**Domain:** Tax | **Grain:** Taxable Event (Tax_Event_ID) | **Columns:** 15
*Granular taxable events across income heads, capital gains, and dividend streams.*

| Current Column | Type | Target Name | Disposition | Classification | Known Consumers / Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Tax_Event_ID` | TEXT | `tax_event_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/tax/events/builder.py, domain/tax/events/schema.py] |
| `FY` | TEXT | `financial_year` | 🏷️ RENAME | `canonical_financial` | Canonical naming alignment (financial_year) conforming to v11 vocabulary standard. [Consumers: infrastructure/warehouse/contracts.py, infrastructure/warehouse/schema/gold.py, infrastructure/providers/files/csv.py (+15 more)] |
| `Event_Date` | DATE | `event_date` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/tax/events/builder.py, domain/tax/events/quant.py, domain/tax/events/schema.py] |
| `Source_Type` | TEXT | `source_type` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: source_type). [Consumers: infrastructure/warehouse/schema/gold.py, domain/common/identity.py, domain/tax/events/builder.py (+5 more)] |
| `Source_ID` | TEXT | `source_id` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: source_id). [Consumers: domain/common/identity.py, domain/tax/events/builder.py, domain/tax/events/hashing.py (+2 more)] |
| `Income_Head` | TEXT | `income_head` | 🏷️ RENAME | `source_taxonomy` | Active analytical dimension or metric (canonical target: income_head). [Consumers: infrastructure/warehouse/schema/gold.py, domain/tax/events/builder.py, domain/tax/events/quant.py (+3 more)] |
| `Tax_Sub_Head` | TEXT | `tax_sub_head` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: tax_sub_head). [Consumers: infrastructure/warehouse/schema/gold.py, domain/common/identity.py, domain/tax/events/builder.py (+6 more)] |
| `Amount_INR` | DOUBLE | `amount_inr` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/tax/events/builder.py, domain/tax/events/quant.py, domain/tax/events/schema.py (+1 more)] |
| `Applied_Rate` | DOUBLE | `applied_rate` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/tax/events/builder.py, domain/tax/events/quant.py, domain/tax/events/schema.py (+4 more)] |
| `Estimated_Tax` | DOUBLE | `estimated_tax` | 🛡️ PROTECTED | `canonical_financial` | Core financial metric, valuation, rate, or balance key; exact financial equivalence required. [Consumers: domain/tax/events/builder.py, domain/tax/events/quant.py, domain/tax/events/schema.py (+5 more)] |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: infrastructure/warehouse/schema/gold.py, infrastructure/providers/market/benchmark.py, domain/common/identity.py (+21 more)] |
| `Tax_Status` | TEXT | `tax_status` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: tax_status). [Consumers: domain/tax/events/builder.py, domain/tax/events/quant.py, domain/tax/events/schema.py (+1 more)] |
| `Tax_Status_Reason` | TEXT | `tax_status_reason` | 🏷️ RENAME | `canonical_financial` | Active analytical dimension or metric (canonical target: tax_status_reason). [Consumers: domain/tax/events/builder.py, domain/tax/events/quant.py, domain/tax/events/schema.py] |
| `ISIN` | TEXT | `isin` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: application/__init__.py, contracts/observability.py, infrastructure/control_plane/run_repository.py (+44 more)] |
| `Lot_ID` | TEXT | `lot_id` | 🛡️ PROTECTED | `canonical_identity` | Critical primary or foreign key business identity; byte-for-byte preservation required. [Consumers: domain/common/identity.py, domain/tax/events/builder.py, domain/tax/events/quant.py (+8 more)] |

---

## 6. Zero-Consumer Removal Safety Ledger

The following columns have been rigorously proven to have **zero consumers** across all downstream analytical, presentation, and reporting engines.
They are safely designated as `REMOVE_CANDIDATE` for elimination during their owning sprint:

#### `silver.d_Income_Category` (5 removal candidates)
`ORDER_SEQUENCE`, `__file_name__`, `__folder_path__`, `S_NO`, `MODIFY_DATE`

#### `silver.d_Income_Subcategory` (5 removal candidates)
`ORDER_SEQUENCE`, `__file_name__`, `__folder_path__`, `S_NO`, `MODIFY_DATE`

#### `silver.d_Expense_Category` (5 removal candidates)
`ORDER_SEQUENCE`, `__file_name__`, `__folder_path__`, `S_NO`, `MODIFY_DATE`

#### `silver.d_Expense_Subcategory` (5 removal candidates)
`ORDER_SEQUENCE`, `__file_name__`, `__folder_path__`, `S_NO`, `MODIFY_DATE`

#### `silver.d_Asset_Category` (5 removal candidates)
`ORDER_SEQUENCE`, `__file_name__`, `__folder_path__`, `DEVICE_ID`, `USE_TIME`

#### `silver.d_Asset_Subcategory` (10 removal candidates)
`AUTOPAY_ASSET_ID`, `ORDER_SEQUENCE`, `TRANSFER_EXPENSE`, `CARD_AUTOPAY`, `CARD_STATEMENT_DATE`, `CARD_PAYMENT_DATE`, `__file_name__`, `__folder_path__`, `S_NO`, `ADDED_TIME`

#### `silver.d_Currency` (12 removal candidates)
`MAIN_ISO`, `SYMBOL_POSITION`, `ORDER_SEQUENCE`, `RATE`, `DECIMAL_POINT`, `IS_MAIN_CURRENCY`, `IS_SHOW`, `INSERT_TYPE`, `__file_name__`, `__folder_path__`, `S_NO`, `MODIFY_DATE`

#### `silver.f_Income_Transactions` (9 removal candidates)
`FEES_NOTES`, `MARK`, `TRANSFER_FEES`, `CARDDIVIDMONTH`, `__file_name__`, `__folder_path__`, `S_NO`, `TIMESTAMP`, `UPDATED_TIME`

#### `silver.f_Expense_Transactions` (9 removal candidates)
`FEES_NOTES`, `MARK`, `TRANSFER_FEES`, `CARDDIVIDMONTH`, `__file_name__`, `__folder_path__`, `S_NO`, `TIMESTAMP`, `UPDATED_TIME`

#### `silver.f_Transfer_Transactions` (9 removal candidates)
`FEES_NOTES`, `MARK`, `TRANSFER_FEES`, `CARDDIVIDMONTH`, `__file_name__`, `__folder_path__`, `S_NO`, `TIMESTAMP`, `UPDATED_TIME`

#### `silver.f_Opening_Balances` (14 removal candidates)
`Z_PK`, `ZCATEGORYUID`, `ZCURRENCYUID`, `ZTOASSETUID`, `ZTXUIDFEE`, `ZTXUIDTRANS`, `ZUID`, `ZCONTENT`, `ZDO_TYPE`, `ZAMOUNT`, `ZAMOUNTSUB`, `ZDATE`, `__file_name__`, `__folder_path__`

#### `silver.d_Investment_Benchmark_Master` (2 removal candidates)
`__file_name__`, `__folder_path__`

#### `silver.d_Macro_Parameters` (2 removal candidates)
`__file_name__`, `__folder_path__`

#### `silver.f_Investment_Purchase_Data` (2 removal candidates)
`__file_name__`, `__folder_path__`

#### `silver.f_Investment_Sale_Data` (2 removal candidates)
`__file_name__`, `__folder_path__`

---

## 7. Protected Financial & Identity Invariants

The v11 program guarantees **zero unexplained financial drift**. The following columns are designated as `PROTECTED`.
Any discrepancy in their values or byte representation during subsequent migrations will halt the pipeline:

- **`silver.d_Calendar`**: `Date`
- **`silver.d_Income_Category`**: `UID`
- **`silver.d_Income_Subcategory`**: `UID`, `CATEGORY_ID`
- **`silver.d_Expense_Category`**: `UID`
- **`silver.d_Expense_Subcategory`**: `UID`, `CATEGORY_ID`
- **`silver.d_Asset_Category`**: `UID`
- **`silver.d_Asset_Subcategory`**: `UID`, `CURRENCY_ID`
- **`silver.d_Currency`**: `UID`
- **`silver.f_Currency_FX_Rates`**: `Date`, `Currency_ID`
- **`silver.f_Income_Transactions`**: `UID`, `DATE`, `CATEGORY_ID`, `CURRENCY_ID`, `BASE_AMOUNT`, `AMOUNT_ACCOUNT`, `LOCAL_AMOUNT`
- **`silver.f_Expense_Transactions`**: `UID`, `DATE`, `CATEGORY_ID`, `CURRENCY_ID`, `BASE_AMOUNT`, `AMOUNT_ACCOUNT`, `LOCAL_AMOUNT`
- **`silver.f_Transfer_Transactions`**: `UID`, `DATE`, `CATEGORY_ID`, `CURRENCY_ID`, `BASE_AMOUNT`, `AMOUNT_ACCOUNT`, `AMOUNT_PROPER`, `LOCAL_AMOUNT`
- **`silver.f_Opening_Balances`**: `ZTXDATESTR`, `ZASSETUID`, `ZAMOUNTACCOUNT`, `ZUTIME`
- **`silver.d_Investment_Benchmark_Master`**: `ID`, `CURRENCY_ID`
- **`silver.d_Investment_Master`**: `ISIN`, `CATEGORY_ID`, `BENCHMARK_ID`, `CURRENCY_ID`
- **`silver.f_Investment_Market_Data`**: `Date`, `ISIN`, `CURRENCY_ID`, `Quantity`, `Buy_Price`, `Buy_Value`
- **`silver.f_Investment_Purchase_Data`**: `Purchase_ID`, `Date`, `ISIN`, `CURRENCY_ID`, `Quantity`
- **`silver.f_Investment_Sale_Data`**: `Sale_ID`, `Date`, `ISIN`, `CURRENCY_ID`, `Quantity`, `Sell_Price`, `Sell_Value`, `Buy_Price`, `Buy_Value`
- **`silver.f_Investment_Benchmark_Data`**: `Date`, `ID`, `CURRENCY_ID`, `Close`
- **`silver.f_Investment_Analytics_Lot`**: `Lot_ID`, `Closing_Date`, `ISIN`, `CURRENCY_ID`, `Buy_Date`, `Purchase_ID`, `BENCHMARK_ID`, `Quantity`, `Buy_Price`, `Market_Price`, `Buy_Value`, `Close_Value`, `Absolute_Return`, `Asset_PnL`, `Forex_PnL`, `CAGR`, `XIRR`, `Tax_Rate`, `Unrealized_LTCG`, `Unrealized_STCG`, `Unrealized_Gain`, `Unrealized_LTCL`, `Unrealized_STCL`, `Unrealized_Loss`, `LTCG_Tax_If_Sold`, `STCG_Tax_If_Sold`, `After_Tax_PL`, `After_Tax_Close_Value`
- **`silver.f_Investment_Realized_Events`**: `Realized_Event_ID`, `Sale_ID`, `Lot_ID`, `Purchase_ID`, `ISIN`, `Acquisition_Date`, `Disposal_Date`, `Quantity_Disposed`, `Realized_Gain_Loss`, `Currency_ID`, `Asset_PnL`, `Forex_PnL`, `Applied_Rate`, `Estimated_Tax`
- **`silver.f_Investment_Reconciliation_Events`**: `Reconciliation_Group_ID`, `Reconciliation_Event_ID`, `Run_ID`, `ISIN`, `Reconciliation_Date`, `Lot_ID`, `Purchase_ID`
- **`silver.f_Tax_Events`**: `Tax_Event_ID`, `Event_Date`, `Amount_INR`, `Applied_Rate`, `Estimated_Tax`, `CURRENCY_ID`, `ISIN`, `Lot_ID`