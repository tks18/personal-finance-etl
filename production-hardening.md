# Personal Finance ETL v8.1.0 - Final Implementation Plan

**Baseline:** v8.0.0  |  **Status:** Implementation scope freeze

## Objective
Replace the tax-computation engine with a simple ledger + Quant FIFO tax-information pipeline. Keep the Wealth Engine investment forecast. Close remaining production correctness defects before documentation.

## Design rules
- Ledger income uses native UID; investment gains use Quant Realized_Event_ID.
- FinancialRules investment exclusions use income subcategory UIDs, not capital_gains_groups.
- TaxEvents are filing-preparation evidence, not statutory tax liability.
- Preserve existing canonical investment grain and atomic publication.
- Comprehensive QA and documentation come after this release.

## 1. FinancialRules simplification

### Remove capital_gains_groups
**Implementation:** Delete Pydantic models, validators, code-to-group mappings, group-name tax inference and consumers.
**Done when:** No capital_gains_groups references remain in active tax flow.

### Add investment ledger exclusions
**Implementation:** Add stcg_sub_cat_ids and ltcg_sub_cat_ids under taxconfig.investment_exclusions; validate UID existence, uniqueness and no overlap.
**Done when:** Matching ledger income is excluded, but remains in the household income fact.

### Keep necessary configuration
**Implementation:** Preserve Head to Tax Sub-Head ledger classification, non-taxable rules, tax credit IDs, and any macro/Quant/Wealth settings still consumed.
**Done when:** No unrelated feature loses its configuration.

## 2. Silver tax evidence pipeline

### Normalize ledger income
**Implementation:** Read silver.f_Income_Transactions, use UID as Source_ID, apply income classification, exclude configured investment STCG/LTCG and non-taxable streams.
**Done when:** Only eligible ledger evidence reaches TaxEvents.

### Normalize Quant realized events
**Implementation:** Read silver.f_Investment_Realized_Events with Realized_Event_ID as Source_ID; preserve signed INR gain/loss, classification, ISIN, Lot_ID, currency and CHECK_REQUIRED status.
**Done when:** Quant alone supplies investment capital gains and losses.

### Union canonical TaxEvents
**Implementation:** Produce silver.f_Tax_Events with Tax_Event_ID, FY, Event_Date, Source_Type, Source_ID, Income_Head, Tax_Sub_Head, Amount_INR, CURRENCY_ID, Tax_Status, Tax_Status_Reason, nullable ISIN and Lot_ID. Use deterministic (Source_Type, Source_ID, Tax_Sub_Head) identity.
**Done when:** One source event appears once and the rebuilt table is deterministic.

### Keep tax credits separate
**Implementation:** Normalize observed TDS/credit and reversals as a distinct event type or amount measure. Never sum tax credits into income.
**Done when:** FY income and credit totals can be independently reconciled.

### Remove computation state
**Implementation:** Remove Tax Engine set-off, carry-forward, liability, exemption and forecast calculations. Drop f_Tax_FY_State if no remaining consumer requires it. Preserve Wealth Engine investment forecast.
**Done when:** No obsolete computation pipeline or dangling imports remain.

## 3. Gold presentation builders

### Tax_Year_Summary
**Implementation:** One row per FY: ledger income, signed investment gains/losses, observed credits, READY/CHECK_REQUIRED counts; no estimated tax.
**Done when:** Annual measures reconcile to TaxEvents.

### Tax_Income_Breakdown
**Implementation:** FY x Income_Head x Tax_Sub_Head x Source_Type: signed amounts and event counts.
**Done when:** Detailed totals reconcile to FY totals.

### Tax_Reconciliation
**Implementation:** Show excluded investment ledger totals, authoritative FIFO realized totals, source counts and informational differences; do not repeat FY measures across detailed rows.
**Done when:** No duplicated totals or statutory set-off claims.

### Register and publish
**Implementation:** Use existing presentation-builder pattern; update DAG, SQL schemas, Data Contract Registry and atomic Silver/Gold publication.
**Done when:** All registered outputs have producers and no dead contracts remain.

## 4. Remaining production correctness

### US historical prices
**Implementation:** Remove future-looking backward fill and missing-price zero fallback. Use same/prior observed price or unavailable state.
**Done when:** No fabricated historical price.

### US FX and benchmarks
**Implementation:** Remove future-looking FX and benchmark fills. Foreign FX=1 only for true identity pairs.
**Done when:** No future observations or false identity FX in historical valuation.

### Household monetary parsing
**Implementation:** Do not turn malformed required amounts into zero via permissive cast plus fill_null(0).
**Done when:** Invalid monetary evidence is visible or rejected.

### Return status
**Implementation:** Preserve undefined XIRR and benchmark-return null/status through Gold; do not convert them to valid 0%.
**Done when:** Valid zero and undefined remain distinct.

### Deterministic identity
**Implementation:** Fix defining field order per namespace; ensure synthetic reconciliation Lot_ID is unique by distinct deterministic operation and stable through mutation.
**Done when:** No accidental re-identification.

### Snapshot consistency
**Implementation:** Verify coordinated SQLite/DuckDB writers or use consistent engine checkpoint/export; preserve restore rollback.
**Done when:** Snapshot has a defined consistency boundary.

## 5. Release closure

### Remove dead references
**Implementation:** Clean obsolete imports, schemas, registry entries and Tax Engine consumers, without deleting Wealth/Quant functionality.
**Done when:** No orphan tax contracts.

### Focused release verification
**Implementation:** Run existing ETL and inspect ledger+FIFO union, exclusion behavior, unique event keys, additive Gold totals and unaffected Wealth/Quant outputs. Full QA remains later.
**Done when:** v8.1.0 publishes expected outputs without breaking current functionality.

### Hard stop
**Implementation:** No new tax-law engine, asset class, UI or opportunistic refactor.
**Done when:** v8.1.0 closes the bounded scope.

## Implementation order
FinancialRules -> TaxEvents -> Gold builders -> registry/DAG cleanup -> production correctness -> focused release verification.

## Out of scope
Set-off, carry-forward, estimated liability, tax-rate inference, new asset classes, new UI, full QA sprint and documentation rewriting.
