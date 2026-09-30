# Financial Domain Freeze

## Goal

Harden the financial model around the scenarios I actually use:

```text
canonical investment purchases/sales
FIFO lots
realized gains/losses
broker reconciliation
household income
capital-loss treatment
estimated tax preparation
year-end review
```

The application remains a financial/tax guidance system. It does not replace final filing due diligence or become a complete Indian tax-return engine.

---

## 1. Add deterministic IDs to canonical investment facts

### Change

Add:

```text
Purchase_ID
```

to:

```text
silver.f_Investment_Purchase_Data
```

and:

```text
Sale_ID
```

to:

```text
silver.f_Investment_Sale_Data
```

### Impact

The current Purchase/Sale tables intentionally contain canonical aggregated financial events rather than source broker transactions.

Stable IDs allow the Quant Engine and new durable facts to reference those events across complete Silver rebuilds.

### Implementation

Do not change Bronze or restore source-order granularity.

Define:

```text
Purchase_ID
→ one canonical aggregated purchase row

Sale_ID
→ one canonical aggregated sale row
```

Suggested defining attributes:

```text
Purchase_ID:
PURCHASE
+ ISIN
+ Date
+ normalized Price
+ normalized Quantity
+ Currency

Sale_ID:
SALE
+ ISIN
+ Date
+ normalized Sell_Price
+ normalized Quantity
+ Currency
```

Do not include derived fields such as:

```text
Value
Buy_Value
Unit_PnL
Total_PnL
```

because correcting a derived calculation must not change entity identity.

Do not include file/folder paths because rename/path changes are provenance changes, not financial identity changes.

Generate IDs only after the canonical aggregation has established the final row.

### Done when

The same canonical Purchase/Sale rows receive the same IDs on every rebuild.

---

## 2. Add deterministic Lot identity

### Change

Extend the Quant Engine `TaxLot` concept and:

```text
silver.f_Investment_Analytics_Lot
```

with:

```text
Lot_ID
Purchase_ID
Lot_Source_Type
```

### Impact

The current lot fact is effectively identified by `ISIN + Buy_Date + Closing_Date`, which cannot distinguish all acquisition lots reliably.

`Lot_ID` becomes the stable identity of the economic FIFO lot.

### Implementation

For normal purchase-derived lots:

```text
Lot_ID = deterministic_id("LOT", Purchase_ID)
Lot_Source_Type = PURCHASE
```

The lot fact grain becomes:

```text
Lot_ID × Closing_Date
```

and should be unique at that grain.

Do not add Lot_ID to:

```text
f_Investment_Market_Data
f_Investment_Benchmark_Data
```

Those tables represent market/benchmark state, not reconstructed FIFO lots.

### Done when

Every active FIFO lot has stable identity across analytical rebuilds.

---

## 3. Preserve Lot identity through FIFO mutation

### Change

Whenever the Quant Engine creates a replacement `TaxLot` during partial sale or reconciliation, preserve the existing lot identity unless a genuinely new lot is being created.

### Impact

Python object replacement no longer looks like economic lot replacement.

### Implementation

Partial sale:

```text
Lot L001: 100 units
sell 30
→ realized event references L001
→ remaining 70 units remain L001
```

Quantity reduction:

```text
existing lot reduced
→ same Lot_ID
```

Cost-basis adjustment:

```text
active lot basis changed
→ same Lot_ID
```

Only a reconciliation-created missing-quantity lot receives a new synthetic Lot_ID.

### Done when

Lot identity survives all state mutations correctly.

---

## 4. Define deterministic same-day FIFO ordering

### Change

Make same-day purchase/sale processing deterministic where unified canonical source evidence no longer preserves intra-day chronology.

### Impact

Multiple different-price events on the same date can otherwise enter FIFO in unstable dataframe order and change realized basis.

### Implementation

Canonical purchase ordering:

```text
Date ASC
Price ASC
Purchase_ID ASC
```

Canonical sale ordering:

```text
Date ASC
Sell_Price ASC
Sale_ID ASC
```

Use numeric normalized price ordering, not formatted text.

This is a reproducibility convention when finer intra-day chronology is unavailable. It must not be described as recovered broker chronology.

Do not collapse different-price same-day purchases into weighted-average lots.

### Done when

Identical canonical inputs always produce the same FIFO ordering and realized output.

