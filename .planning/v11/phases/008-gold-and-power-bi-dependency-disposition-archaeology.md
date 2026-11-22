# Phase 008 - Gold and Power BI Dependency/Disposition Archaeology

**Target release:** v11.2.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 007  
**Next:** Phase 009  
**Risk:** Medium

## 1. Outcome

Produce the authoritative Gold/Power BI dependency and rename manifest before changing any Gold physical contract.

## 2. Why this phase exists

- Gold is the external analytical boundary and has current Power BI consumers.
- The one-owner migration lets names break once, but only after every consumer is known.

## 3. Inherited repository state

- Phase 007 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- 22 Gold contracts in `DATA_CONTRACT_REGISTRY`
- `infrastructure/warehouse/schema/gold.py`
- wealth/tax/investment Gold producers
- Power BI query/model references available to the user/repo docs
- tests/direct SQL/reporting references

## 5. Exact target state after this phase

Produce the authoritative Gold/Power BI dependency and rename manifest before changing any Gold physical contract.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Inventory all 22 Gold tables, grains, columns and producer inputs

Inventory all 22 Gold tables, grains, columns and producer inputs.

### Step 2 - Freeze exact lowercase snake_case table names without changing topology

Freeze exact lowercase snake_case table names without changing topology.

### Step 3 - Classify each Gold column KEEP/RENAME/REMOVE_CANDIDATE/PROTECTED and record consumers

Classify each Gold column KEEP/RENAME/REMOVE_CANDIDATE/PROTECTED and record consumers.

### Step 4 - Build explicit old→new Power BI migration map for every consumed table/column

Build explicit old→new Power BI migration map for every consumed table/column.

### Step 5 - Identify repeated investment aggregate metric definitions that can use a tiny internal shared schema helper without changing outputs

Identify repeated investment aggregate metric definitions that can use a tiny internal shared schema helper without changing outputs.

### Step 6 - Create pre-cutover numerical regression snapshots for every Gold table

Create pre-cutover numerical regression snapshots for every Gold table.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Power BI becomes an explicit migration consumer of Gold vocabulary.

## 9. Tests and verification

- [ ] All 22 Gold tables have target names and consumer maps.
- [ ] Every Power BI dependency has an explicit replacement.
- [ ] No table is scheduled for merge/delete merely due to duplication.
- [ ] Every removal candidate has zero required consumers.
- [ ] No Gold runtime or schema behavior changed in this phase.

## 10. Explicit non-goals

- Do not edit Gold DDL/producers or Power BI yet.
- Do not add the six new analytics.

## 11. Completion checklist

- [ ] Exit assertion: All 22 Gold tables have target names and consumer maps.
- [ ] Exit assertion: Every Power BI dependency has an explicit replacement.
- [ ] Exit assertion: No table is scheduled for merge/delete merely due to duplication.
- [ ] Exit assertion: Every removal candidate has zero required consumers.
- [ ] Exit assertion: No Gold runtime or schema behavior changed in this phase.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 009

The next phase may assume only the verified state above. It begins **Gold Household, Wealth, FIRE and Tax Vocabulary Cutover** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 008
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
