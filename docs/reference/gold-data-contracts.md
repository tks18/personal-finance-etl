# Gold Data Contracts

Gold is the analytical presentation layer. It reshapes canonical state for decision-making, BI, portfolio analysis, Tax summaries, and household/wealth analytics.

Gold is not allowed to become a second financial engine. Its contract is presentation grain plus physical schema, with financial meaning inherited from canonical upstream state.

## Contract catalog

| Contract ID | Physical table | Domain | Grain | Producer | Order |
|---|---|---|---|---|---:|
| `df_p_tax_year_summary` | `gold.tax_financial_year_summary` | Taxes | `FY` | `TaxEngine` | 302 |
| `df_p_tax_income_breakdown` | `gold.tax_income_head_breakdown` | Taxes | `FY-Head-SubHead-Source` | `TaxEngine` | 303 |
| `df_p_tax_reconciliation` | `gold.tax_subhead_reconciliation` | Taxes | `FY-SubHead` | `TaxEngine` | 304 |
| `df_p_tf_wealth_monthly_totals` | `gold.core_monthly_fact` | Wealth | `Month` | `WealthPresentationEngine` | 110 |
| `df_p_tf_net_worth_monthly_summary` | `gold.wealth_asset_breakdown` | Wealth | `Month-Asset` | `WealthPresentationEngine` | 110 |
| `df_p_tf_category_spend_analytics` | `gold.cashflow_expense_breakdown` | Wealth | `Month-ExpenseCategory` | `WealthPresentationEngine` | 120 |
| `df_p_tf_income_streams_monthly` | `gold.cashflow_income_breakdown` | Wealth | `Month-IncomeCategory` | `WealthPresentationEngine` | 130 |
| `df_p_tf_wealth_risk_analytics` | `gold.wealth_fire_analytics` | Wealth | `Month` | `WealthPresentationEngine` | 140 |
| `df_p_tf_budget_forecast_monthly` | `gold.forecast_budget_variance` | Wealth | `Month` | `WealthPresentationEngine` | 160 |
| `df_p_tf_investment_analytics` | `gold.investment_portfolio_summary` | Investments | `Month-ISIN` | `InvestmentQuantEngine` | 170 |
| `df_p_tf_monthly_cashflow_summary` | `gold.cashflow_efficiency_analytics` | Wealth | `Month` | `WealthPresentationEngine` | 180 |
| `df_p_tf_cashflow_activity_summary` | `gold.cashflow_activity_summary` | Wealth | `Month` | `WealthPresentationEngine` | 190 |
| `df_f_investment_analytics_isin` | `gold.investment_by_isin` | Investments | `Date-ISIN` | `InvestmentQuantEngine` | 200 |
| `df_f_investment_analytics_subtype` | `gold.investment_by_subtype` | Investments | `Date-Subtype` | `InvestmentQuantEngine` | 210 |
| `df_f_investment_analytics_class` | `gold.investment_by_class` | Investments | `Date-Class` | `InvestmentQuantEngine` | 220 |
| `df_f_investment_analytics_instrument_type` | `gold.investment_by_instrument_type` | Investments | `Date-InstrumentType` | `InvestmentQuantEngine` | 230 |
| `df_f_investment_analytics_sector` | `gold.investment_by_sector` | Investments | `Date-Sector` | `InvestmentQuantEngine` | 240 |
| `df_f_investment_analytics_industry` | `gold.investment_by_industry` | Investments | `Date-Industry` | `InvestmentQuantEngine` | 250 |
| `df_f_investment_analytics_portfolio` | `gold.investment_by_portfolio` | Investments | `Date` | `InvestmentQuantEngine` | 260 |
| `df_f_investment_analytics_geo` | `gold.investment_by_geo` | Investments | `Date-Geo` | `InvestmentQuantEngine` | 270 |
| `df_f_investment_analytics_country` | `gold.investment_by_country` | Investments | `Date-Country` | `InvestmentQuantEngine` | 280 |
| `df_f_investment_analytics_currency` | `gold.investment_by_currency` | Investments | `Date-Currency` | `InvestmentQuantEngine` | 290 |


## Physical schemas

The following tables are generated directly from `schema/gold.py`.

### `gold.tax_financial_year_summary`

**Contract ID:** `df_p_tax_year_summary`  
**Grain:** `FY`  
**Domain:** `Taxes`  
**Producer:** `TaxEngine`  
**Publication order:** `302`

| Column | Physical type / constraint | Role |
|---|---|---|
| `FY` | `TEXT PRIMARY KEY` | Field |
| `Total_Ledger_Income` | `DOUBLE` | Field |
| `Total_Investment_Gain_Loss` | `DOUBLE` | Field |
| `Total_Tax_Credits` | `DOUBLE` | Field |
| `Total_Estimated_Investment_Tax` | `DOUBLE` | Field |
| `Investment_Tax_Estimate_Count` | `BIGINT` | Field |
| `Investment_Tax_Estimate_Missing_Count` | `BIGINT` | Field |
| `Investment_Tax_Estimate_Complete` | `BOOLEAN` | Field |
| `Total_Estimated_Ledger_Tax` | `DOUBLE` | Field |
| `Ledger_Tax_Estimate_Count` | `BIGINT` | Field |
| `Ledger_Tax_Estimate_Missing_Count` | `BIGINT` | Field |
| `Ledger_Tax_Estimate_Complete` | `BOOLEAN` | Field |
| `Total_Event_Count` | `BIGINT` | Field |
| `Ready_Count` | `BIGINT` | Field |
| `Indicative_Unrealized_Tax_Liability` | `DOUBLE` | Tax Exposure Summary |
| `Indicative_Harvestable_Tax_Savings` | `DOUBLE` | Tax Exposure Summary |
| `Indicative_Net_Tax_Exposure` | `DOUBLE` | Tax Exposure Summary |

**Table constraints**

- `Check_Required_Count BIGINT`

### `gold.tax_income_head_breakdown`

**Contract ID:** `df_p_tax_income_breakdown`  
**Grain:** `FY-Head-SubHead-Source`  
**Domain:** `Taxes`  
**Producer:** `TaxEngine`  
**Publication order:** `303`

