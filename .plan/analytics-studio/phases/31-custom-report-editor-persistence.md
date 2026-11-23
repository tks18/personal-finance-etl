# Phase 31 — Custom Report Editor and Persistence

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 30.

## Phase outcome
Let Shan compose, clone, reorder and save personal report definitions from existing registered analytical blocks/saved views without a scripting language.

## Inherited state
- 15 immutable built-ins, report models/runtime and Studio saved_reports schema exist.

## Files in scope
- `pages/reports.py`
- `reports/service.py`/`registry.py` only where editor APIs are needed
- `state.py`
- `tests/test_reports.py`

## Grounded PFETL / Studio inputs
- Report block model from Phase 24.
- Registered analytics block factories and SavedView definitions.
- Studio `saved_reports` table.

## Required contracts at phase exit
- Editor state uses `ReportDefinitionDraft` (or mutable UI model) converted/validated to immutable `ReportDefinition` on save.
- Custom report CRUD is profile-scoped.
- Clone built-in creates new custom definition with copied block refs/defaults, never modifies built-in registry.
- Broken saved-view/block references remain visible and block save only when required/invalid.

## Data and query semantics
- No raw formula/SQL blocks. Advanced SQL can enter a custom report only through an already saved validated SQL view and only as a table block.
- Global period/filters plus optional block-specific overrides use the same semantic models.

## UI / interaction specification
- Reports page Custom tab: New, Clone Built-in, Rename, Duplicate, Delete.
- Editor: report metadata; global period/filter defaults; ordered block list; Add Block chooser grouped by KPI/Chart/Table/Saved View/Narrative/Provenance/Divider/Page Break; move up/down (drag optional, not required); per-block filter override; validation summary.
- Auto-save is not required; explicit Save protects definitions.

## Implementation sequence
1. Implement editor DTO/state.
2. Expose registry catalog of available block factories/saved views.
3. Implement CRUD/clone with JSON persistence.
4. Render editor and validation.
5. Test round-trip, clone immutability, reorder and broken-ref validation.

## Focused verification
- Saved definition round-trips byte-equivalent semantics.
- Built-in registry unchanged after clone/edit.
- Delete removes definition but not historical `report_runs`.

## Edge cases and failure behaviour
- Referenced saved view deleted later: editor shows broken reference and remediation.
- Same name allowed only according to explicit profile-scoped uniqueness rule; choose one and test it.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- No arbitrary Python/Jinja/SQL formula scripting.

## Exit criteria
- [ ] Shan can create and persist a valid custom report without editing code.

## Handoff to next phase
Phase 32 executes custom reports through the common runtime/exporters.