---

## 5. Fix holding periods to use calendar-month semantics

### Change

Replace approximate day-based holding thresholds with one shared calendar-month utility.

### Impact

Leap years and different month lengths no longer distort ST/LT classification.

### Implementation

Use one domain function:

```text
holding_boundary(acquisition_date, threshold_months)
```

Month addition follows end-of-month clamping:

```text
31 Jan + 1 month → 28/29 Feb
29 Feb + 12 months → 28 Feb next year
31 Mar + 1 month → 30 Apr
```

Then apply the explicitly configured boundary comparison consistently.

Use the same utility for:

```text
realized sale classification
unrealized lot classification
days/months-to-LTCG presentation where relevant
```

Do not maintain separate day-based holding logic in FIFO and snapshot generation.

### Done when

One day before, exact boundary, and one day after classify consistently everywhere.

---

## 6. Persist lot-level realized investment events

### Change

Create:

```text
silver.f_Investment_Realized_Events
```

Grain:

```text
one disposed FIFO lot segment per canonical sale
```

A sale consuming three lots creates three rows.

### Impact

The Quant Engine already calculates lot-level realized events in memory. This change makes them durable and identifiable.

### Implementation

Extend `fifo.sell()` to accept `Sale_ID` and emit:

```text
Realized_Event_ID
Sale_ID
Lot_ID
Purchase_ID
ISIN

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

Lot_Source_Type
```

For normal FIFO realization:

```text
Realized_Event_ID =
deterministic_id(
    "REALIZED",
    Sale_ID,
    Lot_ID
)
```

Business uniqueness:

```text
Sale_ID + Lot_ID
```

Historical realized events are immutable after creation.

### Done when

Multi-lot sales persist exact lot-level realization and full liquidation never removes realized history.

---

## 7. Persist broker/FIFO reconciliation at lot-mutation grain

### Change

Create:

```text
silver.f_Investment_Reconciliation_Events
```

with two identities:

```text
Reconciliation_Group_ID
Reconciliation_Event_ID
```

### Impact

The current Quant Engine can:

```text
add missing quantity as a synthetic lot
remove quantity from FIFO lots
scale active lot cost basis
```

These are financially material mutations and should be explainable.

### Implementation

`Reconciliation_Group_ID` represents one reconciliation operation, for example:

```text
ISIN + Market_Date + Adjustment_Type + canonical pre/target state
```

It must be deterministic and must not include Run_ID.

`Reconciliation_Event_ID` represents one affected lot mutation.

Grain:

```text
one affected lot mutation
```

Suggested fields:

```text
Reconciliation_Group_ID
Reconciliation_Event_ID
Run_ID

ISIN
Reconciliation_Date
Lot_ID
Purchase_ID

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

source / lineage identifiers
```

Keep adjustment types limited to actual behavior:

```text
QUANTITY_ADD
QUANTITY_REMOVE
COST_BASIS_ADJUSTMENT
```

### Done when

Every material broker/FIFO mutation can be explained by ISIN/date/lot/quantity/basis/reason.

---

## 8. Define reconciliation effects on lots and tax

### Change

Make reconciliation consequences explicit.

### Impact

Portfolio reconstruction can remain useful without synthetic evidence silently becoming tax-quality evidence.

### Implementation

#### Quantity add

When broker quantity exceeds reconstructed FIFO quantity:

```text
create synthetic Lot_ID
Purchase_ID = NULL
Lot_Source_Type = RECONCILIATION
```

The reconciliation date is an operational anchor, not asserted true acquisition evidence.

The lot participates in:

```text
portfolio state
wealth analytics
FIRE
market analytics
```

If later sold:

```text
Realized Event → persisted
TaxEvent → CHECK_REQUIRED
Taxable_Amount → NULL
Applied_Rate → NULL
Estimated_Tax → NULL
```

The modelled realized P&L may remain in the realized-event fact, but tax treatment must not pretend the synthetic date/basis is authoritative.

#### Quantity remove

Reduce/remove the affected FIFO lots and record lot-level reconciliation events.

Surviving purchase-derived lots retain their Lot_ID.

If their acquisition date/basis is otherwise unchanged, they do not automatically become tax-check-required merely because quantity was removed.

#### Cost-basis adjustment

Change active lot basis.

