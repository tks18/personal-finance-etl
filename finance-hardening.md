# Financial Domain Implementation Freeze

> **Status: FROZEN FOR IMPLEMENTATION**
>
> This is the implementation authority for the Financial Domain Sprint. The application provides financial/tax guidance and filing-preparation support, not authoritative ITR computation.

## Goal

Harden:

```text
canonical investment identity
FIFO lots
realized events
broker reconciliation
holding periods
household tax classification
capital-loss set-off/carry-forward
FY tax state
tax-preparation Gold
investment tax forecast
XIRR semantics
```

---

## 1. Canonical Purchase_ID / Sale_ID

Add:

```text
Purchase_ID → silver.f_Investment_Purchase_Data
Sale_ID     → silver.f_Investment_Sale_Data
```

These identify canonical aggregated financial events, not broker transactions.

Use Canonical ID Serialization v1.

```text
Purchase_ID defining fields:
PURCHASE + ISIN + Date + Price + Quantity + CURRENCY_ID

Sale_ID defining fields:
SALE + ISIN + Date + Sell_Price + Quantity + CURRENCY_ID
```

Quantity is intentionally part of identity:

```text
quantity correction
→ canonical event changed
→ ID changes
```

Exclude derived fields (`Value`, P&L, weighted-average buy fields) and file/folder paths.

Generate IDs after canonical aggregation.

---

## 2. Lot_ID

Extend Quant `TaxLot` and `silver.f_Investment_Analytics_Lot`:

```text
Lot_ID
Purchase_ID
Lot_Source_Type
```

Normal lot:

```text
Lot_ID = deterministic_id(LOT, Purchase_ID)
Purchase_ID = populated
Lot_Source_Type = PURCHASE
```

Lot fact grain:

```text
Lot_ID × Closing_Date
```

Do not add Lot_ID to Market or Benchmark facts.

---

## 3. Preserve Lot identity

Partial sale, quantity reduction, and cost-basis adjustment preserve the existing Lot_ID.

Only a genuinely new reconciliation-created lot receives a new synthetic Lot_ID.

---

## 4. Same-day FIFO ordering

Where intra-day chronology is unavailable:

```text
Purchases:
Date ASC
Price ASC
Purchase_ID ASC

Sales:
Date ASC
Sell_Price ASC
Sale_ID ASC
```

Use numeric normalized prices.

This is a deterministic canonical convention, not claimed broker chronology.

Do not merge different-price same-day purchases into weighted-average lots.

---

## 5. Calendar-month holding periods

Use one shared utility:

```text
boundary_date = acquisition_date + threshold_months
```

Month addition uses end-of-month clamping:

```text
31 Jan + 1 month → 28/29 Feb
29 Feb + 12 months → 28 Feb next year
31 Mar + 1 month → 30 Apr
```

Classification:

```text
disposal_date > boundary_date
→ LTCG / LTCL

disposal_date <= boundary_date
→ STCG / STCL
```

Exact boundary is short-term.

FinancialRules supplies threshold months. The comparison operator is domain logic, not configurable.

Use the same utility for realized and unrealized classifications.

---

## 6. Lot-level realized events

Create:

```text
silver.f_Investment_Realized_Events
```

Grain:

```text
one disposed FIFO lot segment per Sale_ID
```

Contract:

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

Identity:

```text
Realized_Event_ID = deterministic_id(REALIZED, Sale_ID, Lot_ID)
UNIQUE(Sale_ID, Lot_ID)
```

Logical immutability means the same reproducible source/rule state rebuilds the same event ID and material attributes.

Later reconciliation of an active lot must not rewrite an earlier realized event.

---

## 7. Lot-level reconciliation events

Create:

```text
silver.f_Investment_Reconciliation_Events
```

Two identities:

```text
Reconciliation_Group_ID
Reconciliation_Event_ID
```

Group:

```text
deterministic_id(
  RECON_GROUP,
  ISIN,
  Reconciliation_Date,
  Adjustment_Type,
  canonical pre-adjustment state,
  canonical target state
)
```

Event, where one group/type mutates a lot at most once:

```text
deterministic_id(
  RECON_EVENT,
  Reconciliation_Group_ID,
  Lot_ID,
  Adjustment_Type
)
```

Only introduce a deterministic mutation ordinal if implementation proves repeated same-lot mutation is legitimate.

