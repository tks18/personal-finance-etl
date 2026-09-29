# Final QA & Regression Freeze

## Goal
Turn the finalized Architecture and Financial Domain behavior into repeatable automated protection.

Build this after the first two freezes are implemented.

## 1. Replace stale fixtures
Use final Settings, FinancialRules/TaxConfig, Macro Parameters, and registries. Include taxable ordinary income, non-taxable income, tax credits, investment mapping, non-investment ST/LT capital gains, and an FY macro row.

## 2. Organize by failure scope
```text
unit/
component/
integration/
golden/
recovery/
reproducibility/
packaging/
```

## 3. Golden FIFO / realized events
Cover single/multiple buys, partial/full sells, multi-lot sale, multiple partial sells, remaining inventory, full liquidation.

Verify lot-level row count, Lot_ID, disposed quantity/basis, allocated proceeds, realized P&L, holding classification.

Invariant:
```text
sum(lot-level realized P&L for sale)
=
sale-level FIFO realized P&L
```
Full liquidation must not remove realized history.

## 4. Calendar-month holding boundaries
Test one day before/exact/one day after for every supported threshold, including month-end, February, and leap-year cases.

## 5. TaxConfig resolution
Test category match, subcategory match, tax-credit subcategory, non-taxable sub-head, unmapped income, and overlapping config.

Verify whole-category semantics, exact-subcategory semantics, and overlap validation.

## 6. Tax-event ownership
Invariant:
```text
Every canonical TaxEvent → exactly one producer
```
Test ledger ordinary income, investment gains, and non-investment gains. Investment-related ledger activity must not duplicate FIFO realized gains.

## 7. Non-investment capital gains
Test:
```text
+ST → STCG
-ST → STCL
+LT → LTCG
-LT → LTCL
```
Verify default ST/LT rate resolution and `CHECK_REQUIRED` for insufficient classification.

## 8. Non-taxable income exclusion
Test taxable income plus cashback/wallet income.

Verify non-taxable rows stay in normal income facts, do not enter TaxEvents, and:
```text
Gross Income
- Excluded Non-Taxable Income
= Tax Model Income Universe
```

## 9. TaxEvent contract
Verify Source Type/ID, Head/Sub-Head, method, amounts, applied rate, estimated tax, and Tax Status for `LEDGER`, `INVESTMENT_REALIZED`, `READY`, and `CHECK_REQUIRED`.

## 10. Capital-loss set-off
Test STCL→STCG, STCL→LTCG, LTCL→LTCG, prohibited LTCL→STCG, plus full/partial/no utilization.

Assert utilized and closing ST/LT losses plus net taxable ST/LT gains.

## 11. Carry-forward
Test no opening loss, opening STCL/LTCL, full/partial utilization, and multiple FYs.

Invariant:
```text
Opening Loss + Current Loss - Utilized = Closing Loss
```

## 12. FY Tax State
Verify:
```text
Gross Income - Excluded Non-Taxable = Tax-Relevant Income
Estimated Ordinary Tax + Estimated Capital-Gains Tax = Estimated Gross Tax
Estimated Gross Tax - Observed Tax Credits = Estimated Net Tax Payable
```
Also reconcile all loss-state fields.

## 13. Gold tax marts
Test:
```text
Tax_Year_Summary
Tax_Income_Breakdown
Tax_Reconciliation
```
Verify declared grains and exact reconciliation to `f_Tax_FY_State`. Investment/non-investment capital gains must remain distinguishable.

## 14. Investment tax forecast
Test `gold.Investment_Tax_Liability_Forecast` as current/hypothetical investment exposure, separate from FY realized tax. Verify corrected shared loss semantics.

## 15. Broker/FIFO reconciliation events
Test quantity add/remove and cost-basis adjustment.

Verify ISIN/date/lot where available, adjustment type, quantity/basis impact, and reason.

Invariant:
```text
post-reconciliation reconstructed current state
=
intended broker-anchored current state
```
Historical realized events must not be silently rewritten.

## 16. Investment invariants
```text
Opening Qty + Buys - Sells ± Reconciliation = Closing Qty
Opening Basis + Purchases ± Basis Adjustments - Disposed FIFO Basis = Closing Basis
Sale Proceeds - Disposed FIFO Basis = Realized P&L
```
Every FIFO disposal must produce expected realized-event rows.

