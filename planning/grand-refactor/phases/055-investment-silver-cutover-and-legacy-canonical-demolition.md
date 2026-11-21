# Phase 055 - Investment Silver Cutover and Legacy Canonical Demolition

**Target release:** v10.5.1  
**Expected effort:** 4-6 hours  
**Previous:** Phase 054  
**Next:** Phase 056  
**Risk:** Critical

## 1. Outcome

Complete the canonicalization program by switching investment/reference/provider consumers and capability requirements to the new canonical evidence, proving protected financial identity/output equivalence, and deleting the migration-only legacy architecture.

Phase 056 must inherit exactly one production architecture.

## 2. Why this phase exists

Phase 054 deliberately retained the old investment Silver path so the new evidence model could be proven before touching FIFO/Tax/reconciliation inputs. That coexistence is safe only as a short migration oracle. This phase performs the irreversible cutover and demolition after automated equivalence proof.

## 3. Inherited repository state

Phase 054 guarantees:
- canonical investment transactions/holdings/instrument/reference/provider evidence is produced and validated;
- provider-neutral market evidence exists;
- old investment Silver remains authoritative;
- comparison harness can present old/new equivalent preparation inputs;
- household already uses the new canonical architecture exclusively.

## 4. Current codebase anchors

Trace the complete protected chain:
- investment preparation that constructs purchase/sale inputs;
- deterministic `PURCHASE` and `SALE` IDs;
- FIFO/lot allocation and `LOT` IDs;
- realized events and `REALIZED` IDs;
- reconciliation groups/events/lot groups;
- Tax engine event/ID generation;
- benchmark, FX and foreign-asset enrichment;
- investment capability requirements and plan-aware warehouse outputs;
- old DatasetIds/contracts/schemas/routes/loader compatibility paths introduced before/through Phase 047.

## 5. Exact target state after this phase

Financial consumers read only canonical evidence:

```text
INVESTMENT_TRANSACTIONS
INVESTMENT_HOLDINGS
INVESTMENT_INSTRUMENTS
BENCHMARKS / assignments
PROVIDER_SYMBOL_MAPPINGS
FX_RATES
BENCHMARK_PRICES
INSTRUMENT_PRICES
```

or the exact final names frozen by Phase 054.

Source/vendor strings and old source-family DatasetIds are absent from financial-domain logic.

Investment capability requirements refer to canonical evidence only.

Protected deterministic identities and financial values are unchanged:
- PURCHASE;
- SALE;
- LOT;
- REALIZED;
- RECON_LOT_GROUP;
- RECON_GROUP;
- RECON_EVENT;
- TAX.

After zero-reference proof delete:
- old MF/domestic/US source-container Bronze DatasetIds and schemas;
- US-specific canonical price DatasetId if replaced;
- obsolete benchmark/provider mapping bundles;
- old Silver preparation branches that interpret vendor actions/placeholders;
- `SourceDatasetConfig.dataset_id` runtime coupling and its compatibility compiler;
- old DatasetPlan/Pre-Bronze compatibility APIs not already removed;
- migration-only aliases/adapters.

## 6. Detailed implementation sequence

### Step 1 - Freeze the protected oracle
Before switching consumers, persist deterministic comparison snapshots for protected IDs and financially meaningful purchase/sale/lot/realized/reconciliation/Tax values using current accepted Shan evidence.

### Step 2 - Cut investment preparation
Feed canonical investment transaction/holding/instrument evidence into existing purchase/sale preparation. Remove PURCHASE/REDEEM/BUY/SELL and placeholder interpretation from Silver/domain code.

### Step 3 - Prove PURCHASE/SALE identity equality
Compare full sorted identity sets and identity-driving fields. Any difference is a blocker unless traced to an explicitly approved canonical identity correction, which is outside this phase's default scope.

### Step 4 - Prove FIFO/lot/realized equivalence
Run the same financial engines on new preparation inputs. Compare LOT/REALIZED IDs, quantities, cost basis, proceeds, gains and ordering semantics.

### Step 5 - Prove reconciliation equivalence
Compare reconciliation group/event/lot-group identities and balances. Canonical source changes must not alter accounting truth.

### Step 6 - Prove Tax equivalence
Compare Tax event IDs, heads/subheads, taxable/exempt values and Tax-gated lot analytics. Tax formulas remain unchanged.

### Step 7 - Cut benchmark/FX/foreign enrichment
Switch consumers from old provider/source-shaped contracts to canonical benchmark/FX/instrument price evidence. Preserve plan-driven capability gating from Phases 040-043.

### Step 8 - Switch capability requirements
Update investment accounting, benchmark, foreign-asset, Tax, Wealth/FIRE dependencies to canonical evidence where applicable. Re-run capability composition matrix.

### Step 9 - Delete vendor-shaped Bronze/reference path
Use reference search/architecture tests to prove zero runtime consumers before deleting retired DatasetIds, DDL/Pandera schemas and transitional source routes.

