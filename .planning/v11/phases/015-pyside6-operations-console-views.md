# Phase 015 - PySide6 Operations Console Views

**Target release:** v11.4.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 014  
**Next:** Phase 016  
**Risk:** Medium-High

## 1. Outcome

Build the read-heavy PySide6 operations console views on top of existing Control Plane, warehouse and observability data.

## 2. Why this phase exists

- The backend already contains rich run, artifact, provider, warehouse and forensic history.
- The value is exposing it cleanly, not inventing new storage architecture.

## 3. Inherited repository state

- Phase 014 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- Phase-013 operator/query services
- Control Plane run/artifact/provider repositories
- DuckDB Meta/table row-count data
- observability event/query surfaces
- PySide6 shell from Phase 014

## 5. Exact target state after this phase

Build the read-heavy PySide6 operations console views on top of existing Control Plane, warehouse and observability data.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Implement Overview with latest run, freshness, warning/recovery state and recent runs

Implement Overview with latest run, freshness, warning/recovery state and recent runs.

### Step 2 - Implement Runs with history and drill-down into sync summary/provider/failure/observability context

Implement Runs with history and drill-down into sync summary/provider/failure/observability context.

### Step 3 - Implement Data with configured sources, hash policy, evidence state and last sync/change information actually available

Implement Data with configured sources, hash policy, evidence state and last sync/change information actually available.

### Step 4 - Implement Warehouse with Bronze/Silver/Gold tables, row counts, schema and bounded preview; do not add arbitrary SQL execution

Implement Warehouse with Bronze/Silver/Gold tables, row counts, schema and bounded preview; do not add arbitrary SQL execution.

### Step 5 - Implement Observability filters for run/severity/phase/component/operation plus structured detail/lineage view

Implement Observability filters for run/severity/phase/component/operation plus structured detail/lineage view.

### Step 6 - Implement Recovery/Snapshots view using existing application services

Implement Recovery/Snapshots view using existing application services.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Operational data becomes inspectable without new persistence architecture.

## 9. Tests and verification

- [ ] Each view reads through stable services/repositories and performs no direct financial mutation.
- [ ] Large tables/previews are bounded and the UI remains responsive.
- [ ] Run drill-down can navigate from operational summary to forensic observability evidence.
- [ ] Warehouse view exposes all active Bronze/Silver/Gold tables under the cleaned vocabulary.
- [ ] No finance KPI/dashboard creep appears in the operations console.

## 10. Explicit non-goals

- Do not build Analytics Studio features, chart builder or SQL editor.
- Do not add Settings editing yet.

## 11. Completion checklist

- [ ] Exit assertion: Each view reads through stable services/repositories and performs no direct financial mutation.
- [ ] Exit assertion: Large tables/previews are bounded and the UI remains responsive.
- [ ] Exit assertion: Run drill-down can navigate from operational summary to forensic observability evidence.
- [ ] Exit assertion: Warehouse view exposes all active Bronze/Silver/Gold tables under the cleaned vocabulary.
- [ ] Exit assertion: No finance KPI/dashboard creep appears in the operations console.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 016

The next phase may assume only the verified state above. It begins **Settings UI, Recovery UX and CustomTkinter Retirement** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 015
Target release: v11.4.0
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
