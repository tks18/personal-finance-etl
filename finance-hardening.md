# Personal Finance ETL --- Financial Correctness Hardening Plan

> **Baseline:** v6.5.3 (unreleased)
>
> **Purpose:** freeze a small, trustworthy financial model around the
> evidence Personal Finance ETL actually receives and the decisions it
> is intended to support.
>
> **Product boundary:** Personal Finance ETL is a personal financial
> planning and tax-guidance system. It is **not** an authoritative
> tax-return computation engine. Final filing treatment remains subject
> to verification against applicable law, broker/tax statements, and
> professional judgement.

------------------------------------------------------------------------

# 1. Domain Scope to Freeze

## In scope

The application should optimize for the assets the portfolio actually
uses:

```text
Direct listed equity
Equity mutual funds
Debt mutual funds
Gold ETF / Gold mutual fund exposure
```

Debt-specific sophistication should be implemented only to the level
required by actual holdings.

## Explicitly out of scope unless later required

```text
SGB
Physical gold
Unlisted equity
REIT / InvIT
Complex bond/debenture taxonomy
Full ITR computation
Full corporate-action accounting
Tax filing eligibility/compliance engine
```

The rule is:

> **Do not maintain tax semantics for assets the application does not
> actually need.**

------------------------------------------------------------------------

# 2. Financial Output Contract

The system should provide reliable answers to questions such as:

-   What do I currently own?
-   What did I buy and sell?
-   What gain/loss did FIFO reconstruct?
-   Does a realized gain appear short-term or long-term?
-   What capital losses appear available for planning?
-   What indicative loss set-off is available?
-   What tax exposure should I plan for?
-   What happens to estimated tax if I sell an existing holding?
-   What is my after-tax wealth estimate?
-   What information should I inspect when filing?

The system should **not** claim:

> "This is the final legally authoritative income-tax liability."

Use language such as:

```text
Estimated Portfolio Tax Exposure
Indicative Capital-Loss Carry-Forward
Estimated Tax if Sold
Tax Guidance Status
```

rather than implying final ITR computation.

------------------------------------------------------------------------

# 3. P0 --- Holding-Period Boundary Correctness

## Current risk

Holding classification currently relies on configured day thresholds and
a comparison similar to:

```text
age_days > threshold
```

That can make exact-boundary behavior unclear and can approximate
calendar periods with fixed day counts.

## Target

Use one explicit holding-period function:

```text
acquisition date
+
sale / valuation date
+
supported tax category
+
configured/current rule
        ↓
ST / LT
```

For every supported category, document:

-   threshold,
-   exact boundary semantics,
-   acquisition date treatment,
-   sale date treatment.

Keep the rule model small.

Do not build a general Indian-tax rule registry unless the actual
portfolio requires it.

## Required supported categories

At minimum:

```text
LISTED_EQUITY
EQUITY_MF
DEBT_MF
GOLD_ETF_MF
```

If Gold ETF and Gold MF need different treatment for the portfolio/rule
period being modeled, split them.

## Boundary tests

For each category:

```text
one day before threshold
exact threshold
one day after threshold
```

Also test one leap-year case.

## Done when

Every supported asset has one deterministic, documented boundary and no
generic/default threshold is silently used.

------------------------------------------------------------------------

# 4. P0 --- Safe Tax Classification

## Current risk

A missing/unknown subtype must not accidentally inherit an
equity/default rate.

## Target

Use a small closed set of supported tax categories.

Conceptually:

```text
LISTED_EQUITY
EQUITY_MF
DEBT_MF
GOLD_ETF_MF
UNCLASSIFIED
```

The exact enum names can differ.

The important behavior is:

```text
known category
→ explicit rule

unknown category
→ UNCLASSIFIED / unresolved guidance

not
→ default equity rule
```

## Output

Add or preserve an explicit status such as:

```text
Tax_Guidance_Status
```

Possible values:

```text
CLASSIFIED
UNCLASSIFIED
BASIS_UNKNOWN
REVIEW_REQUIRED
```

## Done when

Every supported instrument maps to exactly one intended category and
unknown instruments cannot silently enter estimated tax calculations.

------------------------------------------------------------------------

# 5. P0 --- Persist Realized Investment Events

## Why this matters

A sale is historical financial evidence.

It must survive after the position is fully liquidated.

The system should support:

```text
Buy
→ Sell
→ Position becomes zero
→ Rebuild analytics

realized sale history still exists
```

## Target Silver fact

Create a durable fact conceptually like:

```text
f_Investment_Realized_Event
```

Recommended grain:

> **one consumed FIFO lot fragment per sale**

Suggested fields:

```text
Realized_Event_ID
ISIN
Instrument
Sale_Date
Acquisition_Date
Quantity
Disposed_Cost_Basis
Sale_Proceeds
Realized_PnL
Holding_Class
Tax_Category
Financial_Year
Source_Sale_ID
Source_Lot_ID
Basis_Quality
```

Do not make this a statutory "tax ledger".

It is a durable realized-investment-event fact that also supports tax
guidance.

## Invariant

```text
every disposed FIFO lot fragment
→ exactly one realized event
```

## Done when

Full liquidation removes active lots but does not remove realized
history.

------------------------------------------------------------------------

# 6. P0 --- Capital-Loss Set-Off Guidance

## Why keep this

This is highly useful for tax planning even without building an ITR
engine.

The guidance model should explicitly represent:

```text
STCL → STCG
STCL → LTCG
LTCL → LTCG
LTCL → STCG  ✗
```

The statutory relationship is supported by Income-tax Act section 74 /
current Income Tax Department guidance. Capital losses remain
capital-gain losses; LTCL is restricted to LTCG, while STCL may be used
against short- or long-term capital gains. Eligible unabsorbed capital
losses may generally carry forward for up to eight succeeding years
subject to filing conditions.

## Target calculation

```text
Gross STCG
Gross LTCG
Gross STCL
Gross LTCL
        ↓
Indicative Set-Off
        ↓
Net STCG
Net LTCG
        ↓
Estimated Capital-Gain Tax Exposure
```

Do not use:

```text
min(total losses, total gains)
```

## Suggested output

```text
Gross_STCG
Gross_LTCG
Gross_STCL
Gross_LTCL
STCL_Used_Against_STCG
STCL_Used_Against_LTCG
LTCL_Used_Against_LTCG
Net_STCG
Net_LTCG
Unused_STCL
Unused_LTCL
```

## Ordering

Choose one deterministic ordering policy and document it.

Do not pretend the ordering policy itself is an authoritative tax-filing
determination.

## Done when

The four legal relationships above are enforced and the set-off bridge
is visible rather than hidden inside one number.

------------------------------------------------------------------------

# 7. P1 --- Lightweight Loss Carry-Forward Guidance

## Product boundary

The app should remember apparent prior-year losses because that is
useful for planning.

It should not decide whether the taxpayer legally satisfied every filing
condition.

## Target state

Keep:

```text
Origin_FY
Loss_Type
Opening_Carryforward
Current_Year_Unused_Loss
Used_Current_FY
Closing_Carryforward
Age
Guidance_Status
```

Possible guidance statuses:

```text
AVAILABLE_FOR_REVIEW
PARTIALLY_USED
FULLY_USED
EXPIRED
REVIEW_FILING_ELIGIBILITY
```

## Important disclaimer

The app may show:

> "₹X STCL appears available from prior years."

The user verifies actual carry-forward eligibility against filed returns
before relying on it for filing.

## Done when

Multiple FYs can be represented without losing the origin year and
STCL/LTCL remain separate.

------------------------------------------------------------------------

# 8. P0 --- Fix Estimated Portfolio Tax Exposure

## Concrete bug

`Taxable_Interest` is available in the analytical output but is omitted
from the current projected-tax calculation.

Fix it.

## Scope

Rename/define the calculation as:

> **Estimated Portfolio Tax Exposure**

It should combine only the financial components the application
intentionally models.

Conceptually:

```text
Estimated capital-gain tax
+
Estimated dividend tax
+
Estimated interest tax
=
Estimated Portfolio Tax Exposure
```

## Avoid overclaiming

Do not imply this includes the complete taxpayer return unless actually
modeled.

The estimate may intentionally exclude:

```text
complete slab computation
rebates
all deductions
surcharge
tax credits
advance tax
other heads of income
filing adjustments
```

Document exactly what is included.

## Rate safety

Do not apply one global equity rate to every realized gain if multiple
supported categories require different rates.

Each tax-guidance component should retain its category until the
estimate is calculated.

## Done when

The tax exposure can be reconciled:

```text
capital-gain component
+
dividend component
+
interest component
=
reported estimated exposure
```

------------------------------------------------------------------------

# 9. P0 --- XIRR Null Semantics

## Current bug

The low-level XIRR path can represent failure as `NaN`, while
portfolio-level calculation can convert failure/non-convergence into
`0.0`.

That makes:

```text
valid 0% return
```

indistinguishable from:

```text
XIRR unavailable
```

## Minimal target

Use:

```text
XIRR = nullable float
```

Optionally add:

```text
XIRR_Status
```

if useful for debugging/UI.

At minimum:

```text
valid 0%
→ 0.0

undefined / invalid / non-convergent
→ null / NaN
```

Apply the same semantics to:

-   ISIN XIRR,
-   portfolio XIRR,
-   benchmark XIRR,
-   after-tax XIRR.

## Done when

No XIRR calculation converts "cannot calculate" into a financial return
of zero.

------------------------------------------------------------------------

# 10. P0 --- Reconciliation Evidence Quality

## Current limitation

Broker evidence can show current holdings that cannot be perfectly
reconstructed from transaction history.

Examples include corporate-action effects where the broker snapshot may
expose:

```text
quantity
```

but not enough reliable evidence to reconstruct:

```text
event type
tax acquisition date
tax cost basis
```

## Product rule

Do **not** infer corporate actions that the evidence cannot prove.

Instead:

```text
Observed transaction history
        ↓
Reconstructed state
        ↓
Broker state differs
        ↓
Explicit reconciliation adjustment
```

## Evidence-quality states

At minimum distinguish:

```text
OBSERVED
RECONCILED
BASIS_UNKNOWN
REVIEW_REQUIRED
```

## Important rule

```text
known zero cost
≠
unknown cost basis
```

Do not turn missing/unknown basis into a fake ₹0 basis and then
calculate a misleading tax result.

## Done when

Current portfolio state can reconcile while the system clearly
identifies where exact historical/tax basis needs manual verification.

------------------------------------------------------------------------

# 11. P0 --- Reconciliation Must Not Rewrite Realized History

## Risk

A current-state cost-basis reconciliation should not silently change a
gain/loss that was already realized from earlier source evidence.

## Target

Separate:

```text
historical realized event
```

from:

```text
current-state reconciliation adjustment
```

Once a realized event is persisted, later current-position
reconciliation must not mutate it unless a deliberate historical
correction is being performed.

## Done when

A test can:

```text
buy
→ sell partially
→ persist realized event
→ reconcile remaining position
```

and prove that the prior realized event is unchanged.

------------------------------------------------------------------------

# 12. P1 --- Corporate Actions: Explicitly Do Not Infer

## Scope decision

Do not build a corporate-action engine in this sprint.

The current broker evidence is not consistently rich enough to identify
every:

```text
bonus
split
merger
demerger
rights issue
```

with tax-quality acquisition/basis evidence.

## Policy

If a corporate action is explicitly represented in reliable source
evidence and already supported, process it according to the existing
documented rule.

Otherwise:

```text
quantity/basis mismatch
→ reconciliation adjustment
→ evidence-quality flag
→ manual review for tax filing
```

## Documentation

Create a tiny support matrix:

  Event                            Current handling
  -------------------------------- -------------------------
  Ordinary buy/sell                Supported
  Partial FIFO sale                Supported
  Full liquidation                 Supported
  Bonus not explicitly evidenced   Reconciliation / review
  Split not explicitly evidenced   Reconciliation / review
  Merger/demerger                  Unsupported / review
  Other corporate action           Unsupported / review

The matrix can evolve only when actual portfolio evidence requires it.

------------------------------------------------------------------------

# 13. P0 --- Sale Quantity / FIFO Completeness

## Financial invariant

A sale must not silently consume fewer units than requested.

Require:

```text
sum(disposed FIFO quantity)
=
sale quantity
```

If:

```text
sale quantity > reconstructed available quantity
```

then either:

-   fail the financial calculation, or
-   create an explicit unresolved reconciliation condition.

Do not silently calculate realized P&L on only the quantity that
happened to exist in reconstructed lots.

## Done when

Oversell is an explicit financial-data problem rather than a partial
result.

------------------------------------------------------------------------

# 14. P1 --- Transaction Costs

If source evidence contains brokerage/transfer expenses, define whether
and how they affect:

```text
sale proceeds
cost basis
realized P&L
tax guidance
```

If the source does not provide reliable expenses:

> explicitly document that estimated capital gains exclude unavailable
> transaction-cost adjustments.

Do not invent missing costs.

------------------------------------------------------------------------

# 15. Financial Invariants to Freeze

## Quantity

```text
Opening Quantity
+ Purchases
- Sales
± Explicit Reconciliation Adjustments
=
Closing Quantity
```

## FIFO

```text
Disposed Quantity
≤ Available Quantity
```

and:

```text
sum(consumed lot fragments)
=
sale quantity
```

## Cost basis

```text
Opening Basis
+ Purchase Basis
± Explicit Basis Adjustments
- Disposed Basis
=
Closing Basis
```

## Realized P&L

```text
Realized P&L
=
Sale Proceeds
- Disposed Cost Basis
```

subject to the documented transaction-cost policy.

## Realized event

```text
every consumed FIFO lot fragment
→ exactly one realized event
```

## FY

```text
every realized event
→ exactly one FY
```

