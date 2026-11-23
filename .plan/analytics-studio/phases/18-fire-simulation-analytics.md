# Phase 18 — FIRE and Simulation Analytics

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 17.

## Phase outcome
Expose all canonical FIRE/Monte Carlo planning outputs and reproducibility metadata without reproducing the simulation engine.

## Inherited state
- Tax and core finance pages exist.

## Files in scope
- `analytics/fire.py`
- `pages/fire.py`
- semantic registry extensions
- `tests/test_semantic_queries.py`

## Grounded PFETL / Studio inputs
- `gold.wealth_fire_analytics` 35 cols: FI targets/gap/trends, P10/P50/P90, probability, runway, withdrawal rate, savings rates, velocity/acceleration.
- `meta.m_Latest_Simulation` and `cp_simulation_runs`: seed, iterations, horizon, input date, implementation version, fingerprints, snapshots, status.
- Selected-run FinancialRules snapshot supplies context for SWR/Monte Carlo assumptions, never execution.

## Required contracts at phase exit
- `FireAnalytics.summary(period)` returns latest canonical planning row plus history.
- `simulation_history()` returns Control Plane runs and latest Meta record.
- Optional `SensitivityScenario` is presentation-only arithmetic over selected canonical outputs and is always labelled non-canonical; it must not run Monte Carlo.

## Data and query semantics
- Use Gold values directly for FI date/gap/probability/P10/P50/P90.
- Simulation provenance links to exact settings/rules snapshot IDs and fingerprints.
- Scenario controls, if implemented here, are limited to documented arithmetic sensitivity and never saved as PFETL truth.

## UI / interaction specification
- FIRE page sections: target/current coverage; FI gap/date; probability and P10/P50/P90; runway/withdrawal; actual vs required savings; simulation history/provenance.
- Historical simulation selection shows seed/iterations/horizon/fingerprints and linked assumption snapshot.
- Scenario panel is visually separated and labelled “Scenario only — not PFETL canonical output”.

## Implementation sequence
1. Implement Gold planning query and simulation history joins.
2. Render trajectory/probability cards and provenance table.
3. Add rule-snapshot viewer for FIRE/Monte Carlo context.
4. Test fixture values pass through and simulation IDs/fingerprints join correctly.

## Focused verification
- Selected latest simulation matches Meta and corresponding CP record.
- No simulation math executes in Studio tests.

## Edge cases and failure behaviour
- No simulation history: show canonical FIRE Gold if available plus missing-provenance warning.
- Failed simulation rows remain visible with status.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not duplicate stochastic model or financial planning engine.

## Exit criteria
- [ ] FIRE page provides planning outputs plus reproducibility evidence.

## Handoff to next phase
Phase 19 begins Operations/Control Plane analytics.
