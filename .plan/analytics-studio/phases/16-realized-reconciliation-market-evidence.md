# Phase 16 — Realized Events, Reconciliation and Market Evidence

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 15.

## Phase outcome
Complete investment traceability from purchase/sale through FIFO realized events, reconciliation adjustments and market/benchmark/FX evidence.

## Inherited state
- Lot Explorer and instrument filters exist.

## Files in scope
- `analytics/investments.py`
- `pages/investments.py`
- `tests/test_investment_queries.py`

## Grounded PFETL / Studio inputs
- `silver.fact_investment_purchases`, `fact_investment_sales`, `fact_investment_realized_events`, `fact_investment_reconciliation_events`.
- `silver.fact_investment_market_data`, `fact_investment_benchmark_data`, `fact_currency_fx_rates`.
- Instrument/benchmark/currency dimensions.

## Required contracts at phase exit
- `realized_events(filters)` with Sale_ID/Lot_ID/Purchase_ID trace fields.
- `reconciliation_events(filters)` grouped by Reconciliation_Group_ID and event.
- `market_evidence(entity,date_range)` returns holdings/price, benchmark and FX observations with provider/gap/imputed provenance.
- Detail helpers may cross-link by exact IDs only.

## Data and query semantics
- Realized P&L/tax comes from `fact_investment_realized_events`, not sale helper `Total_PnL`.
- Reconciliation adjustments are shown as evidence, not applied again.
- Market/FX imputation/gap flags are displayed; Studio does not fill data.

## UI / interaction specification
- Realized & Reconciliation tab has two subviews plus trace drawer: Sale → Realized Event → Lot → Purchase.
- Reconciliation table compares broker/reconstructed quantities and cost basis with reason/adjustment.
- Market Evidence subview plots instrument price/value, benchmark close and FX rate with imputation/gap markers and provider metadata.

## Implementation sequence
1. Implement ID-linked trace queries.
2. Implement reconciliation grouped/detail query.
3. Implement market/benchmark/FX evidence queries with date filters.
4. Render lineage drawer and provenance badges.
5. Test one fixture partial FIFO sale traces to exact lot/purchase and one reconciliation event shows exact adjustment.

## Focused verification
- Disposed cost basis, proceeds, realized gain and estimated tax match fixture source event.
- Market evidence never fabricates dates/values.

## Edge cases and failure behaviour
- Missing linked lot/purchase: show broken-link diagnostic with IDs.
- Multiple realized events per sale are normal and displayed.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not “fix” reconciliation or market gaps from Studio.

## Exit criteria
- [ ] Investment area now covers summary → lot → realized → reconciliation → market evidence.

## Handoff to next phase
Phase 17 starts Tax analytics.
