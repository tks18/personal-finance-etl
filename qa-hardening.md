# Final QA & Regression Freeze

## Goal

Turn the finalized Architecture and Financial Domain behavior into repeatable automated protection.

Build this sprint after the Architecture and Financial Domain freezes are implemented so tests freeze the final behavior rather than a moving design.

---

## 1. Replace stale test fixtures

### Change

Replace legacy fixtures with final:

```text
Settings
FinancialRules / TaxConfig
Macro Parameters
contract registries
investment canonical facts
```

### Implementation

Include fixtures for:

```text
ordinary taxable income
non-taxable income
tax-credit subcategory
investment-category mapping
non-investment ST/LT capital gains
FY macro row
same-day different-price purchases
reconciliation-created lot
basis-adjusted lot
```

### Done when

All tests represent final production contracts.

---

## 2. Organize tests by failure scope

Use a simple structure such as:

```text
unit/
component/
integration/
golden/
recovery/
reproducibility/
packaging/
```

Do not start with one giant E2E test.

---

## 3. Test deterministic ID generation

### Cover

```text
Purchase_ID
Sale_ID
Lot_ID
Realized_Event_ID
Reconciliation_Group_ID
Reconciliation_Event_ID
Tax_Event_ID
```

### Verify

Same canonical inputs produce the same ID across runs.

Changed defining attributes change the ID.

Changed derived fields do not change Purchase_ID/Sale_ID.

Volatile provenance does not affect IDs:

```text
run_id
timestamp
path
hostname
```

Numeric canonicalization must prevent float-formatting differences from changing IDs.

---

## 4. Test canonical Purchase/Sale grain

### Cover

Existing aggregation behavior:

```text
same ISIN + date + price
→ quantity aggregation

different price
→ separate canonical row

different date
→ separate canonical row
```

### Verify

Adding IDs does not change the current financial grain.

Source broker rows are not accidentally exposed as new Silver transaction facts.

---

## 5. Golden FIFO / realized-event scenarios

Cover:

```text
single buy
multiple buys
multiple FIFO lots
partial sell
full sell
multiple partial sells
one sale consuming multiple lots
remaining inventory
full liquidation
```

Verify:

```text
Lot_ID
Purchase_ID
Sale_ID
Realized_Event_ID
disposed quantity
disposed basis
sale proceeds allocation
realized gain/loss
holding classification
```

Invariant:

```text
sum(lot-level realized P&L for sale)
=
sale-level FIFO realized P&L
```

Full liquidation must not remove realized history.

---

## 6. Test Lot identity persistence

### Cover

```text
partial sale
quantity reduction reconciliation
cost-basis adjustment
```

### Verify

The surviving economic lot retains the same:

```text
Lot_ID
Purchase_ID
Lot_Source_Type
```

A new Lot_ID is created only for a genuinely new reconciliation-created lot.

---

## 7. Test deterministic same-day FIFO ordering

### Cover

Multiple purchases on the same date with different prices.

Multiple sales on the same date with different prices.

### Verify

Purchase order:

```text
Date ASC
Price ASC
Purchase_ID ASC
```

Sale order:

```text
Date ASC
Sell_Price ASC
Sale_ID ASC
```

Run the same input repeatedly and assert identical lot consumption and realized events.

Also verify different-price purchases are not collapsed into a weighted-average lot.

---

## 8. Test calendar-month holding boundaries

For every supported threshold test:

```text
one day before boundary
exact boundary
one day after boundary
```

Include:

```text
31 January
28/29 February
31 March
leap year
```

Verify the same holding utility is used for realized and unrealized classification.

---

## 9. Test realized-event uniqueness

### Verify

Business uniqueness:

```text
Sale_ID + Lot_ID
```

and deterministic:

```text
Realized_Event_ID
```

A sale consuming three lots must produce exactly three realized rows.

A partial sale followed by a later sale from the same lot must create different realized IDs because Sale_ID differs.

---

## 10. Test reconciliation groups and events

### Cover

```text
QUANTITY_ADD
QUANTITY_REMOVE
COST_BASIS_ADJUSTMENT
```

### Verify

One reconciliation operation has one:

```text
Reconciliation_Group_ID
```

Each affected lot mutation has one:

```text
Reconciliation_Event_ID
```

Cost-basis scaling across three lots must produce three event rows tied to one group.

---