| Column | Physical type / constraint | Role |
|---|---|---|
| `FY` | `TEXT` | Field |
| `Income_Head` | `TEXT` | Field |
| `Tax_Sub_Head` | `TEXT` | Field |
| `Source_Type` | `TEXT` | Field |
| `Event_Amount_INR` | `DOUBLE` | Field |
| `Estimated_Tax_INR` | `DOUBLE` | Field |
| `Estimated_Tax_Event_Count` | `BIGINT` | Field |
| `Estimated_Tax_Missing_Count` | `BIGINT` | Field |
| `Estimated_Tax_Complete` | `BOOLEAN` | Field |
| `Event_Count` | `BIGINT` | Field |
| `Ready_Count` | `BIGINT` | Field |

**Table constraints**

- `Check_Required_Count BIGINT`

### `gold.tax_subhead_reconciliation`

**Contract ID:** `df_p_tax_reconciliation`  
**Grain:** `FY-SubHead`  
**Domain:** `Taxes`  
**Producer:** `TaxEngine`  
**Publication order:** `304`

| Column | Physical type / constraint | Role |
|---|---|---|
| `FY` | `TEXT` | Field |
| `Tax_Sub_Head` | `TEXT` | Field |
| `Ledger_Tax_Event_Amount` | `DOUBLE` | Field |
| `Excluded_Non_Taxable_Amount` | `DOUBLE` | Field |
| `Excluded_Non_Taxable_Event_Count` | `BIGINT` | Field |
| `Excluded_Investment_Ledger_Amount` | `DOUBLE` | Field |
| `Excluded_Investment_Ledger_Event_Count` | `BIGINT` | Field |
| `Quant_Realized_Gain_Loss` | `DOUBLE` | Field |
| `Estimated_Investment_Tax` | `DOUBLE` | Field |
| `Estimated_Tax_Event_Count` | `BIGINT` | Field |
| `Estimated_Tax_Missing_Count` | `BIGINT` | Field |
| `Estimated_Investment_Tax_Complete` | `BOOLEAN` | Field |
| `Estimated_Ledger_Tax` | `DOUBLE` | Field |
| `Ledger_Tax_Estimate_Count` | `BIGINT` | Field |
| `Ledger_Tax_Estimate_Missing_Count` | `BIGINT` | Field |
| `Estimated_Ledger_Tax_Complete` | `BOOLEAN` | Field |
| `Tax_Credit_Amount` | `DOUBLE` | Field |
| `Tax_Event_Amount` | `DOUBLE` | Field |
| `Investment_Source_Difference_INR` | `DOUBLE` | Field |
| `Ledger_Event_Count` | `BIGINT` | Field |
| `Quant_Event_Count` | `BIGINT` | Field |
| `Tax_Credit_Event_Count` | `BIGINT` | Field |

**Table constraints**

- `Check_Required_Count BIGINT`
- `PRIMARY KEY(FY, Tax_Sub_Head)`

### `gold.wealth_asset_breakdown`

**Contract ID:** `df_p_tf_net_worth_monthly_summary`  
**Grain:** `Month-Asset`  
**Domain:** `Wealth`  
**Producer:** `WealthPresentationEngine`  
**Publication order:** `110`

| Column | Physical type / constraint | Role |
|---|---|---|
| `MONTH_START_DATE` | `DATE` | Identifiers |
| `MONTH_END_DATE` | `DATE` | Identifiers |
| `ASSET_SUBCATEGORY_ID` | `TEXT` | Identifiers |
| `Opening_Balance` | `DOUBLE` | Position Values |
| `Closing_Balance` | `DOUBLE` | Position Values |
| `Closing_Balance_Market` | `DOUBLE` | Position Values |
| `All_Time_High_Balance` | `DOUBLE` | Position Values |
| `Liquid_Assets` | `DOUBLE` | Position Values |
| `Liquid_Assets_Market` | `DOUBLE` | Position Values |
| `Closing_Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Closing_Forex_PnL` | `DOUBLE` | Absolute Returns |
| `"MoM_Balance_Growth_%"` | `DOUBLE` | Performance Returns |
| `"YoY_Balance_Growth_%"` | `DOUBLE` | Performance Returns |
| `Organic_Growth_Value` | `DOUBLE` | Performance Returns |
| `"Organic_Yield_%"` | `DOUBLE` | Performance Returns |
| `Drawdown_From_Peak` | `DOUBLE` | Risk & Weights |
| `Investment_Contribution_Pct` | `DOUBLE` | Risk & Weights |
| `Savings_to_NW_Ratio` | `DOUBLE` | Risk & Weights |
| `Income_Inflow` | `DOUBLE` | Cashflow |
| `Cash_Income_Inflow` | `DOUBLE` | Cashflow |
| `Non_Cash_Income_Inflow` | `DOUBLE` | Cashflow |
| `Expense_Outflow` | `DOUBLE` | Cashflow |
| `Core_Expense_Outflow` | `DOUBLE` | Cashflow |
| `Cash_Expense_Outflow` | `DOUBLE` | Cashflow |
| `Non_Cash_Expense_Outflow` | `DOUBLE` | Cashflow |
| `Net_Transfers` | `DOUBLE` | Cashflow |
| `Net_Cashflow_Month` | `DOUBLE` | Cashflow |
| `Surplus_Deficit_Month` | `DOUBLE` | Cashflow |
| `Cumulative_Net_Savings` | `DOUBLE` | Cashflow |
| `"3M_Avg_Expense"` | `DOUBLE` | Trailing Averages |
| `"3M_Avg_Core_Expense"` | `DOUBLE` | Trailing Averages |
| `"3M_Avg_Income"` | `DOUBLE` | Trailing Averages |
| `Months_of_Runway` | `DOUBLE` | Trailing Averages |

### `gold.core_monthly_fact`

**Contract ID:** `df_p_tf_wealth_monthly_totals`  
**Grain:** `Month`  
**Domain:** `Wealth`  
**Producer:** `WealthPresentationEngine`  
**Publication order:** `110`

