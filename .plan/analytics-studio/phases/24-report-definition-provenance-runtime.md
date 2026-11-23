# Phase 24 — Report Definition, Provenance and Rendering Runtime

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 23.

## Phase outcome
Create the deterministic report domain model, registry, run context, preview runtime and history persistence before implementing exporters or templates.

## Inherited state
- All domain analytics services, Explorer and saved views exist.
- Studio state can persist JSON definitions.

## Files in scope
- `reports/models.py`
- `reports/registry.py`
- `reports/service.py`
- `pages/reports.py`
- `state.py`
- `tests/test_reports.py`

## Grounded PFETL / Studio inputs
- Report sources are registered analytics service calls and validated saved views only.
- Run provenance comes from `cp_runs` + linked Settings/Rules snapshots.
- Studio version from package; period/filter context from semantic layer.

## Required contracts at phase exit
- Frozen `ReportContext(profile_id,pfetl_run_id,core_version,schema_version,settings_snapshot_id,rules_snapshot_id,period,filters,studio_version,generated_at,currency_mode?)`.
- Frozen block discriminated union: `TitleBlock`, `SubtitleBlock`, `NarrativeBlock`, `ProvenanceBlock`, `KPIGroupBlock`, `ChartBlock`, `TableBlock`, `SavedViewBlock`, `DividerBlock`, `PageBreakBlock`.
- `ReportDefinition(id,name,description,default_period,default_filters,blocks,builtin)` contains presentation references, not data.
- `RenderedBlock` + `ReportResult(context,blocks,warnings)` are exporter-neutral in-memory outputs.
- `ReportRegistry` registers built-in block factories/template definitions by stable IDs.
- `ReportService.render(definition, context_overrides)` resolves one PFETL run context and executes blocks in order.
- Studio tables: `saved_reports` and `report_runs` exactly as README §8; this phase creates schema and writes preview/run metadata only where appropriate.

## Data and query semantics
- Every report run is pinned to one PFETL run ID and its immutable Settings/Rules snapshots.
- Block filters inherit global ReportContext then apply explicit block override; overrides cannot widen outside profile/run or mutate financial methodology.
- KPI/chart/table blocks call named analytics registry functions or saved views; no raw SQL inside built-in block definitions.
- Narrative text is static/user-authored in v1, not AI-generated.
- Warnings from missing datasets/empty blocks remain in ReportResult; rendering does not fabricate values.

## UI / interaction specification
- Reports page initially shows empty Built-in/Custom sections and a preview pane powered by one fixture/internal demonstration definition.
- Preview shows cover/title, provenance, KPI, chart/table placeholder rendering from real RenderedBlock types.

## Implementation sequence
1. Implement Pydantic discriminated block models.
2. Implement report registry with stable ID uniqueness checks.
3. Implement ReportContext resolver from selected profile/run snapshots.
4. Implement block execution dispatch to analytics/saved-view registries.
5. Implement deterministic preview result and persistence schema.
6. Render basic web preview independent of PDF/XLSX.
7. Test a fixture report containing provenance + KPI + chart + table + saved view.

## Focused verification
- Rendered fixture blocks preserve definition order.
- Historical run context uses exact snapshot IDs/payload references.
- Missing block source produces typed warning/empty block, not report crash unless block marked required.
- Definition round-trips JSON through Studio SQLite.

## Edge cases and failure behaviour
- Deleted saved view referenced by custom report: report preview marks broken block with remediation.
- Profile incompatible with required built-in source: block unavailable with compatibility warning.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- No arbitrary formula language.
- No PDF/XLSX logic in report service.
- No browser screenshots.

## Exit criteria
- [ ] Report definitions/runtime are deterministic and exporter-neutral.
- [ ] Provenance is mandatory and reproducible.
- [ ] Saved report schema exists for custom phases.

## Handoff to next phase
Phase 25 adds artifact exporters without changing report semantics.