## 11. Test synthetic reconciliation lots

### Quantity add

Verify:

```text
Purchase_ID = NULL
Lot_Source_Type = RECONCILIATION
deterministic Lot_ID
```

The lot participates in portfolio/wealth/FIRE analytics.

If later sold:

```text
Realized Event exists
TaxEvent exists
Tax_Status = CHECK_REQUIRED
Taxable_Amount = NULL
Applied_Rate = NULL
Estimated_Tax = NULL
```

### Quantity remove

Verify surviving normal purchase lots retain identity and do not automatically become check-required if basis/acquisition evidence remains unchanged.

### Cost-basis adjustment

Verify active basis changes and future FIFO uses adjusted basis.

Historical realized events must remain byte-for-byte/materially unchanged.

Future realization from a materially basis-adjusted lot must be `CHECK_REQUIRED`.

---

## 12. Test TaxConfig resolution

Cover:

```text
category-level match
subcategory-level match
tax-credit subcategory
non-taxable sub-head
unmapped income
overlapping configuration
```

Verify:

```text
cat_id claims complete category
sub_cat_id claims exact subcategory
overlap raises configuration error
tax-credit IDs do not behave as income
```

---

## 13. Test tax-credit sign convention

Source examples:

```text
TDS = -20,000
TDS = -5,000
```

Verify canonical:

```text
Observed_Tax_Credits = 25,000
Observed_Tax_Credits >= 0
```

Verify:

```text
Estimated_Net_Tax_Position
=
Estimated_Gross_Tax
-
Observed_Tax_Credits
```

and allow negative tax position without clamping.

---

## 14. Test tax-event ownership

Invariant:

```text
Every canonical TaxEvent
→ exactly one producer
```

Cover:

```text
ordinary ledger income
investment capital gain
non-investment capital gain
```

Investment-related ledger activity must not duplicate FIFO realized gains.

---

## 15. Test TaxEvent identity and uniqueness

Verify:

```text
UNIQUE(Source_Type, Source_ID, Tax_Sub_Head)
```

and deterministic Tax_Event_ID.

Investment case:

```text
Source_Type = INVESTMENT_REALIZED
Source_ID = Realized_Event_ID
```

Ledger case uses stable ledger transaction identity.

If one source legitimately maps to multiple Tax Sub-Heads, each must receive a distinct TaxEvent.

---

## 16. Test non-investment capital gains

Cover:

```text
positive ST → STCG
negative ST → STCL
positive LT → LTCG
negative LT → LTCL
```

Verify default ST/LT rate resolution and:

```text
CHECK_REQUIRED
```

for insufficient classification.

---

## 17. Test non-taxable income exclusion

Create:

```text
taxable salary/interest/dividend
non-taxable cashback/wallet income
```

Verify non-taxable rows:

```text
remain in normal income facts
do not enter f_Tax_Events
```

and:

```text
Gross Income
- Excluded Non-Taxable Income
= Tax Model Income Universe
```

---

## 18. Test TaxEvent contract

Verify:

```text
Source_Type
Source_ID
Income_Head
Tax_Sub_Head
Tax_Method
Gross_Amount
Taxable_Amount
Applied_Rate
Estimated_Tax
Tax_Status
Tax_Status_Reason
```

Cover:

```text
LEDGER
INVESTMENT_REALIZED
READY
CHECK_REQUIRED
```

No test depends on a manual Reviewed workflow.

---

## 19. Test capital-loss set-off priority

Cover exact ordered behavior:

```text
1. STCL → STCG
2. remaining STCL → LTCG
3. LTCL → remaining LTCG
4. LTCL never → STCG
```

Test:

```text
full utilization
partial utilization
no utilization
mixed STCL + LTCL + STCG + LTCG
```

Assert:

```text
stcl_used_against_stcg
stcl_used_against_ltcg
ltcl_used_against_ltcg
net_stcg
net_ltcg
closing_stcl
closing_ltcl
```

---

## 20. Test carry-forward across FYs

Cover:

```text
no opening loss
opening STCL
opening LTCL
full utilization
partial utilization
multiple FYs
```

Invariant:

```text
Opening Loss
+ Current Loss
- Utilized
=
Closing Loss
```

separately for STCL/LTCL.

---

## 21. Test FY Tax State

Verify:

```text
Gross Income
- Excluded Non-Taxable Income
= Tax-Relevant Income
```

