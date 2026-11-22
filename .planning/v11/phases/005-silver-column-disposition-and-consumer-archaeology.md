# Phase 005 - Silver Column Disposition and Consumer Archaeology

**Target release:** v11.2.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 004  
**Next:** Phase 006  
**Risk:** Medium

## 1. Outcome

Produce the authoritative Silver column/consumer disposition manifest before any Silver schema change.

## 2. Why this phase exists

- The conservative Silver rule is consumer-proven cleanup only.
- Fields that look ugly may still feed Gold, Power BI, finance engines or identity logic.
- A checked-in manifest prevents intuition-driven deletion and keeps the actual rename sprint bounded.

## 3. Inherited repository state

- Phase 004 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- `infrastructure/warehouse/schema/silver.py`
- `DATA_CONTRACT_REGISTRY` Silver entries
- Core/wealth/investment/tax producers and consumers
- Gold producers
- tests and any direct SQL/Power BI documentation references

## 5. Exact target state after this phase

Produce the authoritative Silver column/consumer disposition manifest before any Silver schema change.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Inventory every current Silver table, grain and column

Inventory every current Silver table, grain and column.

### Step 2 - For each column classify KEEP, RENAME, REMOVE_CANDIDATE, or PROTECTED; record all code/test/Gold consumers

For each column classify KEEP, RENAME, REMOVE_CANDIDATE, or PROTECTED; record all code/test/Gold consumers.

### Step 3 - Flag source/provenance vocabulary (`__file_*`, raw `Z*`, `S_NO`, provider fields) but do not delete without zero-consumer proof

Flag source/provenance vocabulary (`__file_*`, raw `Z*`, `S_NO`, provider fields) but do not delete without zero-consumer proof.

### Step 4 - Freeze exact table rename map for all 24 Silver tables using dim/fact/ref naming without changing topology

Freeze exact table rename map for all 24 Silver tables using dim/fact/ref naming without changing topology.

### Step 5 - Freeze exact canonical vocabulary for `instrument`, `fx`, `pnl`, `financial_year`, and verified base/local fields

Freeze exact canonical vocabulary for `instrument`, `fx`, `pnl`, `financial_year`, and verified base/local fields.

### Step 6 - Create targeted regression assertions for high-risk IDs/financial columns before implementation

Create targeted regression assertions for high-risk IDs/financial columns before implementation.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- This phase creates evidence for later destructive cleanup but performs none.

## 9. Tests and verification

- [ ] All 24 Silver tables have an explicit target physical name.
- [ ] Every Silver column has a recorded disposition and known consumer list.
- [ ] Every REMOVE_CANDIDATE has zero required consumers or a named migration owner.
- [ ] Protected IDs and formula-bearing fields are clearly marked.
- [ ] No DDL or runtime financial behavior changed in this archaeology phase.

## 10. Explicit non-goals

- Do not edit Silver DDL or producers.
- Do not merge/split tables or add analytics.

## 11. Completion checklist

- [x] Exit assertion: All 24 Silver tables have an explicit target physical name.
- [x] Exit assertion: Every Silver column has a recorded disposition and known consumer list.
- [x] Exit assertion: Every REMOVE_CANDIDATE has zero required consumers or a named migration owner.
- [x] Exit assertion: Protected IDs and formula-bearing fields are clearly marked.
- [x] Exit assertion: No DDL or runtime financial behavior changed in this archaeology phase.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 006

The next phase may assume only the verified state above. It begins **Silver Household and Reference Vocabulary Cutover** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 005
Target release: v11.2.0
Files changed:
- .planning/v11/SILVER-DISPOSITION-MANIFEST.md
- tests/test_phase5_silver_column_disposition.py
- .planning/v11/phases/005-silver-column-disposition-and-consumer-archaeology.md
Contracts/schema changed: None (governance & archaeology only)
Financial formulas changed: None (strictly non-destructive)
Protected identity comparison: 126 critical business keys & financial quantities mapped to PROTECTED with byte-for-byte invariance
Focused tests: 7 passed in tests/test_phase5_silver_column_disposition.py
Architecture tests: 211 passed across full pytest suite
Real-data verification: Rebuild and extraction proven in Phase 4; 0 runtime code changes in Phase 5
Power BI verification: Gold layer untouched; downstream queries protected
Observability/recovery verification: Single-emitter and Control Plane untouched
Compatibility/transitional state remaining: None
Semantic commit groups:
- docs(silver): author authoritative column disposition and consumer manifest
- test(silver): add regression and zero-consumer assertions for silver disposition
- docs(v11): record phase 005 completion in phase roadmap and ledger
Exit assertions green: yes
```