## 17. XIRR status semantics
Test normal XIRR, multiple flows, valid 0%, undefined pattern, non-convergence, invalid input. Non-valid states must not expose misleading 0%.

## 18. Artifact lifecycle provenance
Test discovery, unchanged rediscovery, content change, rename, PENDING_BRONZE replay, self-heal, sync, removal. Verify all first/last seen/changed/synced fields and artifact-run history.

## 19. Bronze synchronization
Test full replace, file-owned replacement, changed source becoming empty, missing table/partition, orphan cleanup, PENDING_BRONZE replay. Empty source must remove stale owned rows.

## 20. Contract registries
Validate unique IDs/tables, valid layers, non-empty grain/producer, publication order.

Planning expectation after implementation:
```text
Bronze 16
Silver ~24
Gold ~20
```
Freeze actual counts from the implemented registry. Verify the old tax-forecast name is not accidentally retained after rename.

## 21. Control Plane
Test run lifecycle, stale-run recovery, Settings/FinancialRules snapshots, failures, compressed logs, artifact-run lineage, simulation-run provenance.

## 22. Worker failure propagation
Force one ISIN worker failure. Entire investment stage/run must fail; partial portfolio must not publish; ISIN/run/stage context must remain available.

## 23. Snapshot / Restore
Test successful snapshot/restore, missing databases, invalid archive members, path traversal, failed install, rollback, sidecars, production lock.

Invariant:
```text
complete new pair OR complete old pair
never mixed generations
```

## 24. Monte Carlo replay
Same inputs/model/settings/rules/macro/seed must reproduce material output. Different seed may differ. Changed input/model must change the corresponding fingerprint.

## 25. Complete Reproducibility Envelope
Deterministic finance/tax:
```text
same evidence
+ same Settings
+ same FinancialRules/TaxConfig
+ same Macro Parameters
+ same implementation
→ same material realized events
→ same reconciliation events
→ same TaxEvents
→ same FY Tax State
→ same Gold tax marts
```
FIRE adds the same root seed.

Ignore operational timestamps/run IDs that are expected to change.

## 26. Pipeline idempotency
Run identical synthetic evidence twice. Verify no duplicate artifact/Bronze/realized/reconciliation/tax-event state and identical material Silver/Gold outputs.

## 27. CLI
Test `cli`, `tkinter`, `--config`, `--rules`, `--auto`, `--cron`, `--snapshot`, `--restore`, `--docs` behavior/error paths.

## 28. Docs runtime
Test manifest coverage, path resolution, navigation, TOC, bundled Mermaid, package resources, README/docs availability.

## 29. Packaging smoke
Verify wheel/sdist build, install, CLI start, Desktop import, docs/Mermaid packaging, configuration imports.

## 30. Performance guard
Use a generous material-regression threshold, not an exact runtime. Never trade correctness for benchmark speed.

## 31. Full synthetic E2E
```text
Synthetic Evidence
→ Discovery
→ Control Plane
→ Bronze
→ Canonical Finance
→ FIFO
→ Realized Events
→ Broker Reconciliation
→ TaxEvents
→ Loss Set-Off
→ FY Tax State
→ Silver / Gold
→ FIRE
→ Snapshot
→ Restore
→ Rebuild
```
Verify financial outputs, tax outputs, lineage, reproducibility, and recovery.

## Suggested order
```text
1 Fixtures
2 Unit/component
3 FIFO + realized events
4 Holding boundaries
5 TaxConfig + TaxEvents
6 Loss set-off/carry-forward
7 FY Tax State + Gold
8 Investment reconciliation
9 Artifact/Control Plane
10 Bronze/recovery
11 Monte Carlo replay
12 Integration/reproducibility
13 CLI/docs/package
14 Full E2E
```

## QA freeze checklist
- Current fixtures.
- Lot-level FIFO golden tests.
- Calendar-month boundary tests.
- TaxConfig ownership/non-taxable tests.
- No capital-gain double counting.
- Correct loss set-off/carry-forward.
- FY Tax State + 3 Gold marts reconcile.
- Investment forecast corrected.
- Broker/FIFO reconciliation tested.
- XIRR statuses tested.
- Artifact/self-healing protected.
- Snapshot/Restore protected.
- Monte Carlo replay protected.
- Reproducibility Envelope executable.
- Idempotency protected.
- CLI/docs/package smoke coverage.
- Full synthetic E2E passes.
