# Gold Warehouse Dependency & Column Disposition Manifest

> **Authority:** PFETL v11 Shan-First Architecture — Phase 008 Governance Artifact  
> **Scope:** Authoritative classification and consumer mapping across all 22 Gold tables (577 columns)  
> **Release Target:** v11.2.0  
> **Operational Constraint:** Strictly Non-Destructive — schema alterations execute in Phase 009 (Household/Tax) and Phase 010 (Investments)  

---

## 1. Executive Summary & Disposition Statistics

The Gold presentation layer serves as the dimensional analytical boundary for Shan's decision making and Power BI reporting.
In accordance with v11 program principles, Gold topology is preserved 1:1, column renames align with canonical vocabulary, and pre-cutover numerical snapshots protect financial invariance.
This manifest freezes the disposition of every single physical column definition in DuckDB Gold schema.

| Metric | Count | Governance Policy |
| :--- | :---: | :--- |
| **Total Gold Tables** | **22** | Proven 22-table topology preserved 1:1 (No merge / split) |
| **Total Gold Columns** | **577** | 100% cataloged and assigned explicit migration targets |
| 🛡️ `PROTECTED` Columns | **212** | Business keys, financial identities & formula inputs; strict equality required |
| 🏷️ `RENAME` Columns | **365** | Canonical naming alignment (`pnl`, `fx`, `financial_year`, lowercase snake_case) |
| 📦 `KEEP` Columns | **0** | Active dimensions and metrics already conforming to canonical vocabulary |
| 🗑️ `REMOVE_CANDIDATE` Columns | **0** | Candidate dead columns with zero downstream consumers proven by archaeology |
| 📦 **Phase 009 Cutover Scope** | **11 Tables** | Household, Wealth, FIRE & Tax presentation marts (283 columns) |
| 📦 **Phase 010 Cutover Scope** | **11 Tables** | Investment Portfolio & 10 breakdown presentation marts (294 columns) |

---

## 2. Frozen 22-Table Topology & Renaming Matrix

All 22 Gold tables transition to canonical lowercase snake_case nomenclature (`gold.*`):

| # | Current Physical Table | Target Physical Table | Domain | Cutover Sprint | Grain | Producer Engine | Columns |
| :---: | :--- | :--- | :--- | :---: | :--- | :--- | :---: |
| 1 | `gold.Tax_Year_Summary` | `gold.tax_financial_year_summary` | Taxes | Phase 009 | FY | TaxEngine | 15 |
| 2 | `gold.Tax_Income_Breakdown` | `gold.tax_income_breakdown` | Taxes | Phase 009 | FY-Head-SubHead-Source | TaxEngine | 12 |
| 3 | `gold.Tax_Reconciliation` | `gold.tax_reconciliation` | Taxes | Phase 009 | FY-SubHead | TaxEngine | 23 |
| 4 | `gold.Wealth_Asset_Breakdown` | `gold.wealth_asset_breakdown` | Wealth | Phase 009 | Month-Asset | WealthPresentationEngine | 33 |
| 5 | `gold.Core_Monthly_Fact` | `gold.core_monthly_fact` | Wealth | Phase 009 | Month | WealthPresentationEngine | 40 |
| 6 | `gold.Cashflow_Expense_Breakdown` | `gold.cashflow_expense_breakdown` | Wealth | Phase 009 | Month-ExpenseCategory | WealthPresentationEngine | 15 |
| 7 | `gold.Cashflow_Income_Breakdown` | `gold.cashflow_income_breakdown` | Wealth | Phase 009 | Month-IncomeCategory | WealthPresentationEngine | 14 |
| 8 | `gold.Wealth_FIRE_Analytics` | `gold.wealth_fire_analytics` | Wealth | Phase 009 | Month | WealthPresentationEngine | 35 |
| 9 | `gold.Forecast_Budget_Variance` | `gold.forecast_budget_variance` | Wealth | Phase 009 | Month | WealthPresentationEngine | 27 |
| 10 | `gold.Investment_Portfolio_Summary` | `gold.investment_portfolio_summary` | Investments | Phase 010 | Month-ISIN | InvestmentQuantEngine | 32 |
| 11 | `gold.Cashflow_Efficiency_Analytics` | `gold.cashflow_efficiency_analytics` | Wealth | Phase 009 | Month | WealthPresentationEngine | 45 |
| 12 | `gold.Investment_By_ISIN` | `gold.investment_by_isin` | Investments | Phase 010 | Date-ISIN | InvestmentQuantEngine | 46 |
| 13 | `gold.Investment_By_Subtype` | `gold.investment_by_subtype` | Investments | Phase 010 | Date-Subtype | InvestmentQuantEngine | 23 |
| 14 | `gold.Investment_By_Class` | `gold.investment_by_class` | Investments | Phase 010 | Date-Class | InvestmentQuantEngine | 22 |
| 15 | `gold.Investment_By_Instrument_Type` | `gold.investment_by_instrument_type` | Investments | Phase 010 | Date-InstrumentType | InvestmentQuantEngine | 22 |
| 16 | `gold.Investment_By_Sector` | `gold.investment_by_sector` | Investments | Phase 010 | Date-Sector | InvestmentQuantEngine | 22 |
| 17 | `gold.Investment_By_Industry` | `gold.investment_by_industry` | Investments | Phase 010 | Date-Industry | InvestmentQuantEngine | 22 |
| 18 | `gold.Investment_By_Portfolio` | `gold.investment_by_portfolio` | Investments | Phase 010 | Date | InvestmentQuantEngine | 21 |
| 19 | `gold.Investment_By_Geo` | `gold.investment_by_geo` | Investments | Phase 010 | Date-Geo | InvestmentQuantEngine | 22 |
| 20 | `gold.Investment_By_Country` | `gold.investment_by_country` | Investments | Phase 010 | Date-Country | InvestmentQuantEngine | 31 |
| 21 | `gold.Investment_By_Currency` | `gold.investment_by_currency` | Investments | Phase 010 | Date-Currency | InvestmentQuantEngine | 31 |
| 22 | `gold.Cashflow_Activity_Summary` | `gold.cashflow_activity_summary` | Wealth | Phase 009 | Month | WealthPresentationEngine | 24 |

---

## 3. Canonical Vocabulary & Syntax Sanitization Rules

1. **Syntax Fix & Identifier Quoting:** Eliminate SQL quotes, percentages, and special characters (`"MoM_Balance_Growth_%"` -> `mom_balance_growth_pct`, `"3M_Avg_Expense"` -> `trailing_3m_avg_expense`).
2. **Canonical Financial Year:** Standardize `FY` to `financial_year` across all summary and breakdown tables.
3. **Canonical FX & PnL:** Eliminate `Forex_` and mixed `P/L` naming; standardize on `fx_pnl`, `asset_pnl`, `pnl`.
4. **Benchmark Prefix:** Normalize `BM_` prefix to `benchmark_` for clarity in reporting.
5. **Base vs Local Clarity:** Retain explicit `_local` suffixes for local currency metrics vs INR base metrics.

---

## 4. Phase 009 Household, Wealth, FIRE & Tax Dispositions (11 Tables)

### `gold.Tax_Year_Summary` -> `gold.tax_financial_year_summary`
**Domain:** Taxes | **Grain:** FY | **Producer:** TaxEngine | **Columns:** 15

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `FY` | TEXT PRIMARY KEY | `financial_year` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `financial_year`). |
| `Total_Ledger_Income` | DOUBLE | `total_ledger_income` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_ledger_income`). |
| `Total_Investment_Gain_Loss` | DOUBLE | `total_investment_gain_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_investment_gain_loss`). |
| `Total_Tax_Credits` | DOUBLE | `total_tax_credits` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_tax_credits`). |
| `Total_Estimated_Investment_Tax` | DOUBLE | `total_estimated_investment_tax` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_estimated_investment_tax`). |
| `Investment_Tax_Estimate_Count` | BIGINT | `investment_tax_estimate_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `investment_tax_estimate_count`). |
| `Investment_Tax_Estimate_Missing_Count` | BIGINT | `investment_tax_estimate_missing_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `investment_tax_estimate_missing_count`). |
| `Investment_Tax_Estimate_Complete` | BOOLEAN | `investment_tax_estimate_complete` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `investment_tax_estimate_complete`). |
| `Total_Estimated_Ledger_Tax` | DOUBLE | `total_estimated_ledger_tax` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_estimated_ledger_tax`). |
| `Ledger_Tax_Estimate_Count` | BIGINT | `ledger_tax_estimate_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `ledger_tax_estimate_count`). |
| `Ledger_Tax_Estimate_Missing_Count` | BIGINT | `ledger_tax_estimate_missing_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `ledger_tax_estimate_missing_count`). |
| `Ledger_Tax_Estimate_Complete` | BOOLEAN | `ledger_tax_estimate_complete` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `ledger_tax_estimate_complete`). |
| `Total_Event_Count` | BIGINT | `total_event_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_event_count`). |
| `Ready_Count` | BIGINT | `ready_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `ready_count`). |
| `Check_Required_Count` | BIGINT | `check_required_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `check_required_count`). |


### `gold.Tax_Income_Breakdown` -> `gold.tax_income_breakdown`
**Domain:** Taxes | **Grain:** FY-Head-SubHead-Source | **Producer:** TaxEngine | **Columns:** 12

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `FY` | TEXT | `financial_year` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `financial_year`). |
| `Income_Head` | TEXT | `income_head` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `income_head`). |
| `Tax_Sub_Head` | TEXT | `tax_sub_head` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `tax_sub_head`). |
| `Source_Type` | TEXT | `source_type` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `source_type`). |
| `Event_Amount_INR` | DOUBLE | `event_amount_inr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `event_amount_inr`). |
| `Estimated_Tax_INR` | DOUBLE | `estimated_tax_inr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `estimated_tax_inr`). |
| `Estimated_Tax_Event_Count` | BIGINT | `estimated_tax_event_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `estimated_tax_event_count`). |
| `Estimated_Tax_Missing_Count` | BIGINT | `estimated_tax_missing_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `estimated_tax_missing_count`). |
| `Estimated_Tax_Complete` | BOOLEAN | `estimated_tax_complete` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `estimated_tax_complete`). |
| `Event_Count` | BIGINT | `event_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `event_count`). |
| `Ready_Count` | BIGINT | `ready_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `ready_count`). |
| `Check_Required_Count` | BIGINT | `check_required_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `check_required_count`). |


### `gold.Tax_Reconciliation` -> `gold.tax_reconciliation`
**Domain:** Taxes | **Grain:** FY-SubHead | **Producer:** TaxEngine | **Columns:** 23

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `FY` | TEXT | `financial_year` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `financial_year`). |
| `Tax_Sub_Head` | TEXT | `tax_sub_head` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `tax_sub_head`). |
| `Ledger_Tax_Event_Amount` | DOUBLE | `ledger_tax_event_amount` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `ledger_tax_event_amount`). |
| `Excluded_Non_Taxable_Amount` | DOUBLE | `excluded_non_taxable_amount` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `excluded_non_taxable_amount`). |
| `Excluded_Non_Taxable_Event_Count` | BIGINT | `excluded_non_taxable_event_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `excluded_non_taxable_event_count`). |
| `Excluded_Investment_Ledger_Amount` | DOUBLE | `excluded_investment_ledger_amount` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `excluded_investment_ledger_amount`). |
| `Excluded_Investment_Ledger_Event_Count` | BIGINT | `excluded_investment_ledger_event_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `excluded_investment_ledger_event_count`). |
| `Quant_Realized_Gain_Loss` | DOUBLE | `quant_realized_gain_loss` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `quant_realized_gain_loss`). |
| `Estimated_Investment_Tax` | DOUBLE | `estimated_investment_tax` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `estimated_investment_tax`). |
| `Estimated_Tax_Event_Count` | BIGINT | `estimated_tax_event_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `estimated_tax_event_count`). |
| `Estimated_Tax_Missing_Count` | BIGINT | `estimated_tax_missing_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `estimated_tax_missing_count`). |
| `Estimated_Investment_Tax_Complete` | BOOLEAN | `estimated_investment_tax_complete` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `estimated_investment_tax_complete`). |
| `Estimated_Ledger_Tax` | DOUBLE | `estimated_ledger_tax` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `estimated_ledger_tax`). |
| `Ledger_Tax_Estimate_Count` | BIGINT | `ledger_tax_estimate_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `ledger_tax_estimate_count`). |
| `Ledger_Tax_Estimate_Missing_Count` | BIGINT | `ledger_tax_estimate_missing_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `ledger_tax_estimate_missing_count`). |
| `Estimated_Ledger_Tax_Complete` | BOOLEAN | `estimated_ledger_tax_complete` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `estimated_ledger_tax_complete`). |
| `Tax_Credit_Amount` | DOUBLE | `tax_credit_amount` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `tax_credit_amount`). |
| `Tax_Event_Amount` | DOUBLE | `tax_event_amount` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `tax_event_amount`). |
| `Investment_Source_Difference_INR` | DOUBLE | `investment_source_difference_inr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `investment_source_difference_inr`). |
| `Ledger_Event_Count` | BIGINT | `ledger_event_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `ledger_event_count`). |
| `Quant_Event_Count` | BIGINT | `quant_event_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `quant_event_count`). |
| `Tax_Credit_Event_Count` | BIGINT | `tax_credit_event_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `tax_credit_event_count`). |
| `Check_Required_Count` | BIGINT | `check_required_count` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `check_required_count`). |


### `gold.Wealth_Asset_Breakdown` -> `gold.wealth_asset_breakdown`
**Domain:** Wealth | **Grain:** Month-Asset | **Producer:** WealthPresentationEngine | **Columns:** 33

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `MONTH_START_DATE` | DATE | `month_start_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_start_date`). |
| `MONTH_END_DATE` | DATE | `month_end_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_end_date`). |
| `ASSET_SUBCATEGORY_ID` | TEXT | `asset_subcategory_id` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `asset_subcategory_id`). |
| `Opening_Balance` | DOUBLE | `opening_balance` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `opening_balance`). |
| `Closing_Balance` | DOUBLE | `closing_balance` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `closing_balance`). |
| `Closing_Balance_Market` | DOUBLE | `closing_balance_market` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `closing_balance_market`). |
| `All_Time_High_Balance` | DOUBLE | `all_time_high_balance` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `all_time_high_balance`). |
| `Liquid_Assets` | DOUBLE | `liquid_assets` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `liquid_assets`). |
| `Liquid_Assets_Market` | DOUBLE | `liquid_assets_market` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `liquid_assets_market`). |
| `Closing_Asset_PnL` | DOUBLE | `closing_asset_pnl` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `closing_asset_pnl`). |
| `Closing_Forex_PnL` | DOUBLE | `closing_fx_pnl` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `closing_fx_pnl`). |
| `MoM_Balance_Growth_%` | DOUBLE | `mom_balance_growth_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `mom_balance_growth_pct`). |
| `YoY_Balance_Growth_%` | DOUBLE | `yoy_balance_growth_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `yoy_balance_growth_pct`). |
| `Organic_Growth_Value` | DOUBLE | `organic_growth_value` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `organic_growth_value`). |
| `Organic_Yield_%` | DOUBLE | `organic_yield_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `organic_yield_pct`). |
| `Drawdown_From_Peak` | DOUBLE | `drawdown_from_peak` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `drawdown_from_peak`). |
| `Investment_Contribution_Pct` | DOUBLE | `investment_contribution_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `investment_contribution_pct`). |
| `Savings_to_NW_Ratio` | DOUBLE | `savings_to_nw_ratio` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `savings_to_nw_ratio`). |
| `Income_Inflow` | DOUBLE | `income_inflow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `income_inflow`). |
| `Cash_Income_Inflow` | DOUBLE | `cash_income_inflow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cash_income_inflow`). |
| `Non_Cash_Income_Inflow` | DOUBLE | `non_cash_income_inflow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `non_cash_income_inflow`). |
| `Expense_Outflow` | DOUBLE | `expense_outflow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `expense_outflow`). |
| `Core_Expense_Outflow` | DOUBLE | `core_expense_outflow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `core_expense_outflow`). |
| `Cash_Expense_Outflow` | DOUBLE | `cash_expense_outflow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cash_expense_outflow`). |
| `Non_Cash_Expense_Outflow` | DOUBLE | `non_cash_expense_outflow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `non_cash_expense_outflow`). |
| `Net_Transfers` | DOUBLE | `net_transfers` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `net_transfers`). |
| `Net_Cashflow_Month` | DOUBLE | `net_cashflow_month` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `net_cashflow_month`). |
| `Surplus_Deficit_Month` | DOUBLE | `surplus_deficit_month` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `surplus_deficit_month`). |
| `Cumulative_Net_Savings` | DOUBLE | `cumulative_net_savings` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cumulative_net_savings`). |
| `3M_Avg_Expense` | DOUBLE | `trailing_3m_avg_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_3m_avg_expense`). |
| `3M_Avg_Core_Expense` | DOUBLE | `trailing_3m_avg_core_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_3m_avg_core_expense`). |
| `3M_Avg_Income` | DOUBLE | `trailing_3m_avg_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_3m_avg_income`). |
| `Months_of_Runway` | DOUBLE | `months_of_runway` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `months_of_runway`). |


### `gold.Core_Monthly_Fact` -> `gold.core_monthly_fact`
**Domain:** Wealth | **Grain:** Month | **Producer:** WealthPresentationEngine | **Columns:** 40

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `MONTH_START_DATE` | DATE | `month_start_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_start_date`). |
| `MONTH_END_DATE` | DATE | `month_end_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_end_date`). |
| `Months_Elapsed` | BIGINT | `months_elapsed` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `months_elapsed`). |
| `Total_Income` | DOUBLE | `total_income` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_income`). |
| `Total_Cash_Income` | DOUBLE | `total_cash_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_cash_income`). |
| `Total_Non_Cash_Income` | DOUBLE | `total_non_cash_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_non_cash_income`). |
| `Total_Expense` | DOUBLE | `total_expense` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_expense`). |
| `Total_Core_Expense` | DOUBLE | `total_core_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_core_expense`). |
| `Total_Cash_Expense` | DOUBLE | `total_cash_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_cash_expense`). |
| `Total_Non_Cash_Expense` | DOUBLE | `total_non_cash_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_non_cash_expense`). |
| `Net_Cashflow_Month` | DOUBLE | `net_cashflow_month` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `net_cashflow_month`). |
| `Opening_Balance_Asset` | DOUBLE | `opening_balance_asset` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `opening_balance_asset`). |
| `Opening_Balance_Asset_Market` | DOUBLE | `opening_balance_asset_market` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `opening_balance_asset_market`). |
| `Closing_Balance_Asset` | DOUBLE | `closing_balance_asset` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `closing_balance_asset`). |
| `Closing_Balance_Asset_Market` | DOUBLE | `closing_balance_asset_market` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `closing_balance_asset_market`). |
| `Asset_Delta` | DOUBLE | `asset_delta` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `asset_delta`). |
| `Asset_Market_Delta` | DOUBLE | `asset_market_delta` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `asset_market_delta`). |
| `Total_Assets` | DOUBLE | `total_assets` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_assets`). |
| `Total_Assets_Market` | DOUBLE | `total_assets_market` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_assets_market`). |
| `Opening_Investment_Book_Value` | DOUBLE | `opening_investment_book_value` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `opening_investment_book_value`). |
| `Closing_Investment_Book_Value` | DOUBLE | `closing_investment_book_value` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `closing_investment_book_value`). |
| `Investment_Book_Value_Delta` | DOUBLE | `investment_book_value_delta` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `investment_book_value_delta`). |
| `Opening_Investment_Market_Value` | DOUBLE | `opening_investment_market_value` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `opening_investment_market_value`). |
| `Closing_Investment_Market_Value` | DOUBLE | `closing_investment_market_value` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `closing_investment_market_value`). |
| `Investment_Market_Value_Delta` | DOUBLE | `investment_market_value_delta` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `investment_market_value_delta`). |
| `Liquid_Assets` | DOUBLE | `liquid_assets` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `liquid_assets`). |
| `Liquid_Assets_Market` | DOUBLE | `liquid_assets_market` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `liquid_assets_market`). |
| `Total_Liabilities` | DOUBLE | `total_liabilities` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_liabilities`). |
| `Total_Net_Worth` | DOUBLE | `total_net_worth` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_net_worth`). |
| `Total_Net_Worth_Market` | DOUBLE | `total_net_worth_market` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_net_worth_market`). |
| `Total_Foreign_Currency_Exposure` | DOUBLE | `total_foreign_currency_exposure` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_foreign_currency_exposure`). |
| `Opening_Unrealized_PL` | DOUBLE | `opening_unrealized_pnl` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `opening_unrealized_pnl`). |
| `Closing_Unrealized_PL` | DOUBLE | `closing_unrealized_pnl` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `closing_unrealized_pnl`). |
| `Closing_Asset_PnL` | DOUBLE | `closing_asset_pnl` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `closing_asset_pnl`). |
| `Closing_Forex_PnL` | DOUBLE | `closing_fx_pnl` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `closing_fx_pnl`). |
| `Opening_Investment_XIRR` | DOUBLE | `opening_investment_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `opening_investment_xirr`). |
| `Closing_Investment_XIRR` | DOUBLE | `closing_investment_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `closing_investment_xirr`). |
| `Foreign_Exposure_Pct` | DOUBLE | `foreign_exposure_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `foreign_exposure_pct`). |
| `CPI_INDEX` | DOUBLE | `cpi_index` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cpi_index`). |
| `INFLATION_YOY_PCT` | DOUBLE | `inflation_yoy_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `inflation_yoy_pct`). |