### Step 10 - Delete compatibility compiler and 1:1 assumptions
Remove the Phase-047 compiler and any API that assumes SourceDatasetConfig DatasetId == Pre-Bronze identity == canonical target. The new binding/route/production model becomes the only supported runtime representation.

### Step 11 - Add permanent demolition guards
Architecture tests reject retired DatasetIds/source action strings/provider-specific canonical names in Silver/Gold/domain modules and reject old compatibility compiler symbols.

### Step 12 - Upgrade/recovery certification
Upgrade existing v10.3.0-style operational state, rebuild canonical Bronze, then compare with a clean run. Test failure/recovery during the cutover lifecycle.

### Step 13 - Final pre-certification run
Run full Shan evidence plus generic topology tests. Verify Phase 056 starts from a single-path canonical architecture with no migration-only runtime branch.

## 7. Files and symbols in scope

Expected changes:
- investment preparation/Silver transforms;
- capability contracts/requirements;
- benchmark/FX/foreign enrichment consumers;
- retired Bronze/reference DatasetIds/schemas/contracts;
- compatibility compiler and legacy config/runtime adapters;
- architecture/demolition tests;
- protected identity/financial equivalence suites.

## 8. Cross-cutting impacts

**Financial correctness:** highest-risk phase. No formula change is permitted; protected IDs and values are the acceptance oracle.

**Configuration:** new source-binding/route/production model becomes the only runtime path. Legacy compatibility exists only for explicit upgrade handling if still required, not ordinary execution.

**Warehouse:** retired vendor-shaped Bronze tables disappear; Silver/Gold remain plan-aware from Phase 043.

**Replay/recovery:** current configuration graph drives rebuilds. No old DatasetId mapping tables remain.

**Observability:** canonical DatasetId plus source binding/route provenance replaces old source-family dataset context.

## 9. Tests and verification

Required:
- canonical investment preparation equals old-path purchase/sale preparation at financial grain;
- exact PURCHASE and SALE ID sets;
- exact LOT, REALIZED, RECON_* and TAX ID sets;
- FIFO quantities/cost/proceeds/gains equivalent;
- reconciliation balances/events equivalent;
- Tax results and Tax-gated analytics equivalent;
- domestic-only, foreign, benchmark-disabled, Tax-disabled and Wealth/FIRE capability compositions remain valid;
- old vendor/source action strings are absent from Silver/domain interpretation;
- all retired DatasetIds/contracts/schemas/routes have zero runtime references before deletion;
- compatibility compiler symbol is absent after deletion;
- current config examples use the new model or approved upgrade translator only;
- upgrade from v10.3.0 state equals clean new run;
- recovery around failed canonical rebuild converges;
- full Shan Gold outputs remain financially equivalent;
- generic N:M topology tests remain green after demolition.

## 10. Explicit non-goals

Do not:
- introduce new investment features or formulas;
- optimize performance beyond correcting regressions;
- perform final external household/investment certification or column-retirement sweep (Phases 056-057);
- freeze the public contract universe yet (Phase 059);
- extract `pfetl-contracts` into a separate package/repository.

## 11. Completion checklist

- [ ] Investment Silver preparation consumes only canonical transaction/holding/instrument/reference/provider evidence.
- [ ] PURCHASE, SALE, LOT, REALIZED, RECON_LOT_GROUP, RECON_GROUP, RECON_EVENT and TAX identity sets are exactly preserved.
- [ ] FIFO, realized, reconciliation, Tax, benchmark, FX and foreign-asset values remain equivalent under the new evidence path.
- [ ] Investment/Tax/Wealth/FIRE capability requirements resolve canonical evidence only.
- [ ] Retired MF/stock/US vendor-shaped Bronze/reference DatasetIds, schemas, routes and Silver interpretation branches are deleted after zero-reference proof.
- [ ] The Phase-047 compatibility compiler and remaining runtime 1:1 SourceDatasetConfig->DatasetId assumptions are deleted.
- [ ] Upgrade/replay/recovery from v10.3.0-style state converges to the same result as a clean canonical run.
- [ ] Phase 056 inherits one production architecture with no migration-only runtime branch.

## 12. Commit boundary

Use `pfetl-conventional-commits` to keep cutover, capability migration and legacy demolition in semantic groups that remain reviewable and green. Preview groupings and let the commit skill own messages/staging. Do not create one giant demolition commit unless the skill/diff genuinely supports it.

## 13. Handoff to Phase 056

Phase 056 may assume the canonical source-binding -> route -> production -> Bronze architecture is the **only** production path for household and investment evidence. No remaining architecture work may be hidden inside external certification. Phase 056's job is to challenge that finished architecture with independent household topologies and perform the consumer-backed household Bronze/Silver column-retirement archaeology before public contract freeze.

## Phase completion record

```text
Phase:
Target release:
Files changed:
Schema changed:
Runtime behavior changed:
Financial formulas changed: NO
Focused tests:
Architecture tests:
Real-data run:
Performance check:
Compatibility path still present:
Old path deleted:
Exit assertions green:
Commits:
```

A phase is incomplete if any required exit assertion is false.
