# Final QA & Regression Implementation Freeze

> **Status: FROZEN FOR IMPLEMENTATION AFTER ARCHITECTURE + DOMAIN SPRINTS**
>
> Tests freeze the implemented contracts. They do not introduce new behavior.

## Goal

Protect:

```text
financial correctness
deterministic identity
tax semantics
lineage
recovery
reproducibility
idempotency
CLI/docs/package surfaces
full-system behavior
```

---

## 1. Final fixtures

Use final Settings, FinancialRules/TaxConfig, Macro Parameters, Contract Registry, ledger UID, and canonical investment facts.

Include:

```text
taxable ordinary income
non-taxable cashback/wallet income
tax credit
non-investment ST/LT gain/loss
same-day different-price purchases
multi-lot sale
synthetic reconciliation lot
basis-adjusted lot
FY macro/loss state
```

---

## 2. Test structure

```text
unit/
component/
integration/
golden/
recovery/
reproducibility/
packaging/
```

---

## 3. Canonical ID Serialization v1

Test:

```text
UTF-8
Unicode NFC
outer-whitespace normalization
null representation
date/datetime format
booleans
numeric normalization
negative zero
field order
namespace
hash stability
```

Assert:

```text
10 = 10.0 = 10.00
-0 = -0.0 = 0.00 = 0
```

Identity-version/hash changes must be explicit.

---

## 4. Identity precedence

Verify native identity:

```text
ISIN
ledger UID
```

and generated identity only where needed:

```text
Purchase_ID
Sale_ID
Lot_ID
Realized_Event_ID
Reconciliation_Group_ID
Reconciliation_Event_ID
Tax_Event_ID
```

---

## 5. Purchase_ID / Sale_ID

Same defining inputs → same ID.

Changing:

```text
ISIN
Date
Price/Sell_Price
Quantity
Currency
```

→ changed ID.

Changing derived values or volatile provenance → unchanged ID.

Explicitly test quantity correction → new canonical ID.

---

## 6. Canonical investment grain

Verify current aggregation remains:

```text
same ISIN + date + price → aggregated quantity
different price → separate event
different date → separate event
```

IDs must not expose source broker rows as new Silver facts.

---

## 7. FIFO golden scenarios

Cover:

```text
single buy
multiple buys
multiple lots
partial sell
full sell
multiple partial sells
sale across multiple lots
remaining inventory
full liquidation
```

Verify IDs, quantities, basis, proceeds, realized P&L, and holding type.

Invariant:

```text
sum(lot realized P&L for Sale_ID)
=
sale FIFO realized P&L
```

---

## 8. Lot identity persistence

Partial sale, quantity reduction, and basis adjustment preserve Lot_ID/Purchase_ID/source type for surviving economic lots.

Only synthetic reconciliation quantity creates a new Lot_ID.

---

## 9. Same-day FIFO ordering

Assert:

```text
Purchase: Date → Price → Purchase_ID
Sale: Date → Sell_Price → Sale_ID
```

Repeated rebuilds must consume identical lots in identical order.

Different-price same-day purchases remain separate.

---

## 10. Holding boundaries

Test one day before / exact / one day after for every supported threshold.

Include month-end, February, leap-year cases.

Assert:

```text
date > boundary → LT
date <= boundary → ST
```

Realized and unrealized paths must share the same utility.

---

## 11. Realized events

Assert:

```text
UNIQUE(Sale_ID, Lot_ID)
```

Multi-lot sale → one event per consumed lot.

Same evidence rebuild → same IDs/material attributes.

Later active-lot reconciliation must not rewrite earlier realized events.

---

## 12. Reconciliation identity

Same canonical reconciliation → same Group/Event IDs.

Run_ID must not affect IDs.

One group affecting multiple lots → one group, multiple event rows.

Where repeated same-lot mutation is impossible, assert:

```text
UNIQUE(Group_ID, Lot_ID, Adjustment_Type)
```

---

## 13. Reconciliation Run_ID

Rebuild identical evidence in another run:

```text
same financial reconciliation IDs
new producing Run_ID
```

Silver remains the current projection; historical run observations remain in Control Plane.

---

## 14. Synthetic reconciliation lots

QUANTITY_ADD:

```text
Purchase_ID NULL
Lot_Source_Type RECONCILIATION
deterministic Lot_ID
```

If sold:

```text
Realized Event exists
TaxEvent CHECK_REQUIRED
Taxable_Amount NULL
Applied_Rate NULL
Estimated_Tax NULL
```

QUANTITY_REMOVE preserves surviving lot identity.

COST_BASIS_ADJUSTMENT changes future basis, preserves earlier realized events, and makes future affected realization CHECK_REQUIRED.

---

## 15. Ledger UID

Assert relevant income UID is non-null and unique.

Tax source:

```text
Source_Type = LEDGER
Source_ID = UID
```

Changing amount while preserving UID keeps Source_ID and same Tax_Event_ID for the same Tax Sub-Head while recalculating amounts.

---

## 16. TaxConfig

Test category match, exact subcategory match, tax credit, non-taxable stream, unmapped stream, and overlap error.

---

## 17. Tax-credit sign

Negative source TDS normalizes to positive credits.

Invariant:

```text
Observed_Tax_Credits >= 0
```

Net tax position may be negative.

---

## 18. TaxEvent ownership

Every Source_Type has one producer.

Assert:

```text
Source_Type + Source_ID + Tax_Sub_Head
→ emitted at most once
```

Investment ledger activity must not duplicate FIFO realized gains.

---

## 19. TaxEvent identity

Assert deterministic:

```text
Tax_Event_ID(Source_Type, Source_ID, Tax_Sub_Head)
```

and unique natural key.

Cover LEDGER/UID and INVESTMENT_REALIZED/Realized_Event_ID.

---

## 20. Non-investment capital gains

Test:

```text
+ST → STCG
-ST → STCL
+LT → LTCG
-LT → LTCL
```

Test default rate resolution and CHECK_REQUIRED when classification is insufficient.

---

## 21. Non-taxable exclusion

Non-taxable income remains in normal income facts and does not enter TaxEvents.

Reconcile:

```text
Gross Income - Excluded = Tax Model Income Universe
```

---

## 22. TaxEvent status/contract

Validate all canonical fields and READY/CHECK_REQUIRED behavior.

No manual Reviewed workflow.

---

## 23. Loss set-off priority

Exact order:

```text
STCL → STCG
remaining STCL → LTCG
LTCL → remaining LTCG
LTCL never → STCG
```

Cover full/partial/no utilization and mixed gain/loss states.

---

## 24. Carry-forward

Cover opening STCL/LTCL, full/partial utilization, and multiple FYs.

Invariant:

```text
Opening + Current Loss - Utilized = Closing
```

---

## 25. FY Tax State

Reconcile:

```text
Gross - Excluded = Tax-Relevant Income
Ordinary Tax + Capital-Gains Tax = Gross Tax
Gross Tax - Credits = Net Tax Position
```

Reconcile all loss movements.

---

## 26. Gold tax marts

Test:

```text
Tax_Year_Summary
Tax_Income_Breakdown
Tax_Reconciliation
```

against their declared grains and FY Tax State.

---

## 27. Investment Tax Liability Forecast

Start from actual FY realized/loss state + brought-forward losses.

Add hypothetical liquidation only for tax-ready lots.

Use shared set-off engine.

Never mutate actual realized events, TaxEvents, or FY state.

CHECK_REQUIRED lots are excluded from precise tax and separately summarized.

---

## 28. Investment invariants

```text
Opening Qty + Buys - Sells ± Reconciliation = Closing Qty

Opening Basis + Purchases ± Basis Adjustments - Disposed Basis = Closing Basis

Sale Proceeds - Disposed Basis = Realized P&L

UNIQUE(Lot_ID, Closing_Date)
```

---

## 29. XIRR propagation

Test valid, valid 0%, undefined, non-convergent, invalid.

Non-valid value remains NULL through math → Quant → Silver → Gold.

---

## 30. Artifact lifecycle

Test discovery, unchanged, changed, rename, pending replay, heal, sync, removal.

Validate pointers, run IDs, event IDs/reasons.

---

## 31. Bronze synchronization

Test full replace, file-owned replace, source becomes empty, missing table/partition, orphan cleanup, pending replay.

---

## 32. Contract Registry fingerprint

Validate registry integrity and deterministic fingerprint.