### `gold.Cashflow_Expense_Breakdown` -> `gold.cashflow_expense_breakdown`
**Domain:** Wealth | **Grain:** Month-ExpenseCategory | **Producer:** WealthPresentationEngine | **Columns:** 15

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `MONTH_START_DATE` | DATE | `month_start_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_start_date`). |
| `MONTH_END_DATE` | DATE | `month_end_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_end_date`). |
| `YEAR_MONTH` | TEXT | `year_month` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `year_month`). |
| `CATEGORY_ID` | TEXT | `category_id` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `category_id`). |
| `CATEGORY_NAME` | TEXT | `category_name` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `category_name`). |
| `CATEGORY_GROUPS` | TEXT | `category_groups` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `category_groups`). |
| `Spend_Type` | TEXT | `spend_type` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `spend_type`). |
| `Is_Core_Expense` | BOOLEAN | `is_core_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_core_expense`). |
| `Is_Investment` | BOOLEAN | `is_investment` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_investment`). |
| `Is_Discretionary` | BOOLEAN | `is_discretionary` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_discretionary`). |
| `Total_Monthly_Spend` | DOUBLE | `total_monthly_spend` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_monthly_spend`). |
| `Cash_Spend` | DOUBLE | `cash_spend` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cash_spend`). |
| `Non_Cash_Spend` | DOUBLE | `non_cash_spend` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `non_cash_spend`). |
| `Trailing_3M_Avg_Spend` | DOUBLE | `trailing_3_m_avg_spend` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_3_m_avg_spend`). |
| `Cumulative_YTD_Spend` | DOUBLE | `cumulative_ytd_spend` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cumulative_ytd_spend`). |


### `gold.Cashflow_Income_Breakdown` -> `gold.cashflow_income_breakdown`
**Domain:** Wealth | **Grain:** Month-IncomeCategory | **Producer:** WealthPresentationEngine | **Columns:** 14

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `MONTH_START_DATE` | DATE | `month_start_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_start_date`). |
| `MONTH_END_DATE` | DATE | `month_end_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_end_date`). |
| `YEAR_MONTH` | TEXT | `year_month` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `year_month`). |
| `CATEGORY_ID` | TEXT | `category_id` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `category_id`). |
| `CATEGORY_NAME` | TEXT | `category_name` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `category_name`). |
| `CATEGORY_GROUPS` | TEXT | `category_groups` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `category_groups`). |
| `Is_Active_Income` | BOOLEAN | `is_active_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_active_income`). |
| `Is_Passive_Income` | BOOLEAN | `is_passive_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_passive_income`). |
| `Is_Dividend_Income` | BOOLEAN | `is_dividend_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_dividend_income`). |
| `Is_Interest_Income` | BOOLEAN | `is_interest_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_interest_income`). |
| `Is_Non_Cash_Income` | BOOLEAN | `is_non_cash_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_non_cash_income`). |
| `Total_Monthly_Income` | DOUBLE | `total_monthly_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_monthly_income`). |
| `Trailing_3M_Avg_Income` | DOUBLE | `trailing_3_m_avg_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_3_m_avg_income`). |
| `Cumulative_YTD_Income` | DOUBLE | `cumulative_ytd_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cumulative_ytd_income`). |


### `gold.Wealth_FIRE_Analytics` -> `gold.wealth_fire_analytics`
**Domain:** Wealth | **Grain:** Month | **Producer:** WealthPresentationEngine | **Columns:** 35

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `MONTH_START_DATE` | DATE | `month_start_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_start_date`). |
| `MONTH_END_DATE` | DATE | `month_end_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_end_date`). |
| `YEAR_MONTH` | TEXT | `year_month` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `year_month`). |
| `Projected_FI_Date_P50` | DATE | `projected_fi_date_p50` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `projected_fi_date_p50`). |
| `Total_Income` | DOUBLE | `total_income` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_income`). |
| `Total_Cash_Income` | DOUBLE | `total_cash_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_cash_income`). |
| `Trailing_6M_Avg_Spend` | DOUBLE | `trailing_6_m_avg_spend` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_6_m_avg_spend`). |
| `Trailing_12M_Avg_Spend` | DOUBLE | `trailing_12_m_avg_spend` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_12_m_avg_spend`). |
| `Trailing_6M_Avg_Savings` | DOUBLE | `trailing_6_m_avg_savings` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_6_m_avg_savings`). |
| `Trailing_12M_Avg_Savings` | DOUBLE | `trailing_12_m_avg_savings` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_12_m_avg_savings`). |
| `Target_FI_Today` | DOUBLE | `target_fi_today` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `target_fi_today`). |
| `Coast_FI_Today` | DOUBLE | `coast_fi_today` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `coast_fi_today`). |
| `Lean_FI_Today` | DOUBLE | `lean_fi_today` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `lean_fi_today`). |
| `Target_FI_Total_Future_Nominal` | DOUBLE | `target_fi_total_future_nominal` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `target_fi_total_future_nominal`). |
| `FI_Gap` | DOUBLE | `fi_gap` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fi_gap`). |
| `FI_Gap_Monthly_Trend` | DOUBLE | `fi_gap_monthly_trend` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fi_gap_monthly_trend`). |
| `Terminal_Wealth_Nominal_P50` | DOUBLE | `terminal_wealth_nominal_p50` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `terminal_wealth_nominal_p50`). |
| `Real_Return_Assumed_Pct` | DOUBLE | `real_return_assumed_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `real_return_assumed_pct`). |
| `Wealth_Velocity` | DOUBLE | `wealth_velocity` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `wealth_velocity`). |
| `Wealth_Acceleration` | DOUBLE | `wealth_acceleration` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `wealth_acceleration`). |
| `Real_NW_CAGR_3Y` | DOUBLE | `real_nw_cagr_3_y` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `real_nw_cagr_3_y`). |
| `Current_FI_Coverage_Pct` | DOUBLE | `current_fi_coverage_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `current_fi_coverage_pct`). |
| `Estimated_Months_To_FI_Linear` | DOUBLE | `estimated_months_to_fi_linear` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `estimated_months_to_fi_linear`). |
| `Months_To_FI_Conservative_P90` | DOUBLE | `months_to_fi_conservative_p90` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `months_to_fi_conservative_p90`). |
| `Months_To_FI_Base_P50` | DOUBLE | `months_to_fi_base_p50` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `months_to_fi_base_p50`). |
| `Months_To_FI_Aggressive_P10` | DOUBLE | `months_to_fi_aggressive_p10` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `months_to_fi_aggressive_p10`). |
| `Probability_Of_Success_Pct` | DOUBLE | `probability_of_success_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `probability_of_success_pct`). |
| `Years_To_FI_P50` | DOUBLE | `years_to_fi_p50` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `years_to_fi_p50`). |
| `Runway_Months_Linear` | DOUBLE | `runway_months_linear` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `runway_months_linear`). |
| `Runway_Months_Stressed_P10` | DOUBLE | `runway_months_stressed_p10` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `runway_months_stressed_p10`). |
| `Runway_Months_Base_P50` | DOUBLE | `runway_months_base_p50` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `runway_months_base_p50`). |
| `Withdrawal_Rate_If_Retired_Now` | DOUBLE | `withdrawal_rate_if_retired_now` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `withdrawal_rate_if_retired_now`). |
| `Savings_Rate_Required` | DOUBLE | `savings_rate_required` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `savings_rate_required`). |
| `Savings_Rate_Actual` | DOUBLE | `savings_rate_actual` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `savings_rate_actual`). |
| `FI_Velocity` | DOUBLE | `fi_velocity` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fi_velocity`). |


### `gold.Forecast_Budget_Variance` -> `gold.forecast_budget_variance`
**Domain:** Wealth | **Grain:** Month | **Producer:** WealthPresentationEngine | **Columns:** 27

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `MONTH_START_DATE` | DATE | `month_start_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_start_date`). |
| `MONTH_END_DATE` | DATE | `month_end_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_end_date`). |
| `YEAR_MONTH` | TEXT | `year_month` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `year_month`). |
| `Is_Core_Overspent` | BOOLEAN | `is_core_overspent` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_core_overspent`). |
| `Is_NonCore_Overspent` | BOOLEAN | `is_non_core_overspent` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_non_core_overspent`). |
| `Is_Investment_Underfunded` | BOOLEAN | `is_investment_underfunded` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_investment_underfunded`). |
| `Is_Income_Volatile` | BOOLEAN | `is_income_volatile` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_income_volatile`). |
| `Is_Budget_Month_Healthy` | BOOLEAN | `is_budget_month_healthy` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_budget_month_healthy`). |
| `Total_Income` | DOUBLE | `total_income` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_income`). |
| `Actual_Income` | DOUBLE | `actual_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `actual_income`). |
| `Budget_Income` | DOUBLE | `budget_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `budget_income`). |
| `Budget_Core_Expense_Target` | DOUBLE | `budget_core_expense_target` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `budget_core_expense_target`). |
| `Budget_NonCore_Expense_Target` | DOUBLE | `budget_non_core_expense_target` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `budget_non_core_expense_target`). |
| `Budget_Investment_Target` | DOUBLE | `budget_investment_target` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `budget_investment_target`). |
| `Budget_Surplus_Buffer` | DOUBLE | `budget_surplus_buffer` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `budget_surplus_buffer`). |
| `Budget_Total_Expense_Target` | DOUBLE | `budget_total_expense_target` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `budget_total_expense_target`). |
| `Actual_Core_Expense` | DOUBLE | `actual_core_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `actual_core_expense`). |
| `Actual_NonCore_Expense` | DOUBLE | `actual_non_core_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `actual_non_core_expense`). |
| `Investment_Deployed` | DOUBLE | `investment_deployed` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `investment_deployed`). |
| `Investment_Redeemed` | DOUBLE | `investment_redeemed` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `investment_redeemed`). |
| `Actual_Investment` | DOUBLE | `actual_investment` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `actual_investment`). |
| `Actual_Savings` | DOUBLE | `actual_savings` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `actual_savings`). |
| `Emergency_Fund_Gap` | DOUBLE | `emergency_fund_gap` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `emergency_fund_gap`). |
| `Rule_Core_Pct_Budget` | DOUBLE | `rule_core_pct_budget` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `rule_core_pct_budget`). |
| `Rule_NonCore_Pct_Budget` | DOUBLE | `rule_non_core_pct_budget` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `rule_non_core_pct_budget`). |
| `Rule_Investment_Pct_Budget` | DOUBLE | `rule_investment_pct_budget` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `rule_investment_pct_budget`). |
| `Zero_Income_Runway_Months` | DOUBLE | `zero_income_runway_months` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `zero_income_runway_months`). |


### `gold.Cashflow_Efficiency_Analytics` -> `gold.cashflow_efficiency_analytics`
**Domain:** Wealth | **Grain:** Month | **Producer:** WealthPresentationEngine | **Columns:** 45

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `MONTH_START_DATE` | DATE | `month_start_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_start_date`). |
| `MONTH_END_DATE` | DATE | `month_end_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_end_date`). |
| `YEAR_MONTH` | TEXT | `year_month` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `year_month`). |
| `Is_Surplus_Month` | BOOLEAN | `is_surplus_month` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_surplus_month`). |
| `Is_Investment_Target_Met` | BOOLEAN | `is_investment_target_met` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_investment_target_met`). |
| `Total_Income` | DOUBLE | `total_income` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_income`). |
| `Total_Cash_Income` | DOUBLE | `total_cash_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_cash_income`). |
| `Total_Non_Cash_Income` | DOUBLE | `total_non_cash_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_non_cash_income`). |
| `Total_Expense` | DOUBLE | `total_expense` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_expense`). |
| `Active_Income` | DOUBLE | `active_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_income`). |
| `Passive_Income` | DOUBLE | `passive_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `passive_income`). |
| `Dividend_Income` | DOUBLE | `dividend_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `dividend_income`). |
| `Interest_Income` | DOUBLE | `interest_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `interest_income`). |
| `Core_Expense` | DOUBLE | `core_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `core_expense`). |
| `NonCore_Expense` | DOUBLE | `non_core_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `non_core_expense`). |
| `Total_Cash_Expense` | DOUBLE | `total_cash_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_cash_expense`). |
| `Total_Non_Cash_Expense` | DOUBLE | `total_non_cash_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_non_cash_expense`). |
| `Total_Investment_Deployed` | DOUBLE | `total_investment_deployed` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_investment_deployed`). |
| `Total_Investment_Redeemed` | DOUBLE | `total_investment_redeemed` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_investment_redeemed`). |
| `Redemption_Gain_Loss_Value` | DOUBLE | `redemption_gain_loss_value` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `redemption_gain_loss_value`). |
| `Net_Investment_Flow` | DOUBLE | `net_investment_flow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `net_investment_flow`). |
| `Gross_Surplus` | DOUBLE | `gross_surplus` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `gross_surplus`). |
| `Net_Surplus_After_Invest` | DOUBLE | `net_surplus_after_invest` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `net_surplus_after_invest`). |
| `Income_MoM_Delta` | DOUBLE | `income_mom_delta` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `income_mom_delta`). |
| `Expense_MoM_Delta` | DOUBLE | `expense_mom_delta` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `expense_mom_delta`). |
| `Investment_MoM_Delta` | DOUBLE | `investment_mom_delta` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `investment_mom_delta`). |
| `Trailing_3M_Avg_Income` | DOUBLE | `trailing_3_m_avg_income` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_3_m_avg_income`). |
| `Trailing_3M_Avg_Expense` | DOUBLE | `trailing_3_m_avg_expense` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_3_m_avg_expense`). |
| `Trailing_3M_Avg_Investment` | DOUBLE | `trailing_3_m_avg_investment` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_3_m_avg_investment`). |
| `Savings_Rate_Pct` | DOUBLE | `savings_rate_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `savings_rate_pct`). |
| `Investment_Rate_Pct` | DOUBLE | `investment_rate_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `investment_rate_pct`). |
| `Active_Income_Share_Pct` | DOUBLE | `active_income_share_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_income_share_pct`). |
| `Passive_Income_Share_Pct` | DOUBLE | `passive_income_share_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `passive_income_share_pct`). |
| `Core_Expense_Share_Pct` | DOUBLE | `core_expense_share_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `core_expense_share_pct`). |
| `NonCore_Expense_Share_Pct` | DOUBLE | `non_core_expense_share_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `non_core_expense_share_pct`). |
| `Income_MoM_Pct` | DOUBLE | `income_mom_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `income_mom_pct`). |
| `Expense_MoM_Pct` | DOUBLE | `expense_mom_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `expense_mom_pct`). |
| `Trailing_3M_Avg_Savings_Rate` | DOUBLE | `trailing_3_m_avg_savings_rate` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_3_m_avg_savings_rate`). |
| `Trailing_3M_Avg_Investment_Rate` | DOUBLE | `trailing_3_m_avg_investment_rate` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `trailing_3_m_avg_investment_rate`). |
| `Liquidity_Ratio_Months` | DOUBLE | `liquidity_ratio_months` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `liquidity_ratio_months`). |
| `Debt_to_Asset_Ratio_Pct` | DOUBLE | `debt_to_asset_ratio_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `debt_to_asset_ratio_pct`). |
| `YoY_Net_Worth_Growth_Pct` | DOUBLE | `yoy_net_worth_growth_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `yoy_net_worth_growth_pct`). |
| `YoY_Net_Worth_Growth_Pct_Real` | DOUBLE | `yoy_net_worth_growth_pct_real` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `yoy_net_worth_growth_pct_real`). |
| `Expense_to_NW_Ratio` | DOUBLE | `expense_to_nw_ratio` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `expense_to_nw_ratio`). |
| `Emergency_Fund_Coverage` | DOUBLE | `emergency_fund_coverage` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `emergency_fund_coverage`). |


