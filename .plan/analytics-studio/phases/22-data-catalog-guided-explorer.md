# Phase 22 — Data Catalog and Guided Explorer

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 21.

## Phase outcome
Provide exhaustive safe access to every PFETL warehouse/control-plane surface plus guided analytical querying over registered datasets/metrics.

## Inherited state
- Catalog covers all 82 surfaces.
- Metric/Dataset specs exist for built domain analytics.

## Files in scope
- `analytics/explorer.py`
- `pages/explorer.py`
- `tests/test_explorer.py`

## Grounded PFETL / Studio inputs
- All Bronze/Silver/Gold/Meta catalog entries and all Control Plane table entries.
- `meta.m_Data_Contracts` grain/producer metadata.
- Semantic DatasetSpec/MetricSpec registry.

## Required contracts at phase exit
- `catalog_entries(layer/domain search)` and `preview(dataset,limit)` use reader bounded-preview.
- `GuidedQuery(dataset,dimensions,metrics,filters,period,sort,limit)` validated entirely against DatasetSpec/MetricSpec.
- `execute_guided(query)` compiles only whitelisted identifiers/expressions and bound values.

## Data and query semantics
- Raw Data Catalog may preview any classified table, including Bronze, but never uses Bronze for derived headline KPIs.
- Guided Explorer exposes only registered safe dimensions/metrics.
- Non-additive metrics cannot be combined with incompatible dimensions/aggregations.
- Default result limit 500; hard maximum 10,000 for interactive queries.

## UI / interaction specification
- Explorer modes: Data Catalog and Guided Analytics (Advanced SQL comes Phase 23).
- Catalog: layer/domain/table search, grain/producer, columns/types, row count, bounded preview.
- Guided: dataset → dimensions → metrics → filters → sort → table/chart preview.
- Show generated semantic query description, not raw SQL by default.

## Implementation sequence
1. Implement catalog browser service.
2. Implement GuidedQuery validator/compiler.
3. Add chart recommendation mapping (time series, bar, stacked, table) without auto-analytics magic.
4. Render page.
5. Add coverage assertion that every catalog table has a classification and every guided metric has source dataset.

## Focused verification
- Guided fixture sums additive values correctly.
- Invalid XIRR sum/dimension rejected.
- Bronze preview bounded and read-only.

## Edge cases and failure behaviour
- New unknown table: compatibility/coverage warning; raw preview may be disabled until classified.
- Empty result: preserve query spec for editing.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not build drag-and-drop BI semantic modeling.

## Exit criteria
- [ ] Every upstream table is browseable/classified and guided analytics are mathematically safe.

## Handoff to next phase
Phase 23 adds persistence and expert SQL escape hatch.
