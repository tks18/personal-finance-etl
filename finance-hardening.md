# Financial Domain Freeze

## Goal
Harden the financial model around investment lots, realized gains/losses, broker reconciliation, household income, capital-loss treatment, estimated tax preparation, and year-end review.

The application remains a financial/tax guidance system, not a complete ITR engine.

## 1. Calendar-month holding periods
### Change
Replace approximate day-based holding thresholds with calendar-month semantics.
### Impact
Leap years and different month lengths cannot distort ST/LT classification.
### Implementation
For each supported tax type/subtype:
```text
acquisition_date
+ configured threshold months
→ boundary date
```
Compare the actual disposal/reference date to the boundary. Lock exact-boundary behavior with tests.
### Done when
One day before, exact boundary, and one day after classify deterministically.

## 2. Lot-level realized investment events
### Change
Create `silver.f_Investment_Realized_Events`.

Grain:
```text
one disposed FIFO lot segment per sale
```
A sale consuming three buy lots creates three rows.
### Impact
FIFO becomes canonical realized gain/loss history while the existing sale-level weighted-average P&L can remain.
### Implementation
Suggested fields:
```text
Realized_Event_ID
Sale_ID / Transaction_ID
ISIN
Lot_ID
Lot_Sequence
Acquisition_Date
Disposal_Date
FY
Quantity_Disposed
Acquisition_Price
Disposed_Cost_Basis
Sale_Price
Sale_Proceeds
Realized_Gain_Loss
Holding_Type
Tax_Type
Tax_Subtype
source / lineage identifiers
reconciliation indicator where relevant
```
### Done when
Multi-lot sales preserve exact lot-level realization and full liquidation never removes realized history.

## 3. TaxConfig at Head → Tax Sub-Head
### Change
Add TaxConfig inside FinancialRules:
```text
Head of Income
→ Tax Sub-Head
→ cat_ids[]
→ sub_cat_ids[]
→ tax_credit_sub_cat_ids[]
→ taxability
→ tax_method
```
Example:
```toml
[taxconfig.income_from_salary.salary]
display_name = "Salary"
cat_ids = ["SALARY"]
sub_cat_ids = []
tax_credit_sub_cat_ids = ["SALARY_TDS"]
taxability = "taxable"
tax_method = "ordinary_rate"
```
### Impact
New income streams normally require only adding IDs to an existing sub-head.
### Implementation
Use one uniform schema. Suggested enums:
```text
taxability: taxable | non_taxable | review
tax_method: ordinary_rate | capital_gains | exempt | review
```
`cat_ids` claims the whole category. `sub_cat_ids` claims only exact subcategories. No override/exclusion semantics. Effective overlaps are configuration errors.
### Done when
Income taxonomy changes normally require FinancialRules changes only.

## 4. Tax credits at Subcategory level only
### Change
Use only `tax_credit_sub_cat_ids`.
### Impact
TDS remains explicit and simple.
### Implementation
For mapped tax-credit subcategories, use the absolute ledger amount as observed tax already withheld/credited.
```text
Gross income +100
TDS -20
Cash received 80

Tax model:
Gross income 100
Observed tax credit 20
```
### Done when
Cash and tax-credit views both reconcile.

## 5. Tax-event ownership
### Change
Every canonical TaxEvent has exactly one producer.
### Impact
Investment capital gains cannot be double counted between the ledger and FIFO.
### Implementation
Use:
```text
specialized Investment Engine
>
generic ledger classification
```
Reuse the existing investment-category configuration to identify investment-related activity.
```text
investment disposal
→ f_Investment_Realized_Events
→ f_Tax_Events
```
Suppress generic ledger-derived capital gains for those investment categories.
### Done when
One economic investment gain appears exactly once in TaxEvents.

## 6. Non-investment capital gains
### Change
Allow the Capital Gains head to map non-investment capital-asset income from the ledger, with separate ST/LT sub-heads where the taxonomy can identify them.
### Impact
Investment and other capital assets can share the tax model while keeping different producers.
### Implementation
For mapped non-investment gains/losses:
```text
positive ST → STCG
negative ST → STCL
positive LT → LTCG
negative LT → LTCL
```
The mapped amount must already represent gain/loss, not gross sale proceeds, unless richer cost-basis evidence exists.

Use `Default_STCG` / `Default_LTCG` from Macro Parameters for the supported default calculation. Insufficient classification becomes `CHECK_REQUIRED`.
### Done when
Non-investment capital gains/losses flow correctly without affecting investment ownership.

