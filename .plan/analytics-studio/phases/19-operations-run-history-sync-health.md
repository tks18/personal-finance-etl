# Phase 19 — Operations Run History and Sync Health

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 18.

## Phase outcome
Build the first operations intelligence surface around run lifecycle, commit state, sync outcomes, warehouse freshness and row-count history.

## Inherited state
- All finance domain pages are functional.
- Control Plane reader/catalog/provenance already exist.

## Files in scope
- `analytics/operations.py`
- `pages/operations.py`
- `tests/test_operations_forensics.py`

## Grounded PFETL / Studio inputs
- `cp_runs`, `cp_run_sync_summaries`.
- `meta.m_Table_Row_Counts`, `meta.m_Data_Contracts`.
- Latest run provenance loader from Phase 04.

## Required contracts at phase exit
- `OperationsAnalytics.run_history(limit,date/status filters)` computes duration only from timestamps, not from logs.
- `sync_history(run filters)` joins one-to-one on run_id.
- `warehouse_health()` exposes classified contract counts and latest row counts.

## Data and query semantics
- Run duration = finished-started only when both exist.
- Commit state/status are independent fields and both displayed.
- Sync actionable/synced/healed/failed/deferred counts are source truth.
- Row counts are diagnostic; do not infer financial correctness from count alone.

## UI / interaction specification
- Operations page tabs: Runs, Sources & Artifacts, Providers & Failures, Forensics & Evidence. This phase implements Runs.
- Run table: ID, started/finished/duration, status, commit state, Core/schema version, snapshots, log availability.
- Charts: duration trend, success/failure, sync outcomes.
- Warehouse cards: Bronze/Silver/Gold/Meta classified counts and selected row-count health.

## Implementation sequence
1. Implement run/sync query joins.
2. Add status/commit/date filters.
3. Implement latest row-count/contract summary.
4. Render run detail drawer linking snapshots and future forensic route.
5. Test duration and sync fields exactly.

## Focused verification
- Run lifecycle/status/sync fixture values are returned exactly; durations use timestamp difference only.
- Warehouse row-count/contract summary includes every classified layer.

## Edge cases and failure behaviour
- Run with unfinished timestamp has null duration and “in progress/stale” display, not negative/zero.
- Missing sync summary allowed.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not implement alerting/notifications.

## Exit criteria
- [ ] Runs tab explains lifecycle, sync and warehouse freshness for historical runs.

## Handoff to next phase
Phase 20 fills Sources/Artifacts and Providers/Failures/Snapshots.
