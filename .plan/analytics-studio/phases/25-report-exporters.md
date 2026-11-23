# Phase 25 — PDF, XLSX, CSV and Chart Exporters

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 24.

## Phase outcome
Render report results and individual analytical tables/charts into polished local files while preserving provenance and keeping export code separate from analytics.

## Inherited state
- ReportResult/blocks exist and web preview works.

## Files in scope
- `reports/exporters.py` or small `reports/export/` package only if needed
- `pages/reports.py`
- `ui/charts.py` if shared static-image helper
- `tests/test_reports.py`

## Grounded PFETL / Studio inputs
- Plotly figures from chart blocks.
- Kaleido static export; runtime Chrome/Chromium prerequisite.
- ReportLab PDF; XlsxWriter XLSX; Polars CSV.
- ReportContext provenance fields.

## Required contracts at phase exit
- `ReportExporter` facade with `export_pdf`, `export_xlsx`; individual result helpers `export_csv`, `export_chart_png/svg`.
- All exporters accept `ReportResult`/RenderedBlock, never rerun finance queries.
- `ExportResult(path,format,bytes_written,warnings)`.

## Data and query semantics
- PDF uses ReportLab composition with chart images generated via Kaleido; no screenshot of NiceGUI DOM.
- XLSX contains Summary/Provenance plus report table sheets and embedded charts; sanitize sheet names.
- CSV exports one selected visible result table only.
- All generated report artifacts include run ID/as-of/provenance; tax reports include indicative disclaimer.

## UI / interaction specification
- Reports page adds output directory selector (remembered in Studio preferences), export buttons and clear dependency/prerequisite errors.
- Existing domain tables/charts can later call individual exporters through shared helpers.

## Implementation sequence
1. Implement chart image export and Chrome prerequisite check.
2. Implement PDF page/section renderer for all current block types.
3. Implement XLSX renderer with provenance sheet.
4. Implement CSV/table and PNG/SVG chart export.
5. Record successful report export in `report_runs`.
6. Test generated files open/contain expected provenance strings/sheets and have nonzero chart assets.

## Focused verification
- PDF/XLSX generated from fixture ReportResult without database access.
- CSV values exactly match Polars frame.
- Export never mutates PFETL or report definition.

## Edge cases and failure behaviour
- Missing Chrome/Kaleido: PDF with chart blocks fails with actionable prerequisite; table-only CSV/XLSX remain usable where possible.
- Invalid filename/path: sanitize name and surface filesystem error.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not implement email/cloud upload/share.

## Exit criteria
- [ ] Common exporters support the complete report block runtime.

## Handoff to next phase
Phases 26–30 can focus only on defining/certifying built-in report templates.