Contract includes:

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
```

Adjustment types:

```text
QUANTITY_ADD
QUANTITY_REMOVE
COST_BASIS_ADJUSTMENT
```

`Run_ID` is producing-run provenance only. It never participates in financial identity.

Silver is a rebuilt projection; repeated historical run observations remain a Control Plane responsibility.

---

## 8. Reconciliation financial/tax semantics

### QUANTITY_ADD

Create:

```text
synthetic deterministic Lot_ID
Purchase_ID = NULL
Lot_Source_Type = RECONCILIATION
```

The reconciliation date is an operational anchor, not asserted acquisition evidence.

The lot participates in portfolio/wealth/FIRE analytics.

If sold:

```text
Realized Event → persisted with modelled P&L

TaxEvent:
Tax_Status = CHECK_REQUIRED
Taxable_Amount = NULL
Applied_Rate = NULL
Estimated_Tax = NULL
```

### QUANTITY_REMOVE

Reduce/remove affected lots and persist lot-level events.

Surviving purchase lots retain identity.

Quantity removal alone does not make the surviving lot CHECK_REQUIRED if its acquisition/basis evidence remains unchanged.

### COST_BASIS_ADJUSTMENT

Adjust active basis.

Future FIFO uses adjusted basis.

Earlier realized events remain logically immutable.

Future realization from a materially basis-adjusted lot:

```text
Tax_Status = CHECK_REQUIRED
```

---

## 9. TaxConfig: Head → Tax Sub-Head

Inside FinancialRules:

```text
Head of Income
→ Tax Sub-Head
→ cat_ids[]
→ sub_cat_ids[]
→ tax_credit_sub_cat_ids[]
→ taxability
→ tax_method
```

Uniform metadata:

```text
display_name
cat_ids[]
sub_cat_ids[]
tax_credit_sub_cat_ids[]
taxability
tax_method
```

Enums:

```text
taxability: taxable | non_taxable | review
tax_method: ordinary_rate | capital_gains | exempt | review
```

`cat_ids` claims the full category.

`sub_cat_ids` claims exact subcategories.

No override/exclusion semantics.

Effective overlaps are configuration errors.

---

## 10. Tax credits

Use only:

```text
tax_credit_sub_cat_ids
```

Normalize ledger sign:

```text
source TDS = -20,000
→ Observed_Tax_Credits = 20,000
```

Invariant:

```text
Observed_Tax_Credits >= 0
```

---

## 11. TaxEvent ownership

Every Source_Type has one declared producer.

```text
Investment Engine
→ owns investment realized capital gains

Ledger classification
→ owns configured ledger tax streams
```

Investment-category ledger capital-gain emission is suppressed when Investment Engine owns the economic event.

Freeze:

```text
same Source_Type + Source_ID + Tax_Sub_Head
→ emitted at most once
```

---

## 12. TaxEvent identity

### Ledger

The household source already supplies stable native:

```text
UID
```

which survives into `f_Income_Transactions`.

Therefore:

```text
Source_Type = LEDGER
Source_ID = UID
```

Do not generate another ledger ID.

### Investment

```text
Source_Type = INVESTMENT_REALIZED
Source_ID = Realized_Event_ID
```

### Tax event

```text
Tax_Event_ID =
deterministic_id(
  TAX,
  Source_Type,
  Source_ID,
  Tax_Sub_Head
)
```

Business uniqueness:

```text
Source_Type + Source_ID + Tax_Sub_Head
```

---

## 13. Non-investment capital gains

TaxConfig may map non-investment capital-asset gain/loss ledger streams.

```text
positive ST → STCG
negative ST → STCL
positive LT → LTCG
negative LT → LTCL
```

Mapped amount must already represent gain/loss unless richer evidence exists.

Use:

```text
Default_STCG
Default_LTCG
```

for supported default treatment.

Insufficient classification:

```text
CHECK_REQUIRED
```

---

## 14. Ordinary-income macro rate

Rename:

```text
Dividend_Income_Tax_Rate
→ Estimated_Ordinary_Income_Tax_Rate
```

Route:

```text
tax_method = ordinary_rate
→ Estimated_Ordinary_Income_Tax_Rate
```

Use for supported salary/interest/dividend/ordinary streams.

Keep existing capital-gain rate/exemption fields.

Do not build a slab engine.

---

## 15. Non-taxable income

Configured non-taxable streams such as cashback/digital-wallet income do **not** enter `silver.f_Tax_Events`.

Reconcile:

```text
Gross Income Ledger
- Explicitly Non-Taxable / Excluded Income
= Tax Model Income Universe
```

---

## 16. Canonical TaxEvents

Create:

```text
silver.f_Tax_Events
```

Grain:

```text
Source_Type + Source_ID + Tax_Sub_Head
```

Contract:

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

Initial Source Types:

```text
LEDGER
INVESTMENT_REALIZED
```

Status:

```text
READY
CHECK_REQUIRED
```

Status is calculation confidence/eligibility, not a manual review workflow.

---

## 17. Capital-loss set-off

One domain function owns the exact order:

```text
1. STCL → STCG
2. remaining STCL → LTCG
3. LTCL → remaining LTCG
4. LTCL cannot → STCG
```

Return:

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

---

## 18. Carry-forward

```text
Opening STCL/LTCL
+ Current FY gain/loss state
→ ordered set-off
→ Closing STCL/LTCL
```

Keep ST/LT separately.

Allow explicit opening loss state if application history begins after the loss originated.

This is financial analytical state, not Control Plane state.

---

## 19. FY Tax State

Create:

```text
silver.f_Tax_FY_State
```

Grain:

```text
FY
```

Contract:

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

```text
Estimated_Net_Tax_Position
=
Estimated_Gross_Tax
-
Observed_Tax_Credits
```

Do not clamp to zero. Negative means estimated excess-credit/refund position.

---

## 20. Gold tax marts

### `gold.Tax_Year_Summary`

Grain: FY.

### `gold.Tax_Income_Breakdown`

Grain:

```text
FY × Income Head × Tax Sub-Head × Source Type
```

### `gold.Tax_Reconciliation`

Grain:

```text
FY × Tax Sub-Head × Source Type
```

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
Estimated_Net_Tax_Position
Event_Count
Check_Required_Count
```

