# Phase 012 - Investment and Tax Intelligence Expansion

**Target release:** v11.3.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 011  
**Next:** Phase 013  
**Risk:** Medium-High

## 1. Outcome

Add the three approved investment/Tax analytics from existing lot, portfolio and Tax evidence.

## 2. Why this phase exists

- PFETL already has rich lot-level investment and tax state; these analytics convert existing sophistication into decisions without new platform machinery.

## 3. Inherited repository state

- Phase 011 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- fact investment lot/Gold investment surfaces
- portfolio weights and instrument classifications
- Tax events and tax summary surfaces
- current LTCG threshold/days-to-LTCG fields

## 5. Exact target state after this phase

Add the three approved investment/Tax analytics from existing lot, portfolio and Tax evidence.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Implement portfolio concentration with top-1/top-5/top-10 weights, HHI and effective holdings at the approved portfolio grain

Implement portfolio concentration with top-1/top-5/top-10 weights, HHI and effective holdings at the approved portfolio grain.

### Step 2 - Implement LTCG maturity buckets from existing days-to-LTCG logic; keep Tax methodology unchanged

Implement LTCG maturity buckets from existing days-to-LTCG logic; keep Tax methodology unchanged.

### Step 3 - Implement tax exposure summary using existing estimated tax, tax-if-sold, unrealized gain/loss, harvestability and exemption evidence; label outputs indicative/estimated

Implement tax exposure summary using existing estimated tax, tax-if-sold, unrealized gain/loss, harvestability and exemption evidence; label outputs indicative/estimated.

### Step 4 - Use existing Gold surfaces where grain matches and keep dynamic cross-slicing for future Analytics Studio

Use existing Gold surfaces where grain matches and keep dynamic cross-slicing for future Analytics Studio.

### Step 5 - Add deterministic tests for concentration math, maturity bucket boundaries and Tax aggregation

Add deterministic tests for concentration math, maturity bucket boundaries and Tax aggregation.

### Step 6 - Run full investment/Tax oracle to confirm existing outputs are unchanged

Run full investment/Tax oracle to confirm existing outputs are unchanged.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- New investment/Tax methodology is additive and explicitly indicative where appropriate.

## 9. Tests and verification

- [ ] HHI/effective-holdings metrics match independent fixture calculations.
- [ ] LTCG bucket totals reconcile to the underlying eligible lots.
- [ ] Tax exposure totals reconcile to existing Tax/lot evidence and remain explicitly indicative.
- [ ] No trade recommendation or rebalance action is emitted.
- [ ] No new source data or generalized analytical framework was introduced.

## 10. Explicit non-goals

- Do not add rebalancing actions, scenario UI, arbitrary group-by tables or expense/income volatility metrics.

## 11. Completion checklist

- [ ] Exit assertion: HHI/effective-holdings metrics match independent fixture calculations.
- [ ] Exit assertion: LTCG bucket totals reconcile to the underlying eligible lots.
- [ ] Exit assertion: Tax exposure totals reconcile to existing Tax/lot evidence and remain explicitly indicative.
- [ ] Exit assertion: No trade recommendation or rebalance action is emitted.
- [ ] Exit assertion: No new source data or generalized analytical framework was introduced.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 013

The next phase may assume only the verified state above. It begins **Single pfetl Command and Operator Read Services** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 012
Target release: v11.3.0
Files changed:
Contracts/schema changed:
Financial formulas changed:
Protected identity comparison:
Focused tests:
Architecture tests:
Real-data verification:
Power BI verification:
Observability/recovery verification:
Compatibility/transitional state remaining:
Semantic commit groups:
Exit assertions green: yes/no
```
