# Phase 013 - Single pfetl Command and Operator Read Services

**Target release:** v11.2.0  
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

- [x] Only `pfetl` is installed as the primary application entry point.
- [x] `pfetl run/status/doctor/info/snapshot/restore` execute through application services.
- [x] Doctor can identify missing config/source/store/provider conditions with actionable output.
- [x] Info/status operate read-only and do not mutate financial state.
- [x] Existing headless/scheduled execution remains possible.

## 10. Explicit non-goals

- Do not build PySide6 yet.
- Do not add a SQL console or financial dashboard to the CLI.

## 11. Completion checklist

- [x] Exit assertion: Only `pfetl` is installed as the primary application entry point.
- [x] Exit assertion: `pfetl run/status/doctor/info/snapshot/restore` execute through application services.
- [x] Exit assertion: Doctor can identify missing config/source/store/provider conditions with actionable output.
- [x] Exit assertion: Info/status operate read-only and do not mutate financial state.
- [x] Exit assertion: Existing headless/scheduled execution remains possible.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 014

The next phase may assume only the verified state above. It begins **PySide6 Shell, Run Workflow and Observability Parity** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 013
Target release: v11.2.0
Files changed: pyproject.toml, uv.lock, src/personal_finance_etl/__init__.py, src/personal_finance_etl/application/operator.py, src/personal_finance_etl/application/facade.py, src/personal_finance_etl/presentation/launcher.py, src/personal_finance_etl/presentation/cli/app.py, scripts/run_pipeline.bat, tests/test_phase13_single_command_and_operator_services.py, tests/test_phase10_presentation.py, tests/test_phase12_constitutional_certification.py, docs/getting-started/cli-and-desktop.md, docs/getting-started/installation.md, docs/getting-started/quick-start.md, docs/getting-started/README.md, README.md, g:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\ETL App\run_pipeline_prod.ps1, g:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\ETL App\run_pipeline_test.ps1
Contracts/schema changed: None (financial schema and contracts strictly preserved)
Financial formulas changed: None (financial formulas untouched)
Protected identity comparison: Preserved exact canonical domain grain and identity contracts
Focused tests: tests/test_phase13_single_command_and_operator_services.py (7 passed), tests/test_phase10_presentation.py (7 passed), tests/test_phase12_constitutional_certification.py (5 passed); 142 total cutover phase tests passed
Architecture tests: uv run poe audit-fast (Ruff check, Ruff format, Mypy 100% clean); zero inline imports verified
Real-data verification: Verified pfetl status, pfetl doctor, and pfetl info against local repository state and stores
Power BI verification: N/A (presentation and CLI entry point refactor)
Observability/recovery verification: Read-only operator services (status, doctor, info) acquire no file locks or DuckDB write locks; FileLock.is_locked inspection only; actionable diagnostics per check without raw stack traces
Compatibility/transitional state remaining: Naked pfetl routes to DesktopApp (Tkinter GUI) until PySide6 cutover in Phase 014
Semantic commit groups: feat(cli), feat(diagnostics), test(cli), docs(cli), docs(v11)
Exit assertions green: yes
```