All three reconcile to FY Tax State.

---

## 21. Investment Tax Liability Forecast

Rename:

```text
Tax_Liability_Forecast
→ gold.Investment_Tax_Liability_Forecast
```

Question answered:

> If tax-ready current open investments were liquidated on the forecast date, what incremental capital-gain tax exposure would they create given current FY tax state?

Start from:

```text
current FY realized gain/loss state
+ brought-forward STCL/LTCL
```

Add hypothetical gains/losses from **tax-ready** open lots, then run the shared set-off engine.

### CHECK_REQUIRED exposure

Uncertain reconciliation-derived/check-required lots are excluded from precise tax.

Report separately at minimum:

```text
Check_Required_Lot_Count
Check_Required_Market_Value
Check_Required_Unrealized_PL
```

No lower/upper-bound tax scenarios in this sprint.

### Non-mutation

Forecast never writes hypothetical events into:

```text
f_Investment_Realized_Events
f_Tax_Events
f_Tax_FY_State
```

---

## 22. XIRR semantics

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

Non-valid:

```text
value = NULL
```

Propagate through math → Quant → Silver → Gold.

Never convert failure to meaningful 0%.

---

## Final contract changes

Existing Silver:

```text
f_Investment_Purchase_Data + Purchase_ID
f_Investment_Sale_Data + Sale_ID
f_Investment_Analytics_Lot + Lot_ID + Purchase_ID + Lot_Source_Type
```

New Silver:

```text
f_Investment_Realized_Events
f_Investment_Reconciliation_Events
f_Tax_Events
f_Tax_FY_State
```

New Gold:

```text
Tax_Year_Summary
Tax_Income_Breakdown
Tax_Reconciliation
```

Renamed Gold:

```text
Tax_Liability_Forecast
→ Investment_Tax_Liability_Forecast
```

Exact inventory/counts come from the Data Contract Registry.

---

## Explicitly out of scope

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
tax forecast confidence intervals
```

---

## Financial Domain Implementation Freeze checklist

1. Deterministic canonical Purchase/Sale identity.
2. Quantity is a defining Purchase/Sale attribute.
3. Deterministic Lot_ID.
4. Lot identity survives mutation.
5. Deterministic same-day FIFO ordering.
6. Calendar-month holding period with strict `>` LT boundary.
7. Durable lot-level realized events.
8. Logical realized-event immutability.
9. Lot-mutation reconciliation events.
10. Reconciliation identity excludes Run_ID.
11. Synthetic reconciliation lots have safe tax semantics.
12. Head → Tax Sub-Head TaxConfig.
13. Non-negative tax credits.
14. Single TaxEvent producer ownership.
15. Ledger TaxEvents use native UID.
16. Deterministic TaxEvent identity/uniqueness.
17. Non-investment ST/LT gains/losses.
18. General ordinary-income macro rate.
19. Non-taxable income excluded from TaxEvents.
20. Ordered capital-loss set-off.
21. Explicit carry-forward state.
22. FY Tax State.
23. Three reconciling Gold tax marts.
24. Forecast separates precise tax from CHECK_REQUIRED exposure.
25. Explicit XIRR failure state.
26. Registry owns exact final inventory.