| Column | Physical type / constraint | Role |
|---|---|---|
| `MONTH_START_DATE` | `DATE` | Identifiers |
| `MONTH_END_DATE` | `DATE` | Identifiers |
| `Months_Elapsed` | `BIGINT` | Descriptors/Classifications |
| `Total_Income` | `DOUBLE` | Position Values |
| `Total_Cash_Income` | `DOUBLE` | Position Values |
| `Total_Non_Cash_Income` | `DOUBLE` | Position Values |
| `Total_Expense` | `DOUBLE` | Position Values |
| `Total_Core_Expense` | `DOUBLE` | Position Values |
| `Total_Cash_Expense` | `DOUBLE` | Position Values |
| `Total_Non_Cash_Expense` | `DOUBLE` | Position Values |
| `Net_Cashflow_Month` | `DOUBLE` | Position Values |
| `Opening_Balance_Asset` | `DOUBLE` | Position Values |
| `Opening_Balance_Asset_Market` | `DOUBLE` | Position Values |
| `Closing_Balance_Asset` | `DOUBLE` | Position Values |
| `Closing_Balance_Asset_Market` | `DOUBLE` | Position Values |
| `Asset_Delta` | `DOUBLE` | Position Values |
| `Asset_Market_Delta` | `DOUBLE` | Position Values |
| `Total_Assets` | `DOUBLE` | Position Values |
| `Total_Assets_Market` | `DOUBLE` | Position Values |
| `Opening_Investment_Book_Value` | `DOUBLE` | Position Values |
| `Closing_Investment_Book_Value` | `DOUBLE` | Position Values |
| `Investment_Book_Value_Delta` | `DOUBLE` | Position Values |
| `Opening_Investment_Market_Value` | `DOUBLE` | Position Values |
| `Closing_Investment_Market_Value` | `DOUBLE` | Position Values |
| `Investment_Market_Value_Delta` | `DOUBLE` | Position Values |
| `Liquid_Assets` | `DOUBLE` | Position Values |
| `Liquid_Assets_Market` | `DOUBLE` | Position Values |
| `Total_Liabilities` | `DOUBLE` | Position Values |
| `Total_Net_Worth` | `DOUBLE` | Position Values |
| `Total_Net_Worth_Market` | `DOUBLE` | Position Values |
| `Total_Foreign_Currency_Exposure` | `DOUBLE` | Local/FX Values |
| `Opening_Unrealized_PL` | `DOUBLE` | Absolute Returns |
| `Closing_Unrealized_PL` | `DOUBLE` | Absolute Returns |
| `Closing_Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Closing_Forex_PnL` | `DOUBLE` | Absolute Returns |
| `Opening_Investment_XIRR` | `DOUBLE` | Performance Returns |
| `Closing_Investment_XIRR` | `DOUBLE` | Performance Returns |
| `Foreign_Exposure_Pct` | `DOUBLE` | Risk & Weights |
| `CPI_INDEX` | `DOUBLE` | Risk & Weights |
| `INFLATION_YOY_PCT` | `DOUBLE` | Risk & Weights |
| `Net_Savings_Flow` | `DOUBLE` | Net-Worth Attribution |
| `Market_Return_Flow` | `DOUBLE` | Net-Worth Attribution |
| `Attribution_Residual` | `DOUBLE` | Net-Worth Attribution |
| `Inflation_Adjusted_Core_Expense` | `DOUBLE` | Real Expense Growth |
| `Real_Core_Expense_Growth_Pct` | `DOUBLE` | Real Expense Growth |

### `gold.cashflow_expense_breakdown`

**Contract ID:** `df_p_tf_category_spend_analytics`  
**Grain:** `Month-ExpenseCategory`  
**Domain:** `Wealth`  
**Producer:** `WealthPresentationEngine`  
**Publication order:** `120`

| Column | Physical type / constraint | Role |
|---|---|---|
| `MONTH_START_DATE` | `DATE` | Identifiers |
| `MONTH_END_DATE` | `DATE` | Identifiers |
| `YEAR_MONTH` | `TEXT` | Identifiers |
| `CATEGORY_ID` | `TEXT` | Identifiers |
| `CATEGORY_NAME` | `TEXT` | Descriptors/Classifications |
| `CATEGORY_GROUPS` | `TEXT` | Descriptors/Classifications |
| `Spend_Type` | `TEXT` | Descriptors/Classifications |
| `Is_Core_Expense` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Investment` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Discretionary` | `BOOLEAN` | Descriptors/Classifications |
| `Total_Monthly_Spend` | `DOUBLE` | Position Values |
| `Cash_Spend` | `DOUBLE` | Position Values |
| `Non_Cash_Spend` | `DOUBLE` | Position Values |
| `Trailing_3M_Avg_Spend` | `DOUBLE` | Position Values |
| `Cumulative_YTD_Spend` | `DOUBLE` | Position Values |

### `gold.cashflow_income_breakdown`

**Contract ID:** `df_p_tf_income_streams_monthly`  
**Grain:** `Month-IncomeCategory`  
**Domain:** `Wealth`  
**Producer:** `WealthPresentationEngine`  
**Publication order:** `130`

| Column | Physical type / constraint | Role |
|---|---|---|
| `MONTH_START_DATE` | `DATE` | Identifiers |
| `MONTH_END_DATE` | `DATE` | Identifiers |
| `YEAR_MONTH` | `TEXT` | Identifiers |
| `CATEGORY_ID` | `TEXT` | Identifiers |
| `CATEGORY_NAME` | `TEXT` | Descriptors/Classifications |
| `CATEGORY_GROUPS` | `TEXT` | Descriptors/Classifications |
| `Is_Active_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Passive_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Dividend_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Interest_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Non_Cash_Income` | `BOOLEAN` | Descriptors/Classifications |
| `Total_Monthly_Income` | `DOUBLE` | Position Values |
| `Trailing_3M_Avg_Income` | `DOUBLE` | Position Values |
| `Cumulative_YTD_Income` | `DOUBLE` | Position Values |

### `gold.wealth_fire_analytics`

**Contract ID:** `df_p_tf_wealth_risk_analytics`  
**Grain:** `Month`  
**Domain:** `Wealth`  
**Producer:** `WealthPresentationEngine`  
**Publication order:** `140`