```text
Estimated Ordinary Tax
+ Estimated Capital-Gains Tax
= Estimated Gross Tax
```

```text
Estimated Gross Tax
- Observed Tax Credits
= Estimated Net Tax Position
```

Also reconcile every capital-loss movement.

---

## 22. Test all three Gold tax marts

### `gold.Tax_Year_Summary`

Verify one row per FY and exact reconciliation to FY Tax State.

### `gold.Tax_Income_Breakdown`

Verify grain:

```text
FY × Income Head × Tax Sub-Head × Source Type
```

Investment/non-investment capital gains remain distinguishable.

### `gold.Tax_Reconciliation`

Verify source amounts, excluded income, TaxEvents, set-off, net taxable amounts, tax, credits, and net position reconcile through the complete chain.

---

## 23. Test Investment Tax Liability Forecast semantics

### Scenario definition

Start with:

```text
current FY realized gains/losses
+ brought-forward losses
```

then add hypothetical liquidation gains/losses from current open lots.

Run the same set-off engine.

### Verify

Hypothetical events do not write into actual:

```text
f_Investment_Realized_Events
f_Tax_Events
f_Tax_FY_State
```

Check-required reconciliation lots do not generate falsely precise forecast tax.

---

## 24. Test investment invariants

### Quantity

```text
Opening Quantity
+ Buys
- Sells
± Reconciliation Adjustments
=
Closing Quantity
```

### Cost basis

```text
Opening Basis
+ Purchases
± Basis Adjustments
- Disposed FIFO Basis
=
Closing Basis
```

### Realized P&L

```text
Sale Proceeds
- Disposed FIFO Basis
=
Realized P&L
```

### Lot grain

```text
UNIQUE(Lot_ID, Closing_Date)
```

Every FIFO disposal produces the expected realized-event rows.

---

## 25. Test XIRR status propagation

Cover:

```text
normal XIRR
multiple cash flows
valid 0% return
undefined cash-flow pattern
non-convergence
invalid input
```

Verify non-valid states remain distinguishable through:

```text
math result
→ Quant Engine
→ lot/instrument analytics
→ Gold consumers
```

No layer may silently convert failure to meaningful `0%`.

---

## 26. Test artifact lifecycle provenance

Cover:

```text
first discovery
unchanged rediscovery
content change
rename
PENDING_BRONZE replay
self-heal
successful sync
removal
```

Verify lifecycle pointers, run IDs, historical events, event IDs, and event reasons.

---

## 27. Test Bronze synchronization

Cover:

```text
full replacement
file-owned historical replacement
changed source becomes empty
missing Bronze table
missing artifact partition
orphan cleanup
PENDING_BRONZE replay
```

The empty-source case must remove stale owned rows.

---

## 28. Test contract registry

Validate:

```text
unique contract IDs
unique physical tables
valid layers
non-empty grain
non-empty producer
valid publication order
```

After implementation, derive exact Bronze/Silver/Gold counts from the registry.

Do not maintain approximate counts as release truth.

Verify the old Tax Liability Forecast name is not accidentally retained after rename.

---

## 29. Test Control Plane behavior

Cover:

```text
run lifecycle
stale-run recovery
Settings snapshots
FinancialRules snapshots
structured failures
compressed execution logs
artifact-run lineage
simulation-run provenance
```

Failed runs must never become successful history.

---

## 30. Test worker failure propagation

Force one deterministic ISIN worker failure.

Assert:

```text
one worker fails
→ investment stage fails
→ run fails
→ partial portfolio is not published
```

Verify run/stage/ISIN context remains available.

---

## 31. Test Snapshot / Restore

Cover:

```text
successful snapshot
missing SQLite
missing DuckDB
unexpected archive member
nested/path-traversal member
successful restore
failed installation
rollback
sidecar preservation
production lock
```

Invariant:

```text
complete new pair
OR
complete old pair

never mixed generations
```

---

## 32. Test Monte Carlo replay and fingerprint scope

Given:

```text
same canonical inputs
same model fingerprint
same implementation version
same Settings/FinancialRules
same macro/reference state
same root seed
```

assert the same material simulation output.

Verify:

```text
changed financial input
→ input_fingerprint changes

changed assumption/config
→ model_fingerprint changes

changed implementation version
→ model_implementation_version changes

different seed
→ stochastic result may differ
```

