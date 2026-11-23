# Phase 03 — Read-only DuckDB and Control Plane Gateways

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 02.

## Phase outcome
Create the only modules allowed to open PFETL databases and enforce strict read-only/concurrency safety with bounded query primitives.

## Inherited state
- `PFETLProfile` resolves DuckDB, Control Plane and `pipeline.lock`.
- No analytics/page code exists yet, so the data package can define the database boundary cleanly.

## Files in scope
- `src/pfetl_analytics_studio/data/duckdb_reader.py`
- `src/pfetl_analytics_studio/data/control_plane_reader.py`
- optional `src/pfetl_analytics_studio/data/errors.py` if shared typed exceptions materially reduce duplication
- `tests/test_profile_connections.py`

## Grounded PFETL / Studio inputs
- PFETL DuckDB contains `bronze`, `silver`, `gold`, `meta`.
- Control Plane SQLite contains the ten `cp_*` tables listed in README §9.5.
- `pipeline.lock` sits beside the resolved DuckDB in `target_db_base_path`.

## Required contracts at phase exit
- `DuckDBReader(profile)` and `ControlPlaneReader(profile)` are immutable/lightweight handles, not live connection singletons.
- Public reader primitives: `fetch_df(sql, params=()) -> pl.DataFrame`, `fetch_one(...)`, `fetch_scalar(...)`, `table_exists(schema, table)`, `bounded_preview(schema, table, limit<=500)`.
- `PFETLLockedError`, `PFETLDataAccessError` (or equivalent typed exceptions) carry path/profile context but never credentials/private row contents.
- Connections are context-managed and closed inside each operation; no connection escapes to pages/services.

## Data and query semantics
- DuckDB connection must use `duckdb.connect(path, read_only=True)`.
- Before each DuckDB open, test `lock_path.exists()`; while locked, refuse warehouse access rather than copying/attaching the DB.
- SQLite connection URI uses `file:<path>?mode=ro` with `uri=True`; optionally set `PRAGMA query_only=ON` defensively.
- SQL values use parameter binding. Dynamic schema/table identifiers are accepted only through a validated identifier/catalog path; preview must quote identifiers safely.
- Large result helpers return Polars at the boundary; do not introduce pandas.

## UI / interaction specification
- No standalone page work. Surface three typed connectivity states to the shell: warehouse available, warehouse locked, warehouse unavailable; Control Plane availability is independent.
- A lock warning explains that PFETL is currently writing and Studio will not read DuckDB.

## Implementation sequence
1. Implement typed errors/states.
2. Implement DuckDB context-managed connection helper and read-only query primitives.
3. Implement SQLite read-only helper with row-to-dict/Polars conversion.
4. Add table-existence and bounded-preview helpers used by catalog later.
5. Add query-level path/profile context to raised Studio errors without leaking full SQL into end-user messages.
6. Test actual write attempts (`CREATE TABLE`, `DELETE`) fail on both fixture DBs.

## Focused verification
- Fixture SELECT/scalar/Polars queries return exact values.
- DuckDB lock fixture raises `PFETLLockedError` before connection.
- SQLite/DuckDB write attempts fail.
- Repeated calls close connections and permit temp DB cleanup on Windows.

## Edge cases and failure behaviour
- DuckDB file missing: warehouse-unavailable, not app crash.
- Control Plane missing while DuckDB exists: independent partial-availability state.
- Lock disappears between check/open: catch connection failure and surface retryable state; do not spin.
- Corrupt DB: typed access error with path and underlying exception available for diagnostics.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- No global persistent database connection.
- No SQL parser/query builder framework yet.

## Exit criteria
- [ ] All PFETL DB access is centralized under `data/`.
- [ ] Read-only and lock behaviour are mechanically tested.
- [ ] No caller can obtain a writable/live connection.
- [ ] Partial availability is representable without killing the app.

## Handoff to next phase
Phase 04 may build catalog/provenance/log readers entirely on these gateways.
