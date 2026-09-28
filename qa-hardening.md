# Final QA & Regression Sprint

## Goal

Turn the behavior finalized by the Architecture and Financial Domain sprints into repeatable automated protection.

Build this sprint **after the first two are implemented**, so tests freeze the final intended behavior rather than semantics that are about to change.

## 1. Replace stale test fixtures

### Problem

Current test configuration predates parts of the v6.5.x model.

### Impact

Tests can accidentally validate behavior production no longer uses.

### Implementation

Replace legacy fixtures with small canonical fixtures built from the final:

```text
Settings
FinancialRules
Macro Parameters
taxconfig
```

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

Keep small logic failures easy to diagnose.

## 3. Golden investment scenarios

Cover:

```text
single buy
multiple buys
multiple FIFO lots
partial sell
full sell
multiple partial sells
sale across multiple lots
remaining inventory
full liquidation
```

Verify quantity, basis, realized P&L, and remaining lot state.

## 4. Holding/tax boundary scenarios

For every supported treatment test:

```text
one day before threshold
exact threshold
one day after threshold
```

Also cover gain, loss, zero gain, missing basis, reconciliation-affected basis, and review-required classification.

## 5. Golden tax-event scenarios

Cover:

```text
salary/ordinary income
interest
dividend
investment STCG
investment LTCG
STCL
LTCL
non-investment capital gain
exempt/review event
TDS / tax credit
mixed income
```

Verify tax head, producer, taxable amount, rate path, and review state.

## 6. Test event ownership and double-count prevention

### Invariant

```text
Every canonical TaxEvent
→ exactly one producer
```

For investment activity:

```text
Realized Investment Event
→ owns capital gain

generic ledger mapping
→ must not duplicate it
```

Create a scenario containing both investment ledger activity and realized investment state and prove the gain is counted once.

## 7. Test capital-loss set-off

Cover:

```text
STCL against STCG
STCL against LTCG
LTCL against LTCG
prohibited LTCL against STCG
full utilization
partial utilization
no utilization
```

Assert remaining STCL/LTCL explicitly.

## 8. Test carry-forward across FYs

Cover:

```text
no opening loss
opening STCL
opening LTCL
full utilization
partial utilization
multiple FYs
```

If the final model represents expiry, test that boundary too.

## 9. Test FY Tax State and Gold reconciliation

Assert:

```text
Tax Events
→ FY Tax State
→ Tax Income Breakdown
→ Tax Year Summary
```

reconciles exactly.

Also verify:

```text
Estimated Gross Tax
-
Observed Tax Credits
=
Estimated Net Tax Payable
```

and that review items surface correctly.

## 10. Add core financial invariants

### Quantity

```text
Opening Quantity
+ Buys
- Sells
± Supported Adjustments
=
Closing Quantity
```

### Cost basis

```text
Opening Basis
+ Purchases
± Basis Adjustments
- Disposed Basis
=
Closing Basis
```

### Realized P&L

```text
Sale Proceeds
-
Disposed Cost Basis
=
Realized P&L
```

### Tax event

```text
Every supported tax-relevant financial event
→ exactly one canonical TaxEvent
```

### FY

```text
Every TaxEvent
→ exactly one FY
```

## 11. Test artifact lifecycle provenance

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

Verify:

```text
first_seen
last_seen
last_changed
last_synced
corresponding run IDs
historical artifact-run events
```

## 12. Test Bronze synchronization

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

The empty-source test must prove stale owned rows are removed.

## 13. Test contract registries

Validate:

```text
unique contract IDs
unique physical tables
valid layers
non-empty grain
non-empty producer
valid publication order
```

Freeze the **final** Bronze/Silver/Gold counts after the first two sprints. Do not assume today's counts remain unchanged.

## 14. Test Control Plane behavior

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

## 15. Test worker failure propagation

Force one deterministic ISIN worker failure.

Assert:

```text
one worker fails
→ investment stage fails
→ run fails
→ partial portfolio is not published
```

Verify run/stage/ISIN context remains available.

## 16. Test Snapshot / Restore

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

Main invariant:

```text
complete new pair
OR
complete old pair

never mixed generations
```

## 17. Test Monte Carlo replay

Given:

```text
same canonical inputs
same model fingerprint
same Settings/FinancialRules
same macro/reference state
same root seed
```

assert the same material simulation output.

Also verify:

```text
different seed
→ result can differ

same seed + changed input
→ input fingerprint changes

same input + changed model
→ model fingerprint changes
```

## 18. Test the Reproducibility Envelope

For deterministic analytics:

```text
same evidence
+ same Settings
+ same FinancialRules
+ same macro/reference state
+ same implementation
→ same material output
```

For stochastic analytics:

```text
same envelope
+ same seed
→ same material output
```

Ignore operational timestamps that are expected to change.

## 19. Test pipeline idempotency

Run the same synthetic evidence twice.

Verify:

```text
no duplicate artifact state
no duplicate Bronze history
same canonical financial state
same material Silver output
same material Gold output
```

Run IDs/timestamps may differ.

## 20. Test XIRR edge states

Cover:

```text
normal XIRR
multiple cash flows
valid 0% return
undefined cash-flow pattern
non-convergence
invalid input
```

An invalid/undefined result must not silently become a meaningful 0%.

## 21. Test reconciliation provenance

Create cases where broker reconciliation:

```text
adds quantity
removes quantity
adjusts basis
```

Verify current state reconciles, the adjustment is explainable, evidence quality changes appropriately, and review flags appear where required.

## 22. Test CLI behavior

Cover routing for:

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

Test behavior and error paths, not terminal pixels.

## 23. Test the documentation runtime

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

## 24. Add packaging smoke tests

Build the real distribution and verify:

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

## 25. Add a generous performance regression guard

Do not assert an exact runtime.

Only fail on a material slowdown large enough to indicate a real regression.

Never trade financial correctness for benchmark speed.

## 26. Build one full synthetic E2E test

Final system test:

```text
Synthetic Source Evidence
→ Discovery
→ Control Plane
→ Bronze
→ Canonical Finance
→ Investment / Wealth
→ Realized Events
→ Tax Events
→ FY Tax State
→ Silver / Gold
→ FIRE
→ Snapshot
→ Restore
→ Rebuild
```

Verify both:

```text
financial outputs
+
provenance/reproducibility
```

## Suggested implementation order

```text
1. Replace fixtures
2. Unit/component tests
3. Financial golden scenarios
4. Tax golden scenarios
5. Invariants
6. Artifact/Control Plane tests
7. Bronze/recovery tests
8. Simulation replay
9. Integration tests
10. CLI/docs/package smoke tests
11. Full synthetic E2E
```

Do not start with the giant E2E test.

## Sprint completion

The final QA sprint is complete when:

1. Final configuration contracts have current fixtures.
2. Core finance has deterministic golden scenarios.
3. Tax events/set-off/carry-forward reconcile.
4. Financial invariants are automated.
5. Artifact lifecycle and self-healing are protected.
6. Snapshot/Restore rollback is protected.
7. Monte Carlo is replay-tested.
8. The Reproducibility Envelope is executable.
9. Pipeline idempotency is protected.
10. CLI/docs/package surfaces have smoke coverage.
11. One complete synthetic E2E scenario passes.
12. A failing test clearly points toward the broken subsystem.
