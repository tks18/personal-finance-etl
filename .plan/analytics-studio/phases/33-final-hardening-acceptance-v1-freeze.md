# Phase 33 — Final Hardening, Acceptance, README and 1.0.0 Freeze

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 32.

## Phase outcome
Prove the complete product against the finished PFETL Core profile, fix only demonstrated defects/polish gaps, simplify the root README, and freeze Analytics Studio 1.0.0.

## Inherited state
- All product capabilities are implemented and individually tested.
- No unfinished phase-owned feature remains.

## Files in scope
- Only files required for defects/polish discovered by acceptance.
- Root `README.md` for the **product repository** (not this planning README) is finalized.
- `pyproject.toml`/version metadata updated to 1.0.0 after gates pass.
- `tests/` may be adjusted only for final regression coverage.

## Grounded PFETL / Studio inputs
- Shan’s real completed PFETL Core Settings/FinancialRules profile.
- Real DuckDB, Control Plane and archived logs are used locally for smoke/acceptance but no private data is copied into repository fixtures.
- All 82 surface classifications and 15 built-in report registrations.

## Required contracts at phase exit
- No new public architecture is introduced.
- Acceptance defects are fixed in their owning modules.
- Version becomes `1.0.0` only after all gates pass.

## Data and query semantics
- No new data semantics are introduced; acceptance uses the already-certified domain/report contracts.
- Version becomes `1.0.0` only after all automated and real-profile checks pass.

## UI / interaction specification
- Validate all nine pages, key filters/periods, representative drill paths, Explorer, saved views, SQL, all built-ins and one custom report.
- Check empty/locked/incompatible states and common browser viewport.
- Polish only demonstrated usability defects; do not redesign navigation/theme at freeze time.

## Implementation sequence
1. Run automated suite and static gates.
2. Open real profile; verify profile drift/provenance and latest/historical run selection.
3. Smoke each page with latest month, selected FY and at least one custom period where relevant.
4. Verify lot→realized→reconciliation and run→forensic→source evidence drill paths.
5. Generate all 15 built-in reports in their default period; spot-check meaningful custom periods/filters.
6. Clone one built-in, customize, save, rerun against a different PFETL run, export PDF/XLSX.
7. Export representative CSV and PNG/SVG.
8. Hash PFETL DuckDB, Control Plane, Settings and Rules before/after Studio acceptance; prove Studio did not mutate them (allow PFETL itself to be stopped during test).
9. Check performance on real profile; fix only obvious query/index/cache/render bottlenecks within current architecture.
10. Remove dead dependencies/code, finalize concise user README, set version 1.0.0 and rerun gates.

## Focused verification
- `pytest`, Ruff, mypy green.
- All 82 upstream surfaces classified.
- All 15 built-ins registered/renderable.
- One custom report lifecycle works.
- PFETL files/TOMLs byte/hash unchanged after Studio-only acceptance.
- No page performs direct DB access/SQL.

## Edge cases and failure behaviour
- PFETL pipeline lock active: Studio blocks warehouse access and does not corrupt data.
- Old run with missing snapshots/logs: graceful incomplete provenance.
- No Chrome/Kaleido: actionable export prerequisite while app remains usable.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- No new features, AI layer, cloud sync, authentication, API, plugins or methodology changes in this phase.

## Exit criteria
- [ ] Real-profile acceptance complete.
- [ ] Read-only mutation proof complete.
- [ ] Product README accurately documents install/run/profile/report workflow.
- [ ] Version is 1.0.0 and repository is clean.

## Handoff to next phase
Program complete. Future work starts only from demonstrated user need, not speculative architecture.