### `gold.Cashflow_Activity_Summary` -> `gold.cashflow_activity_summary`
**Domain:** Wealth | **Grain:** Month | **Producer:** WealthPresentationEngine | **Columns:** 24

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `MONTH_START_DATE` | DATE | `month_start_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_start_date`). |
| `MONTH_END_DATE` | DATE | `month_end_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_end_date`). |
| `YEAR_MONTH` | TEXT | `year_month` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `year_month`). |
| `Opening_Cash_Balance` | DOUBLE | `opening_cash_balance` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `opening_cash_balance`). |
| `Closing_Cash_Balance` | DOUBLE | `closing_cash_balance` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `closing_cash_balance`). |
| `Net_Cash_Movement` | DOUBLE | `net_cash_movement` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `net_cash_movement`). |
| `Cash_Inflow_Operating` | DOUBLE | `cash_inflow_operating` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cash_inflow_operating`). |
| `Cash_Outflow_Operating` | DOUBLE | `cash_outflow_operating` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cash_outflow_operating`). |
| `Net_Cashflow_Operating` | DOUBLE | `net_cashflow_operating` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `net_cashflow_operating`). |
| `Cash_Inflow_Investing` | DOUBLE | `cash_inflow_investing` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cash_inflow_investing`). |
| `Cash_Outflow_Investing` | DOUBLE | `cash_outflow_investing` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cash_outflow_investing`). |
| `Net_Cashflow_Investing` | DOUBLE | `net_cashflow_investing` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `net_cashflow_investing`). |
| `Cash_Inflow_Financing` | DOUBLE | `cash_inflow_financing` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cash_inflow_financing`). |
| `Cash_Outflow_Financing` | DOUBLE | `cash_outflow_financing` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `cash_outflow_financing`). |
| `Net_Cashflow_Financing` | DOUBLE | `net_cashflow_financing` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `net_cashflow_financing`). |
| `Internal_Transfer_Inflow` | DOUBLE | `internal_transfer_inflow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `internal_transfer_inflow`). |
| `Internal_Transfer_Outflow` | DOUBLE | `internal_transfer_outflow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `internal_transfer_outflow`). |
| `Net_Internal_Transfers` | DOUBLE | `net_internal_transfers` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `net_internal_transfers`). |
| `Total_Cash_Expenses` | DOUBLE | `total_cash_expenses` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_cash_expenses`). |
| `Total_Non_Cash_Expenses` | DOUBLE | `total_non_cash_expenses` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_non_cash_expenses`). |
| `Total_Cash_Inflow` | DOUBLE | `total_cash_inflow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_cash_inflow`). |
| `Total_Cash_Outflow` | DOUBLE | `total_cash_outflow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_cash_outflow`). |
| `Calculated_Net_Cashflow` | DOUBLE | `calculated_net_cashflow` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `calculated_net_cashflow`). |
| `Unreconciled_Difference` | DOUBLE | `unreconciled_difference` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `unreconciled_difference`). |


---

## 5. Phase 010 Investment Portfolio & Breakdown Dispositions (11 Tables)

### `gold.Investment_Portfolio_Summary` -> `gold.investment_portfolio_summary`
**Domain:** Investments | **Grain:** Month-ISIN | **Producer:** InvestmentQuantEngine | **Columns:** 32

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `MONTH_START_DATE` | DATE | `month_start_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `month_start_date`). |
| `Max_Closing_Date` | DATE | `max_closing_date` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `max_closing_date`). |
| `ISIN` | TEXT | `isin` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `isin`). |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `currency_id`). |
| `INSTRUMENT_NAME` | TEXT | `instrument_name` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `instrument_name`). |
| `INSTRUMENT_CLASS` | TEXT | `instrument_class` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `instrument_class`). |
| `INSTRUMENT_TYPE` | TEXT | `instrument_type` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `instrument_type`). |
| `INSTRUMENT_SUBTYPE` | TEXT | `instrument_subtype` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `instrument_subtype`). |
| `SECTOR` | TEXT | `sector` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `sector`). |
| `Rebalance_Required` | BOOLEAN | `rebalance_required` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `rebalance_required`). |
| `ISIN_Market_Value` | DOUBLE | `isin_market_value` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_market_value`). |
| `ISIN_Book_Value` | DOUBLE | `isin_book_value` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_book_value`). |
| `ISIN_Market_Value_Local` | DOUBLE | `isin_market_value_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_market_value_local`). |
| `ISIN_Book_Value_Local` | DOUBLE | `isin_book_value_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_book_value_local`). |
| `ISIN_Unrealized_PnL` | DOUBLE | `isin_unrealized_pnl` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_unrealized_pnl`). |
| `ISIN_Asset_PnL` | DOUBLE | `isin_asset_pnl` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_asset_pnl`). |
| `ISIN_Forex_PnL` | DOUBLE | `isin_fx_pnl` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_fx_pnl`). |
| `ISIN_Forex_Contribution_Pct` | DOUBLE | `isin_fx_contribution_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_fx_contribution_pct`). |
| `ISIN_XIRR_Local` | DOUBLE | `isin_xirr_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_xirr_local`). |
| `ISIN_FX_XIRR_Impact` | DOUBLE | `isin_fx_xirr_impact` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_fx_xirr_impact`). |
| `ISIN_BM_XIRR` | DOUBLE | `isin_benchmark_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_benchmark_xirr`). |
| `ISIN_BM_XIRR_Local` | DOUBLE | `isin_benchmark_xirr_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_benchmark_xirr_local`). |
| `ISIN_Active_Return` | DOUBLE | `isin_active_return` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_active_return`). |
| `ISIN_Active_Return_Local` | DOUBLE | `isin_active_return_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_active_return_local`). |
| `ISIN_Weight` | DOUBLE | `isin_weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_weight`). |
| `Class_Weight` | DOUBLE | `class_weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `class_weight`). |
| `Class_Target_Weight` | DOUBLE | `class_target_weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `class_target_weight`). |
| `Class_Drift` | DOUBLE | `class_drift` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `class_drift`). |
| `Sector_Weight` | DOUBLE | `sector_weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `sector_weight`). |
| `Monthly_Market_Value_Change_Pct` | DOUBLE | `monthly_market_value_change_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `monthly_market_value_change_pct`). |
| `ISIN_Harvestable_Loss` | DOUBLE | `isin_harvestable_loss` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `isin_harvestable_loss`). |
| `Tax_Harvesting_Priority_Score` | DOUBLE | `tax_harvesting_priority_score` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `tax_harvesting_priority_score`). |


### `gold.Investment_By_ISIN` -> `gold.investment_by_isin`
**Domain:** Investments | **Grain:** Date-ISIN | **Producer:** InvestmentQuantEngine | **Columns:** 46

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Closing_Date` | DATE NOT NULL | `closing_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `closing_date`). |
| `ISIN` | TEXT NOT NULL | `isin` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `isin`). |
| `CURRENCY_ID` | TEXT | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `currency_id`). |
| `Total_Invested_Value` | DOUBLE | `total_invested_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_invested_value`). |
| `Total_Current_Value` | DOUBLE | `total_current_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_current_value`). |
| `Total_Quantity` | DOUBLE | `total_quantity` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_quantity`). |
| `Total_Stocks` | DOUBLE | `total_stocks` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_stocks`). |
| `Total_Invested_Value_Local` | DOUBLE | `total_invested_value_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_invested_value_local`). |
| `Total_Current_Value_Local` | DOUBLE | `total_current_value_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_current_value_local`). |
| `Current_FX_Rate` | DOUBLE | `current_fx_rate` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `current_fx_rate`). |
| `Blended_FX_Buy_Rate` | DOUBLE | `blended_fx_buy_rate` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `blended_fx_buy_rate`). |
| `Currency_Appreciation_Pct` | DOUBLE | `currency_appreciation_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `currency_appreciation_pct`). |
| `Unrealized_PL` | DOUBLE | `unrealized_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_pnl`). |
| `Asset_PnL` | DOUBLE | `asset_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `asset_pnl`). |
| `Forex_PnL` | DOUBLE | `fx_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fx_pnl`). |
| `Forex_Contribution_Pct` | DOUBLE | `fx_contribution_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_contribution_pct`). |
| `Absolute_Return` | DOUBLE | `absolute_return` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `absolute_return`). |
| `CAGR` | DOUBLE | `cagr` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `cagr`). |
| `XIRR` | DOUBLE | `xirr` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `xirr`). |
| `XIRR_Local` | DOUBLE | `xirr_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `xirr_local`). |
| `FX_XIRR_Impact` | DOUBLE | `fx_xirr_impact` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_xirr_impact`). |
| `After_Tax_XIRR` | DOUBLE | `after_tax_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `after_tax_xirr`). |
| `BM_CAGR` | DOUBLE | `benchmark_cagr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_cagr`). |
| `BM_XIRR` | DOUBLE | `benchmark_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr`). |
| `BM_XIRR_Local` | DOUBLE | `benchmark_xirr_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr_local`). |
| `Active_Return` | DOUBLE | `active_return` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return`). |
| `Active_Return_Local` | DOUBLE | `active_return_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return_local`). |
| `Is_Lagging_Benchmark` | BIGINT | `is_lagging_benchmark` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `is_lagging_benchmark`). |
| `Outperforming_Lot_Ratio` | DOUBLE | `outperforming_lot_ratio` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `outperforming_lot_ratio`). |
| `Max_Drawdown` | DOUBLE | `max_drawdown` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `max_drawdown`). |
| `Weight` | DOUBLE | `weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `weight`). |
| `Unrealized_LTCG` | DOUBLE | `unrealized_ltcg` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_ltcg`). |
| `Unrealized_STCG` | DOUBLE | `unrealized_stcg` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_stcg`). |
| `Unrealized_Gain` | DOUBLE | `unrealized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_gain`). |
| `Unrealized_LTCL` | DOUBLE | `unrealized_ltcl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_ltcl`). |
| `Unrealized_STCL` | DOUBLE | `unrealized_stcl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_stcl`). |
| `Unrealized_Loss` | DOUBLE | `unrealized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_loss`). |
| `LTCG_Tax_If_Sold` | DOUBLE | `ltcg_tax_if_sold` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `ltcg_tax_if_sold`). |
| `STCG_Tax_If_Sold` | DOUBLE | `stcg_tax_if_sold` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `stcg_tax_if_sold`). |
| `FY_Realized_LTCG` | DOUBLE | `fy_realized_ltcg` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_ltcg`). |
| `FY_Realized_STCG` | DOUBLE | `fy_realized_stcg` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_stcg`). |
| `FY_Realized_Gain` | DOUBLE | `fy_realized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_gain`). |
| `FY_Realized_LTCL` | DOUBLE | `fy_realized_ltcl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_ltcl`). |
| `FY_Realized_STCL` | DOUBLE | `fy_realized_stcl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_stcl`). |
| `FY_Realized_Loss` | DOUBLE | `fy_realized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_loss`). |
| `FY_Realized_Net_PnL` | DOUBLE | `fy_realized_net_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_net_pnl`). |


### `gold.Investment_By_Subtype` -> `gold.investment_by_subtype`
**Domain:** Investments | **Grain:** Date-Subtype | **Producer:** InvestmentQuantEngine | **Columns:** 23

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Closing_Date` | DATE NOT NULL | `closing_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `closing_date`). |
| `INSTRUMENT_SUBTYPE` | TEXT NOT NULL | `instrument_subtype` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `instrument_subtype`). |
| `INSTRUMENT_CLASS` | TEXT NOT NULL | `instrument_class` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `instrument_class`). |
| `Total_Invested_Value` | DOUBLE | `total_invested_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_invested_value`). |
| `Total_Current_Value` | DOUBLE | `total_current_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_current_value`). |
| `Total_Quantity` | DOUBLE | `total_quantity` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_quantity`). |
| `Total_Stocks` | DOUBLE | `total_stocks` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_stocks`). |
| `Unrealized_PL` | DOUBLE | `unrealized_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_pnl`). |
| `Asset_PnL` | DOUBLE | `asset_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `asset_pnl`). |
| `Forex_PnL` | DOUBLE | `fx_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fx_pnl`). |
| `Forex_Contribution_Pct` | DOUBLE | `fx_contribution_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_contribution_pct`). |
| `Absolute_Return` | DOUBLE | `absolute_return` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `absolute_return`). |
| `XIRR` | DOUBLE | `xirr` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `xirr`). |
| `After_Tax_XIRR` | DOUBLE | `after_tax_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `after_tax_xirr`). |
| `BM_XIRR` | DOUBLE | `benchmark_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr`). |
| `Active_Return` | DOUBLE | `active_return` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return`). |
| `Max_Drawdown` | DOUBLE | `max_drawdown` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `max_drawdown`). |
| `Weight` | DOUBLE | `weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `weight`). |
| `Unrealized_Gain` | DOUBLE | `unrealized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_gain`). |
| `Unrealized_Loss` | DOUBLE | `unrealized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_loss`). |
| `FY_Realized_Gain` | DOUBLE | `fy_realized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_gain`). |
| `FY_Realized_Loss` | DOUBLE | `fy_realized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_loss`). |
| `FY_Realized_Net_PnL` | DOUBLE | `fy_realized_net_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_net_pnl`). |


