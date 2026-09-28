# Financial Domain Freeze Sprint

## Goal

Harden the financial model around the scenarios I actually use: investment lots, realized gains/losses, household income, estimated tax preparation, and year-end review.

The output remains financial and tax guidance. It does not replace final filing due diligence or become a general Indian tax-return engine.

## 1. Lock supported holding-period semantics

### Change

Make holding classification deterministic for the investment types currently supported and actually used.

### Impact

Boundary dates, partial lots, and sale-date treatment stop depending on implicit assumptions.

### Implementation

For each supported tax type/subtype, define and test:

```text
acquisition date
disposal/reference date
holding threshold
exact threshold behavior
STCG / LTCG result
partial FIFO disposal
```

Keep the current FinancialRules approach unless a real scenario requires another model.

## 2. Persist realized investment events

### Change

Create durable canonical realized events when FIFO disposes a lot.

```text
Sale → FIFO disposal → Realized Investment Event
```

### Impact

Realized history survives full portfolio liquidation and becomes independently queryable.

It also separates financial history from later tax interpretation.

### Implementation

Persist useful financial facts:

```text
event_id
instrument / ISIN
acquisition_date
disposal_date
quantity
sale_proceeds
disposed_cost_basis
realized_gain_loss
source lineage
```

Tax treatment is derived downstream from the event plus rules/macro context.

## 3. Add a minimal `taxconfig` to FinancialRules

### Change

Map the existing household Category/Subcategory taxonomy into tax heads.

Each section key is the stable tax-head ID.

Example:

```toml
[taxconfig.income_from_salary]
display_name = "Income from Salary"
cat_ids = ["SALARY"]
sub_cat_ids = []
tax_credit_sub_cat_ids = ["SALARY_TDS"]
taxability = "taxable"
tax_method = "ordinary_rate"
```

### Impact

Adding a new income stream later normally means adding its Category/Subcategory ID to an existing list, not creating new Python/config structures.

### Implementation

Use one uniform schema for every tax head:

```text
display_name
cat_ids[]
sub_cat_ids[]
tax_credit_sub_cat_ids[]
taxability
tax_method
```

Keep enums small:

```text
taxability:
taxable
exempt
review

tax_method:
ordinary_rate
capital_gains
exempt
review
```

Matching rules:

```text
cat_ids
→ claims the complete category and all its subcategories

sub_cat_ids
→ claims only those specific subcategories
```

Do not support overrides/exclusions.

A Category/Subcategory must resolve to at most one tax head. Overlap is a configuration error.

## 4. Keep tax credits simple

### Change

Use only:

```text
tax_credit_sub_cat_ids
```

### Impact

TDS stays explicit without introducing unnecessary category inheritance.

The household ledger can still represent:

```text
Gross income +100
TDS -20
Cash received 80
```

while the tax model sees gross income of 100 and observed tax credit of 20.

### Implementation

For mapped tax-credit subcategories, use the absolute ledger amount as observed tax already withheld/credited.

Gold should show:

```text
Estimated Gross Tax
Observed Tax Credits
Estimated Net Tax Payable
```

## 5. Define tax-event ownership

### Change

Every canonical tax event has exactly one financial producer.

### Impact

Capital gains cannot be double counted between the household ledger and Investment Engine.

### Implementation

Use this precedence:

```text
specialized Investment Engine
>
generic ledger classification
```

For configured investment activity:

```text
Investment Engine
→ Realized Investment Event
→ Capital Gain Tax Event
```

Suppress the generic ledger-derived gain for the same investment activity.

Reuse the existing investment-category rules to identify investment activity. Do not duplicate those IDs inside `taxconfig`.

## 6. Support non-investment capital gains from the ledger

### Change

Allow `income_from_capital_gains` to also map household Category/Subcategory IDs.

Example:

```toml
[taxconfig.income_from_capital_gains]
display_name = "Capital Gains"
cat_ids = ["CAPITAL_GAINS"]
sub_cat_ids = []
tax_credit_sub_cat_ids = []
taxability = "taxable"
tax_method = "capital_gains"
```

