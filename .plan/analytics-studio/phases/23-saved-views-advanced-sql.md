# Phase 23 — Saved Views and Advanced Read-only SQL

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 22.

## Phase outcome
Persist reusable guided/expert analytical views in Studio state and add a strictly read-only SQL workspace for Shan without weakening database safety.

## Inherited state
- Explorer GuidedQuery works.
- Studio state DB exists.

## Files in scope
- `analytics/explorer.py`
- `pages/explorer.py`
- `state.py`
- `tests/test_explorer.py`

## Grounded PFETL / Studio inputs
- Studio `saved_views` schema from README §8.
- Read-only DuckDB/Control Plane gateways.

## Required contracts at phase exit
- `SavedViewDefinition` supports kind=`guided|sql`, profile_id, name, description, datasource, query_spec/sql_text, default period/filter overrides.
- State CRUD: create/update/list/get/delete saved view with timestamps.
- Advanced SQL validator accepts one statement beginning with SELECT or WITH after comments/whitespace; rejects semicolon-separated multiple statements and obvious DDL/DML/PRAGMA/ATTACH/COPY/INSTALL/LOAD. Database read-only mode remains the ultimate guard.
- SQL result hard limit applied by wrapper unless smaller user limit.

## Data and query semantics
- Saved guided views persist semantic spec, not materialized results.
- Saved SQL persists SQL text locally; it is personal Studio state, never PFETL.
- Control Plane and DuckDB are separate datasource choices.

## UI / interaction specification
- Explorer gains Saved Views list and Advanced SQL tab.
- SQL editor shows datasource, row limit, execution duration, result table, save-as-view.
- Saved view can re-run under current selected PFETL run/period; SQL views do not receive automatic period rewriting unless parameters were explicitly designed.

## Implementation sequence
1. Add saved_views table/migration.
2. Implement CRUD and duplicate-name handling per profile.
3. Implement conservative SQL validation and bounded execution.
4. Render saved-view lifecycle and SQL workspace.
5. Test write/attach/copy attempts fail both validator and read-only DB.

## Focused verification
- Saved guided view replays exact fixture spec.
- SQL SELECT returns rows; CREATE/DELETE/PRAGMA/ATTACH/COPY rejected.
- No result blobs stored in Studio SQLite.

## Edge cases and failure behaviour
- CTEs beginning WITH allowed only when final statement is SELECT-compatible; read-only DB still protects.
- Long query timeout: use a simple execution time guard/cancel strategy supported by local client where practical; at minimum cap results and surface cancel/refresh UI.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not build SQL autocomplete/parser IDE.

## Exit criteria
- [ ] Shan can save/replay guided or expert views safely.

## Handoff to next phase
Phase 24 builds reports on top of registered analytics/saved views.
