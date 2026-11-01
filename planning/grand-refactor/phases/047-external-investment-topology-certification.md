# Phase 047 - External Investment Topology Certification

**Target release:** v10.3.2  
**Expected effort:** 3-4 hours  
**Previous:** Phase 046  
**Next:** Phase 048  
**Risk:** High

## 1. Outcome

Certify external investment use cases with at least:
1. household + domestic investments with no foreign/FX requirement;
2. household + foreign investments requiring FX/foreign-market evidence.

Both configurations must use source shapes/topologies different from Shan's current vendors and require no source-code changes. Capability dependency failures must be diagnosed before financial execution.

## 2. Why this phase exists

Investment generalization is more demanding than household onboarding because source evidence feeds financial reconstruction, provider enrichments, FIFO/reconciliation, Tax and wealth. The final product claim is not credible until alternate investment sources reach those same canonical engines safely.

## 3. Inherited repository state

Phase 046 proves external household topologies. Phases 039-042 provide capability composition. Provider-generated evidence is generalized. Protected financial identities remain canonical.

## 4. Current codebase anchors

Build fixtures from current canonical investment Bronze contracts, not Shan vendor formats.

Domestic fixture should include enough evidence to exercise:
- investment master/reference resolution;
- purchases and sales;
- FIFO lot/realized reconstruction;
- reconciliation if applicable;
- current valuation if domestic market evidence is required;
- optional Tax/wealth according to selected plan.

Foreign fixture should exercise:
- canonical foreign classification;
- FX requirement;
- foreign/US market provider dataset plan using deterministic test provider/cache fixtures;
- purchase/sale and valuation.

Use Phase-045 diagnostics before full runs.

## 5. Exact target state after this phase

External investment configurations map arbitrary supported source shapes into the same canonical investment evidence.

Domestic-only plan performs zero unnecessary foreign/US provider work.

Foreign plan requests exactly required FX/market evidence.

Financial identities are derived from canonical financial state after Bronze, not vendor/source identity.

Invalid capability combinations fail at planner/preflight with remediation.

## 6. Detailed implementation sequence

### Step 1 - Freeze domestic scenario
Define source files/tables, mappings, canonical transactions and expected purchase/sale/lot/realized outcomes.

### Step 2 - Configure domestic source
Use a different source vocabulary/shape from Shan. Run validate/check/dry-run.

### Step 3 - Full domestic run
Assert no foreign provider calls; accounting/FIFO/reconciliation outputs match expected scenario.

### Step 4 - Freeze foreign scenario
Include foreign instrument/currency/transaction evidence and deterministic provider fixtures for FX/market.

### Step 5 - Full foreign run
Assert exact provider requirements/ranges and expected valuation.

### Step 6 - Identity stability
Reorder source rows/files and rerun. PURCHASE/SALE/LOT/REALIZED/RECON IDs remain stable for unchanged canonical scenario.

### Step 7 - Capability failure matrix
Examples:
- request foreign valuation with required FX/provider capability disabled;
- request Tax without mandatory accounting evidence;
- request FIRE/wealth with missing required household state.
Failures occur before engine execution and identify missing capability/DatasetId.

### Step 8 - Source failure matrix
Bad transaction type/date/amount/schema, missing instrument mapping, duplicate canonical grain where prohibited.

### Step 9 - Recovery/incremental
Change one transaction; verify affected canonical/financial state and replay behavior.

### Step 10 - Full Shan regression
External fixtures must not introduce special-case code that changes Shan outputs.

## 7. Files and symbols in scope

Create external investment fixtures/configs/provider test responses and certification tests.

Production changes only for genuine generalized-contract defects; no vendor-specific branches.

## 8. Cross-cutting impacts

**Persistence:** isolated fixture warehouses.

**Identity:** PURCHASE/SALE/LOT/REALIZED/RECON/TAX stability is central.

**Provider provenance:** deterministic test provider/cache responses use same provider-plan contracts.

**Observability:** foreign provider request and financial lineage traceable.

**Performance:** correctness fixtures; Phase 048 handles scale.

## 9. Tests and verification

Mandatory:
- domestic external topology;
- zero inappropriate foreign provider calls;
- foreign external topology;
- exact FX/market request requirements;
- accounting/FIFO/reconciliation expected values;
- protected IDs stable across reorder/rerun;
- capability failure matrix;
- malformed source/mapping failures;
- incremental change/replay;
- full Shan regression.

## 10. Explicit non-goals

Do not:
- add vendor-specific adapters beyond generic supported providers;
- change FIFO/reconciliation/Tax methodology;
- add new market providers;
- weaken capability dependencies.

## 11. Completion checklist

- [ ] Domestic external investment topology passes.
- [ ] Foreign external topology passes.
- [ ] Provider requirements correct.
- [ ] Financial identities stable.
- [ ] Capability failures are early/actionable.
- [ ] No vendor-specific production branch added.
- [ ] Shan regression green.

## 12. Commit boundary

```text
test(certification): add external investment topologies
```

## 13. Handoff to Phase 048

Phase 048 may assume correctness and configurability are proven across Shan and external topologies. It can now optimize the generalized architecture using representative workloads without hiding correctness defects behind performance work.

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
Commit:
```

A phase is incomplete if any required exit assertion is false.
