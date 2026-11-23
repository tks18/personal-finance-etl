# Phase 15 — Investment Lot Explorer

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 14.

## Phase outcome
Make the full 87-column canonical lot analytics fact usable through grouped views, filtering and detail drill without flattening away audit information.

## Inherited state
- Investment overview/performance complete.

## Files in scope
- `analytics/investments.py`
- `pages/investments.py`
- `tests/test_investment_queries.py`

## Grounded PFETL / Studio inputs
- `silver.fact_investment_lot_analytics` 87 columns listed in README/source: identity, cost/value, local/base/FX, return/XIRR, benchmark, risk/weights, holding/LTCG, unrealized/realized FY tax, harvesting.
- `silver.dim_instrument_master`, `dim_currency`, `dim_benchmark_master` for labels.

## Required contracts at phase exit
- `LotFilter` supports close date, ISIN, class/type/subtype, currency, holding type, harvest flag, days-to-LTCG range, gain/loss state.
- `lot_rows(filter,limit,offset)` returns a curated summary projection plus IDs.
- `lot_detail(lot_id,closing_date)` returns all source columns grouped into sections; source field names may be retained in a raw section.

## Data and query semantics
- Lot identity is `Lot_ID` plus relevant close snapshot; do not assume one row per Lot_ID across all dates.
- No lot return/tax values are recomputed.
- Tax-if-sold, FY realized values and harvest recommendation are Core outputs and labelled accordingly.
- Pagination is query-side; default to latest closing date.

## UI / interaction specification
- Lots tab: filter bar; summary table with instrument, buy date, quantity, cost, current value, P&L, XIRR, benchmark, holding type, days to LTCG, tax-if-sold, harvest flag.
- Detail drawer sections: Identity; Cost & Market; Local/Base/FX; Performance; Benchmark/Alpha; Risk/Weight; Holding/Tax; FY Realized; Harvesting.
- Provide source-field toggle for audit users.

## Implementation sequence
1. Implement latest-date and historical lot queries.
2. Join instrument/benchmark/currency labels.
3. Define summary projection explicitly; detail fetch selects all columns.
4. Render paged table/detail sections.
5. Add deep links from ISIN performance/allocation to prefiltered Lots.
6. Test identity, pagination and exact tax/performance passthrough.

## Focused verification
- All lot columns are reachable either summary or detail.
- Filtering by `Can_Harvest_Loss`, Holding_Type and Days_To_LTCG returns expected fixture rows.

## Edge cases and failure behaviour
- Execution_Residual or status columns may be null; render as diagnostic data, not error.
- No lots at chosen historical date: show nearest available dates as suggestion, do not silently change period.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not create editable lot annotations.

## Exit criteria
- [ ] Lot Lab provides complete inspectability of canonical lot truth.

## Handoff to next phase
Phase 16 completes investment traceability with realized/reconciliation/market evidence.