Verify volatile metadata does not affect fingerprints.

---

## 33. Test the complete Reproducibility Envelope

### Deterministic finance/tax

Given:

```text
same source evidence
same Settings
same FinancialRules/TaxConfig
same Macro Parameters
same implementation
```

verify the same:

```text
Purchase_ID / Sale_ID
Lot_ID
Realized Events
Reconciliation Groups/Events
TaxEvents
FY Tax State
Gold tax marts
```

### Stochastic FIRE

Add the same root seed and verify the same material FIRE output.

Ignore operational run IDs/timestamps that are expected to change.

---

## 34. Test pipeline idempotency

Run identical synthetic evidence twice.

Verify:

```text
no duplicate artifact state
no duplicate Bronze history
same deterministic IDs
no duplicate realized events
no duplicate reconciliation events
no duplicate TaxEvents
same material Silver outputs
same material Gold outputs
```

---

## 35. Test CLI behavior

Cover:

```text
cli
tkinter
--config
--rules
--auto
--cron
--snapshot
--restore
--docs
```

Test behavior/error paths, not terminal pixels.

---

## 36. Test documentation runtime

Protect:

```text
manifest coverage
path resolution
internal navigation
TOC generation
bundled Mermaid resource
package-resource loading
README/docs availability
```

---

## 37. Add packaging smoke tests

Verify:

```text
wheel builds
sdist builds
package installs
CLI entry point starts
Desktop entry point imports
docs are packaged
Mermaid asset is packaged
configuration models import
```

---

## 38. Add a generous performance regression guard

Do not assert an exact runtime.

Only fail on a material slowdown large enough to indicate a real regression.

Never trade financial correctness for benchmark speed.

---

## 39. Build one full synthetic E2E test

Final system scenario:

```text
Synthetic Source Evidence
→ Discovery
→ Control Plane
→ Bronze
→ Canonical Purchase/Sale IDs
→ FIFO / Lot IDs
→ Realized Events
→ Broker Reconciliation
→ TaxEvents
→ Capital-Loss Set-Off
→ FY Tax State
→ Silver / Gold
→ FIRE
→ Snapshot
→ Restore
→ Rebuild
```

Verify:

```text
financial outputs
tax outputs
deterministic identities
lineage
reproducibility
recovery
```

---

## Suggested implementation order

```text
1. Replace fixtures
2. Deterministic ID utility/tests
3. Canonical Purchase/Sale ID tests
4. FIFO + Lot identity tests
5. Same-day ordering
6. Holding boundaries
7. Realized-event golden scenarios
8. Reconciliation groups/events
9. TaxConfig + TaxEvents
10. Loss set-off / carry-forward
11. FY Tax State + Gold
12. Investment tax forecast
13. XIRR propagation
14. Artifact / Control Plane
15. Bronze / recovery
16. Monte Carlo replay
17. Integration / reproducibility
18. CLI / docs / package
19. Full synthetic E2E
```

---

## Final QA Freeze completion

The QA freeze is complete when:

1. Final fixtures match production contracts.
2. Every deterministic financial ID is tested.
3. Canonical Purchase/Sale grain remains unchanged.
4. Lot identity survives all FIFO/reconciliation mutations.
5. Same-day FIFO ordering is deterministic.
6. Calendar-month holding boundaries are tested.
7. Lot-level realized events are golden-tested.
8. Reconciliation groups/events are tested at lot-mutation grain.
9. Synthetic reconciliation lots have safe tax behavior.
10. TaxConfig ownership and non-taxable exclusions are tested.
11. Tax credits are non-negative by contract.
12. TaxEvent identity/uniqueness is enforced.
13. Capital gains cannot double count across producers.
14. Loss set-off priority and carry-forward reconcile.
15. FY Tax State and all three Gold tax marts reconcile.
16. Investment forecast uses actual FY state plus hypothetical liquidation without mutation.
17. XIRR status propagates correctly.
18. Artifact lifecycle and self-healing are protected.
19. Snapshot/Restore rollback is protected.
20. Monte Carlo fingerprint/replay semantics are protected.
21. The complete Reproducibility Envelope is executable.
22. Pipeline idempotency is protected.
23. Contract counts come from the registry.
24. CLI/docs/package surfaces have smoke coverage.
25. One complete synthetic E2E scenario passes.
