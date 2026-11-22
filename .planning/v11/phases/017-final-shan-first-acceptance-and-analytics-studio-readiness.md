# Phase 017 - Final Shan-First Acceptance and Analytics Studio Readiness

**Target release:** v11.4.1  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 016  
**Next:** Program complete  
**Risk:** High

## 1. Outcome

Certify the complete Shan-first v11 program and freeze PFETL Core for daily use plus future read-only Analytics Studio consumption.

## 2. Why this phase exists

- The program succeeds only if it reduces friction without losing the reliability and financial sophistication of v11.0.0.
- Final acceptance must certify the whole user journey, not individual phase tests in isolation.

## 3. Inherited repository state

- Phase 016 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- all changed subsystems
- full test/quality gate
- real Shan dataset and pre-program financial oracle
- Power BI model
- packaged CLI/PySide6 application
- Raw Store/Control Plane/observability/recovery

## 5. Exact target state after this phase

Certify the complete Shan-first v11 program and freeze PFETL Core for daily use plus future read-only Analytics Studio consumption.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Run clean-install/configuration validation and `pfetl doctor/info/status`

Run clean-install/configuration validation and `pfetl doctor/info/status`.

### Step 2 - Run cold/full and cached production executions; compare runtime to the accepted envelope without chasing micro-optimizations

Run cold/full and cached production executions; compare runtime to the accepted envelope without chasing micro-optimizations.

### Step 3 - Verify Bronze/Silver/Gold table inventory and cleaned vocabulary; confirm no retired compatibility aliases/portal assets/legacy UI binaries remain

Verify Bronze/Silver/Gold table inventory and cleaned vocabulary; confirm no retired compatibility aliases/portal assets/legacy UI binaries remain.

### Step 4 - Compare all protected IDs and unchanged financial outputs to the v11

Compare all protected IDs and unchanged financial outputs to the v11.0.0 oracle, then validate the six new analytics independently.

### Step 5 - Exercise deliberate failure, recovery-required state, snapshot/restore, provider failure and multiprocessing observability lineage

Exercise deliberate failure, recovery-required state, snapshot/restore, provider failure and multiprocessing observability lineage.

### Step 6 - Run packaged PySide6 workflow and full Power BI refresh

Run packaged PySide6 workflow and full Power BI refresh.

### Step 7 - Verify future Analytics Studio can read DuckDB/Meta read-only and determine version/freshness without a separate contracts package

Verify future Analytics Studio can read DuckDB/Meta read-only and determine version/freshness without a separate contracts package.

### Step 8 - Record final accepted architecture, known limitations and migration completion

Record final accepted architecture, known limitations and migration completion.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Program-wide acceptance freezes the simplified Core for daily use.

## 9. Tests and verification

- [ ] All quality gates and real-data financial regressions are green.
- [ ] Protected identities exactly match the oracle.
- [ ] The six new analytics pass independent calculations and add no unexplained existing-output changes.
- [ ] One `pfetl` command and one PySide6 GUI are the only supported application entry experience.
- [ ] Raw Store and Control Plane history survived the program.
- [ ] Power BI refreshes successfully.
- [ ] No generic-platform architecture or unfinished compatibility layer remains.
- [ ] PFETL is ready for daily use; Analytics Studio is optional future work, not a missing Core requirement.

## 10. Explicit non-goals

- Do not start Analytics Studio implementation in this phase.
- Do not create a Phase 018 merely to continue architectural polishing.

## 11. Completion checklist

- [ ] Exit assertion: All quality gates and real-data financial regressions are green.
- [ ] Exit assertion: Protected identities exactly match the oracle.
- [ ] Exit assertion: The six new analytics pass independent calculations and add no unexplained existing-output changes.
- [ ] Exit assertion: One `pfetl` command and one PySide6 GUI are the only supported application entry experience.
- [ ] Exit assertion: Raw Store and Control Plane history survived the program.
- [ ] Exit assertion: Power BI refreshes successfully.
- [ ] Exit assertion: No generic-platform architecture or unfinished compatibility layer remains.
- [ ] Exit assertion: PFETL is ready for daily use; Analytics Studio is optional future work, not a missing Core requirement.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Program complete

No further Core architecture phase is implied. Future Analytics Studio work begins only as a separate read-only product initiative if desired.

## Phase completion record

```text
Phase: 017
Target release: v11.4.1
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
