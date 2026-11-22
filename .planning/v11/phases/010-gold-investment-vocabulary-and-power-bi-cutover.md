# Phase 010 - Gold Investment Vocabulary and Power BI Cutover

**Target release:** v11.2.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 009  
**Next:** Phase 011  
**Risk:** High

## 1. Outcome

Cut over all investment Gold vocabulary and complete the one-time Power BI warehouse migration.

## 2. Why this phase exists

- Investment Gold includes ten breakdown surfaces with shared metrics; consistent vocabulary is valuable, but topology remains unchanged.
- Completing Power BI in the same phase closes the external-consumer migration rather than leaving aliases.

## 3. Inherited repository state

- Phase 009 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- Investment portfolio summary and ten `Investment_By_*` Gold tables
- investment aggregation service
- Gold schema/registry
- Phase 008 Power BI map

## 5. Exact target state after this phase

Cut over all investment Gold vocabulary and complete the one-time Power BI warehouse migration.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Rename investment Gold tables to approved lowercase analytical names

Rename investment Gold tables to approved lowercase analytical names.

### Step 2 - Normalize approved repeated metric names consistently across all investment breakdowns

Normalize approved repeated metric names consistently across all investment breakdowns.

### Step 3 - Where DDL repetition is exact, introduce only the minimal shared metric-column helper approved in Phase 008

Where DDL repetition is exact, introduce only the minimal shared metric-column helper approved in Phase 008.

### Step 4 - Update aggregation outputs/contracts/tests

Update aggregation outputs/contracts/tests.

### Step 5 - Migrate every remaining Power BI investment reference and refresh the complete model

Migrate every remaining Power BI investment reference and refresh the complete model.

### Step 6 - Compare all Gold investment values, weights, returns, XIRR, benchmark metrics and P&L against the oracle

Compare all Gold investment values, weights, returns, XIRR, benchmark metrics and P&L against the oracle.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Investment Power BI surfaces cut over and v11.2.0 schema migration closes.

## 9. Tests and verification

- [ ] All 22 Gold tables exist under approved target names with no old Gold aliases.
- [ ] All ten investment breakdown surfaces retain their original grain.
- [ ] Investment numerical outputs match the pre-cutover oracle.
- [ ] Power BI completes a full refresh against only the new warehouse vocabulary.
- [ ] The v11.2.0 warehouse migration is complete with Bronze/Silver/Gold naming internally coherent.

## 10. Explicit non-goals

- Do not add portfolio concentration metrics yet.
- Do not convert Gold tables to views or remove breakdown surfaces.

## 11. Completion checklist

- [ ] Exit assertion: All 22 Gold tables exist under approved target names with no old Gold aliases.
- [ ] Exit assertion: All ten investment breakdown surfaces retain their original grain.
- [ ] Exit assertion: Investment numerical outputs match the pre-cutover oracle.
- [ ] Exit assertion: Power BI completes a full refresh against only the new warehouse vocabulary.
- [ ] Exit assertion: The v11.2.0 warehouse migration is complete with Bronze/Silver/Gold naming internally coherent.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 011

The next phase may assume only the verified state above. It begins **Household and Wealth Intelligence Expansion** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 010
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