### Impact

Broker-managed investment gains and other capital-asset gains can flow into one tax head without sharing the same producer.

### Implementation

Investment gains come from Realized Investment Events.

Non-investment mapped ledger amounts may create capital-gain TaxEvents.

For ledger-derived capital gains, the mapped amount must already represent gain/loss, not gross sale proceeds, unless richer cost-basis evidence exists.

If holding treatment cannot be determined, mark it for review instead of inventing STCG/LTCG.

## 7. Extend Macro Parameters minimally

### Change

The existing `silver.d_Macro_Parameters` already has FY grain and owns tax-rate assumptions.

Add:

```text
Estimated_Ordinary_Income_Tax_Rate
```

Deprecate/replace:

```text
Dividend_Income_Tax_Rate
```

once dividends use the common ordinary-income path.

### Impact

Salary, interest, and dividend can share one explicit planning rate instead of creating separate tax-rate columns.

### Implementation

Route:

```text
ordinary_rate
→ Estimated_Ordinary_Income_Tax_Rate
```

Keep the existing equity/gold/debt/default capital-gain rates and Equity LTCG exemption.

Do not add:

```text
salary rate
interest rate
dividend rate
slab calculator
basic exemption
standard deduction
rebate
cess/surcharge model
```

unless a real future use case requires it.

## 8. Freeze tax responsibility boundaries

Use this ownership model:

```text
FinancialRules.taxconfig
→ maps financial taxonomy to tax heads

d_Macro_Parameters
→ FY-specific numeric assumptions

Python tax domain
→ calculation algorithms

Tax Events / FY Tax State
→ derived financial interpretation

Gold
→ filing-preparation presentation
```

Never put these into `taxconfig`:

```text
tax rates
slabs
cess/surcharge
rebates/deductions
holding periods
set-off rules
carry-forward years
ITR schedule/field numbers
tax-law formulas
```

## 9. Create a canonical Tax Event stream

### Change

Create a Silver fact such as:

```text
silver.f_Tax_Events
```

Grain:

```text
one tax-relevant financial event
```

### Impact

Household income and investment gains reach the tax engine through one inspectable contract.

### Implementation

Keep the fields practical:

```text
tax_event_id
event_date
FY
source_type
source_id
tax_head_id
taxability
tax_method
gross_amount
taxable_amount
gain_type
realized_gain_loss
applied_rate
estimated_tax
evidence_quality
requires_review
review_reason
rules_snapshot_id
```

Use a small evidence-quality set:

```text
OBSERVED
RECONSTRUCTED
RECONCILED
MODELLED
```

Use the normal reproducibility envelope for macro/reference provenance rather than copying the whole macro row.

## 10. Add review flags

### Change

Tax events can explicitly require manual review.

### Impact

Weak or incomplete evidence becomes visible instead of silently becoming a confident tax answer.

### Implementation

Use:

```text
requires_review
review_reason
```

Examples:

```text
missing acquisition basis
reconciliation affected basis
unknown tax subtype
unmapped classification
insufficient holding evidence
fallback treatment used
```

Unmapped/ambiguous activity should become `review`, not automatically non-taxable.

## 11. Implement explicit capital-loss set-off

### Change

Calculate STCL/LTCL set-off explicitly instead of using aggregate loss arithmetic.

### Impact

The FY tax state can explain where every supported capital loss was used.

### Implementation

Track separately:

```text
STCL
LTCL
STCG
LTCG
```

Apply the supported set-off rules in Python domain code, not user configuration.

Return:

```text
loss_used
remaining_STCL
remaining_LTCL
net_taxable_STCG
net_taxable_LTCG
```

## 12. Add carry-forward state where required

### Change

Represent remaining STCL/LTCL across FYs.

### Impact

Supported brought-forward losses do not disappear between snapshots/FYs.

### Implementation

Use:

```text
Opening Tax Loss State
+
Current FY Tax Events
→ Set-Off Engine
→ Closing Tax Loss State
```

