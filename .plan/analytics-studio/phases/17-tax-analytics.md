# Phase 17 — Tax Analytics

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 16.

## Phase outcome
Make PFETL tax evidence, estimate completeness, reconciliation, unrealized exposure and harvesting understandable while preserving the indicative/non-statutory boundary.

## Inherited state
- Investment lots/realized events available for drill.

## Files in scope
- `analytics/tax.py`
- `pages/tax.py`
- semantic registry extensions
- `tests/test_semantic_queries.py` or `test_investment_queries.py` as appropriate

## Grounded PFETL / Studio inputs
- Gold `tax_financial_year_summary`, `tax_income_breakdown`, `tax_reconciliation`.
- Silver `fact_tax_events`, `ref_financial_year_parameters`, income subcategory tax mappings.
- Lot analytics tax-if-sold/harvest fields and realized events for drill.

## Required contracts at phase exit
- `TaxAnalytics.fy_summary(fy)`, `income_breakdown(fy,filters)`, `reconciliation(fy,filters)`, `tax_events(fy,filters)`, `harvesting_snapshot(as_of)`.
- Every output includes `indicative=True` metadata for UI/report disclaimers.

## Data and query semantics
- Tax figures are consumed exactly as PFETL generated.
- Estimate completeness counts/booleans must be visible; incomplete estimate is not silently totalled as fully reliable.
- Unrealized tax-if-sold and harvestable savings are indicative scenario outputs, distinct from realized tax events.
- FY selection uses Silver calendar/ref data, not locale assumptions.

## UI / interaction specification
- Tax page sections: FY summary cards; income head/sub-head breakdown; reconciliation table; realized tax-event browser; unrealized exposure/harvesting/LTCG maturity links.
- Persistent disclaimer: “Indicative / estimated, not statutory tax liability.”
- Drill links from Gold lines to Silver tax/realized/lot evidence.

## Implementation sequence
1. Implement FY summary and breakdown queries.
2. Implement completeness/status presentation.
3. Implement reconciliation and event drill.
4. Reuse investment lot/realized services for harvesting link rather than duplicate queries where practical.
5. Test exact fixture tax totals, counts and incomplete-estimate behavior.

## Focused verification
- Gold FY totals equal fixture.
- Source-type/head filters reconcile to tax events.
- Indicative disclaimer metadata always set.

## Edge cases and failure behaviour
- Missing FY parameter/reference row: show context unavailable, not substitute current rules.
- Incomplete estimated tax remains visibly incomplete.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not calculate statutory liability, deductions, advance tax or filing forms.

## Exit criteria
- [ ] Tax page exposes all three Gold tax marts and canonical event drill with correct disclaimers.

## Handoff to next phase
Phase 18 builds FIRE/simulation analytics.