Future FIFO disposals use the adjusted basis.

Historical realized events remain immutable.

A future disposal from a materially basis-adjusted lot becomes:

```text
Tax_Status = CHECK_REQUIRED
```

because its gain depends on reconstructed basis.

### Done when

Reconciliation affects current/future state without rewriting realized history or manufacturing false tax certainty.

---

## 9. Add TaxConfig at Head → Tax Sub-Head level

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

New income streams normally require only adding IDs to an existing tax sub-head.

### Implementation

Use one uniform schema.

Suggested enums:

```text
taxability:
taxable
non_taxable
review

tax_method:
ordinary_rate
capital_gains
exempt
review
```

`cat_ids` claims the complete category.

`sub_cat_ids` claims exact subcategories only.

No category override/exclusion semantics.

Effective overlaps across tax sub-heads are configuration errors.

### Done when

Income taxonomy changes normally require FinancialRules changes only.

---

## 10. Keep tax credits at Subcategory level only

### Change

Use only:

```text
tax_credit_sub_cat_ids
```

### Impact

TDS/tax-credit mapping remains explicit and simple.

### Implementation

Source ledger entries may be negative:

```text
TDS = -20,000
```

Canonical tax state must normalize:

```text
Observed_Tax_Credits = 20,000
```

Contract:

```text
Observed_Tax_Credits >= 0
```

Do not add category-level tax-credit inheritance.

### Done when

Cash and tax-credit views both reconcile and tax credits are always non-negative.

---

## 11. Define tax-event ownership

### Change

Every canonical TaxEvent must have exactly one producer.

### Impact

Investment capital gains cannot be double counted between household income mappings and FIFO realized events.

### Implementation

Use:

```text
specialized Investment Engine
>
generic ledger classification
```

Reuse the existing investment-category configuration to identify investment-related activity.

For investment activity:

```text
FIFO
→ f_Investment_Realized_Events
→ f_Tax_Events
```

Suppress generic ledger-derived capital gains for those investment categories.

### Done when

One economic investment gain appears exactly once in TaxEvents.

---

## 12. Define TaxEvent identity and uniqueness

### Change

Give every TaxEvent a deterministic identity and explicit natural uniqueness.

### Impact

Tax events remain stable across full Silver rebuilds and cannot duplicate silently.

### Implementation

Business uniqueness:

```text
Source_Type
+ Source_ID
+ Tax_Sub_Head
```

Deterministic ID:

```text
Tax_Event_ID =
deterministic_id(
    "TAX",
    Source_Type,
    Source_ID,
    Tax_Sub_Head
)
```

For investment realization:

```text
Source_Type = INVESTMENT_REALIZED
Source_ID = Realized_Event_ID
```

For ledger income:

```text
Source_Type = LEDGER
Source_ID = stable ledger transaction identity
```

Including `Tax_Sub_Head` allows one source event to produce multiple legitimate tax interpretations if that is ever supported.

### Done when

TaxEvent rebuilds are stable and the natural uniqueness constraint is enforceable.

---

## 13. Support non-investment capital gains

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

The mapped amount must already represent gain/loss, not gross sale proceeds, unless richer evidence exists.

Use:

```text
Default_STCG
Default_LTCG
```

from Macro Parameters for the supported default calculation.

Insufficient classification becomes:

```text
CHECK_REQUIRED
```

### Done when

Non-investment capital gains/losses flow correctly without affecting investment ownership.

---

## 14. Rename the ordinary-income macro parameter

### Change

Rename:

```text
Dividend_Income_Tax_Rate
```

to:

```text
Estimated_Ordinary_Income_Tax_Rate
```

in:

```text
silver.d_Macro_Parameters
```

### Impact

Salary, interest, dividend, and other supported ordinary taxable streams share one explicit FY planning assumption.

### Implementation

Route:

```text
tax_method = ordinary_rate
→ Estimated_Ordinary_Income_Tax_Rate
```

Keep existing capital-gain rate fields and exemptions.

Do not add separate salary/interest/dividend rates or a slab engine.

### Done when

A new FY ordinary-rate assumption is a macro-data change.

---

## 15. Keep non-taxable income outside TaxEvents

### Change

Configured non-taxable streams such as cashback/digital-wallet income do not enter:

```text
silver.f_Tax_Events
```

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

---

