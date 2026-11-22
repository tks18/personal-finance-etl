# Phase 009 - Gold Household, Wealth, FIRE and Tax Vocabulary Cutover

**Target release:** v11.2.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 008  
**Next:** Phase 010  
**Risk:** High

## 1. Outcome

Cut over household, wealth, FIRE and Tax Gold vocabulary with exact numerical equivalence.

## 2. Why this phase exists

- This separates household/planning analytical migration from investment aggregation migration and keeps each sprint verifiable.

## 3. Inherited repository state

- Phase 008 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- Gold tax summaries/breakdowns/reconciliation
- Core monthly fact, wealth asset breakdown, cashflow expense/income, FIRE, budget, cashflow efficiency/activity tables
- Phase 008 rename/disposition map

## 5. Exact target state after this phase

Cut over household, wealth, FIRE and Tax Gold vocabulary with exact numerical equivalence.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Rename the targeted Gold physical tables and approved columns

Rename the targeted Gold physical tables and approved columns.

### Step 2 - Update producer output keys/contracts and all application/test consumers

Update producer output keys/contracts and all application/test consumers.

### Step 3 - Apply approved `fx`, `pnl`, `financial_year`, percentage and base/local vocabulary without unit conversion

Apply approved `fx`, `pnl`, `financial_year`, percentage and base/local vocabulary without unit conversion.

### Step 4 - Remove only Phase-008-proven dead columns

Remove only Phase-008-proven dead columns.

### Step 5 - Update the corresponding Power BI queries/model references for these surfaces

Update the corresponding Power BI queries/model references for these surfaces.

### Step 6 - Refresh Power BI and compare all financial outputs to pre-cutover values

Refresh Power BI and compare all financial outputs to pre-cutover values.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Household/wealth/FIRE/tax Power BI surfaces cut over.

## 9. Tests and verification

- [ ] Target household/wealth/FIRE/tax Gold tables publish successfully with the same grains.
- [ ] All renamed metrics retain identical numerical units/values.
- [ ] Tax and FIRE outputs match the oracle.
- [ ] Power BI refreshes without references to retired names in the migrated surfaces.
- [ ] No compatibility view/alias remains.

## 10. Explicit non-goals

- Do not rename investment Gold aggregations yet.
- Do not add new analytics.

## 11. Completion checklist

- [ ] Exit assertion: Target household/wealth/FIRE/tax Gold tables publish successfully with the same grains.
- [ ] Exit assertion: All renamed metrics retain identical numerical units/values.
- [ ] Exit assertion: Tax and FIRE outputs match the oracle.
- [ ] Exit assertion: Power BI refreshes without references to retired names in the migrated surfaces.
- [ ] Exit assertion: No compatibility view/alias remains.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 010

The next phase may assume only the verified state above. It begins **Gold Investment Vocabulary and Power BI Cutover** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 009
Target release: v11.2.0
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