| Column | Physical type / constraint | Role |
|---|---|---|
| `MONTH_START_DATE` | `DATE` | Identifiers |
| `MONTH_END_DATE` | `DATE` | Identifiers |
| `YEAR_MONTH` | `TEXT` | Identifiers |
| `Projected_FI_Date_P50` | `DATE` | Descriptors/Classifications |
| `Total_Income` | `DOUBLE` | Position Values |
| `Total_Cash_Income` | `DOUBLE` | Position Values |
| `Trailing_6M_Avg_Spend` | `DOUBLE` | Position Values |
| `Trailing_12M_Avg_Spend` | `DOUBLE` | Position Values |
| `Trailing_6M_Avg_Savings` | `DOUBLE` | Position Values |
| `Trailing_12M_Avg_Savings` | `DOUBLE` | Position Values |
| `Target_FI_Today` | `DOUBLE` | Position Values |
| `Coast_FI_Today` | `DOUBLE` | Position Values |
| `Lean_FI_Today` | `DOUBLE` | Position Values |
| `Target_FI_Total_Future_Nominal` | `DOUBLE` | Position Values |
| `FI_Gap` | `DOUBLE` | Position Values |
| `FI_Gap_Monthly_Trend` | `DOUBLE` | Position Values |
| `Terminal_Wealth_Nominal_P50` | `DOUBLE` | Position Values |
| `Real_Return_Assumed_Pct` | `DOUBLE` | Performance Returns |
| `Wealth_Velocity` | `DOUBLE` | Performance Returns |
| `Wealth_Acceleration` | `DOUBLE` | Performance Returns |
| `Real_NW_CAGR_3Y` | `DOUBLE` | Performance Returns |
| `Current_FI_Coverage_Pct` | `DOUBLE` | Risk & Weights |
| `Estimated_Months_To_FI_Linear` | `DOUBLE` | Risk & Weights |
| `Months_To_FI_Conservative_P90` | `DOUBLE` | Risk & Weights |
| `Months_To_FI_Base_P50` | `DOUBLE` | Risk & Weights |
| `Months_To_FI_Aggressive_P10` | `DOUBLE` | Risk & Weights |
| `Probability_Of_Success_Pct` | `DOUBLE` | Risk & Weights |
| `Years_To_FI_P50` | `DOUBLE` | Risk & Weights |
| `Runway_Months_Linear` | `DOUBLE` | Risk & Weights |
| `Runway_Months_Stressed_P10` | `DOUBLE` | Risk & Weights |
| `Runway_Months_Base_P50` | `DOUBLE` | Risk & Weights |
| `Withdrawal_Rate_If_Retired_Now` | `DOUBLE` | Risk & Weights |
| `Savings_Rate_Required` | `DOUBLE` | Risk & Weights |
| `Savings_Rate_Actual` | `DOUBLE` | Risk & Weights |
| `FI_Velocity` | `DOUBLE` | Risk & Weights |

### `gold.forecast_budget_variance`

**Contract ID:** `df_p_tf_budget_forecast_monthly`  
**Grain:** `Month`  
**Domain:** `Wealth`  
**Producer:** `WealthPresentationEngine`  
**Publication order:** `160`