## Loss set-off

```text
LTCL used against STCG
=
0
```

## Estimated tax exposure

```text
Estimated Portfolio Tax Exposure
=
sum(modeled tax-guidance components)
```

## Rebuild

```text
same evidence
+
same financial configuration
=
same deterministic outputs
```

------------------------------------------------------------------------

# 16. Golden Financial Scenarios

Target approximately **25-35 small deterministic scenarios**.

## FIFO

-   Single buy.
-   Multiple buys.
-   Partial sell.
-   Sell across multiple lots.
-   Multiple partial sells.
-   Full liquidation.
-   Sale exceeds available inventory.

## Holding period

For each supported category:

-   one day before boundary,
-   exact boundary,
-   one day after boundary.

## Gain/loss

-   STCG.
-   LTCG.
-   STCL.
-   LTCL.
-   Zero gain.

## Loss set-off

-   STCL against STCG.
-   STCL against LTCG.
-   LTCL against LTCG.
-   LTCL blocked against STCG.
-   Mixed STCG/LTCG/STCL/LTCL.

## Carry-forward guidance

-   no prior loss,
-   partial utilization,
-   multiple FYs,
-   STCL/LTCL kept separately,
-   expired/review-required state.

## Income/tax guidance

-   dividend only,
-   interest only,
-   capital gain only,
-   gain + dividend + interest,
-   loss set-off reducing estimated exposure.

## XIRR

-   positive,
-   negative,
-   valid 0%,
-   undefined/non-convergent.

## Reconciliation

-   quantity mismatch,
-   basis mismatch,
-   unknown basis,
-   prior realized history survives reconciliation.

## Lifecycle

```text
buy
→ hold
→ partial sell
→ buy again
→ sell
→ full liquidation
→ rebuild

realized history remains identical
```

------------------------------------------------------------------------

# 17. Financial Reconciliation Report

Build one correctness report, not another decision dashboard.

## Flow

```text
Broker Transactions
        ↓
FIFO Lots
        ↓
Realized Events
        ↓
ST / LT Classification
        ↓
Gross Gain / Loss
        ↓
Indicative Loss Set-Off
        ↓
Estimated Portfolio Tax Exposure
```

## Required sections

### Source

-   purchase quantity/value,
-   sale quantity/value,
-   transaction count.

### FIFO

-   lots created,
-   lots consumed,
-   remaining lots,
-   quantity reconciliation.

### Realized events

-   sale,
-   acquisition lot,
-   quantity,
-   basis,
-   proceeds,
-   realized P&L,
-   holding class.

### Tax guidance

-   gross STCG,
-   gross LTCG,
-   gross STCL,
-   gross LTCL,
-   indicative set-off,
-   net gains,
-   dividend,
-   interest,
-   estimated portfolio tax exposure.

### Review flags

-   unclassified asset,
-   unknown basis,
-   reconciliation adjustment,
-   unsupported corporate action,
-   other review-required evidence.

## Primary question

For every material tax-guidance amount:

> **Can I trace this estimate back to the source evidence and
> assumptions that produced it?**

------------------------------------------------------------------------

# 18. Domain Freeze Deliverables

The sprint is complete when these exist:

1.  **Supported Asset & Tax Guidance Matrix**
2.  **Holding-Period Specification**
3.  **Durable Realized Event Contract**
4.  **Loss Set-Off Calculation**
5.  **Indicative Carry-Forward State**
6.  **Estimated Portfolio Tax Exposure Reconciliation**
7.  **Nullable XIRR Semantics**
8.  **Reconciliation Evidence-Quality Model**
9.  **Corporate-Action Limitation Matrix**
10. **25-35 Golden Financial Scenarios**
11. **Financial Invariants**
12. **One FY Financial Reconciliation Report**

------------------------------------------------------------------------

# 19. Definition of Done

Financial correctness is frozen when:

-   supported assets are explicit,
-   unsupported assets/events do not receive invented treatment,
-   holding-period boundaries are deterministic,
-   unknown tax classification fails safely,
-   realized events survive liquidation,
-   loss set-off follows the intended STCL/LTCL relationships,
-   carry-forward guidance retains FY/type state,
-   taxable interest flows into estimated tax exposure,
-   mixed tax components cannot accidentally receive one generic rate,
-   undefined XIRR is not 0%,
-   reconciliation does not invent tax evidence,
-   prior realized history cannot be rewritten by current-state
    reconciliation,
-   oversells are explicit,
-   golden scenarios pass,
-   financial invariants pass,
-   and one reconciliation report can trace material guidance back to
    source evidence.

> **Target:** highly trustworthy personal financial guidance without
> pretending to replace tax-filing due diligence.