## 16. Create canonical TaxEvents

### Change

Create:

```text
silver.f_Tax_Events
```

Grain:

```text
one Source_Type + Source_ID + Tax_Sub_Head
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

Tax Status remains descriptive, not workflow:

```text
READY
CHECK_REQUIRED
```

### Done when

Every supported tax-relevant event enters the tax engine through one inspectable Silver fact.

---

## 17. Fix capital-loss set-off with explicit priority

### Change

Replace aggregate loss arithmetic with one explicit ordered ST/LT set-off function.

### Impact

Net gains/losses and estimated tax remain correct and explainable when capital losses exist.

### Implementation

Use this supported order:

```text
1. STCL against STCG
2. remaining STCL against LTCG
3. LTCL against remaining LTCG
4. LTCL cannot offset STCG
```

One tested domain function owns the ordering.

Return an explicit result:

```text
original_stcg
original_ltcg
available_stcl
available_ltcl

stcl_used_against_stcg
stcl_used_against_ltcg
ltcl_used_against_ltcg

net_stcg
net_ltcg

closing_stcl
closing_ltcl
```

### Done when

Every loss movement can be explained from the returned state.

---

## 18. Add carry-forward state

### Change

Represent brought-forward and closing STCL/LTCL across FYs.

### Impact

Supported capital losses do not disappear between FYs.

### Implementation

Use:

```text
Opening Tax Loss State
+
Current FY Capital Gains/Losses
→ ordered Set-Off Engine
→ Closing Tax Loss State
```

Keep STCL and LTCL separate.

If application history begins with an existing brought-forward loss, allow a small explicit opening state instead of inventing historical transactions.

Carry-forward remains financial analytical state, not Control Plane state.

### Done when

Full, partial, no-utilization, and multi-FY scenarios reconcile deterministically.

---

## 19. Add FY Tax State in Silver

### Change

Create:

```text
silver.f_Tax_FY_State
```

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

STCL_Used_Against_STCG
STCL_Used_Against_LTCG
LTCL_Used_Against_LTCG

Closing_STCL
Closing_LTCL

Net_Taxable_STCG
Net_Taxable_LTCG

Estimated_Ordinary_Tax
Estimated_Capital_Gains_Tax
Estimated_Gross_Tax

Observed_Tax_Credits
Estimated_Net_Tax_Position

Check_Required_Count
```

Use:

```text
Estimated_Net_Tax_Position
=
Estimated_Gross_Tax
-
Observed_Tax_Credits
```

Do not clamp to zero.

A negative value represents an estimated excess-credit/refund position rather than a payable amount.

### Done when

Every material Gold tax value reconciles through FY Tax State to TaxEvents.

---

## 20. Add three Gold tax marts

### A. `gold.Tax_Year_Summary`

Grain:

```text
FY
```

Purpose:

```text
one-row year-end tax picture
```

### B. `gold.Tax_Income_Breakdown`

Grain:

```text
FY
× Income Head
× Tax Sub-Head
× Source Type
```

Purpose:

```text
detailed tax-preparation breakdown
```

Investment and other capital gains remain distinguishable.

### C. `gold.Tax_Reconciliation`

Grain:

```text
FY
× Tax Sub-Head
× Source Type
```

Purpose:

```text
trace financial amounts through tax calculation
```

Suggested measures:

```text
Gross_Source_Amount
Excluded_Non_Taxable_Amount
Tax_Event_Amount
Realized_Investment_Gain_Loss
Set_Off_Amount
Net_Taxable_Amount
Estimated_Tax
Tax_Credits
Estimated_Net_Tax_Position
Event_Count
Check_Required_Count
```

### Impact

Gold answers:

```text
Tax_Year_Summary
→ What is the FY tax picture?

Tax_Income_Breakdown
→ Where did it come from?

Tax_Reconciliation
→ Can I trace the calculation?
```

### Done when

All three marts reconcile to the same FY Tax State.

---

## 21. Keep and rename the investment tax forecast

### Change

Rename the existing Tax Liability Forecast to:

```text
gold.Investment_Tax_Liability_Forecast
```

### Impact

It remains clearly separate from realized FY tax reporting.

### Forecast definition

The forecast asks:

> If the current open investment portfolio were liquidated as of the forecast date, what incremental capital-gain tax exposure would those hypothetical disposals create given the current FY tax state?