### `gold.Investment_By_Class` -> `gold.investment_by_class`
**Domain:** Investments | **Grain:** Date-Class | **Producer:** InvestmentQuantEngine | **Columns:** 22

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Closing_Date` | DATE NOT NULL | `closing_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `closing_date`). |
| `INSTRUMENT_CLASS` | TEXT NOT NULL | `instrument_class` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `instrument_class`). |
| `Total_Invested_Value` | DOUBLE | `total_invested_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_invested_value`). |
| `Total_Current_Value` | DOUBLE | `total_current_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_current_value`). |
| `Total_Quantity` | DOUBLE | `total_quantity` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_quantity`). |
| `Total_Stocks` | DOUBLE | `total_stocks` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_stocks`). |
| `Unrealized_PL` | DOUBLE | `unrealized_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_pnl`). |
| `Asset_PnL` | DOUBLE | `asset_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `asset_pnl`). |
| `Forex_PnL` | DOUBLE | `fx_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fx_pnl`). |
| `Forex_Contribution_Pct` | DOUBLE | `fx_contribution_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_contribution_pct`). |
| `Absolute_Return` | DOUBLE | `absolute_return` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `absolute_return`). |
| `XIRR` | DOUBLE | `xirr` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `xirr`). |
| `After_Tax_XIRR` | DOUBLE | `after_tax_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `after_tax_xirr`). |
| `BM_XIRR` | DOUBLE | `benchmark_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr`). |
| `Active_Return` | DOUBLE | `active_return` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return`). |
| `Max_Drawdown` | DOUBLE | `max_drawdown` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `max_drawdown`). |
| `Weight` | DOUBLE | `weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `weight`). |
| `Unrealized_Gain` | DOUBLE | `unrealized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_gain`). |
| `Unrealized_Loss` | DOUBLE | `unrealized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_loss`). |
| `FY_Realized_Gain` | DOUBLE | `fy_realized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_gain`). |
| `FY_Realized_Loss` | DOUBLE | `fy_realized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_loss`). |
| `FY_Realized_Net_PnL` | DOUBLE | `fy_realized_net_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_net_pnl`). |


### `gold.Investment_By_Instrument_Type` -> `gold.investment_by_instrument_type`
**Domain:** Investments | **Grain:** Date-InstrumentType | **Producer:** InvestmentQuantEngine | **Columns:** 22

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Closing_Date` | DATE NOT NULL | `closing_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `closing_date`). |
| `INSTRUMENT_TYPE` | TEXT NOT NULL | `instrument_type` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `instrument_type`). |
| `Total_Invested_Value` | DOUBLE | `total_invested_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_invested_value`). |
| `Total_Current_Value` | DOUBLE | `total_current_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_current_value`). |
| `Total_Quantity` | DOUBLE | `total_quantity` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_quantity`). |
| `Total_Stocks` | DOUBLE | `total_stocks` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_stocks`). |
| `Unrealized_PL` | DOUBLE | `unrealized_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_pnl`). |
| `Asset_PnL` | DOUBLE | `asset_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `asset_pnl`). |
| `Forex_PnL` | DOUBLE | `fx_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fx_pnl`). |
| `Forex_Contribution_Pct` | DOUBLE | `fx_contribution_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_contribution_pct`). |
| `Absolute_Return` | DOUBLE | `absolute_return` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `absolute_return`). |
| `XIRR` | DOUBLE | `xirr` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `xirr`). |
| `After_Tax_XIRR` | DOUBLE | `after_tax_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `after_tax_xirr`). |
| `BM_XIRR` | DOUBLE | `benchmark_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr`). |
| `Active_Return` | DOUBLE | `active_return` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return`). |
| `Max_Drawdown` | DOUBLE | `max_drawdown` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `max_drawdown`). |
| `Weight` | DOUBLE | `weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `weight`). |
| `Unrealized_Gain` | DOUBLE | `unrealized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_gain`). |
| `Unrealized_Loss` | DOUBLE | `unrealized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_loss`). |
| `FY_Realized_Gain` | DOUBLE | `fy_realized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_gain`). |
| `FY_Realized_Loss` | DOUBLE | `fy_realized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_loss`). |
| `FY_Realized_Net_PnL` | DOUBLE | `fy_realized_net_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_net_pnl`). |


### `gold.Investment_By_Sector` -> `gold.investment_by_sector`
**Domain:** Investments | **Grain:** Date-Sector | **Producer:** InvestmentQuantEngine | **Columns:** 22

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Closing_Date` | DATE NOT NULL | `closing_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `closing_date`). |
| `SECTOR` | TEXT NOT NULL | `sector` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `sector`). |
| `Total_Invested_Value` | DOUBLE | `total_invested_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_invested_value`). |
| `Total_Current_Value` | DOUBLE | `total_current_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_current_value`). |
| `Total_Quantity` | DOUBLE | `total_quantity` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_quantity`). |
| `Total_Stocks` | DOUBLE | `total_stocks` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_stocks`). |
| `Unrealized_PL` | DOUBLE | `unrealized_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_pnl`). |
| `Asset_PnL` | DOUBLE | `asset_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `asset_pnl`). |
| `Forex_PnL` | DOUBLE | `fx_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fx_pnl`). |
| `Forex_Contribution_Pct` | DOUBLE | `fx_contribution_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_contribution_pct`). |
| `Absolute_Return` | DOUBLE | `absolute_return` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `absolute_return`). |
| `XIRR` | DOUBLE | `xirr` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `xirr`). |
| `After_Tax_XIRR` | DOUBLE | `after_tax_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `after_tax_xirr`). |
| `BM_XIRR` | DOUBLE | `benchmark_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr`). |
| `Active_Return` | DOUBLE | `active_return` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return`). |
| `Max_Drawdown` | DOUBLE | `max_drawdown` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `max_drawdown`). |
| `Weight` | DOUBLE | `weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `weight`). |
| `Unrealized_Gain` | DOUBLE | `unrealized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_gain`). |
| `Unrealized_Loss` | DOUBLE | `unrealized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_loss`). |
| `FY_Realized_Gain` | DOUBLE | `fy_realized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_gain`). |
| `FY_Realized_Loss` | DOUBLE | `fy_realized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_loss`). |
| `FY_Realized_Net_PnL` | DOUBLE | `fy_realized_net_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_net_pnl`). |


### `gold.Investment_By_Industry` -> `gold.investment_by_industry`
**Domain:** Investments | **Grain:** Date-Industry | **Producer:** InvestmentQuantEngine | **Columns:** 22

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Closing_Date` | DATE NOT NULL | `closing_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `closing_date`). |
| `INDUSTRY` | TEXT NOT NULL | `industry` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `industry`). |
| `Total_Invested_Value` | DOUBLE | `total_invested_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_invested_value`). |
| `Total_Current_Value` | DOUBLE | `total_current_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_current_value`). |
| `Total_Quantity` | DOUBLE | `total_quantity` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_quantity`). |
| `Total_Stocks` | DOUBLE | `total_stocks` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_stocks`). |
| `Unrealized_PL` | DOUBLE | `unrealized_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_pnl`). |
| `Asset_PnL` | DOUBLE | `asset_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `asset_pnl`). |
| `Forex_PnL` | DOUBLE | `fx_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fx_pnl`). |
| `Forex_Contribution_Pct` | DOUBLE | `fx_contribution_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_contribution_pct`). |
| `Absolute_Return` | DOUBLE | `absolute_return` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `absolute_return`). |
| `XIRR` | DOUBLE | `xirr` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `xirr`). |
| `After_Tax_XIRR` | DOUBLE | `after_tax_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `after_tax_xirr`). |
| `BM_XIRR` | DOUBLE | `benchmark_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr`). |
| `Active_Return` | DOUBLE | `active_return` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return`). |
| `Max_Drawdown` | DOUBLE | `max_drawdown` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `max_drawdown`). |
| `Weight` | DOUBLE | `weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `weight`). |
| `Unrealized_Gain` | DOUBLE | `unrealized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_gain`). |
| `Unrealized_Loss` | DOUBLE | `unrealized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_loss`). |
| `FY_Realized_Gain` | DOUBLE | `fy_realized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_gain`). |
| `FY_Realized_Loss` | DOUBLE | `fy_realized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_loss`). |
| `FY_Realized_Net_PnL` | DOUBLE | `fy_realized_net_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_net_pnl`). |


### `gold.Investment_By_Portfolio` -> `gold.investment_by_portfolio`
**Domain:** Investments | **Grain:** Date | **Producer:** InvestmentQuantEngine | **Columns:** 21

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Closing_Date` | DATE NOT NULL | `closing_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `closing_date`). |
| `Total_Invested_Value` | DOUBLE | `total_invested_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_invested_value`). |
| `Total_Current_Value` | DOUBLE | `total_current_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_current_value`). |
| `Total_Quantity` | DOUBLE | `total_quantity` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_quantity`). |
| `Total_Stocks` | DOUBLE | `total_stocks` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_stocks`). |
| `Unrealized_PL` | DOUBLE | `unrealized_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_pnl`). |
| `Asset_PnL` | DOUBLE | `asset_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `asset_pnl`). |
| `Forex_PnL` | DOUBLE | `fx_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fx_pnl`). |
| `Forex_Contribution_Pct` | DOUBLE | `fx_contribution_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_contribution_pct`). |
| `Absolute_Return` | DOUBLE | `absolute_return` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `absolute_return`). |
| `XIRR` | DOUBLE | `xirr` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `xirr`). |
| `After_Tax_XIRR` | DOUBLE | `after_tax_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `after_tax_xirr`). |
| `BM_XIRR` | DOUBLE | `benchmark_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr`). |
| `Active_Return` | DOUBLE | `active_return` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return`). |
| `Max_Drawdown` | DOUBLE | `max_drawdown` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `max_drawdown`). |
| `Weight` | DOUBLE | `weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `weight`). |
| `Unrealized_Gain` | DOUBLE | `unrealized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_gain`). |
| `Unrealized_Loss` | DOUBLE | `unrealized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_loss`). |
| `FY_Realized_Gain` | DOUBLE | `fy_realized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_gain`). |
| `FY_Realized_Loss` | DOUBLE | `fy_realized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_loss`). |
| `FY_Realized_Net_PnL` | DOUBLE | `fy_realized_net_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_net_pnl`). |


### `gold.Investment_By_Geo` -> `gold.investment_by_geo`
**Domain:** Investments | **Grain:** Date-Geo | **Producer:** InvestmentQuantEngine | **Columns:** 22

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Closing_Date` | DATE NOT NULL | `closing_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `closing_date`). |
| `GEO` | TEXT NOT NULL | `geo` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `geo`). |
| `Total_Invested_Value` | DOUBLE | `total_invested_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_invested_value`). |
| `Total_Current_Value` | DOUBLE | `total_current_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_current_value`). |
| `Total_Quantity` | DOUBLE | `total_quantity` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_quantity`). |
| `Total_Stocks` | DOUBLE | `total_stocks` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_stocks`). |
| `Unrealized_PL` | DOUBLE | `unrealized_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_pnl`). |
| `Asset_PnL` | DOUBLE | `asset_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `asset_pnl`). |
| `Forex_PnL` | DOUBLE | `fx_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fx_pnl`). |
| `Forex_Contribution_Pct` | DOUBLE | `fx_contribution_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_contribution_pct`). |
| `Absolute_Return` | DOUBLE | `absolute_return` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `absolute_return`). |
| `XIRR` | DOUBLE | `xirr` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `xirr`). |
| `After_Tax_XIRR` | DOUBLE | `after_tax_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `after_tax_xirr`). |
| `BM_XIRR` | DOUBLE | `benchmark_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr`). |
| `Active_Return` | DOUBLE | `active_return` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return`). |
| `Max_Drawdown` | DOUBLE | `max_drawdown` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `max_drawdown`). |
| `Weight` | DOUBLE | `weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `weight`). |
| `Unrealized_Gain` | DOUBLE | `unrealized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_gain`). |
| `Unrealized_Loss` | DOUBLE | `unrealized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_loss`). |
| `FY_Realized_Gain` | DOUBLE | `fy_realized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_gain`). |
| `FY_Realized_Loss` | DOUBLE | `fy_realized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_loss`). |
| `FY_Realized_Net_PnL` | DOUBLE | `fy_realized_net_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_net_pnl`). |