| Column | Physical type / constraint | Role |
|---|---|---|
| `MONTH_START_DATE` | `DATE` | Identifiers |
| `MONTH_END_DATE` | `DATE` | Identifiers |
| `YEAR_MONTH` | `TEXT` | Identifiers |
| `Is_Core_Overspent` | `BOOLEAN` | Descriptors/Classifications |
| `Is_NonCore_Overspent` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Investment_Underfunded` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Income_Volatile` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Budget_Month_Healthy` | `BOOLEAN` | Descriptors/Classifications |
| `Total_Income` | `DOUBLE` | Position Values |
| `Actual_Income` | `DOUBLE` | Position Values |
| `Budget_Income` | `DOUBLE` | Position Values |
| `Budget_Core_Expense_Target` | `DOUBLE` | Position Values |
| `Budget_NonCore_Expense_Target` | `DOUBLE` | Position Values |
| `Budget_Investment_Target` | `DOUBLE` | Position Values |
| `Budget_Surplus_Buffer` | `DOUBLE` | Position Values |
| `Budget_Total_Expense_Target` | `DOUBLE` | Position Values |
| `Actual_Core_Expense` | `DOUBLE` | Position Values |
| `Actual_NonCore_Expense` | `DOUBLE` | Position Values |
| `Investment_Deployed` | `DOUBLE` | Position Values |
| `Investment_Redeemed` | `DOUBLE` | Position Values |
| `Actual_Investment` | `DOUBLE` | Position Values |
| `Actual_Savings` | `DOUBLE` | Position Values |
| `Emergency_Fund_Gap` | `DOUBLE` | Position Values |
| `Rule_Core_Pct_Budget` | `DOUBLE` | Risk & Weights |
| `Rule_NonCore_Pct_Budget` | `DOUBLE` | Risk & Weights |
| `Rule_Investment_Pct_Budget` | `DOUBLE` | Risk & Weights |
| `Zero_Income_Runway_Months` | `DOUBLE` | Risk & Weights |

### `gold.investment_portfolio_summary`

**Contract ID:** `df_p_tf_investment_analytics`  
**Grain:** `Month-ISIN`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `170`

| Column | Physical type / constraint | Role |
|---|---|---|
| `MONTH_START_DATE` | `DATE` | Identifiers |
| `Max_Closing_Date` | `DATE` | Identifiers |
| `ISIN` | `TEXT` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `INSTRUMENT_NAME` | `TEXT` | Descriptors/Classifications |
| `INSTRUMENT_CLASS` | `TEXT` | Descriptors/Classifications |
| `INSTRUMENT_TYPE` | `TEXT` | Descriptors/Classifications |
| `INSTRUMENT_SUBTYPE` | `TEXT` | Descriptors/Classifications |
| `SECTOR` | `TEXT` | Descriptors/Classifications |
| `Rebalance_Required` | `BOOLEAN` | Descriptors/Classifications |
| `ISIN_Market_Value` | `DOUBLE` | Position Values |
| `ISIN_Book_Value` | `DOUBLE` | Position Values |
| `ISIN_Market_Value_Local` | `DOUBLE` | Local/FX Values |
| `ISIN_Book_Value_Local` | `DOUBLE` | Local/FX Values |
| `ISIN_Unrealized_PnL` | `DOUBLE` | Absolute Returns |
| `ISIN_Asset_PnL` | `DOUBLE` | Absolute Returns |
| `ISIN_Forex_PnL` | `DOUBLE` | Absolute Returns |
| `ISIN_Forex_Contribution_Pct` | `DOUBLE` | Absolute Returns |
| `ISIN_XIRR_Local` | `DOUBLE` | Performance Returns |
| `ISIN_FX_XIRR_Impact` | `DOUBLE` | Performance Returns |
| `ISIN_BM_XIRR` | `DOUBLE` | Benchmark Comparisons |
| `ISIN_BM_XIRR_Local` | `DOUBLE` | Benchmark Comparisons |
| `ISIN_Active_Return` | `DOUBLE` | Benchmark Comparisons |
| `ISIN_Active_Return_Local` | `DOUBLE` | Benchmark Comparisons |
| `ISIN_Weight` | `DOUBLE` | Risk & Weights |
| `Class_Weight` | `DOUBLE` | Risk & Weights |
| `Class_Target_Weight` | `DOUBLE` | Risk & Weights |
| `Class_Drift` | `DOUBLE` | Risk & Weights |
| `Sector_Weight` | `DOUBLE` | Risk & Weights |
| `Monthly_Market_Value_Change_Pct` | `DOUBLE` | Risk & Weights |
| `ISIN_Harvestable_Loss` | `DOUBLE` | Tax & Harvesting |
| `Tax_Harvesting_Priority_Score` | `DOUBLE` | Tax & Harvesting |
| `Top1_Holding_Weight` | `DOUBLE` | Portfolio Concentration |
| `Top5_Holdings_Weight` | `DOUBLE` | Portfolio Concentration |
| `Top10_Holdings_Weight` | `DOUBLE` | Portfolio Concentration |
| `HHI_Score` | `DOUBLE` | Portfolio Concentration |
| `Effective_Holdings_Count` | `DOUBLE` | Portfolio Concentration |
| `LTCG_Maturing_30D` | `DOUBLE` | LTCG Maturity Ladder |
| `LTCG_Maturing_90D` | `DOUBLE` | LTCG Maturity Ladder |
| `LTCG_Maturing_180D` | `DOUBLE` | LTCG Maturity Ladder |
| `LTCG_Maturing_365D` | `DOUBLE` | LTCG Maturity Ladder |
| `LTCG_Mature_Value` | `DOUBLE` | LTCG Maturity Ladder |

### `gold.cashflow_efficiency_analytics`

**Contract ID:** `df_p_tf_monthly_cashflow_summary`  
**Grain:** `Month`  
**Domain:** `Wealth`  
**Producer:** `WealthPresentationEngine`  
**Publication order:** `180`

| Column | Physical type / constraint | Role |
|---|---|---|
| `MONTH_START_DATE` | `DATE` | Identifiers |
| `MONTH_END_DATE` | `DATE` | Identifiers |
| `YEAR_MONTH` | `TEXT` | Identifiers |
| `Is_Surplus_Month` | `BOOLEAN` | Descriptors/Classifications |
| `Is_Investment_Target_Met` | `BOOLEAN` | Descriptors/Classifications |
| `Total_Income` | `DOUBLE` | Position Values |
| `Total_Cash_Income` | `DOUBLE` | Position Values |
| `Total_Non_Cash_Income` | `DOUBLE` | Position Values |
| `Total_Expense` | `DOUBLE` | Position Values |
| `Active_Income` | `DOUBLE` | Position Values |
| `Passive_Income` | `DOUBLE` | Position Values |
| `Dividend_Income` | `DOUBLE` | Position Values |
| `Interest_Income` | `DOUBLE` | Position Values |
| `Core_Expense` | `DOUBLE` | Position Values |
| `NonCore_Expense` | `DOUBLE` | Position Values |
| `Total_Cash_Expense` | `DOUBLE` | Position Values |
| `Total_Non_Cash_Expense` | `DOUBLE` | Position Values |
| `Total_Investment_Deployed` | `DOUBLE` | Position Values |
| `Total_Investment_Redeemed` | `DOUBLE` | Position Values |
| `Redemption_Gain_Loss_Value` | `DOUBLE` | Position Values |
| `Net_Investment_Flow` | `DOUBLE` | Position Values |
| `Gross_Surplus` | `DOUBLE` | Position Values |
| `Net_Surplus_After_Invest` | `DOUBLE` | Position Values |
| `Income_MoM_Delta` | `DOUBLE` | Position Values |
| `Expense_MoM_Delta` | `DOUBLE` | Position Values |
| `Investment_MoM_Delta` | `DOUBLE` | Position Values |
| `Trailing_3M_Avg_Income` | `DOUBLE` | Position Values |
| `Trailing_3M_Avg_Expense` | `DOUBLE` | Position Values |
| `Trailing_3M_Avg_Investment` | `DOUBLE` | Position Values |
| `Savings_Rate_Pct` | `DOUBLE` | Risk & Weights |
| `Investment_Rate_Pct` | `DOUBLE` | Risk & Weights |
| `Active_Income_Share_Pct` | `DOUBLE` | Risk & Weights |
| `Passive_Income_Share_Pct` | `DOUBLE` | Risk & Weights |
| `Core_Expense_Share_Pct` | `DOUBLE` | Risk & Weights |
| `NonCore_Expense_Share_Pct` | `DOUBLE` | Risk & Weights |
| `Income_MoM_Pct` | `DOUBLE` | Risk & Weights |
| `Expense_MoM_Pct` | `DOUBLE` | Risk & Weights |
| `Trailing_3M_Avg_Savings_Rate` | `DOUBLE` | Risk & Weights |
| `Trailing_3M_Avg_Investment_Rate` | `DOUBLE` | Risk & Weights |
| `Liquidity_Ratio_Months` | `DOUBLE` | Risk & Weights |
| `Debt_to_Asset_Ratio_Pct` | `DOUBLE` | Risk & Weights |
| `YoY_Net_Worth_Growth_Pct` | `DOUBLE` | Risk & Weights |
| `YoY_Net_Worth_Growth_Pct_Real` | `DOUBLE` | Risk & Weights |
| `Expense_to_NW_Ratio` | `DOUBLE` | Risk & Weights |
| `Emergency_Fund_Coverage` | `DOUBLE` | Risk & Weights |
| `Passive_Income_Core_Expense_Coverage_Ratio` | `DOUBLE` | Income Resilience |
| `Active_Income_Dependency_Pct` | `DOUBLE` | Income Resilience |

### `gold.investment_by_isin`

**Contract ID:** `df_f_investment_analytics_isin`  
**Grain:** `Date-ISIN`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `200`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Closing_Date` | `DATE NOT NULL` | Identifiers |
| `ISIN` | `TEXT NOT NULL` | Identifiers |
| `CURRENCY_ID` | `TEXT` | Identifiers |
| `Total_Invested_Value` | `DOUBLE` | Position Values |
| `Total_Current_Value` | `DOUBLE` | Position Values |
| `Total_Quantity` | `DOUBLE` | Position Values |
| `Total_Stocks` | `DOUBLE` | Position Values |
| `Total_Invested_Value_Local` | `DOUBLE` | Local/FX Values |
| `Total_Current_Value_Local` | `DOUBLE` | Local/FX Values |
| `Current_FX_Rate` | `DOUBLE` | Local/FX Values |
| `Blended_FX_Buy_Rate` | `DOUBLE` | Local/FX Values |
| `Currency_Appreciation_Pct` | `DOUBLE` | Local/FX Values |
| `Unrealized_PL` | `DOUBLE` | Absolute Returns |
| `Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_Contribution_Pct` | `DOUBLE` | Absolute Returns |
| `Absolute_Return` | `DOUBLE` | Absolute Returns |
| `CAGR` | `DOUBLE` | Performance Returns |
| `XIRR` | `DOUBLE` | Performance Returns |
| `XIRR_Local` | `DOUBLE` | Performance Returns |
| `FX_XIRR_Impact` | `DOUBLE` | Performance Returns |
| `After_Tax_XIRR` | `DOUBLE` | Performance Returns |
| `BM_CAGR` | `DOUBLE` | Benchmark Comparisons |
| `BM_XIRR` | `DOUBLE` | Benchmark Comparisons |
| `BM_XIRR_Local` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return_Local` | `DOUBLE` | Benchmark Comparisons |
| `Is_Lagging_Benchmark` | `BIGINT` | Benchmark Comparisons |
| `Outperforming_Lot_Ratio` | `DOUBLE` | Benchmark Comparisons |
| `Max_Drawdown` | `DOUBLE` | Risk & Weights |
| `Weight` | `DOUBLE` | Risk & Weights |
| `Unrealized_LTCG` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_STCG` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Gain` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_LTCL` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_STCL` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Loss` | `DOUBLE` | Tax & Harvesting |
| `LTCG_Tax_If_Sold` | `DOUBLE` | Tax & Harvesting |
| `STCG_Tax_If_Sold` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_LTCG` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_STCG` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Gain` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_LTCL` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_STCL` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Net_PnL` | `DOUBLE` | Tax & Harvesting |