Keep STCL and LTCL separate.

If history begins after an existing brought-forward loss, allow a small explicit opening state rather than inventing old transactions.

Keep this in financial analytical state, not the Control Plane.

## 13. Build FY Tax State

### Change

Aggregate Tax Events into one annual calculation state.

Suggested fields:

```text
FY
gross_income
ordinary_taxable_income
STCG
LTCG
STCL
LTCL
loss_utilized
loss_carried_forward
exemptions
estimated_ordinary_tax
estimated_capital_gains_tax
estimated_gross_tax
observed_tax_credits
estimated_net_tax_payable
review_item_count
```

### Impact

This becomes the reconciliation point between Tax Events and Gold.

## 14. Create two Gold tax-preparation marts

### Tax Year Summary

Grain:

```text
FY
```

Show:

```text
gross income
taxable income
estimated ordinary tax
estimated capital-gains tax
estimated gross tax
observed tax credits
estimated net tax payable
loss carry-forward
review count
```

### Tax Income Breakdown

Grain:

```text
FY × Tax Head × Source Type
```

Show:

```text
tax head
source type
gross amount
taxable amount
estimated tax
tax credits
evidence quality
review state
```

For Capital Gains, allow:

```text
Investment Realized
Other Capital Assets
→ Total Capital Gains
```

### Impact

The year-end dashboard becomes a filing-preparation aid without mirroring the full ITR schema.

## 15. Fix XIRR edge states

### Change

Do not convert every invalid/non-convergent portfolio XIRR into a meaningful `0%`.

### Implementation

Return an explicit result such as:

```text
value
status
reason
```

Possible statuses:

```text
VALID
UNDEFINED_CASH_FLOWS
NON_CONVERGENT
INVALID_INPUT
```

### Impact

A genuine 0% return is distinguishable from an XIRR that could not be calculated.

## 16. Make reconciliation adjustments explainable

### Change

Keep broker reconciliation but preserve adjustment provenance.

### Implementation

Expose enough information to explain:

```text
adjustment_type
reason
quantity_impact
basis_impact
evidence_quality
```

### Impact

Current-state reconciliation remains useful without making synthetic adjustments look like observed historical acquisition evidence.

## 17. Keep corporate actions limited

### Change

Support/test only cases that current source evidence can determine reliably.

### Impact

The application avoids a large corporate-actions framework built on incomplete broker evidence.

### Implementation

Test deterministic supported behavior.

Anything ambiguous becomes a documented review boundary.

## 18. Build one financial/tax reconciliation view

The final trace should be:

```text
Source Evidence
→ Financial Event
→ Realized / Income Event
→ Tax Event
→ FY Tax State
→ Set-Off / Carry-Forward
→ Tax Preparation Gold
→ Review Items
```

### Impact

A material estimated-tax number can be traced back to the financial evidence that produced it.

## Explicitly out of scope

Do not build:

```text
complete ITR preparation
ITR schedule/field emulator
tax-regime optimizer
slab engine
TDS/TCS reconciliation platform
AIS / 26AS ingestion
deduction engine
Form 16 reconstruction
house-property tax engine
business/profession tax
foreign-asset reporting
universal corporate-actions engine
every Indian asset class
```

## Sprint completion

The domain is frozen when:

1. Holding boundaries are deterministic.
2. Realized investment events survive liquidation.
3. Tax heads use simple Category/Subcategory mappings.
4. Tax credits use only explicit Subcategory IDs.
5. Investment gains cannot double-count ledger activity.
6. Non-investment capital gains can enter with review boundaries.
7. Macro Parameters provide one estimated ordinary-income rate.
8. Tax Events unify supported income/gain streams.
9. Loss set-off/carry-forward is explicit where supported.
10. FY Tax State reconciles the calculation.
11. Gold provides Tax Summary and Income Breakdown.
12. XIRR edge states are explicit.
13. Reconciliation provenance is visible.
14. Unknown/weak evidence becomes reviewable rather than silently assumed.