### `gold.Investment_By_Country` -> `gold.investment_by_country`
**Domain:** Investments | **Grain:** Date-Country | **Producer:** InvestmentQuantEngine | **Columns:** 31

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Closing_Date` | DATE NOT NULL | `closing_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `closing_date`). |
| `COUNTRY` | TEXT NOT NULL | `country` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `country`). |
| `Total_Invested_Value` | DOUBLE | `total_invested_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_invested_value`). |
| `Total_Current_Value` | DOUBLE | `total_current_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_current_value`). |
| `Total_Quantity` | DOUBLE | `total_quantity` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_quantity`). |
| `Total_Stocks` | DOUBLE | `total_stocks` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_stocks`). |
| `Total_Invested_Value_Local` | DOUBLE | `total_invested_value_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_invested_value_local`). |
| `Total_Current_Value_Local` | DOUBLE | `total_current_value_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_current_value_local`). |
| `Current_FX_Rate` | DOUBLE | `current_fx_rate` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `current_fx_rate`). |
| `Blended_FX_Buy_Rate` | DOUBLE | `blended_fx_buy_rate` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `blended_fx_buy_rate`). |
| `Currency_Appreciation_Pct` | DOUBLE | `currency_appreciation_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `currency_appreciation_pct`). |
| `Unrealized_PL` | DOUBLE | `unrealized_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_pnl`). |
| `Asset_PnL` | DOUBLE | `asset_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `asset_pnl`). |
| `Forex_PnL` | DOUBLE | `fx_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fx_pnl`). |
| `Forex_Contribution_Pct` | DOUBLE | `fx_contribution_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_contribution_pct`). |
| `Absolute_Return` | DOUBLE | `absolute_return` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `absolute_return`). |
| `XIRR` | DOUBLE | `xirr` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `xirr`). |
| `After_Tax_XIRR` | DOUBLE | `after_tax_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `after_tax_xirr`). |
| `BM_XIRR` | DOUBLE | `benchmark_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr`). |
| `Active_Return` | DOUBLE | `active_return` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return`). |
| `XIRR_Local` | DOUBLE | `xirr_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `xirr_local`). |
| `BM_XIRR_Local` | DOUBLE | `benchmark_xirr_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr_local`). |
| `Active_Return_Local` | DOUBLE | `active_return_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return_local`). |
| `FX_XIRR_Impact` | DOUBLE | `fx_xirr_impact` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_xirr_impact`). |
| `Max_Drawdown` | DOUBLE | `max_drawdown` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `max_drawdown`). |
| `Weight` | DOUBLE | `weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `weight`). |
| `Unrealized_Gain` | DOUBLE | `unrealized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_gain`). |
| `Unrealized_Loss` | DOUBLE | `unrealized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_loss`). |
| `FY_Realized_Gain` | DOUBLE | `fy_realized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_gain`). |
| `FY_Realized_Loss` | DOUBLE | `fy_realized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_loss`). |
| `FY_Realized_Net_PnL` | DOUBLE | `fy_realized_net_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_net_pnl`). |


### `gold.Investment_By_Currency` -> `gold.investment_by_currency`
**Domain:** Investments | **Grain:** Date-Currency | **Producer:** InvestmentQuantEngine | **Columns:** 31

| Current Column | Type | Target Name | Disposition | Classification | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `Closing_Date` | DATE NOT NULL | `closing_date` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `closing_date`). |
| `CURRENCY_ID` | TEXT NOT NULL | `currency_id` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `currency_id`). |
| `Total_Invested_Value` | DOUBLE | `total_invested_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_invested_value`). |
| `Total_Current_Value` | DOUBLE | `total_current_value` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_current_value`). |
| `Total_Quantity` | DOUBLE | `total_quantity` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `total_quantity`). |
| `Total_Stocks` | DOUBLE | `total_stocks` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_stocks`). |
| `Total_Invested_Value_Local` | DOUBLE | `total_invested_value_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_invested_value_local`). |
| `Total_Current_Value_Local` | DOUBLE | `total_current_value_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `total_current_value_local`). |
| `Current_FX_Rate` | DOUBLE | `current_fx_rate` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `current_fx_rate`). |
| `Blended_FX_Buy_Rate` | DOUBLE | `blended_fx_buy_rate` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `blended_fx_buy_rate`). |
| `Currency_Appreciation_Pct` | DOUBLE | `currency_appreciation_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `currency_appreciation_pct`). |
| `Unrealized_PL` | DOUBLE | `unrealized_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_pnl`). |
| `Asset_PnL` | DOUBLE | `asset_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `asset_pnl`). |
| `Forex_PnL` | DOUBLE | `fx_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fx_pnl`). |
| `Forex_Contribution_Pct` | DOUBLE | `fx_contribution_pct` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_contribution_pct`). |
| `Absolute_Return` | DOUBLE | `absolute_return` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `absolute_return`). |
| `XIRR` | DOUBLE | `xirr` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `xirr`). |
| `XIRR_Local` | DOUBLE | `xirr_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `xirr_local`). |
| `FX_XIRR_Impact` | DOUBLE | `fx_xirr_impact` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `fx_xirr_impact`). |
| `After_Tax_XIRR` | DOUBLE | `after_tax_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `after_tax_xirr`). |
| `BM_XIRR` | DOUBLE | `benchmark_xirr` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr`). |
| `BM_XIRR_Local` | DOUBLE | `benchmark_xirr_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `benchmark_xirr_local`). |
| `Active_Return` | DOUBLE | `active_return` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return`). |
| `Active_Return_Local` | DOUBLE | `active_return_local` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `active_return_local`). |
| `Max_Drawdown` | DOUBLE | `max_drawdown` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `max_drawdown`). |
| `Weight` | DOUBLE | `weight` | 🏷️ RENAME | `vocabulary_alignment` | Standardize casing, eliminate quotes/percentages, or align with canonical vocabulary (canonical target: `weight`). |
| `Unrealized_Gain` | DOUBLE | `unrealized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_gain`). |
| `Unrealized_Loss` | DOUBLE | `unrealized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `unrealized_loss`). |
| `FY_Realized_Gain` | DOUBLE | `fy_realized_gain` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_gain`). |
| `FY_Realized_Loss` | DOUBLE | `fy_realized_loss` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_loss`). |
| `FY_Realized_Net_PnL` | DOUBLE | `fy_realized_net_pnl` | 🛡️ PROTECTED | `canonical_identity` | Critical business key, deterministic temporal identity, or invariant financial aggregate (canonical target: `fy_realized_net_pnl`). |


---

## 6. Shared Investment Aggregate Metric DDL Helper Specification

Ten Gold investment tables (`gold.Investment_By_*`) repeat identical aggregate metric blocks.
In Phase 010, the following reusable SQL snippet constants will be introduced into `schema/gold.py` to ensure schema consistency:

```python
CORE_INVESTMENT_AGGREGATE_METRICS_SQL = """
    total_invested_value DOUBLE,
    total_current_value DOUBLE,
    total_quantity DOUBLE,
    total_stocks DOUBLE,
    -- Absolute Returns
    unrealized_pnl DOUBLE,
    asset_pnl DOUBLE,
    fx_pnl DOUBLE,
    fx_contribution_pct DOUBLE,
    absolute_return DOUBLE,
    -- Performance Returns
    xirr DOUBLE,
    after_tax_xirr DOUBLE,
    -- Benchmark Comparisons
    benchmark_xirr DOUBLE,
    active_return DOUBLE,
    -- Risk & Weights
    max_drawdown DOUBLE,
    weight DOUBLE,
    -- Tax & Harvesting
    unrealized_gain DOUBLE,
    unrealized_loss DOUBLE,
    fy_realized_gain DOUBLE,
    fy_realized_loss DOUBLE,
    fy_realized_net_pnl DOUBLE
"""
```

---

## 7. Power BI Forward Column Mapping Matrix

For all downstream analytical consumers and Power BI reports, this reference provides the 1:1 field mappings from legacy physical columns to target physical columns:

| Legacy Table | Legacy Column | Target Table | Target Column | Role |
| :--- | :--- | :--- | :--- | :--- |
| `gold.Tax_Year_Summary` | `FY` | `gold.tax_financial_year_summary` | `financial_year` | 🛡️ PROTECTED |
| `gold.Tax_Year_Summary` | `Total_Ledger_Income` | `gold.tax_financial_year_summary` | `total_ledger_income` | 🛡️ PROTECTED |
| `gold.Tax_Year_Summary` | `Total_Investment_Gain_Loss` | `gold.tax_financial_year_summary` | `total_investment_gain_loss` | 🛡️ PROTECTED |
| `gold.Tax_Year_Summary` | `Total_Tax_Credits` | `gold.tax_financial_year_summary` | `total_tax_credits` | 🛡️ PROTECTED |
| `gold.Tax_Year_Summary` | `Total_Estimated_Investment_Tax` | `gold.tax_financial_year_summary` | `total_estimated_investment_tax` | 🛡️ PROTECTED |
| `gold.Tax_Year_Summary` | `Investment_Tax_Estimate_Count` | `gold.tax_financial_year_summary` | `investment_tax_estimate_count` | 🏷️ RENAME |
| `gold.Tax_Year_Summary` | `Investment_Tax_Estimate_Missing_Count` | `gold.tax_financial_year_summary` | `investment_tax_estimate_missing_count` | 🏷️ RENAME |
| `gold.Tax_Year_Summary` | `Investment_Tax_Estimate_Complete` | `gold.tax_financial_year_summary` | `investment_tax_estimate_complete` | 🏷️ RENAME |
| `gold.Tax_Year_Summary` | `Total_Estimated_Ledger_Tax` | `gold.tax_financial_year_summary` | `total_estimated_ledger_tax` | 🛡️ PROTECTED |
| `gold.Tax_Year_Summary` | `Ledger_Tax_Estimate_Count` | `gold.tax_financial_year_summary` | `ledger_tax_estimate_count` | 🏷️ RENAME |
| `gold.Tax_Year_Summary` | `Ledger_Tax_Estimate_Missing_Count` | `gold.tax_financial_year_summary` | `ledger_tax_estimate_missing_count` | 🏷️ RENAME |
| `gold.Tax_Year_Summary` | `Ledger_Tax_Estimate_Complete` | `gold.tax_financial_year_summary` | `ledger_tax_estimate_complete` | 🏷️ RENAME |
| `gold.Tax_Year_Summary` | `Total_Event_Count` | `gold.tax_financial_year_summary` | `total_event_count` | 🏷️ RENAME |
| `gold.Tax_Year_Summary` | `Ready_Count` | `gold.tax_financial_year_summary` | `ready_count` | 🏷️ RENAME |
| `gold.Tax_Year_Summary` | `Check_Required_Count` | `gold.tax_financial_year_summary` | `check_required_count` | 🏷️ RENAME |
| `gold.Tax_Income_Breakdown` | `FY` | `gold.tax_income_breakdown` | `financial_year` | 🛡️ PROTECTED |
| `gold.Tax_Income_Breakdown` | `Income_Head` | `gold.tax_income_breakdown` | `income_head` | 🏷️ RENAME |
| `gold.Tax_Income_Breakdown` | `Tax_Sub_Head` | `gold.tax_income_breakdown` | `tax_sub_head` | 🏷️ RENAME |
| `gold.Tax_Income_Breakdown` | `Source_Type` | `gold.tax_income_breakdown` | `source_type` | 🏷️ RENAME |
| `gold.Tax_Income_Breakdown` | `Event_Amount_INR` | `gold.tax_income_breakdown` | `event_amount_inr` | 🏷️ RENAME |
| `gold.Tax_Income_Breakdown` | `Estimated_Tax_INR` | `gold.tax_income_breakdown` | `estimated_tax_inr` | 🏷️ RENAME |
| `gold.Tax_Income_Breakdown` | `Estimated_Tax_Event_Count` | `gold.tax_income_breakdown` | `estimated_tax_event_count` | 🏷️ RENAME |
| `gold.Tax_Income_Breakdown` | `Estimated_Tax_Missing_Count` | `gold.tax_income_breakdown` | `estimated_tax_missing_count` | 🏷️ RENAME |
| `gold.Tax_Income_Breakdown` | `Estimated_Tax_Complete` | `gold.tax_income_breakdown` | `estimated_tax_complete` | 🏷️ RENAME |
| `gold.Tax_Income_Breakdown` | `Event_Count` | `gold.tax_income_breakdown` | `event_count` | 🏷️ RENAME |
| `gold.Tax_Income_Breakdown` | `Ready_Count` | `gold.tax_income_breakdown` | `ready_count` | 🏷️ RENAME |
| `gold.Tax_Income_Breakdown` | `Check_Required_Count` | `gold.tax_income_breakdown` | `check_required_count` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `FY` | `gold.tax_reconciliation` | `financial_year` | 🛡️ PROTECTED |
| `gold.Tax_Reconciliation` | `Tax_Sub_Head` | `gold.tax_reconciliation` | `tax_sub_head` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Ledger_Tax_Event_Amount` | `gold.tax_reconciliation` | `ledger_tax_event_amount` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Excluded_Non_Taxable_Amount` | `gold.tax_reconciliation` | `excluded_non_taxable_amount` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Excluded_Non_Taxable_Event_Count` | `gold.tax_reconciliation` | `excluded_non_taxable_event_count` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Excluded_Investment_Ledger_Amount` | `gold.tax_reconciliation` | `excluded_investment_ledger_amount` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Excluded_Investment_Ledger_Event_Count` | `gold.tax_reconciliation` | `excluded_investment_ledger_event_count` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Quant_Realized_Gain_Loss` | `gold.tax_reconciliation` | `quant_realized_gain_loss` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Estimated_Investment_Tax` | `gold.tax_reconciliation` | `estimated_investment_tax` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Estimated_Tax_Event_Count` | `gold.tax_reconciliation` | `estimated_tax_event_count` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Estimated_Tax_Missing_Count` | `gold.tax_reconciliation` | `estimated_tax_missing_count` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Estimated_Investment_Tax_Complete` | `gold.tax_reconciliation` | `estimated_investment_tax_complete` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Estimated_Ledger_Tax` | `gold.tax_reconciliation` | `estimated_ledger_tax` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Ledger_Tax_Estimate_Count` | `gold.tax_reconciliation` | `ledger_tax_estimate_count` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Ledger_Tax_Estimate_Missing_Count` | `gold.tax_reconciliation` | `ledger_tax_estimate_missing_count` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Estimated_Ledger_Tax_Complete` | `gold.tax_reconciliation` | `estimated_ledger_tax_complete` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Tax_Credit_Amount` | `gold.tax_reconciliation` | `tax_credit_amount` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Tax_Event_Amount` | `gold.tax_reconciliation` | `tax_event_amount` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Investment_Source_Difference_INR` | `gold.tax_reconciliation` | `investment_source_difference_inr` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Ledger_Event_Count` | `gold.tax_reconciliation` | `ledger_event_count` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Quant_Event_Count` | `gold.tax_reconciliation` | `quant_event_count` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Tax_Credit_Event_Count` | `gold.tax_reconciliation` | `tax_credit_event_count` | 🏷️ RENAME |
| `gold.Tax_Reconciliation` | `Check_Required_Count` | `gold.tax_reconciliation` | `check_required_count` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `MONTH_START_DATE` | `gold.wealth_asset_breakdown` | `month_start_date` | 🛡️ PROTECTED |
| `gold.Wealth_Asset_Breakdown` | `MONTH_END_DATE` | `gold.wealth_asset_breakdown` | `month_end_date` | 🛡️ PROTECTED |
| `gold.Wealth_Asset_Breakdown` | `ASSET_SUBCATEGORY_ID` | `gold.wealth_asset_breakdown` | `asset_subcategory_id` | 🛡️ PROTECTED |
| `gold.Wealth_Asset_Breakdown` | `Opening_Balance` | `gold.wealth_asset_breakdown` | `opening_balance` | 🛡️ PROTECTED |
| `gold.Wealth_Asset_Breakdown` | `Closing_Balance` | `gold.wealth_asset_breakdown` | `closing_balance` | 🛡️ PROTECTED |
| `gold.Wealth_Asset_Breakdown` | `Closing_Balance_Market` | `gold.wealth_asset_breakdown` | `closing_balance_market` | 🛡️ PROTECTED |
| `gold.Wealth_Asset_Breakdown` | `All_Time_High_Balance` | `gold.wealth_asset_breakdown` | `all_time_high_balance` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Liquid_Assets` | `gold.wealth_asset_breakdown` | `liquid_assets` | 🛡️ PROTECTED |
| `gold.Wealth_Asset_Breakdown` | `Liquid_Assets_Market` | `gold.wealth_asset_breakdown` | `liquid_assets_market` | 🛡️ PROTECTED |
| `gold.Wealth_Asset_Breakdown` | `Closing_Asset_PnL` | `gold.wealth_asset_breakdown` | `closing_asset_pnl` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Closing_Forex_PnL` | `gold.wealth_asset_breakdown` | `closing_fx_pnl` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `MoM_Balance_Growth_%` | `gold.wealth_asset_breakdown` | `mom_balance_growth_pct` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `YoY_Balance_Growth_%` | `gold.wealth_asset_breakdown` | `yoy_balance_growth_pct` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Organic_Growth_Value` | `gold.wealth_asset_breakdown` | `organic_growth_value` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Organic_Yield_%` | `gold.wealth_asset_breakdown` | `organic_yield_pct` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Drawdown_From_Peak` | `gold.wealth_asset_breakdown` | `drawdown_from_peak` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Investment_Contribution_Pct` | `gold.wealth_asset_breakdown` | `investment_contribution_pct` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Savings_to_NW_Ratio` | `gold.wealth_asset_breakdown` | `savings_to_nw_ratio` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Income_Inflow` | `gold.wealth_asset_breakdown` | `income_inflow` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Cash_Income_Inflow` | `gold.wealth_asset_breakdown` | `cash_income_inflow` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Non_Cash_Income_Inflow` | `gold.wealth_asset_breakdown` | `non_cash_income_inflow` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Expense_Outflow` | `gold.wealth_asset_breakdown` | `expense_outflow` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Core_Expense_Outflow` | `gold.wealth_asset_breakdown` | `core_expense_outflow` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Cash_Expense_Outflow` | `gold.wealth_asset_breakdown` | `cash_expense_outflow` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Non_Cash_Expense_Outflow` | `gold.wealth_asset_breakdown` | `non_cash_expense_outflow` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Net_Transfers` | `gold.wealth_asset_breakdown` | `net_transfers` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Net_Cashflow_Month` | `gold.wealth_asset_breakdown` | `net_cashflow_month` | 🛡️ PROTECTED |
| `gold.Wealth_Asset_Breakdown` | `Surplus_Deficit_Month` | `gold.wealth_asset_breakdown` | `surplus_deficit_month` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Cumulative_Net_Savings` | `gold.wealth_asset_breakdown` | `cumulative_net_savings` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `3M_Avg_Expense` | `gold.wealth_asset_breakdown` | `trailing_3m_avg_expense` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `3M_Avg_Core_Expense` | `gold.wealth_asset_breakdown` | `trailing_3m_avg_core_expense` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `3M_Avg_Income` | `gold.wealth_asset_breakdown` | `trailing_3m_avg_income` | 🏷️ RENAME |
| `gold.Wealth_Asset_Breakdown` | `Months_of_Runway` | `gold.wealth_asset_breakdown` | `months_of_runway` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `MONTH_START_DATE` | `gold.core_monthly_fact` | `month_start_date` | 🛡️ PROTECTED |
| `gold.Core_Monthly_Fact` | `MONTH_END_DATE` | `gold.core_monthly_fact` | `month_end_date` | 🛡️ PROTECTED |
| `gold.Core_Monthly_Fact` | `Months_Elapsed` | `gold.core_monthly_fact` | `months_elapsed` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Total_Income` | `gold.core_monthly_fact` | `total_income` | 🛡️ PROTECTED |
| `gold.Core_Monthly_Fact` | `Total_Cash_Income` | `gold.core_monthly_fact` | `total_cash_income` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Total_Non_Cash_Income` | `gold.core_monthly_fact` | `total_non_cash_income` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Total_Expense` | `gold.core_monthly_fact` | `total_expense` | 🛡️ PROTECTED |
| `gold.Core_Monthly_Fact` | `Total_Core_Expense` | `gold.core_monthly_fact` | `total_core_expense` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Total_Cash_Expense` | `gold.core_monthly_fact` | `total_cash_expense` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Total_Non_Cash_Expense` | `gold.core_monthly_fact` | `total_non_cash_expense` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Net_Cashflow_Month` | `gold.core_monthly_fact` | `net_cashflow_month` | 🛡️ PROTECTED |
| `gold.Core_Monthly_Fact` | `Opening_Balance_Asset` | `gold.core_monthly_fact` | `opening_balance_asset` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Opening_Balance_Asset_Market` | `gold.core_monthly_fact` | `opening_balance_asset_market` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Closing_Balance_Asset` | `gold.core_monthly_fact` | `closing_balance_asset` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Closing_Balance_Asset_Market` | `gold.core_monthly_fact` | `closing_balance_asset_market` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Asset_Delta` | `gold.core_monthly_fact` | `asset_delta` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Asset_Market_Delta` | `gold.core_monthly_fact` | `asset_market_delta` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Total_Assets` | `gold.core_monthly_fact` | `total_assets` | 🛡️ PROTECTED |
| `gold.Core_Monthly_Fact` | `Total_Assets_Market` | `gold.core_monthly_fact` | `total_assets_market` | 🛡️ PROTECTED |
| `gold.Core_Monthly_Fact` | `Opening_Investment_Book_Value` | `gold.core_monthly_fact` | `opening_investment_book_value` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Closing_Investment_Book_Value` | `gold.core_monthly_fact` | `closing_investment_book_value` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Investment_Book_Value_Delta` | `gold.core_monthly_fact` | `investment_book_value_delta` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Opening_Investment_Market_Value` | `gold.core_monthly_fact` | `opening_investment_market_value` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Closing_Investment_Market_Value` | `gold.core_monthly_fact` | `closing_investment_market_value` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Investment_Market_Value_Delta` | `gold.core_monthly_fact` | `investment_market_value_delta` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Liquid_Assets` | `gold.core_monthly_fact` | `liquid_assets` | 🛡️ PROTECTED |
| `gold.Core_Monthly_Fact` | `Liquid_Assets_Market` | `gold.core_monthly_fact` | `liquid_assets_market` | 🛡️ PROTECTED |
| `gold.Core_Monthly_Fact` | `Total_Liabilities` | `gold.core_monthly_fact` | `total_liabilities` | 🛡️ PROTECTED |
| `gold.Core_Monthly_Fact` | `Total_Net_Worth` | `gold.core_monthly_fact` | `total_net_worth` | 🛡️ PROTECTED |
| `gold.Core_Monthly_Fact` | `Total_Net_Worth_Market` | `gold.core_monthly_fact` | `total_net_worth_market` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Total_Foreign_Currency_Exposure` | `gold.core_monthly_fact` | `total_foreign_currency_exposure` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Opening_Unrealized_PL` | `gold.core_monthly_fact` | `opening_unrealized_pnl` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Closing_Unrealized_PL` | `gold.core_monthly_fact` | `closing_unrealized_pnl` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Closing_Asset_PnL` | `gold.core_monthly_fact` | `closing_asset_pnl` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Closing_Forex_PnL` | `gold.core_monthly_fact` | `closing_fx_pnl` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Opening_Investment_XIRR` | `gold.core_monthly_fact` | `opening_investment_xirr` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Closing_Investment_XIRR` | `gold.core_monthly_fact` | `closing_investment_xirr` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `Foreign_Exposure_Pct` | `gold.core_monthly_fact` | `foreign_exposure_pct` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `CPI_INDEX` | `gold.core_monthly_fact` | `cpi_index` | 🏷️ RENAME |
| `gold.Core_Monthly_Fact` | `INFLATION_YOY_PCT` | `gold.core_monthly_fact` | `inflation_yoy_pct` | 🏷️ RENAME |
| `gold.Cashflow_Expense_Breakdown` | `MONTH_START_DATE` | `gold.cashflow_expense_breakdown` | `month_start_date` | 🛡️ PROTECTED |
| `gold.Cashflow_Expense_Breakdown` | `MONTH_END_DATE` | `gold.cashflow_expense_breakdown` | `month_end_date` | 🛡️ PROTECTED |
| `gold.Cashflow_Expense_Breakdown` | `YEAR_MONTH` | `gold.cashflow_expense_breakdown` | `year_month` | 🛡️ PROTECTED |
| `gold.Cashflow_Expense_Breakdown` | `CATEGORY_ID` | `gold.cashflow_expense_breakdown` | `category_id` | 🛡️ PROTECTED |
| `gold.Cashflow_Expense_Breakdown` | `CATEGORY_NAME` | `gold.cashflow_expense_breakdown` | `category_name` | 🏷️ RENAME |
| `gold.Cashflow_Expense_Breakdown` | `CATEGORY_GROUPS` | `gold.cashflow_expense_breakdown` | `category_groups` | 🏷️ RENAME |
| `gold.Cashflow_Expense_Breakdown` | `Spend_Type` | `gold.cashflow_expense_breakdown` | `spend_type` | 🏷️ RENAME |
| `gold.Cashflow_Expense_Breakdown` | `Is_Core_Expense` | `gold.cashflow_expense_breakdown` | `is_core_expense` | 🏷️ RENAME |
| `gold.Cashflow_Expense_Breakdown` | `Is_Investment` | `gold.cashflow_expense_breakdown` | `is_investment` | 🏷️ RENAME |
| `gold.Cashflow_Expense_Breakdown` | `Is_Discretionary` | `gold.cashflow_expense_breakdown` | `is_discretionary` | 🏷️ RENAME |
| `gold.Cashflow_Expense_Breakdown` | `Total_Monthly_Spend` | `gold.cashflow_expense_breakdown` | `total_monthly_spend` | 🏷️ RENAME |
| `gold.Cashflow_Expense_Breakdown` | `Cash_Spend` | `gold.cashflow_expense_breakdown` | `cash_spend` | 🏷️ RENAME |
| `gold.Cashflow_Expense_Breakdown` | `Non_Cash_Spend` | `gold.cashflow_expense_breakdown` | `non_cash_spend` | 🏷️ RENAME |
| `gold.Cashflow_Expense_Breakdown` | `Trailing_3M_Avg_Spend` | `gold.cashflow_expense_breakdown` | `trailing_3_m_avg_spend` | 🏷️ RENAME |
| `gold.Cashflow_Expense_Breakdown` | `Cumulative_YTD_Spend` | `gold.cashflow_expense_breakdown` | `cumulative_ytd_spend` | 🏷️ RENAME |
| `gold.Cashflow_Income_Breakdown` | `MONTH_START_DATE` | `gold.cashflow_income_breakdown` | `month_start_date` | 🛡️ PROTECTED |
| `gold.Cashflow_Income_Breakdown` | `MONTH_END_DATE` | `gold.cashflow_income_breakdown` | `month_end_date` | 🛡️ PROTECTED |
| `gold.Cashflow_Income_Breakdown` | `YEAR_MONTH` | `gold.cashflow_income_breakdown` | `year_month` | 🛡️ PROTECTED |
| `gold.Cashflow_Income_Breakdown` | `CATEGORY_ID` | `gold.cashflow_income_breakdown` | `category_id` | 🛡️ PROTECTED |
| `gold.Cashflow_Income_Breakdown` | `CATEGORY_NAME` | `gold.cashflow_income_breakdown` | `category_name` | 🏷️ RENAME |
| `gold.Cashflow_Income_Breakdown` | `CATEGORY_GROUPS` | `gold.cashflow_income_breakdown` | `category_groups` | 🏷️ RENAME |
| `gold.Cashflow_Income_Breakdown` | `Is_Active_Income` | `gold.cashflow_income_breakdown` | `is_active_income` | 🏷️ RENAME |
| `gold.Cashflow_Income_Breakdown` | `Is_Passive_Income` | `gold.cashflow_income_breakdown` | `is_passive_income` | 🏷️ RENAME |
| `gold.Cashflow_Income_Breakdown` | `Is_Dividend_Income` | `gold.cashflow_income_breakdown` | `is_dividend_income` | 🏷️ RENAME |
| `gold.Cashflow_Income_Breakdown` | `Is_Interest_Income` | `gold.cashflow_income_breakdown` | `is_interest_income` | 🏷️ RENAME |
| `gold.Cashflow_Income_Breakdown` | `Is_Non_Cash_Income` | `gold.cashflow_income_breakdown` | `is_non_cash_income` | 🏷️ RENAME |
| `gold.Cashflow_Income_Breakdown` | `Total_Monthly_Income` | `gold.cashflow_income_breakdown` | `total_monthly_income` | 🏷️ RENAME |
| `gold.Cashflow_Income_Breakdown` | `Trailing_3M_Avg_Income` | `gold.cashflow_income_breakdown` | `trailing_3_m_avg_income` | 🏷️ RENAME |
| `gold.Cashflow_Income_Breakdown` | `Cumulative_YTD_Income` | `gold.cashflow_income_breakdown` | `cumulative_ytd_income` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `MONTH_START_DATE` | `gold.wealth_fire_analytics` | `month_start_date` | 🛡️ PROTECTED |
| `gold.Wealth_FIRE_Analytics` | `MONTH_END_DATE` | `gold.wealth_fire_analytics` | `month_end_date` | 🛡️ PROTECTED |
| `gold.Wealth_FIRE_Analytics` | `YEAR_MONTH` | `gold.wealth_fire_analytics` | `year_month` | 🛡️ PROTECTED |
| `gold.Wealth_FIRE_Analytics` | `Projected_FI_Date_P50` | `gold.wealth_fire_analytics` | `projected_fi_date_p50` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Total_Income` | `gold.wealth_fire_analytics` | `total_income` | 🛡️ PROTECTED |
| `gold.Wealth_FIRE_Analytics` | `Total_Cash_Income` | `gold.wealth_fire_analytics` | `total_cash_income` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Trailing_6M_Avg_Spend` | `gold.wealth_fire_analytics` | `trailing_6_m_avg_spend` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Trailing_12M_Avg_Spend` | `gold.wealth_fire_analytics` | `trailing_12_m_avg_spend` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Trailing_6M_Avg_Savings` | `gold.wealth_fire_analytics` | `trailing_6_m_avg_savings` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Trailing_12M_Avg_Savings` | `gold.wealth_fire_analytics` | `trailing_12_m_avg_savings` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Target_FI_Today` | `gold.wealth_fire_analytics` | `target_fi_today` | 🛡️ PROTECTED |
| `gold.Wealth_FIRE_Analytics` | `Coast_FI_Today` | `gold.wealth_fire_analytics` | `coast_fi_today` | 🛡️ PROTECTED |
| `gold.Wealth_FIRE_Analytics` | `Lean_FI_Today` | `gold.wealth_fire_analytics` | `lean_fi_today` | 🛡️ PROTECTED |
| `gold.Wealth_FIRE_Analytics` | `Target_FI_Total_Future_Nominal` | `gold.wealth_fire_analytics` | `target_fi_total_future_nominal` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `FI_Gap` | `gold.wealth_fire_analytics` | `fi_gap` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `FI_Gap_Monthly_Trend` | `gold.wealth_fire_analytics` | `fi_gap_monthly_trend` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Terminal_Wealth_Nominal_P50` | `gold.wealth_fire_analytics` | `terminal_wealth_nominal_p50` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Real_Return_Assumed_Pct` | `gold.wealth_fire_analytics` | `real_return_assumed_pct` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Wealth_Velocity` | `gold.wealth_fire_analytics` | `wealth_velocity` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Wealth_Acceleration` | `gold.wealth_fire_analytics` | `wealth_acceleration` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Real_NW_CAGR_3Y` | `gold.wealth_fire_analytics` | `real_nw_cagr_3_y` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Current_FI_Coverage_Pct` | `gold.wealth_fire_analytics` | `current_fi_coverage_pct` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Estimated_Months_To_FI_Linear` | `gold.wealth_fire_analytics` | `estimated_months_to_fi_linear` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Months_To_FI_Conservative_P90` | `gold.wealth_fire_analytics` | `months_to_fi_conservative_p90` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Months_To_FI_Base_P50` | `gold.wealth_fire_analytics` | `months_to_fi_base_p50` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Months_To_FI_Aggressive_P10` | `gold.wealth_fire_analytics` | `months_to_fi_aggressive_p10` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Probability_Of_Success_Pct` | `gold.wealth_fire_analytics` | `probability_of_success_pct` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Years_To_FI_P50` | `gold.wealth_fire_analytics` | `years_to_fi_p50` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Runway_Months_Linear` | `gold.wealth_fire_analytics` | `runway_months_linear` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Runway_Months_Stressed_P10` | `gold.wealth_fire_analytics` | `runway_months_stressed_p10` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Runway_Months_Base_P50` | `gold.wealth_fire_analytics` | `runway_months_base_p50` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Withdrawal_Rate_If_Retired_Now` | `gold.wealth_fire_analytics` | `withdrawal_rate_if_retired_now` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Savings_Rate_Required` | `gold.wealth_fire_analytics` | `savings_rate_required` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `Savings_Rate_Actual` | `gold.wealth_fire_analytics` | `savings_rate_actual` | 🏷️ RENAME |
| `gold.Wealth_FIRE_Analytics` | `FI_Velocity` | `gold.wealth_fire_analytics` | `fi_velocity` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `MONTH_START_DATE` | `gold.forecast_budget_variance` | `month_start_date` | 🛡️ PROTECTED |
| `gold.Forecast_Budget_Variance` | `MONTH_END_DATE` | `gold.forecast_budget_variance` | `month_end_date` | 🛡️ PROTECTED |
| `gold.Forecast_Budget_Variance` | `YEAR_MONTH` | `gold.forecast_budget_variance` | `year_month` | 🛡️ PROTECTED |
| `gold.Forecast_Budget_Variance` | `Is_Core_Overspent` | `gold.forecast_budget_variance` | `is_core_overspent` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Is_NonCore_Overspent` | `gold.forecast_budget_variance` | `is_non_core_overspent` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Is_Investment_Underfunded` | `gold.forecast_budget_variance` | `is_investment_underfunded` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Is_Income_Volatile` | `gold.forecast_budget_variance` | `is_income_volatile` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Is_Budget_Month_Healthy` | `gold.forecast_budget_variance` | `is_budget_month_healthy` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Total_Income` | `gold.forecast_budget_variance` | `total_income` | 🛡️ PROTECTED |
| `gold.Forecast_Budget_Variance` | `Actual_Income` | `gold.forecast_budget_variance` | `actual_income` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Budget_Income` | `gold.forecast_budget_variance` | `budget_income` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Budget_Core_Expense_Target` | `gold.forecast_budget_variance` | `budget_core_expense_target` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Budget_NonCore_Expense_Target` | `gold.forecast_budget_variance` | `budget_non_core_expense_target` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Budget_Investment_Target` | `gold.forecast_budget_variance` | `budget_investment_target` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Budget_Surplus_Buffer` | `gold.forecast_budget_variance` | `budget_surplus_buffer` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Budget_Total_Expense_Target` | `gold.forecast_budget_variance` | `budget_total_expense_target` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Actual_Core_Expense` | `gold.forecast_budget_variance` | `actual_core_expense` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Actual_NonCore_Expense` | `gold.forecast_budget_variance` | `actual_non_core_expense` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Investment_Deployed` | `gold.forecast_budget_variance` | `investment_deployed` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Investment_Redeemed` | `gold.forecast_budget_variance` | `investment_redeemed` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Actual_Investment` | `gold.forecast_budget_variance` | `actual_investment` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Actual_Savings` | `gold.forecast_budget_variance` | `actual_savings` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Emergency_Fund_Gap` | `gold.forecast_budget_variance` | `emergency_fund_gap` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Rule_Core_Pct_Budget` | `gold.forecast_budget_variance` | `rule_core_pct_budget` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Rule_NonCore_Pct_Budget` | `gold.forecast_budget_variance` | `rule_non_core_pct_budget` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Rule_Investment_Pct_Budget` | `gold.forecast_budget_variance` | `rule_investment_pct_budget` | 🏷️ RENAME |
| `gold.Forecast_Budget_Variance` | `Zero_Income_Runway_Months` | `gold.forecast_budget_variance` | `zero_income_runway_months` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `MONTH_START_DATE` | `gold.investment_portfolio_summary` | `month_start_date` | 🛡️ PROTECTED |
| `gold.Investment_Portfolio_Summary` | `Max_Closing_Date` | `gold.investment_portfolio_summary` | `max_closing_date` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN` | `gold.investment_portfolio_summary` | `isin` | 🛡️ PROTECTED |
| `gold.Investment_Portfolio_Summary` | `CURRENCY_ID` | `gold.investment_portfolio_summary` | `currency_id` | 🛡️ PROTECTED |
| `gold.Investment_Portfolio_Summary` | `INSTRUMENT_NAME` | `gold.investment_portfolio_summary` | `instrument_name` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `INSTRUMENT_CLASS` | `gold.investment_portfolio_summary` | `instrument_class` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `INSTRUMENT_TYPE` | `gold.investment_portfolio_summary` | `instrument_type` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `INSTRUMENT_SUBTYPE` | `gold.investment_portfolio_summary` | `instrument_subtype` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `SECTOR` | `gold.investment_portfolio_summary` | `sector` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `Rebalance_Required` | `gold.investment_portfolio_summary` | `rebalance_required` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_Market_Value` | `gold.investment_portfolio_summary` | `isin_market_value` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_Book_Value` | `gold.investment_portfolio_summary` | `isin_book_value` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_Market_Value_Local` | `gold.investment_portfolio_summary` | `isin_market_value_local` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_Book_Value_Local` | `gold.investment_portfolio_summary` | `isin_book_value_local` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_Unrealized_PnL` | `gold.investment_portfolio_summary` | `isin_unrealized_pnl` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_Asset_PnL` | `gold.investment_portfolio_summary` | `isin_asset_pnl` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_Forex_PnL` | `gold.investment_portfolio_summary` | `isin_fx_pnl` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_Forex_Contribution_Pct` | `gold.investment_portfolio_summary` | `isin_fx_contribution_pct` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_XIRR_Local` | `gold.investment_portfolio_summary` | `isin_xirr_local` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_FX_XIRR_Impact` | `gold.investment_portfolio_summary` | `isin_fx_xirr_impact` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_BM_XIRR` | `gold.investment_portfolio_summary` | `isin_benchmark_xirr` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_BM_XIRR_Local` | `gold.investment_portfolio_summary` | `isin_benchmark_xirr_local` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_Active_Return` | `gold.investment_portfolio_summary` | `isin_active_return` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_Active_Return_Local` | `gold.investment_portfolio_summary` | `isin_active_return_local` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_Weight` | `gold.investment_portfolio_summary` | `isin_weight` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `Class_Weight` | `gold.investment_portfolio_summary` | `class_weight` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `Class_Target_Weight` | `gold.investment_portfolio_summary` | `class_target_weight` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `Class_Drift` | `gold.investment_portfolio_summary` | `class_drift` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `Sector_Weight` | `gold.investment_portfolio_summary` | `sector_weight` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `Monthly_Market_Value_Change_Pct` | `gold.investment_portfolio_summary` | `monthly_market_value_change_pct` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `ISIN_Harvestable_Loss` | `gold.investment_portfolio_summary` | `isin_harvestable_loss` | 🏷️ RENAME |
| `gold.Investment_Portfolio_Summary` | `Tax_Harvesting_Priority_Score` | `gold.investment_portfolio_summary` | `tax_harvesting_priority_score` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `MONTH_START_DATE` | `gold.cashflow_efficiency_analytics` | `month_start_date` | 🛡️ PROTECTED |
| `gold.Cashflow_Efficiency_Analytics` | `MONTH_END_DATE` | `gold.cashflow_efficiency_analytics` | `month_end_date` | 🛡️ PROTECTED |
| `gold.Cashflow_Efficiency_Analytics` | `YEAR_MONTH` | `gold.cashflow_efficiency_analytics` | `year_month` | 🛡️ PROTECTED |
| `gold.Cashflow_Efficiency_Analytics` | `Is_Surplus_Month` | `gold.cashflow_efficiency_analytics` | `is_surplus_month` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Is_Investment_Target_Met` | `gold.cashflow_efficiency_analytics` | `is_investment_target_met` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Total_Income` | `gold.cashflow_efficiency_analytics` | `total_income` | 🛡️ PROTECTED |
| `gold.Cashflow_Efficiency_Analytics` | `Total_Cash_Income` | `gold.cashflow_efficiency_analytics` | `total_cash_income` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Total_Non_Cash_Income` | `gold.cashflow_efficiency_analytics` | `total_non_cash_income` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Total_Expense` | `gold.cashflow_efficiency_analytics` | `total_expense` | 🛡️ PROTECTED |
| `gold.Cashflow_Efficiency_Analytics` | `Active_Income` | `gold.cashflow_efficiency_analytics` | `active_income` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Passive_Income` | `gold.cashflow_efficiency_analytics` | `passive_income` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Dividend_Income` | `gold.cashflow_efficiency_analytics` | `dividend_income` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Interest_Income` | `gold.cashflow_efficiency_analytics` | `interest_income` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Core_Expense` | `gold.cashflow_efficiency_analytics` | `core_expense` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `NonCore_Expense` | `gold.cashflow_efficiency_analytics` | `non_core_expense` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Total_Cash_Expense` | `gold.cashflow_efficiency_analytics` | `total_cash_expense` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Total_Non_Cash_Expense` | `gold.cashflow_efficiency_analytics` | `total_non_cash_expense` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Total_Investment_Deployed` | `gold.cashflow_efficiency_analytics` | `total_investment_deployed` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Total_Investment_Redeemed` | `gold.cashflow_efficiency_analytics` | `total_investment_redeemed` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Redemption_Gain_Loss_Value` | `gold.cashflow_efficiency_analytics` | `redemption_gain_loss_value` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Net_Investment_Flow` | `gold.cashflow_efficiency_analytics` | `net_investment_flow` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Gross_Surplus` | `gold.cashflow_efficiency_analytics` | `gross_surplus` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Net_Surplus_After_Invest` | `gold.cashflow_efficiency_analytics` | `net_surplus_after_invest` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Income_MoM_Delta` | `gold.cashflow_efficiency_analytics` | `income_mom_delta` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Expense_MoM_Delta` | `gold.cashflow_efficiency_analytics` | `expense_mom_delta` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Investment_MoM_Delta` | `gold.cashflow_efficiency_analytics` | `investment_mom_delta` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Trailing_3M_Avg_Income` | `gold.cashflow_efficiency_analytics` | `trailing_3_m_avg_income` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Trailing_3M_Avg_Expense` | `gold.cashflow_efficiency_analytics` | `trailing_3_m_avg_expense` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Trailing_3M_Avg_Investment` | `gold.cashflow_efficiency_analytics` | `trailing_3_m_avg_investment` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Savings_Rate_Pct` | `gold.cashflow_efficiency_analytics` | `savings_rate_pct` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Investment_Rate_Pct` | `gold.cashflow_efficiency_analytics` | `investment_rate_pct` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Active_Income_Share_Pct` | `gold.cashflow_efficiency_analytics` | `active_income_share_pct` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Passive_Income_Share_Pct` | `gold.cashflow_efficiency_analytics` | `passive_income_share_pct` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Core_Expense_Share_Pct` | `gold.cashflow_efficiency_analytics` | `core_expense_share_pct` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `NonCore_Expense_Share_Pct` | `gold.cashflow_efficiency_analytics` | `non_core_expense_share_pct` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Income_MoM_Pct` | `gold.cashflow_efficiency_analytics` | `income_mom_pct` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Expense_MoM_Pct` | `gold.cashflow_efficiency_analytics` | `expense_mom_pct` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Trailing_3M_Avg_Savings_Rate` | `gold.cashflow_efficiency_analytics` | `trailing_3_m_avg_savings_rate` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Trailing_3M_Avg_Investment_Rate` | `gold.cashflow_efficiency_analytics` | `trailing_3_m_avg_investment_rate` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Liquidity_Ratio_Months` | `gold.cashflow_efficiency_analytics` | `liquidity_ratio_months` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Debt_to_Asset_Ratio_Pct` | `gold.cashflow_efficiency_analytics` | `debt_to_asset_ratio_pct` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `YoY_Net_Worth_Growth_Pct` | `gold.cashflow_efficiency_analytics` | `yoy_net_worth_growth_pct` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `YoY_Net_Worth_Growth_Pct_Real` | `gold.cashflow_efficiency_analytics` | `yoy_net_worth_growth_pct_real` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Expense_to_NW_Ratio` | `gold.cashflow_efficiency_analytics` | `expense_to_nw_ratio` | 🏷️ RENAME |
| `gold.Cashflow_Efficiency_Analytics` | `Emergency_Fund_Coverage` | `gold.cashflow_efficiency_analytics` | `emergency_fund_coverage` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Closing_Date` | `gold.investment_by_isin` | `closing_date` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `ISIN` | `gold.investment_by_isin` | `isin` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `CURRENCY_ID` | `gold.investment_by_isin` | `currency_id` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `Total_Invested_Value` | `gold.investment_by_isin` | `total_invested_value` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `Total_Current_Value` | `gold.investment_by_isin` | `total_current_value` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `Total_Quantity` | `gold.investment_by_isin` | `total_quantity` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `Total_Stocks` | `gold.investment_by_isin` | `total_stocks` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Total_Invested_Value_Local` | `gold.investment_by_isin` | `total_invested_value_local` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Total_Current_Value_Local` | `gold.investment_by_isin` | `total_current_value_local` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Current_FX_Rate` | `gold.investment_by_isin` | `current_fx_rate` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Blended_FX_Buy_Rate` | `gold.investment_by_isin` | `blended_fx_buy_rate` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Currency_Appreciation_Pct` | `gold.investment_by_isin` | `currency_appreciation_pct` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Unrealized_PL` | `gold.investment_by_isin` | `unrealized_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `Asset_PnL` | `gold.investment_by_isin` | `asset_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `Forex_PnL` | `gold.investment_by_isin` | `fx_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `Forex_Contribution_Pct` | `gold.investment_by_isin` | `fx_contribution_pct` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Absolute_Return` | `gold.investment_by_isin` | `absolute_return` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `CAGR` | `gold.investment_by_isin` | `cagr` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `XIRR` | `gold.investment_by_isin` | `xirr` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `XIRR_Local` | `gold.investment_by_isin` | `xirr_local` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `FX_XIRR_Impact` | `gold.investment_by_isin` | `fx_xirr_impact` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `After_Tax_XIRR` | `gold.investment_by_isin` | `after_tax_xirr` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `BM_CAGR` | `gold.investment_by_isin` | `benchmark_cagr` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `BM_XIRR` | `gold.investment_by_isin` | `benchmark_xirr` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `BM_XIRR_Local` | `gold.investment_by_isin` | `benchmark_xirr_local` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Active_Return` | `gold.investment_by_isin` | `active_return` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Active_Return_Local` | `gold.investment_by_isin` | `active_return_local` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Is_Lagging_Benchmark` | `gold.investment_by_isin` | `is_lagging_benchmark` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Outperforming_Lot_Ratio` | `gold.investment_by_isin` | `outperforming_lot_ratio` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Max_Drawdown` | `gold.investment_by_isin` | `max_drawdown` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Weight` | `gold.investment_by_isin` | `weight` | 🏷️ RENAME |
| `gold.Investment_By_ISIN` | `Unrealized_LTCG` | `gold.investment_by_isin` | `unrealized_ltcg` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `Unrealized_STCG` | `gold.investment_by_isin` | `unrealized_stcg` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `Unrealized_Gain` | `gold.investment_by_isin` | `unrealized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `Unrealized_LTCL` | `gold.investment_by_isin` | `unrealized_ltcl` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `Unrealized_STCL` | `gold.investment_by_isin` | `unrealized_stcl` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `Unrealized_Loss` | `gold.investment_by_isin` | `unrealized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `LTCG_Tax_If_Sold` | `gold.investment_by_isin` | `ltcg_tax_if_sold` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `STCG_Tax_If_Sold` | `gold.investment_by_isin` | `stcg_tax_if_sold` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `FY_Realized_LTCG` | `gold.investment_by_isin` | `fy_realized_ltcg` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `FY_Realized_STCG` | `gold.investment_by_isin` | `fy_realized_stcg` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `FY_Realized_Gain` | `gold.investment_by_isin` | `fy_realized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `FY_Realized_LTCL` | `gold.investment_by_isin` | `fy_realized_ltcl` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `FY_Realized_STCL` | `gold.investment_by_isin` | `fy_realized_stcl` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `FY_Realized_Loss` | `gold.investment_by_isin` | `fy_realized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_ISIN` | `FY_Realized_Net_PnL` | `gold.investment_by_isin` | `fy_realized_net_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `Closing_Date` | `gold.investment_by_subtype` | `closing_date` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `INSTRUMENT_SUBTYPE` | `gold.investment_by_subtype` | `instrument_subtype` | 🏷️ RENAME |
| `gold.Investment_By_Subtype` | `INSTRUMENT_CLASS` | `gold.investment_by_subtype` | `instrument_class` | 🏷️ RENAME |
| `gold.Investment_By_Subtype` | `Total_Invested_Value` | `gold.investment_by_subtype` | `total_invested_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `Total_Current_Value` | `gold.investment_by_subtype` | `total_current_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `Total_Quantity` | `gold.investment_by_subtype` | `total_quantity` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `Total_Stocks` | `gold.investment_by_subtype` | `total_stocks` | 🏷️ RENAME |
| `gold.Investment_By_Subtype` | `Unrealized_PL` | `gold.investment_by_subtype` | `unrealized_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `Asset_PnL` | `gold.investment_by_subtype` | `asset_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `Forex_PnL` | `gold.investment_by_subtype` | `fx_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `Forex_Contribution_Pct` | `gold.investment_by_subtype` | `fx_contribution_pct` | 🏷️ RENAME |
| `gold.Investment_By_Subtype` | `Absolute_Return` | `gold.investment_by_subtype` | `absolute_return` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `XIRR` | `gold.investment_by_subtype` | `xirr` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `After_Tax_XIRR` | `gold.investment_by_subtype` | `after_tax_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Subtype` | `BM_XIRR` | `gold.investment_by_subtype` | `benchmark_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Subtype` | `Active_Return` | `gold.investment_by_subtype` | `active_return` | 🏷️ RENAME |
| `gold.Investment_By_Subtype` | `Max_Drawdown` | `gold.investment_by_subtype` | `max_drawdown` | 🏷️ RENAME |
| `gold.Investment_By_Subtype` | `Weight` | `gold.investment_by_subtype` | `weight` | 🏷️ RENAME |
| `gold.Investment_By_Subtype` | `Unrealized_Gain` | `gold.investment_by_subtype` | `unrealized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `Unrealized_Loss` | `gold.investment_by_subtype` | `unrealized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `FY_Realized_Gain` | `gold.investment_by_subtype` | `fy_realized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `FY_Realized_Loss` | `gold.investment_by_subtype` | `fy_realized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Subtype` | `FY_Realized_Net_PnL` | `gold.investment_by_subtype` | `fy_realized_net_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `Closing_Date` | `gold.investment_by_class` | `closing_date` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `INSTRUMENT_CLASS` | `gold.investment_by_class` | `instrument_class` | 🏷️ RENAME |
| `gold.Investment_By_Class` | `Total_Invested_Value` | `gold.investment_by_class` | `total_invested_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `Total_Current_Value` | `gold.investment_by_class` | `total_current_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `Total_Quantity` | `gold.investment_by_class` | `total_quantity` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `Total_Stocks` | `gold.investment_by_class` | `total_stocks` | 🏷️ RENAME |
| `gold.Investment_By_Class` | `Unrealized_PL` | `gold.investment_by_class` | `unrealized_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `Asset_PnL` | `gold.investment_by_class` | `asset_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `Forex_PnL` | `gold.investment_by_class` | `fx_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `Forex_Contribution_Pct` | `gold.investment_by_class` | `fx_contribution_pct` | 🏷️ RENAME |
| `gold.Investment_By_Class` | `Absolute_Return` | `gold.investment_by_class` | `absolute_return` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `XIRR` | `gold.investment_by_class` | `xirr` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `After_Tax_XIRR` | `gold.investment_by_class` | `after_tax_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Class` | `BM_XIRR` | `gold.investment_by_class` | `benchmark_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Class` | `Active_Return` | `gold.investment_by_class` | `active_return` | 🏷️ RENAME |
| `gold.Investment_By_Class` | `Max_Drawdown` | `gold.investment_by_class` | `max_drawdown` | 🏷️ RENAME |
| `gold.Investment_By_Class` | `Weight` | `gold.investment_by_class` | `weight` | 🏷️ RENAME |
| `gold.Investment_By_Class` | `Unrealized_Gain` | `gold.investment_by_class` | `unrealized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `Unrealized_Loss` | `gold.investment_by_class` | `unrealized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `FY_Realized_Gain` | `gold.investment_by_class` | `fy_realized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `FY_Realized_Loss` | `gold.investment_by_class` | `fy_realized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Class` | `FY_Realized_Net_PnL` | `gold.investment_by_class` | `fy_realized_net_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `Closing_Date` | `gold.investment_by_instrument_type` | `closing_date` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `INSTRUMENT_TYPE` | `gold.investment_by_instrument_type` | `instrument_type` | 🏷️ RENAME |
| `gold.Investment_By_Instrument_Type` | `Total_Invested_Value` | `gold.investment_by_instrument_type` | `total_invested_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `Total_Current_Value` | `gold.investment_by_instrument_type` | `total_current_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `Total_Quantity` | `gold.investment_by_instrument_type` | `total_quantity` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `Total_Stocks` | `gold.investment_by_instrument_type` | `total_stocks` | 🏷️ RENAME |
| `gold.Investment_By_Instrument_Type` | `Unrealized_PL` | `gold.investment_by_instrument_type` | `unrealized_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `Asset_PnL` | `gold.investment_by_instrument_type` | `asset_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `Forex_PnL` | `gold.investment_by_instrument_type` | `fx_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `Forex_Contribution_Pct` | `gold.investment_by_instrument_type` | `fx_contribution_pct` | 🏷️ RENAME |
| `gold.Investment_By_Instrument_Type` | `Absolute_Return` | `gold.investment_by_instrument_type` | `absolute_return` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `XIRR` | `gold.investment_by_instrument_type` | `xirr` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `After_Tax_XIRR` | `gold.investment_by_instrument_type` | `after_tax_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Instrument_Type` | `BM_XIRR` | `gold.investment_by_instrument_type` | `benchmark_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Instrument_Type` | `Active_Return` | `gold.investment_by_instrument_type` | `active_return` | 🏷️ RENAME |
| `gold.Investment_By_Instrument_Type` | `Max_Drawdown` | `gold.investment_by_instrument_type` | `max_drawdown` | 🏷️ RENAME |
| `gold.Investment_By_Instrument_Type` | `Weight` | `gold.investment_by_instrument_type` | `weight` | 🏷️ RENAME |
| `gold.Investment_By_Instrument_Type` | `Unrealized_Gain` | `gold.investment_by_instrument_type` | `unrealized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `Unrealized_Loss` | `gold.investment_by_instrument_type` | `unrealized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `FY_Realized_Gain` | `gold.investment_by_instrument_type` | `fy_realized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `FY_Realized_Loss` | `gold.investment_by_instrument_type` | `fy_realized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Instrument_Type` | `FY_Realized_Net_PnL` | `gold.investment_by_instrument_type` | `fy_realized_net_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `Closing_Date` | `gold.investment_by_sector` | `closing_date` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `SECTOR` | `gold.investment_by_sector` | `sector` | 🏷️ RENAME |
| `gold.Investment_By_Sector` | `Total_Invested_Value` | `gold.investment_by_sector` | `total_invested_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `Total_Current_Value` | `gold.investment_by_sector` | `total_current_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `Total_Quantity` | `gold.investment_by_sector` | `total_quantity` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `Total_Stocks` | `gold.investment_by_sector` | `total_stocks` | 🏷️ RENAME |
| `gold.Investment_By_Sector` | `Unrealized_PL` | `gold.investment_by_sector` | `unrealized_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `Asset_PnL` | `gold.investment_by_sector` | `asset_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `Forex_PnL` | `gold.investment_by_sector` | `fx_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `Forex_Contribution_Pct` | `gold.investment_by_sector` | `fx_contribution_pct` | 🏷️ RENAME |
| `gold.Investment_By_Sector` | `Absolute_Return` | `gold.investment_by_sector` | `absolute_return` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `XIRR` | `gold.investment_by_sector` | `xirr` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `After_Tax_XIRR` | `gold.investment_by_sector` | `after_tax_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Sector` | `BM_XIRR` | `gold.investment_by_sector` | `benchmark_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Sector` | `Active_Return` | `gold.investment_by_sector` | `active_return` | 🏷️ RENAME |
| `gold.Investment_By_Sector` | `Max_Drawdown` | `gold.investment_by_sector` | `max_drawdown` | 🏷️ RENAME |
| `gold.Investment_By_Sector` | `Weight` | `gold.investment_by_sector` | `weight` | 🏷️ RENAME |
| `gold.Investment_By_Sector` | `Unrealized_Gain` | `gold.investment_by_sector` | `unrealized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `Unrealized_Loss` | `gold.investment_by_sector` | `unrealized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `FY_Realized_Gain` | `gold.investment_by_sector` | `fy_realized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `FY_Realized_Loss` | `gold.investment_by_sector` | `fy_realized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Sector` | `FY_Realized_Net_PnL` | `gold.investment_by_sector` | `fy_realized_net_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `Closing_Date` | `gold.investment_by_industry` | `closing_date` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `INDUSTRY` | `gold.investment_by_industry` | `industry` | 🏷️ RENAME |
| `gold.Investment_By_Industry` | `Total_Invested_Value` | `gold.investment_by_industry` | `total_invested_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `Total_Current_Value` | `gold.investment_by_industry` | `total_current_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `Total_Quantity` | `gold.investment_by_industry` | `total_quantity` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `Total_Stocks` | `gold.investment_by_industry` | `total_stocks` | 🏷️ RENAME |
| `gold.Investment_By_Industry` | `Unrealized_PL` | `gold.investment_by_industry` | `unrealized_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `Asset_PnL` | `gold.investment_by_industry` | `asset_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `Forex_PnL` | `gold.investment_by_industry` | `fx_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `Forex_Contribution_Pct` | `gold.investment_by_industry` | `fx_contribution_pct` | 🏷️ RENAME |
| `gold.Investment_By_Industry` | `Absolute_Return` | `gold.investment_by_industry` | `absolute_return` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `XIRR` | `gold.investment_by_industry` | `xirr` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `After_Tax_XIRR` | `gold.investment_by_industry` | `after_tax_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Industry` | `BM_XIRR` | `gold.investment_by_industry` | `benchmark_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Industry` | `Active_Return` | `gold.investment_by_industry` | `active_return` | 🏷️ RENAME |
| `gold.Investment_By_Industry` | `Max_Drawdown` | `gold.investment_by_industry` | `max_drawdown` | 🏷️ RENAME |
| `gold.Investment_By_Industry` | `Weight` | `gold.investment_by_industry` | `weight` | 🏷️ RENAME |
| `gold.Investment_By_Industry` | `Unrealized_Gain` | `gold.investment_by_industry` | `unrealized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `Unrealized_Loss` | `gold.investment_by_industry` | `unrealized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `FY_Realized_Gain` | `gold.investment_by_industry` | `fy_realized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `FY_Realized_Loss` | `gold.investment_by_industry` | `fy_realized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Industry` | `FY_Realized_Net_PnL` | `gold.investment_by_industry` | `fy_realized_net_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `Closing_Date` | `gold.investment_by_portfolio` | `closing_date` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `Total_Invested_Value` | `gold.investment_by_portfolio` | `total_invested_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `Total_Current_Value` | `gold.investment_by_portfolio` | `total_current_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `Total_Quantity` | `gold.investment_by_portfolio` | `total_quantity` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `Total_Stocks` | `gold.investment_by_portfolio` | `total_stocks` | 🏷️ RENAME |
| `gold.Investment_By_Portfolio` | `Unrealized_PL` | `gold.investment_by_portfolio` | `unrealized_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `Asset_PnL` | `gold.investment_by_portfolio` | `asset_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `Forex_PnL` | `gold.investment_by_portfolio` | `fx_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `Forex_Contribution_Pct` | `gold.investment_by_portfolio` | `fx_contribution_pct` | 🏷️ RENAME |
| `gold.Investment_By_Portfolio` | `Absolute_Return` | `gold.investment_by_portfolio` | `absolute_return` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `XIRR` | `gold.investment_by_portfolio` | `xirr` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `After_Tax_XIRR` | `gold.investment_by_portfolio` | `after_tax_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Portfolio` | `BM_XIRR` | `gold.investment_by_portfolio` | `benchmark_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Portfolio` | `Active_Return` | `gold.investment_by_portfolio` | `active_return` | 🏷️ RENAME |
| `gold.Investment_By_Portfolio` | `Max_Drawdown` | `gold.investment_by_portfolio` | `max_drawdown` | 🏷️ RENAME |
| `gold.Investment_By_Portfolio` | `Weight` | `gold.investment_by_portfolio` | `weight` | 🏷️ RENAME |
| `gold.Investment_By_Portfolio` | `Unrealized_Gain` | `gold.investment_by_portfolio` | `unrealized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `Unrealized_Loss` | `gold.investment_by_portfolio` | `unrealized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `FY_Realized_Gain` | `gold.investment_by_portfolio` | `fy_realized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `FY_Realized_Loss` | `gold.investment_by_portfolio` | `fy_realized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Portfolio` | `FY_Realized_Net_PnL` | `gold.investment_by_portfolio` | `fy_realized_net_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `Closing_Date` | `gold.investment_by_geo` | `closing_date` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `GEO` | `gold.investment_by_geo` | `geo` | 🏷️ RENAME |
| `gold.Investment_By_Geo` | `Total_Invested_Value` | `gold.investment_by_geo` | `total_invested_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `Total_Current_Value` | `gold.investment_by_geo` | `total_current_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `Total_Quantity` | `gold.investment_by_geo` | `total_quantity` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `Total_Stocks` | `gold.investment_by_geo` | `total_stocks` | 🏷️ RENAME |
| `gold.Investment_By_Geo` | `Unrealized_PL` | `gold.investment_by_geo` | `unrealized_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `Asset_PnL` | `gold.investment_by_geo` | `asset_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `Forex_PnL` | `gold.investment_by_geo` | `fx_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `Forex_Contribution_Pct` | `gold.investment_by_geo` | `fx_contribution_pct` | 🏷️ RENAME |
| `gold.Investment_By_Geo` | `Absolute_Return` | `gold.investment_by_geo` | `absolute_return` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `XIRR` | `gold.investment_by_geo` | `xirr` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `After_Tax_XIRR` | `gold.investment_by_geo` | `after_tax_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Geo` | `BM_XIRR` | `gold.investment_by_geo` | `benchmark_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Geo` | `Active_Return` | `gold.investment_by_geo` | `active_return` | 🏷️ RENAME |
| `gold.Investment_By_Geo` | `Max_Drawdown` | `gold.investment_by_geo` | `max_drawdown` | 🏷️ RENAME |
| `gold.Investment_By_Geo` | `Weight` | `gold.investment_by_geo` | `weight` | 🏷️ RENAME |
| `gold.Investment_By_Geo` | `Unrealized_Gain` | `gold.investment_by_geo` | `unrealized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `Unrealized_Loss` | `gold.investment_by_geo` | `unrealized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `FY_Realized_Gain` | `gold.investment_by_geo` | `fy_realized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `FY_Realized_Loss` | `gold.investment_by_geo` | `fy_realized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Geo` | `FY_Realized_Net_PnL` | `gold.investment_by_geo` | `fy_realized_net_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `Closing_Date` | `gold.investment_by_country` | `closing_date` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `COUNTRY` | `gold.investment_by_country` | `country` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Total_Invested_Value` | `gold.investment_by_country` | `total_invested_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `Total_Current_Value` | `gold.investment_by_country` | `total_current_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `Total_Quantity` | `gold.investment_by_country` | `total_quantity` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `Total_Stocks` | `gold.investment_by_country` | `total_stocks` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Total_Invested_Value_Local` | `gold.investment_by_country` | `total_invested_value_local` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Total_Current_Value_Local` | `gold.investment_by_country` | `total_current_value_local` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Current_FX_Rate` | `gold.investment_by_country` | `current_fx_rate` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Blended_FX_Buy_Rate` | `gold.investment_by_country` | `blended_fx_buy_rate` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Currency_Appreciation_Pct` | `gold.investment_by_country` | `currency_appreciation_pct` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Unrealized_PL` | `gold.investment_by_country` | `unrealized_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `Asset_PnL` | `gold.investment_by_country` | `asset_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `Forex_PnL` | `gold.investment_by_country` | `fx_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `Forex_Contribution_Pct` | `gold.investment_by_country` | `fx_contribution_pct` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Absolute_Return` | `gold.investment_by_country` | `absolute_return` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `XIRR` | `gold.investment_by_country` | `xirr` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `After_Tax_XIRR` | `gold.investment_by_country` | `after_tax_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `BM_XIRR` | `gold.investment_by_country` | `benchmark_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Active_Return` | `gold.investment_by_country` | `active_return` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `XIRR_Local` | `gold.investment_by_country` | `xirr_local` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `BM_XIRR_Local` | `gold.investment_by_country` | `benchmark_xirr_local` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Active_Return_Local` | `gold.investment_by_country` | `active_return_local` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `FX_XIRR_Impact` | `gold.investment_by_country` | `fx_xirr_impact` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Max_Drawdown` | `gold.investment_by_country` | `max_drawdown` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Weight` | `gold.investment_by_country` | `weight` | 🏷️ RENAME |
| `gold.Investment_By_Country` | `Unrealized_Gain` | `gold.investment_by_country` | `unrealized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `Unrealized_Loss` | `gold.investment_by_country` | `unrealized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `FY_Realized_Gain` | `gold.investment_by_country` | `fy_realized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `FY_Realized_Loss` | `gold.investment_by_country` | `fy_realized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Country` | `FY_Realized_Net_PnL` | `gold.investment_by_country` | `fy_realized_net_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `Closing_Date` | `gold.investment_by_currency` | `closing_date` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `CURRENCY_ID` | `gold.investment_by_currency` | `currency_id` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `Total_Invested_Value` | `gold.investment_by_currency` | `total_invested_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `Total_Current_Value` | `gold.investment_by_currency` | `total_current_value` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `Total_Quantity` | `gold.investment_by_currency` | `total_quantity` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `Total_Stocks` | `gold.investment_by_currency` | `total_stocks` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `Total_Invested_Value_Local` | `gold.investment_by_currency` | `total_invested_value_local` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `Total_Current_Value_Local` | `gold.investment_by_currency` | `total_current_value_local` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `Current_FX_Rate` | `gold.investment_by_currency` | `current_fx_rate` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `Blended_FX_Buy_Rate` | `gold.investment_by_currency` | `blended_fx_buy_rate` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `Currency_Appreciation_Pct` | `gold.investment_by_currency` | `currency_appreciation_pct` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `Unrealized_PL` | `gold.investment_by_currency` | `unrealized_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `Asset_PnL` | `gold.investment_by_currency` | `asset_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `Forex_PnL` | `gold.investment_by_currency` | `fx_pnl` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `Forex_Contribution_Pct` | `gold.investment_by_currency` | `fx_contribution_pct` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `Absolute_Return` | `gold.investment_by_currency` | `absolute_return` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `XIRR` | `gold.investment_by_currency` | `xirr` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `XIRR_Local` | `gold.investment_by_currency` | `xirr_local` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `FX_XIRR_Impact` | `gold.investment_by_currency` | `fx_xirr_impact` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `After_Tax_XIRR` | `gold.investment_by_currency` | `after_tax_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `BM_XIRR` | `gold.investment_by_currency` | `benchmark_xirr` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `BM_XIRR_Local` | `gold.investment_by_currency` | `benchmark_xirr_local` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `Active_Return` | `gold.investment_by_currency` | `active_return` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `Active_Return_Local` | `gold.investment_by_currency` | `active_return_local` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `Max_Drawdown` | `gold.investment_by_currency` | `max_drawdown` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `Weight` | `gold.investment_by_currency` | `weight` | 🏷️ RENAME |
| `gold.Investment_By_Currency` | `Unrealized_Gain` | `gold.investment_by_currency` | `unrealized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `Unrealized_Loss` | `gold.investment_by_currency` | `unrealized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `FY_Realized_Gain` | `gold.investment_by_currency` | `fy_realized_gain` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `FY_Realized_Loss` | `gold.investment_by_currency` | `fy_realized_loss` | 🛡️ PROTECTED |
| `gold.Investment_By_Currency` | `FY_Realized_Net_PnL` | `gold.investment_by_currency` | `fy_realized_net_pnl` | 🛡️ PROTECTED |
| `gold.Cashflow_Activity_Summary` | `MONTH_START_DATE` | `gold.cashflow_activity_summary` | `month_start_date` | 🛡️ PROTECTED |
| `gold.Cashflow_Activity_Summary` | `MONTH_END_DATE` | `gold.cashflow_activity_summary` | `month_end_date` | 🛡️ PROTECTED |
| `gold.Cashflow_Activity_Summary` | `YEAR_MONTH` | `gold.cashflow_activity_summary` | `year_month` | 🛡️ PROTECTED |
| `gold.Cashflow_Activity_Summary` | `Opening_Cash_Balance` | `gold.cashflow_activity_summary` | `opening_cash_balance` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Closing_Cash_Balance` | `gold.cashflow_activity_summary` | `closing_cash_balance` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Net_Cash_Movement` | `gold.cashflow_activity_summary` | `net_cash_movement` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Cash_Inflow_Operating` | `gold.cashflow_activity_summary` | `cash_inflow_operating` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Cash_Outflow_Operating` | `gold.cashflow_activity_summary` | `cash_outflow_operating` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Net_Cashflow_Operating` | `gold.cashflow_activity_summary` | `net_cashflow_operating` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Cash_Inflow_Investing` | `gold.cashflow_activity_summary` | `cash_inflow_investing` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Cash_Outflow_Investing` | `gold.cashflow_activity_summary` | `cash_outflow_investing` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Net_Cashflow_Investing` | `gold.cashflow_activity_summary` | `net_cashflow_investing` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Cash_Inflow_Financing` | `gold.cashflow_activity_summary` | `cash_inflow_financing` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Cash_Outflow_Financing` | `gold.cashflow_activity_summary` | `cash_outflow_financing` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Net_Cashflow_Financing` | `gold.cashflow_activity_summary` | `net_cashflow_financing` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Internal_Transfer_Inflow` | `gold.cashflow_activity_summary` | `internal_transfer_inflow` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Internal_Transfer_Outflow` | `gold.cashflow_activity_summary` | `internal_transfer_outflow` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Net_Internal_Transfers` | `gold.cashflow_activity_summary` | `net_internal_transfers` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Total_Cash_Expenses` | `gold.cashflow_activity_summary` | `total_cash_expenses` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Total_Non_Cash_Expenses` | `gold.cashflow_activity_summary` | `total_non_cash_expenses` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Total_Cash_Inflow` | `gold.cashflow_activity_summary` | `total_cash_inflow` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Total_Cash_Outflow` | `gold.cashflow_activity_summary` | `total_cash_outflow` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Calculated_Net_Cashflow` | `gold.cashflow_activity_summary` | `calculated_net_cashflow` | 🏷️ RENAME |
| `gold.Cashflow_Activity_Summary` | `Unreconciled_Difference` | `gold.cashflow_activity_summary` | `unreconciled_difference` | 🏷️ RENAME |

---

## 8. Pre-Cutover Numerical Oracle Strategy

Prior to modifying any Gold DDL or producer outputs in Phases 009 and 010, the test suite `tests/test_phase8_gold_dependency_and_disposition.py` records checksums and invariants for:
- Exact table topology (22 tables)
- Exact column inventory (577 columns)
- Grains and primary/temporal keys
- Producer contract alignments
During Phases 009 and 010, end-to-end execution must preserve byte-for-byte or epsilon-equivalent numerical outputs across all 22 Gold tables.