### `gold.investment_by_subtype`

**Contract ID:** `df_f_investment_analytics_subtype`  
**Grain:** `Date-Subtype`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `210`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Closing_Date` | `DATE NOT NULL` | Identifiers |
| `INSTRUMENT_SUBTYPE` | `TEXT NOT NULL` | Identifiers |
| `INSTRUMENT_CLASS` | `TEXT NOT NULL` | Descriptors/Classifications |
| `Total_Invested_Value` | `DOUBLE` | Position Values |
| `Total_Current_Value` | `DOUBLE` | Position Values |
| `Total_Quantity` | `DOUBLE` | Position Values |
| `Total_Stocks` | `DOUBLE` | Position Values |
| `Unrealized_PL` | `DOUBLE` | Absolute Returns |
| `Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_Contribution_Pct` | `DOUBLE` | Absolute Returns |
| `Absolute_Return` | `DOUBLE` | Absolute Returns |
| `XIRR` | `DOUBLE` | Performance Returns |
| `After_Tax_XIRR` | `DOUBLE` | Performance Returns |
| `BM_XIRR` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return` | `DOUBLE` | Benchmark Comparisons |
| `Max_Drawdown` | `DOUBLE` | Risk & Weights |
| `Weight` | `DOUBLE` | Risk & Weights |
| `Unrealized_Gain` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Gain` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Net_PnL` | `DOUBLE` | Tax & Harvesting |

### `gold.investment_by_class`

**Contract ID:** `df_f_investment_analytics_class`  
**Grain:** `Date-Class`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `220`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Closing_Date` | `DATE NOT NULL` | Identifiers |
| `INSTRUMENT_CLASS` | `TEXT NOT NULL` | Identifiers |
| `Total_Invested_Value` | `DOUBLE` | Position Values |
| `Total_Current_Value` | `DOUBLE` | Position Values |
| `Total_Quantity` | `DOUBLE` | Position Values |
| `Total_Stocks` | `DOUBLE` | Position Values |
| `Unrealized_PL` | `DOUBLE` | Absolute Returns |
| `Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_Contribution_Pct` | `DOUBLE` | Absolute Returns |
| `Absolute_Return` | `DOUBLE` | Absolute Returns |
| `XIRR` | `DOUBLE` | Performance Returns |
| `After_Tax_XIRR` | `DOUBLE` | Performance Returns |
| `BM_XIRR` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return` | `DOUBLE` | Benchmark Comparisons |
| `Max_Drawdown` | `DOUBLE` | Risk & Weights |
| `Weight` | `DOUBLE` | Risk & Weights |
| `Unrealized_Gain` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Gain` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Net_PnL` | `DOUBLE` | Tax & Harvesting |

### `gold.investment_by_instrument_type`

**Contract ID:** `df_f_investment_analytics_instrument_type`  
**Grain:** `Date-InstrumentType`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `230`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Closing_Date` | `DATE NOT NULL` | Identifiers |
| `INSTRUMENT_TYPE` | `TEXT NOT NULL` | Identifiers |
| `Total_Invested_Value` | `DOUBLE` | Position Values |
| `Total_Current_Value` | `DOUBLE` | Position Values |
| `Total_Quantity` | `DOUBLE` | Position Values |
| `Total_Stocks` | `DOUBLE` | Position Values |
| `Unrealized_PL` | `DOUBLE` | Absolute Returns |
| `Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_Contribution_Pct` | `DOUBLE` | Absolute Returns |
| `Absolute_Return` | `DOUBLE` | Absolute Returns |
| `XIRR` | `DOUBLE` | Performance Returns |
| `After_Tax_XIRR` | `DOUBLE` | Performance Returns |
| `BM_XIRR` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return` | `DOUBLE` | Benchmark Comparisons |
| `Max_Drawdown` | `DOUBLE` | Risk & Weights |
| `Weight` | `DOUBLE` | Risk & Weights |
| `Unrealized_Gain` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Gain` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Net_PnL` | `DOUBLE` | Tax & Harvesting |