### Implementation

Start from a copy of actual tax state:

```text
current FY realized gain/loss state
+ brought-forward STCL/LTCL
```

Then add:

```text
hypothetical gains/losses from liquidation of current open lots
```

Run the same ordered capital-loss set-off logic.

Do not write hypothetical disposals back into:

```text
f_Investment_Realized_Events
f_Tax_Events
f_Tax_FY_State
```

This is a read-only scenario calculation.

Reconciliation-created/check-required lots must not generate falsely precise forecast tax. Surface their uncertainty according to the final forecast presentation design.

### Done when

Investment tax forecasting is scenario-based, uses actual FY loss state, and never mutates realized tax state.

---

## 22. Fix XIRR failure semantics

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

Propagate status through the Quant Engine, lot/instrument analytics, and Gold consumers rather than fixing only the lowest-level solver.

### Done when

All XIRR consumers preserve the distinction between valid zero and failure.

---

## Final contract changes

Existing Silver changes:

```text
f_Investment_Purchase_Data
+ Purchase_ID

f_Investment_Sale_Data
+ Sale_ID

f_Investment_Analytics_Lot
+ Lot_ID
+ Purchase_ID
+ Lot_Source_Type
```

New Silver:

```text
silver.f_Investment_Realized_Events
silver.f_Investment_Reconciliation_Events
silver.f_Tax_Events
silver.f_Tax_FY_State
```

New Gold:

```text
gold.Tax_Year_Summary
gold.Tax_Income_Breakdown
gold.Tax_Reconciliation
```

Renamed Gold:

```text
Tax_Liability_Forecast
→ Investment_Tax_Liability_Forecast
```

Do not freeze handwritten total counts here.

After implementation:

```text
Data Contract Registry = source of truth
```

for exact Bronze/Silver/Gold inventory.

---

## Final financial flow

```text
CANONICAL PURCHASE
      ↓
Purchase_ID
      ↓
Lot_ID [PURCHASE]
      │
      ├───────────────┐
      │               │
      ▼               ▼
LOT ANALYTICS    RECONCILIATION
                     │
                     └─ may create Lot_ID [RECONCILIATION]

CANONICAL SALE
      ↓
Sale_ID
      ↓
FIFO consumes Lot_ID(s)
      ↓
f_Investment_Realized_Events
      ↓
f_Tax_Events
      ↓
ordered capital-loss set-off
      ↓
carry-forward
      ↓
f_Tax_FY_State
      ↓
┌──────────────┬──────────────────┬──────────────────┐
▼              ▼                  ▼
Tax_Year_      Tax_Income_        Tax_
Summary        Breakdown          Reconciliation
```

Market/benchmark state remain separate:

```text
Market Data
→ broker/current-state reconciliation anchor

Benchmark Data
→ reference market series
```

---

## Explicitly out of scope

Do not build:

```text
source-row broker transaction redesign
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
manual review-workflow system
```

---

## Financial Domain Freeze completion

The domain is frozen when:

1. Canonical purchases/sales have deterministic IDs.
2. FIFO lots have deterministic Lot_ID and explicit source type.
3. Lot identity survives partial sales and reconciliation mutations.
4. Same-day FIFO ordering is deterministic and documented.
5. Holding periods use one calendar-month utility.
6. Lot-level realized events are durable and immutable.
7. Broker/FIFO reconciliation is persisted at lot-mutation grain.
8. Synthetic reconciliation lots cannot masquerade as tax-ready purchase evidence.
9. TaxConfig uses Head → Tax Sub-Head mappings.
10. Tax credits use Subcategory IDs and normalize to non-negative values.
11. Investment capital gains have one canonical producer.
12. TaxEvents have deterministic identity and uniqueness.
13. Non-investment ST/LT capital gains/losses are supported.
14. The ordinary-income macro rate is generalized.
15. Non-taxable income stays outside TaxEvents.
16. Capital-loss set-off uses one explicit priority function.
17. Carry-forward state is explicit.
18. FY Tax State reconciles annual calculation.
19. Three Gold tax marts reconcile to FY Tax State.
20. Investment tax forecasting uses actual FY state plus hypothetical liquidation without mutating actual tax state.
21. XIRR failure states propagate explicitly.
22. Contract inventory is frozen from the implemented registry.