Same registry → same fingerprint.

Material contract change → changed fingerprint.

Exact layer counts derive from registry.

---

## 33. Control Plane

Test run lifecycle, stale recovery, config/rules snapshots, failures, compressed logs, artifact-run lineage, simulation provenance, registry fingerprint linkage.

---

## 34. Worker failure propagation

Forced ISIN worker failure must fail stage/run and prevent partial publication while preserving failure context.

---

## 35. Snapshot / Restore

Test success, missing DBs, unsafe archive members, failed installation, rollback, sidecars, production lock.

Invariant:

```text
complete new pair OR complete old pair
never mixed generations
```

---

## 36. Monte Carlo replay

Given same:

```text
inputs
model fingerprint
implementation version
settings/rules
macro/reference state
registry fingerprint
root seed
```

compare:

```text
discrete → exact
floating scalar → centralized abs/rel tolerance
floating arrays → element-wise centralized abs/rel tolerance
```

Test fingerprint changes for input/model/implementation changes.

---

## 37. Reproducibility Envelope

Same deterministic envelope must reproduce:

```text
Purchase_ID / Sale_ID
Lot_ID
Realized Events
Reconciliation Groups/Events
TaxEvents
FY Tax State
Gold tax marts
```

FIRE additionally uses the same seed/tolerance contract.

---

## 38. Pipeline idempotency

Run identical evidence twice.

Assert no duplicate state/events and identical deterministic IDs/material Silver/Gold outputs.

Operational run IDs/timestamps may differ.

---

## 39. CLI

Test behavior/error paths for:

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

---

## 40. Docs runtime

Test manifest, path resolution, navigation, TOC, bundled Mermaid, package resources, README/docs availability.

---

## 41. Packaging smoke

Verify wheel/sdist, install, CLI, Desktop import, docs/Mermaid packaging, config imports.

---

## 42. Performance guard

Use a generous material-regression threshold, not exact runtime.

Never trade financial correctness for benchmark speed.

---

## 43. Full synthetic E2E

```text
Synthetic Evidence
→ Discovery
→ Control Plane
→ Bronze
→ Purchase/Sale IDs
→ FIFO/Lot IDs
→ Realized Events
→ Reconciliation
→ TaxEvents
→ Loss Set-Off
→ FY Tax State
→ Silver/Gold
→ FIRE
→ Snapshot
→ Restore
→ Rebuild
```

Verify financial/tax outputs, deterministic identities, lineage, registry identity, reproducibility, and recovery.

---

## Suggested order

```text
1 Fixtures
2 Canonical serialization + ID utility
3 Purchase/Sale identity
4 FIFO/Lot identity
5 Same-day ordering
6 Holding boundaries
7 Realized events
8 Reconciliation
9 Ledger UID + TaxConfig + TaxEvents
10 Loss set-off/carry-forward
11 FY Tax State + Gold
12 Investment forecast
13 XIRR
14 Artifact/Control Plane
15 Registry fingerprint
16 Bronze/recovery
17 Monte Carlo replay
18 Integration/reproducibility
19 CLI/docs/package
20 Full E2E
```

---

## Final QA Implementation Freeze checklist

1. Final fixtures.
2. Canonical serialization.
3. Identity precedence.
4. Purchase/Sale IDs.
5. Existing canonical grain preserved.
6. Lot identity persistence.
7. Same-day deterministic FIFO.
8. Strict calendar-month boundary.
9. Realized-event identity/immutability.
10. Reconciliation identity + Run_ID semantics.
11. Synthetic-lot safe tax behavior.
12. Ledger UID contract.
13. TaxConfig ownership.
14. Non-negative tax credits.
15. TaxEvent identity/uniqueness.
16. No capital-gain double counting.
17. Ordered loss set-off/carry-forward.
18. FY Tax State + three Gold marts.
19. Forecast precise-vs-CHECK_REQUIRED separation.
20. XIRR propagation.
21. Artifact/self-healing protection.
22. Registry fingerprint.
23. Snapshot/Restore.
24. Monte Carlo replay tolerance.
25. Complete Reproducibility Envelope.
26. Idempotency.
27. Registry-derived contract counts.
28. CLI/docs/package smoke.
29. Full synthetic E2E.