### `gold.investment_by_sector`

**Contract ID:** `df_f_investment_analytics_sector`  
**Grain:** `Date-Sector`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `240`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Closing_Date` | `DATE NOT NULL` | Identifiers |
| `SECTOR` | `TEXT NOT NULL` | Identifiers |
| `Total_Invested_Value` | `DOUBLE` | Position Values |
| `Total_Current_Value` | `DOUBLE` | Position Values |
| `Total_Quantity` | `DOUBLE` | Position Values |
| `Total_Stocks` | `DOUBLE` | Position Values |
| `Unrealized_PL` | `DOUBLE` | Absolute Returns |
| `Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_Contribution_Pct` | `DOUBLE` | Absolute Returns |
| `Absolute_Return` | `DOUBLE` | Absolute Returns |
| `XIRR` | `DOUBLE` | Performance Returns |
| `After_Tax_XIRR` | `DOUBLE` | Performance Returns |
| `BM_XIRR` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return` | `DOUBLE` | Benchmark Comparisons |
| `Max_Drawdown` | `DOUBLE` | Risk & Weights |
| `Weight` | `DOUBLE` | Risk & Weights |
| `Unrealized_Gain` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Gain` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Net_PnL` | `DOUBLE` | Tax & Harvesting |

### `gold.investment_by_industry`

**Contract ID:** `df_f_investment_analytics_industry`  
**Grain:** `Date-Industry`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `250`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Closing_Date` | `DATE NOT NULL` | Identifiers |
| `INDUSTRY` | `TEXT NOT NULL` | Identifiers |
| `Total_Invested_Value` | `DOUBLE` | Position Values |
| `Total_Current_Value` | `DOUBLE` | Position Values |
| `Total_Quantity` | `DOUBLE` | Position Values |
| `Total_Stocks` | `DOUBLE` | Position Values |
| `Unrealized_PL` | `DOUBLE` | Absolute Returns |
| `Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_Contribution_Pct` | `DOUBLE` | Absolute Returns |
| `Absolute_Return` | `DOUBLE` | Absolute Returns |
| `XIRR` | `DOUBLE` | Performance Returns |
| `After_Tax_XIRR` | `DOUBLE` | Performance Returns |
| `BM_XIRR` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return` | `DOUBLE` | Benchmark Comparisons |
| `Max_Drawdown` | `DOUBLE` | Risk & Weights |
| `Weight` | `DOUBLE` | Risk & Weights |
| `Unrealized_Gain` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Gain` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Net_PnL` | `DOUBLE` | Tax & Harvesting |

### `gold.investment_by_portfolio`

**Contract ID:** `df_f_investment_analytics_portfolio`  
**Grain:** `Date`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `260`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Closing_Date` | `DATE NOT NULL` | Identifiers |
| `Total_Invested_Value` | `DOUBLE` | Position Values |
| `Total_Current_Value` | `DOUBLE` | Position Values |
| `Total_Quantity` | `DOUBLE` | Position Values |
| `Total_Stocks` | `DOUBLE` | Position Values |
| `Unrealized_PL` | `DOUBLE` | Absolute Returns |
| `Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_Contribution_Pct` | `DOUBLE` | Absolute Returns |
| `Absolute_Return` | `DOUBLE` | Absolute Returns |
| `XIRR` | `DOUBLE` | Performance Returns |
| `After_Tax_XIRR` | `DOUBLE` | Performance Returns |
| `BM_XIRR` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return` | `DOUBLE` | Benchmark Comparisons |
| `Max_Drawdown` | `DOUBLE` | Risk & Weights |
| `Weight` | `DOUBLE` | Risk & Weights |
| `Unrealized_Gain` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Gain` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Net_PnL` | `DOUBLE` | Tax & Harvesting |

### `gold.investment_by_geo`

**Contract ID:** `df_f_investment_analytics_geo`  
**Grain:** `Date-Geo`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `270`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Closing_Date` | `DATE NOT NULL` | Identifiers |
| `GEO` | `TEXT NOT NULL` | Identifiers |
| `Total_Invested_Value` | `DOUBLE` | Position Values |
| `Total_Current_Value` | `DOUBLE` | Position Values |
| `Total_Quantity` | `DOUBLE` | Position Values |
| `Total_Stocks` | `DOUBLE` | Position Values |
| `Unrealized_PL` | `DOUBLE` | Absolute Returns |
| `Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_Contribution_Pct` | `DOUBLE` | Absolute Returns |
| `Absolute_Return` | `DOUBLE` | Absolute Returns |
| `XIRR` | `DOUBLE` | Performance Returns |
| `After_Tax_XIRR` | `DOUBLE` | Performance Returns |
| `BM_XIRR` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return` | `DOUBLE` | Benchmark Comparisons |
| `Max_Drawdown` | `DOUBLE` | Risk & Weights |
| `Weight` | `DOUBLE` | Risk & Weights |
| `Unrealized_Gain` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Gain` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Net_PnL` | `DOUBLE` | Tax & Harvesting |

### `gold.investment_by_country`

