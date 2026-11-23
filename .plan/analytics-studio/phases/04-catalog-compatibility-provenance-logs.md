# Phase 04 — Catalog, Compatibility, Provenance and Archived-log Spine

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 03.

## Phase outcome
Discover the complete PFETL upstream surface at runtime, validate compatibility, reconstruct run/config/rules provenance, and decode archived forensic JSONL before domain analytics begin.

## Inherited state
- Read-only readers work independently.
- The README enumerates 20 Bronze, 24 Silver, 22 Gold, 6 Meta and 10 Control Plane surfaces.

## Files in scope
- `src/pfetl_analytics_studio/data/catalog.py`
- `src/pfetl_analytics_studio/data/log_reader.py`
- `tests/test_catalog_compatibility.py`
- small model additions in `profile.py` only if provenance types fit there

## Grounded PFETL / Studio inputs
- DuckDB `information_schema.tables/columns`.
- `meta.m_Data_Contracts(contract_id, layer, physical_table, domain, grain, producer, is_full_replace, publication_order)`.
- `meta.m_Table_Row_Counts`.
- `cp_runs(run_id,...,application_version,schema_version,settings_snapshot_id,rules_snapshot_id,execution_log)`.
- `cp_settings_snapshots` and `cp_rules_snapshots` canonical payloads.
- Filesystem logs path is fallback only; archived `cp_runs.execution_log` is preferred for historical run evidence.

## Required contracts at phase exit
- `CatalogEntry` captures schema/table/layer/domain/grain/producer/columns/row_count/classification.
- `PFETLCatalog.discover()` returns every Bronze/Silver/Gold/Meta table plus every Control Plane table and a compatibility report.
- `RunProvenance` contains run ID, timestamps, status, commit state, Core/schema versions, snapshot IDs and parsed snapshot payloads.
- `ArchivedLogReader.read_run(run_id)` returns parsed JSON event dicts plus malformed-line diagnostics; it must transparently decompress the zlib payload used by Core.
- `CompatibilityReport` distinguishes supported, missing-required-surface, unexpected-new-surface and missing-required-column.

## Data and query semantics
- Runtime catalog is authoritative for what physically exists; README's 82-surface atlas is the required classification baseline.
- New columns are tolerated and shown in raw catalog. New datasets/tables require explicit Studio classification before compatibility is green.
- Historical run context uses linked snapshots, never the current selected TOMLs.
- Do not deserialize PFETL Python event classes; parse archived JSON as data contracts to keep repos independent.

## UI / interaction specification
- Profile shell gains a compatibility summary: Core version/schema, latest successful run, surface counts, snapshot/log availability.
- No finance dashboard yet.

## Implementation sequence
1. Query information_schema and `meta.m_Data_Contracts` to construct DuckDB catalog.
2. Enumerate SQLite schema for Control Plane and classify the exact ten expected `cp_*` tables.
3. Implement required-surface classification map covering all 82 surfaces.
4. Implement latest-successful-run and arbitrary-run provenance loading with snapshot JSON parsing.
5. Inspect Core archival implementation and decode `execution_log` zlib bytes/string exactly; fall back to filesystem JSONL only when archived log is absent.
6. Add a coverage test that fails for an unclassified table.

## Focused verification
- Fixture catalog discovers expected schemas/columns/grains.
- Coverage fixture fails when an extra unclassified Gold or `cp_*` table is added.
- Historical run returns exact Settings/Rules snapshot payloads.
- Archived compressed log decodes multiple JSONL events in order.

## Edge cases and failure behaviour
- No successful run: provenance returns `None`/empty state, not fake “latest”.
- Snapshot row missing: mark provenance incomplete.
- Malformed snapshot JSON or malformed JSONL line: retain run usability and expose diagnostic count.
- Unknown future columns: keep in raw catalog without failing compatibility.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not build domain query services yet.
- Do not hardcode private data values from Shan’s production DB into tests.

## Exit criteria
- [ ] All 82 upstream surfaces have an explicit classification.
- [ ] Latest and historical run provenance is queryable.
- [ ] Archived JSONL is decodable without importing Core.
- [ ] Compatibility state can block analytical pages while leaving profile/operations diagnostics available.

## Handoff to next phase
Phase 05 may assume a complete runtime catalog and run provenance spine.
