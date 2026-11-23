# Phase 05 — Semantic Periods, Filters, Metrics and Query Cache

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 04.

## Phase outcome
Create the small shared semantic layer that prevents each page/report from inventing periods, filters, metric aggregation and cache behaviour independently.

## Inherited state
- Catalog/provenance can identify tables and latest successful run.
- `silver.dim_calendar` is the authoritative date/FY model.

## Files in scope
- `src/pfetl_analytics_studio/semantic/periods.py`
- `semantic/filters.py`
- `semantic/metrics.py`
- `semantic/datasets.py`
- `data/cache.py`
- `tests/test_semantic_queries.py`

## Grounded PFETL / Studio inputs
- `silver.dim_calendar` date, month, quarter, FY columns/flags from README §9.2.
- Gold monthly tables use `MONTH_START_DATE`/`MONTH_END_DATE`; investment Gold uses `Closing_Date`; tax Gold uses `FY`.
- Current FinancialRules/Settings snapshots are context only, not period engines.

## Required contracts at phase exit
- Frozen `PeriodPreset`: latest_complete_month, selected_month, calendar_quarter, fy_quarter, calendar_ytd, fytd, selected_fy, rolling_3m, rolling_6m, rolling_12m, rolling_24m, since_inception, custom.
- `PeriodContext(start_date,end_date,label,preset,financial_year?,comparison?)` resolved by querying `dim_calendar`.
- Frozen `FilterSpec`/`FilterSet` with whitelisted fields and typed scalar/list/range values.
- `MetricSpec(id,label,dataset,expression,aggregation,format,unit,allowed_dimensions,additive,description)`.
- `DatasetSpec` names the semantic datasets exposed to Guided Explorer/reporting and their safe dimensions/date field.
- `QueryCache` key includes profile_id + latest/selected PFETL run ID + semantic query spec; never cache across run changes.

## Data and query semantics
- Do not infer financial-year dates in Python; query `dim_calendar`.
- `latest_complete_month` must use the latest month represented by Gold data and calendar boundaries, not system month blindly.
- Non-additive metrics (`XIRR`, `CAGR`, weights, ratios) default to `none`/native grain; do not average/sum unless an explicit MetricSpec says so.
- Filter values are always bound parameters; dimension names come from DatasetSpec whitelists.

## UI / interaction specification
- No full pages yet. Provide reusable display labels for period selector and filter chips.

## Implementation sequence
1. Implement period resolver queries against calendar fixture.
2. Implement filter models/normalization and stable cache serialization.
3. Register foundational datasets/metrics needed by Overview and later pages; investment/domain registries can extend in their phases.
4. Implement cache with bounded in-memory entries; key invalidates when selected PFETL run changes.
5. Write tests for FYTD vs calendar YTD, rolling windows, custom inclusivity and non-additive metric rules.

## Focused verification
- Period fixtures resolve exact date boundaries.
- Metric registry rejects duplicate IDs and invalid aggregation/dimension combinations.
- Cache returns same object/value for same run+spec and misses after run ID changes.

## Edge cases and failure behaviour
- Future dates in `dim_calendar` are excluded from latest-complete/data-as-of resolution.
- Empty requested period returns valid empty context/result, not SQL error.
- Custom start>end is validation error.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- No generic semantic DSL or cube engine.
- Do not register every numeric warehouse column; raw Explorer remains the exhaustive escape hatch.

## Exit criteria
- [ ] All pages/reports can share one period/filter model.
- [ ] Foundational MetricSpec registry protects against invalid aggregation.
- [ ] Cache cannot serve stale results across PFETL runs.

## Handoff to next phase
Phase 06 may use these shared semantics in global UI context.
