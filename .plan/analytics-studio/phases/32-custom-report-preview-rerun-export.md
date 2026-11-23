# Phase 32 — Custom Report Preview, Rerun and Export Integration

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 31.

## Phase outcome
Run saved custom definitions through the exact same deterministic preview/provenance/export pipeline as built-ins and support rerunning against newer PFETL runs.

## Inherited state
- Custom definitions persist and validate.
- Common report runtime/exporters are stable.

## Files in scope
- `pages/reports.py`
- `reports/service.py`
- `tests/test_reports.py`

## Grounded PFETL / Studio inputs
- Saved custom definitions, current/historical RunProvenance, report exporters.

## Required contracts at phase exit
- `ReportService.render` is the only execution path for built-in and custom definitions.
- Rerun chooses a new PFETL run/context while keeping definition unchanged unless user saves edits.
- `report_runs` records report ID, PFETL run ID, period JSON, format, output path, generated_at.

## Data and query semantics
- Custom rerun must resolve historical/current snapshots exactly like built-ins.
- Block-level missing data produces warnings, not silent substitutions.

## UI / interaction specification
- Custom list shows last run/export history.
- Preview supports current selected run or chosen historical run.
- Buttons: Preview, Export PDF, Export XLSX, Duplicate, Edit; rerun against latest successful run.
- Show provenance changes between prior and rerun.

## Implementation sequence
1. Wire custom definitions into common runtime.
2. Implement rerun context selection/history.
3. Integrate exporters and history record.
4. Test one cloned built-in customized with saved-view/table/narrative, save, preview, export, rerun on second fixture run.

## Focused verification
- Custom and built-in ReportResult structures identical.
- Rerun changes provenance/run values and source data as expected while definition ID/content stays stable.

## Edge cases and failure behaviour
- Upstream schema incompatible on later run: render compatibility error; do not auto-edit definition.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not version-control generated reports or persist result blobs.

## Exit criteria
- [ ] Custom report lifecycle is complete end-to-end.

## Handoff to next phase
Phase 33 is final real-profile hardening and v1 freeze only, not feature development.
