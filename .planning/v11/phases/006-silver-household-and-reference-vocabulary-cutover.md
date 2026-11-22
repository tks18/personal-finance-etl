# Phase 006 - Silver Household and Reference Vocabulary Cutover

**Target release:** v11.2.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 005  
**Next:** Phase 007  
**Risk:** High

## 1. Outcome

Apply the approved Silver vocabulary cleanup to household/reference tables only, preserving all existing table grains and values.

## 2. Why this phase exists

- Splitting Silver implementation keeps the 2–3 hour sprint honest and isolates household/reference blast radius from investments.
- This phase converts obvious canonical vocabulary without touching protected investment identities.

## 3. Inherited repository state

- Phase 005 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- Silver calendar/income/expense/asset/currency/benchmark/macro/opening-balance/FX DDL and transforms
- household ledger/wealth consumers
- Gold household producers
- Phase 005 disposition manifest

## 5. Exact target state after this phase

Apply the approved Silver vocabulary cleanup to household/reference tables only, preserving all existing table grains and values.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Rename the household/reference Silver physical tables according to the approved 24-table map

Rename the household/reference Silver physical tables according to the approved 24-table map.

### Step 2 - Apply approved column renames only; preserve units and value semantics exactly

Apply approved column renames only; preserve units and value semantics exactly.

### Step 3 - Remove only Phase-005-proven dead provenance/source columns

Remove only Phase-005-proven dead provenance/source columns.

### Step 4 - Update contract IDs only where the plan explicitly chooses semantic IDs; keep publication order/grain unchanged

Update contract IDs only where the plan explicitly chooses semantic IDs; keep publication order/grain unchanged.

### Step 5 - Migrate ledger/wealth/Gold/test consumers in the same semantic commit groups

Migrate ledger/wealth/Gold/test consumers in the same semantic commit groups.

### Step 6 - Run household monthly totals, balances, net-worth, FX and FIRE regression against the oracle

Run household monthly totals, balances, net-worth, FX and FIRE regression against the oracle.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Household/wealth consumers and tests migrate to new Silver vocabulary.

## 9. Tests and verification

- [ ] All targeted household/reference Silver tables exist under approved names and old names do not.
- [ ] No table grain or row count changes unexpectedly.
- [ ] Income/expense/transfer/opening-balance values are equivalent.
- [ ] Net worth and FIRE outputs remain equivalent.
- [ ] No unapproved source/provenance column was removed.

## 10. Explicit non-goals

- Do not modify investment/event/tax Silver tables.
- Do not add new analytics or change Gold physical names.

## 11. Completion checklist

- [ ] Exit assertion: All targeted household/reference Silver tables exist under approved names and old names do not.
- [ ] Exit assertion: No table grain or row count changes unexpectedly.
- [ ] Exit assertion: Income/expense/transfer/opening-balance values are equivalent.
- [ ] Exit assertion: Net worth and FIRE outputs remain equivalent.
- [ ] Exit assertion: No unapproved source/provenance column was removed.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 007

The next phase may assume only the verified state above. It begins **Silver Investment, Event and Tax Vocabulary Cutover** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 006
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
