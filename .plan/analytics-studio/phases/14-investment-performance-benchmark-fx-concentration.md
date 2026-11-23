# Phase 14 — Investment Performance, Benchmark, FX and Concentration

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 13.

## Phase outcome
Expose PFETL return, benchmark, FX, risk and concentration outputs at portfolio, ISIN and supported segment grains without recomputing any financial metric.

## Inherited state
- Allocation mart registry and Investments page exist.

## Files in scope
- `analytics/investments.py`
- `pages/investments.py`
- semantic metric registry
- `tests/test_investment_queries.py`

## Grounded PFETL / Studio inputs
- `gold.investment_by_portfolio`: invested/current value, unrealized P&L, Asset_PnL, Forex_PnL, Forex_Contribution_Pct, Absolute_Return, XIRR, After_Tax_XIRR, BM_XIRR, Active_Return, Max_Drawdown, Top1/5/10, HHI, Effective_Holdings_Count, LTCG ladder.
- `gold.investment_by_isin`: CAGR, XIRR/XIRR_Local, FX_XIRR_Impact, benchmark CAGR/XIRR, active return, lagging flag, outperforming-lot ratio, drawdown, tax fields.
- Segment marts carry XIRR/after-tax/benchmark/active return/drawdown/weight/P&L.
- Country/currency marts additionally carry local values, FX rate, blended buy rate, currency appreciation, local XIRR/benchmark/active return and FX XIRR impact.
- `gold.investment_portfolio_summary` carries ISIN-level monthly market value change, class/sector weights/drift and harvest priority.

## Required contracts at phase exit
- Register performance MetricSpecs with aggregation=`none`/native: CAGR, XIRR, After_Tax_XIRR, BM_XIRR, Active_Return, Max_Drawdown, Forex_Contribution_Pct, HHI, concentration weights.
- Additive/value metrics: invested/current value, Asset_PnL, Forex_PnL, unrealized gain/loss at compatible Gold native grains.
- `InvestmentAnalytics.performance(dimension,period,filters)` returns latest/native metrics plus history only when the underlying Gold table has multiple `Closing_Date` rows.

## Data and query semantics
- Never calculate XIRR/CAGR/benchmark/alpha/drawdown/FX attribution in Studio.
- Do not average or sum return metrics across segments. Comparison charts compare native rows.
- Portfolio-vs-benchmark uses PFETL `XIRR` and `BM_XIRR`/Active_Return directly.
- FX decomposition displays Asset_PnL + Forex_PnL and contribution as separate Core outputs; do not derive a new residual unless explicitly present.
- Concentration cards come from `investment_by_portfolio`, not from Studio recomputation.

## UI / interaction specification
- Performance tab: portfolio KPI strip (absolute return, XIRR, after-tax XIRR, benchmark XIRR, active return, drawdown).
- Charts: portfolio vs benchmark history where dates exist; Asset P&L vs Forex P&L; segment performance table; country/currency FX view; concentration cards Top1/5/10, HHI, effective holdings.
- Dimension selector uses same safe mart registry as Phase 13.
- Tooltips include source Gold mart and as-of close date.

## Implementation sequence
1. Register metric semantics explicitly.
2. Implement performance query returning only source metrics.
3. Add country/currency FX panels conditional on fields being present.
4. Add concentration query from portfolio mart.
5. Render charts/tables and drill to ISIN/lot route.
6. Test every non-additive metric is rejected for `sum` in Guided semantics and values equal fixture source rows exactly.

## Focused verification
- Fixture XIRR, BM_XIRR, active return, drawdown and HHI pass through exactly.
- Attempt to guided-sum XIRR/weight raises validation error.
- Country/currency local/base and FX fields map correctly.

## Edge cases and failure behaviour
- Missing benchmark values: show unavailable, never zero benchmark.
- Single-date datasets: show snapshot table rather than fabricated trend.
- Negative/NaN return values display according to source; sanitize only infinities/invalid serialization for UI.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- No rebalancing recommendation/trade sizing.
- No new risk model or attribution formula.

## Exit criteria
- [ ] Shan can evaluate return, benchmark, FX and concentration at portfolio and segment level with source-faithful numbers.

## Handoff to next phase
Phase 15 can drill into canonical lot analytics.