**Contract ID:** `df_f_investment_analytics_country`  
**Grain:** `Date-Country`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `280`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Closing_Date` | `DATE NOT NULL` | Identifiers |
| `COUNTRY` | `TEXT NOT NULL` | Identifiers |
| `Total_Invested_Value` | `DOUBLE` | Position Values |
| `Total_Current_Value` | `DOUBLE` | Position Values |
| `Total_Quantity` | `DOUBLE` | Position Values |
| `Total_Stocks` | `DOUBLE` | Position Values |
| `Total_Invested_Value_Local` | `DOUBLE` | Local/FX Values |
| `Total_Current_Value_Local` | `DOUBLE` | Local/FX Values |
| `Current_FX_Rate` | `DOUBLE` | Local/FX Values |
| `Blended_FX_Buy_Rate` | `DOUBLE` | Local/FX Values |
| `Currency_Appreciation_Pct` | `DOUBLE` | Local/FX Values |
| `Unrealized_PL` | `DOUBLE` | Absolute Returns |
| `Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_Contribution_Pct` | `DOUBLE` | Absolute Returns |
| `Absolute_Return` | `DOUBLE` | Absolute Returns |
| `XIRR` | `DOUBLE` | Performance Returns |
| `After_Tax_XIRR` | `DOUBLE` | Performance Returns |
| `BM_XIRR` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return` | `DOUBLE` | Benchmark Comparisons |
| `XIRR_Local` | `DOUBLE` | Benchmark Comparisons |
| `BM_XIRR_Local` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return_Local` | `DOUBLE` | Benchmark Comparisons |
| `FX_XIRR_Impact` | `DOUBLE` | Benchmark Comparisons |
| `Max_Drawdown` | `DOUBLE` | Risk & Weights |
| `Weight` | `DOUBLE` | Risk & Weights |
| `Unrealized_Gain` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Gain` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Net_PnL` | `DOUBLE` | Tax & Harvesting |

### `gold.investment_by_currency`

**Contract ID:** `df_f_investment_analytics_currency`  
**Grain:** `Date-Currency`  
**Domain:** `Investments`  
**Producer:** `InvestmentQuantEngine`  
**Publication order:** `290`

| Column | Physical type / constraint | Role |
|---|---|---|
| `Closing_Date` | `DATE NOT NULL` | Identifiers |
| `CURRENCY_ID` | `TEXT NOT NULL` | Identifiers |
| `Total_Invested_Value` | `DOUBLE` | Position Values |
| `Total_Current_Value` | `DOUBLE` | Position Values |
| `Total_Quantity` | `DOUBLE` | Position Values |
| `Total_Stocks` | `DOUBLE` | Position Values |
| `Total_Invested_Value_Local` | `DOUBLE` | Local/FX Values |
| `Total_Current_Value_Local` | `DOUBLE` | Local/FX Values |
| `Current_FX_Rate` | `DOUBLE` | Local/FX Values |
| `Blended_FX_Buy_Rate` | `DOUBLE` | Local/FX Values |
| `Currency_Appreciation_Pct` | `DOUBLE` | Local/FX Values |
| `Unrealized_PL` | `DOUBLE` | Absolute Returns |
| `Asset_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_PnL` | `DOUBLE` | Absolute Returns |
| `Forex_Contribution_Pct` | `DOUBLE` | Absolute Returns |
| `Absolute_Return` | `DOUBLE` | Absolute Returns |
| `XIRR` | `DOUBLE` | Performance Returns |
| `XIRR_Local` | `DOUBLE` | Performance Returns |
| `FX_XIRR_Impact` | `DOUBLE` | Performance Returns |
| `After_Tax_XIRR` | `DOUBLE` | Performance Returns |
| `BM_XIRR` | `DOUBLE` | Benchmark Comparisons |
| `BM_XIRR_Local` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return` | `DOUBLE` | Benchmark Comparisons |
| `Active_Return_Local` | `DOUBLE` | Benchmark Comparisons |
| `Max_Drawdown` | `DOUBLE` | Risk & Weights |
| `Weight` | `DOUBLE` | Risk & Weights |
| `Unrealized_Gain` | `DOUBLE` | Tax & Harvesting |
| `Unrealized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Gain` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Loss` | `DOUBLE` | Tax & Harvesting |
| `FY_Realized_Net_PnL` | `DOUBLE` | Tax & Harvesting |

### `gold.cashflow_activity_summary`

**Contract ID:** `df_p_tf_cashflow_activity_summary`  
**Grain:** `Month`  
**Domain:** `Wealth`  
**Producer:** `WealthPresentationEngine`  
**Publication order:** `190`

| Column | Physical type / constraint | Role |
|---|---|---|
| `MONTH_START_DATE` | `DATE` | Identifiers |
| `MONTH_END_DATE` | `DATE` | Identifiers |
| `YEAR_MONTH` | `TEXT` | Identifiers |
| `Opening_Cash_Balance` | `DOUBLE` | Position Values |
| `Closing_Cash_Balance` | `DOUBLE` | Position Values |
| `Net_Cash_Movement` | `DOUBLE` | Position Values |
| `Cash_Inflow_Operating` | `DOUBLE` | Position Values |
| `Cash_Outflow_Operating` | `DOUBLE` | Position Values |
| `Net_Cashflow_Operating` | `DOUBLE` | Position Values |
| `Cash_Inflow_Investing` | `DOUBLE` | Position Values |
| `Cash_Outflow_Investing` | `DOUBLE` | Position Values |
| `Net_Cashflow_Investing` | `DOUBLE` | Position Values |
| `Cash_Inflow_Financing` | `DOUBLE` | Position Values |
| `Cash_Outflow_Financing` | `DOUBLE` | Position Values |
| `Net_Cashflow_Financing` | `DOUBLE` | Position Values |
| `Internal_Transfer_Inflow` | `DOUBLE` | Position Values |
| `Internal_Transfer_Outflow` | `DOUBLE` | Position Values |
| `Net_Internal_Transfers` | `DOUBLE` | Position Values |
| `Total_Cash_Expenses` | `DOUBLE` | Position Values |
| `Total_Non_Cash_Expenses` | `DOUBLE` | Position Values |
| `Total_Cash_Inflow` | `DOUBLE` | Position Values |
| `Total_Cash_Outflow` | `DOUBLE` | Position Values |
| `Calculated_Net_Cashflow` | `DOUBLE` | Position Values |
| `Unreconciled_Difference` | `DOUBLE` | Position Values |


## Analytical semantics

Gold measures are not uniformly additive.

- cash amounts may be additive at their declared grain;
- balances are usually semi-additive across time;
- ratios, CAGR, XIRR, drawdown, and percentages are non-additive;
- validity/null fields remain part of the metric contract.

A BI tool can sum a column. That does not mean finance asked it to.

## Ownership boundary

Gold builders can aggregate, reshape, and publish. They should not invent new Tax classification, FIFO logic, FX economics, or FIRE model semantics. If new financial meaning is required, it belongs upstream in the owning domain first.

## Related specifications

- [Metrics & Methodology](../finance/metrics-and-methodology.md)
- [Adding Gold Marts](../developer/adding-gold-marts.md)
- [Warehouse Architecture](../architecture/warehouse-architecture.md)
