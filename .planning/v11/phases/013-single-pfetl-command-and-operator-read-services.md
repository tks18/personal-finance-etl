# Phase 013 - Single pfetl Command and Operator Read Services

**Target release:** v11.4.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 012  
**Next:** Phase 014  
**Risk:** Medium

## 1. Outcome

Replace historical `shan-fin`/`shan-fin-gui` entry points with one `pfetl` product command and add small operator read services for status/doctor/info.

## 2. Why this phase exists

- The application identity should match PFETL and the CLI should reduce daily friction rather than expose implementation names.
- Operator commands need dedicated read services instead of scraping logs or presentation state.

## 3. Inherited repository state

- Phase 012 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- `presentation/launcher.py`
- `presentation/cli/app.py`
- `pyproject.toml [project.scripts]`
- application facade and Control Plane/warehouse read APIs
- snapshot/restore services

## 5. Exact target state after this phase

Replace historical `shan-fin`/`shan-fin-gui` entry points with one `pfetl` product command and add small operator read services for status/doctor/info.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Define the final command surface: naked `pfetl`, `run`, `status`, `doctor`, `info`, `snapshot`, `restore`, `--version`

Define the final command surface: naked `pfetl`, `run`, `status`, `doctor`, `info`, `snapshot`, `restore`, `--version`.

### Step 2 - Make naked `pfetl` route to the current GUI entry until PySide6 replaces it; keep CLI actions presentation-neutral

Make naked `pfetl` route to the current GUI entry until PySide6 replaces it; keep CLI actions presentation-neutral.

### Step 3 - Implement small application/query services for status/info/doctor using Settings, Control Plane, warehouse and provider checks

Implement small application/query services for status/info/doctor using Settings, Control Plane, warehouse and provider checks.

### Step 4 - Make `doctor` actionable and fail per check rather than emitting raw stack traces

Make `doctor` actionable and fail per check rather than emitting raw stack traces.

### Step 5 - Remove public `shan-fin`, `shan-fin-gui`, `cli`, `tkinter`, and docs-specific command vocabulary once equivalent behavior exists

Remove public `shan-fin`, `shan-fin-gui`, `cli`, `tkinter`, and docs-specific command vocabulary once equivalent behavior exists.

### Step 6 - Add CLI tests and packaging/script metadata updates

Add CLI tests and packaging/script metadata updates.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Entry-point/product identity changes without changing finance execution.

## 9. Tests and verification

- [ ] Only `pfetl` is installed as the primary application entry point.
- [ ] `pfetl run/status/doctor/info/snapshot/restore` execute through application services.
- [ ] Doctor can identify missing config/source/store/provider conditions with actionable output.
- [ ] Info/status operate read-only and do not mutate financial state.
- [ ] Existing headless/scheduled execution remains possible.

## 10. Explicit non-goals

- Do not build PySide6 yet.
- Do not add a SQL console or financial dashboard to the CLI.

## 11. Completion checklist

- [ ] Exit assertion: Only `pfetl` is installed as the primary application entry point.
- [ ] Exit assertion: `pfetl run/status/doctor/info/snapshot/restore` execute through application services.
- [ ] Exit assertion: Doctor can identify missing config/source/store/provider conditions with actionable output.
- [ ] Exit assertion: Info/status operate read-only and do not mutate financial state.
- [ ] Exit assertion: Existing headless/scheduled execution remains possible.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 014

The next phase may assume only the verified state above. It begins **PySide6 Shell, Run Workflow and Observability Parity** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 013
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