## 7. Rename ordinary-income macro rate
### Change
Rename:
```text
Dividend_Income_Tax_Rate
→ Estimated_Ordinary_Income_Tax_Rate
```
in `silver.d_Macro_Parameters`.
### Impact
Salary, interest, dividend, and other supported ordinary taxable streams share one explicit FY planning assumption.
### Implementation
```text
tax_method = ordinary_rate
→ Estimated_Ordinary_Income_Tax_Rate
```
Keep existing equity/gold/debt/default capital-gain rates and exemptions. Do not add a slab engine or separate ordinary-income rates.
### Done when
A new FY ordinary-rate assumption is a macro-data change.

## 8. Keep non-taxable income outside TaxEvents
### Change
Configured non-taxable streams such as cashback/digital-wallet income do not enter `silver.f_Tax_Events`.
### Impact
TaxEvents remains a tax-relevant fact rather than a duplicate income fact.
### Implementation
```text
taxability = non_taxable
→ classify intentionally
→ exclude before f_Tax_Events
```
Reconcile at a higher level:
```text
Gross Income Ledger
- Explicitly Non-Taxable / Excluded Income
= Tax Model Income Universe
```
### Done when
Non-taxable income remains in normal financial reporting but not TaxEvents.

## 9. Canonical TaxEvents
### Change
Create `silver.f_Tax_Events`.

Grain:
```text
one tax-relevant financial event
```
### Impact
Ledger-derived taxable income and FIFO realized investment events share one canonical tax input.
### Implementation
Suggested fields:
```text
Tax_Event_ID
Event_Date
FY
Source_Type
Source_ID
Income_Head
Tax_Sub_Head
Taxability
Tax_Method
Gross_Amount
Taxable_Amount
Gain_Type
Realized_Gain_Loss
Applied_Rate
Estimated_Tax
Tax_Status
Tax_Status_Reason
Rules_Snapshot_ID
```
Suggested Source Types:
```text
LEDGER
INVESTMENT_REALIZED
```
Keep Tax Status minimal:
```text
READY
CHECK_REQUIRED
```
This is calculation status, not a review workflow.
### Done when
Every supported tax-relevant event enters the tax engine through this fact.

## 10. Capital-loss set-off + carry-forward
### Change
Replace aggregate loss arithmetic with explicit ST/LT state.
### Impact
Net gains/losses and estimated tax remain correct when capital losses exist.
### Implementation
Track:
```text
Current STCG / LTCG / STCL / LTCL
Brought-Forward STCL / LTCL
```
Apply supported set-off rules in Python domain code and return:
```text
STCL utilized
LTCL utilized
Net taxable STCG
Net taxable LTCG
Closing STCL
Closing LTCL
```
Carry-forward remains financial analytical state. If history starts with an existing brought-forward loss, support a small explicit opening loss state.
### Done when
Full, partial, no-utilization, and multi-FY scenarios reconcile.

## 11. FY Tax State in Silver
### Change
Create `silver.f_Tax_FY_State`.

Grain:
```text
one row per FY
```
### Impact
This becomes the canonical annual calculation state between TaxEvents and Gold.
### Implementation
Suggested fields:
```text
FY
Gross_Income
Excluded_Non_Taxable_Income
Tax_Relevant_Income
Ordinary_Taxable_Income
STCG
LTCG
STCL
LTCL
Brought_Forward_STCL
Brought_Forward_LTCL
STCL_Utilized
LTCL_Utilized
Closing_STCL
Closing_LTCL
Net_Taxable_STCG
Net_Taxable_LTCG
Estimated_Ordinary_Tax
Estimated_Capital_Gains_Tax
Estimated_Gross_Tax
Observed_Tax_Credits
Estimated_Net_Tax_Payable
Check_Required_Count
```
### Done when
Every material Gold tax value reconciles through FY Tax State to TaxEvents.

## 12. Three Gold tax marts
### `gold.Tax_Year_Summary`
Grain: FY.

Purpose: one-row year-end tax picture.

### `gold.Tax_Income_Breakdown`
Grain:
```text
FY × Income Head × Tax Sub-Head × Source Type
```
Purpose: detailed tax-preparation breakdown. Investment and other capital gains remain distinguishable.

### `gold.Tax_Reconciliation`
Grain:
```text
FY × Tax Sub-Head × Source Type
```
Purpose: trace financial amounts through the tax calculation.

