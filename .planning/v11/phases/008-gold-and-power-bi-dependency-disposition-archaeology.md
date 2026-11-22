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

- [x] All 22 Gold tables have target names and consumer maps.
- [x] Every Power BI dependency has an explicit replacement.
- [x] No table is scheduled for merge/delete merely due to duplication.
- [x] Every removal candidate has zero required consumers.
- [x] No Gold runtime or schema behavior changed in this phase.

## 10. Explicit non-goals

- Do not edit Gold DDL/producers or Power BI yet.
- Do not add the six new analytics.

## 11. Completion checklist

- [x] Exit assertion: All 22 Gold tables have target names and consumer maps.
- [x] Exit assertion: Every Power BI dependency has an explicit replacement.
- [x] Exit assertion: No table is scheduled for merge/delete merely due to duplication.
- [x] Exit assertion: Every removal candidate has zero required consumers.
- [x] Exit assertion: No Gold runtime or schema behavior changed in this phase.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 009

The next phase may assume only the verified state above. It begins **Gold Household, Wealth, FIRE and Tax Vocabulary Cutover** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 008
Target release: v11.2.0
Files changed:
  - .planning/v11/GOLD-DISPOSITION-MANIFEST.md
  - tests/test_phase8_gold_dependency_and_disposition.py
  - .planning/v11/phases/008-gold-and-power-bi-dependency-disposition-archaeology.md
Contracts/schema changed: None (Strictly non-destructive archaeology; 0 DDL or contracts modified in Phase 008). 22 tables cataloged, 577 physical columns cataloged, 212 PROTECTED, 365 RENAME, 0 dead removals.
Financial formulas changed: None (0 formulas changed; 100% financial formula invariance preserved).
Protected identity comparison: 100% byte-for-byte identical (FY, MONTH_START_DATE, MONTH_END_DATE, YEAR_MONTH, ASSET_SUBCATEGORY_ID, CATEGORY_ID, ISIN, CURRENCY_ID, Closing_Date).
Focused tests: tests/test_phase8_gold_dependency_and_disposition.py (7/7 passed in 2.70s).
Architecture tests: 33/33 phase suite passed in 2.85s. Ruff clean, Ruff format clean, Mypy clean.
Real-data verification: Rebuild ready; pending user unattended execution.
Power BI verification: Complete 1:1 forward column mapping matrix produced in Section 7 of manifest for all 22 tables and 577 columns.
Observability/recovery verification: Single-emitter observability intact; 0 regressions in backup/restore/fingerprints.
Compatibility/transitional state remaining: Gold DDL, producer outputs, and Power BI cutovers scheduled for Phase 009 (Household/Tax) and Phase 010 (Investments).
Semantic commit groups:
  - docs(gold): author authoritative gold disposition manifest
  - test(gold): add phase 8 gold disposition suite
  - docs(v11): record phase 008 completion
Exit assertions green: yes
```