Suggested reconciliation measures:
```text
Gross_Source_Amount
Excluded_Non_Taxable_Amount
Tax_Event_Amount
Realized_Investment_Gain_Loss
Set_Off_Amount
Net_Taxable_Amount
Estimated_Tax
Tax_Credits
Estimated_Net_Tax
Event_Count
Check_Required_Count
```
### Impact
Gold answers:
```text
Tax_Year_Summary → What is the FY tax picture?
Tax_Income_Breakdown → Where did it come from?
Tax_Reconciliation → Can I trace it?
```
### Done when
All three reconcile to the same FY Tax State.

## 13. Keep and rename investment tax forecast
### Change
Rename the existing Tax Liability Forecast to:
```text
gold.Investment_Tax_Liability_Forecast
```
### Impact
It remains clearly separate from realized FY tax reporting:
```text
Investment_Tax_Liability_Forecast
→ current/hypothetical investment tax exposure

Tax_Year_Summary
→ realized FY tax preparation
```
### Implementation
Keep the useful forecast behavior but fix its capital-loss set-off logic. Reuse shared tax-domain functions where practical.
### Done when
Investment tax forecasting and FY tax reporting are semantically separate but use consistent tax logic.

## 14. Persist broker/FIFO reconciliation events
### Change
Create `silver.f_Investment_Reconciliation_Events`.

Grain:
```text
one reconciliation adjustment event
```
### Impact
Broker reconciliation becomes explainable instead of silently changing active quantity/basis.
### Implementation
Suggested fields:
```text
Reconciliation_Event_ID
Run_ID
ISIN
Reconciliation_Date
Lot_ID               # nullable
Acquisition_Date     # nullable
Adjustment_Type
Reason
Broker_Quantity
Reconstructed_Quantity
Quantity_Adjustment
Broker_Cost_Basis
Reconstructed_Cost_Basis
Cost_Basis_Adjustment
Original_Unit_Cost
Adjusted_Unit_Cost
Related_Lot_ID
source / lineage identifiers
```
Keep adjustment types limited to what the engine actually performs, e.g.:
```text
QUANTITY_ADD
QUANTITY_REMOVE
COST_BASIS_ADJUSTMENT
```
### Done when
A broker/FIFO mismatch can be explained by ISIN/date/lot/quantity/basis/reason.

## 15. Fix XIRR failure semantics
### Change
Do not emit a meaningful `0%` when XIRR is undefined or the solver fails.
### Impact
A real 0% return is distinguishable from calculation failure.
### Implementation
Return:
```text
value
status
reason
```
Statuses:
```text
VALID
UNDEFINED
NON_CONVERGENT
INVALID_INPUT
```
Use nullable value for non-valid results.
### Done when
All XIRR consumers preserve the distinction.

## Final contract changes
Assuming the current 20 Silver / 17 Gold baseline and no removals:

New Silver:
```text
silver.f_Investment_Realized_Events
silver.f_Investment_Reconciliation_Events
silver.f_Tax_Events
silver.f_Tax_FY_State
```
Planning expectation:
```text
20 → 24 Silver
```

New Gold:
```text
gold.Tax_Year_Summary
gold.Tax_Income_Breakdown
gold.Tax_Reconciliation
```
Planning expectation:
```text
17 → 20 Gold
```

Renamed Gold:
```text
Tax_Liability_Forecast
→ Investment_Tax_Liability_Forecast
```

Freeze actual counts from the implemented registry.

## Explicitly out of scope
```text
corporate-actions framework
complete ITR preparation
ITR schedule/field emulator
tax-regime optimizer
slab engine
AIS / 26AS ingestion
deduction engine
Form 16 reconstruction
house-property tax engine
business/profession tax
foreign-asset reporting
every Indian asset class
review-workflow system
```

## Domain freeze checklist
- Calendar-month holding semantics.
- Lot-level FIFO realized history.
- Head → Tax Sub-Head config.
- Tax credits at Subcategory level.
- Single producer per TaxEvent.
- Non-investment ST/LT gains/losses supported.
- Ordinary-rate macro renamed.
- Non-taxable income excluded from TaxEvents.
- Minimal Tax Status.
- Correct loss set-off/carry-forward.
- FY Tax State in Silver.
- Three reconciling Gold tax marts.
- Investment tax forecast renamed/corrected.
- Broker/FIFO reconciliation events persisted.
- XIRR failure states explicit.
