# Phase 28 — Prebuilt Portfolio, Performance and Multi-Currency Reports

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 27.

## Phase outcome
Implement Portfolio Review, Investment Performance & Benchmark, and Multi-Currency Exposure Review using the certified investment services.

## Inherited state
- Investment analytics and six reports complete.

## Files in scope
- `reports/templates/portfolio.py`
- `reports/templates/performance.py`
- `reports/templates/currency.py`
- registry/tests

## Grounded PFETL / Studio inputs
- Investment allocation/performance services; country/currency marts; lot links for appendix.

## Required contracts at phase exit
- Stable IDs: `portfolio_review`, `investment_performance_benchmark`, `multi_currency_exposure_review`.

## Data and query semantics
- Portfolio default latest close; Performance custom period; Currency latest close/custom.
- Return/XIRR/weights remain native metrics; templates never aggregate them.

## UI / interaction specification
- Filters: ISIN/class/type/subtype/sector/industry/country/geo/currency as supported by each service.

## Implementation sequence
1. Define Portfolio blocks: value/allocation/performance/concentration/drift/harvest context.
2. Performance blocks: XIRR/CAGR/benchmark/active return/drawdown/FX impact.
3. Currency blocks: base/local value, FX rates/appreciation, Asset_PnL vs Forex_PnL, FX XIRR impact.
4. Test numeric pass-through and filters.

## Focused verification
- Each report exports PDF/XLSX and provenance.
- No non-additive metric is summed.

## Edge cases and failure behaviour
- Missing local-currency columns for some segment marts handled by conditional blocks.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- No portfolio optimization/recommendation.

## Exit criteria
- [ ] Nine total built-ins are certified.

## Exact report composition
### Portfolio Review
- **Default period:** latest available close; allow custom historical period where Gold history exists.
- **Blocks:** invested/current value; unrealized P&L; XIRR/after-tax XIRR; benchmark/active return; class/type/subtype allocation; sector/industry; geography/country/currency; Top1/5/10, HHI, effective holdings; class target/drift/rebalance flags; harvesting-priority table.
- **Filters:** ISIN, class, type, subtype, sector, industry, geography, country, currency.
- **Acceptance:** allocation charts use the registered Gold marts and native weights; no weight recomputation from Silver.

### Investment Performance & Benchmark
- **Default period:** user-selected custom period; latest close snapshot if only one date is available.
- **Blocks:** portfolio XIRR/CAGR/absolute return; after-tax XIRR; benchmark XIRR/CAGR; active return; alpha where provided; max drawdown; Asset_PnL vs Forex_PnL; FX XIRR impact; ISIN/segment performance table; lagging/outperforming-lot indicators.
- **Acceptance:** XIRR/CAGR/benchmark/drawdown values are source pass-through and are never summed or averaged.

### Multi-Currency Exposure Review
- **Default period:** latest close; custom period supported.
- **Blocks:** foreign exposure; currency allocation; country allocation; base/local invested/current values; current/blended FX rates; currency appreciation; Asset_PnL vs Forex_PnL; FX contribution; local vs base XIRR/benchmark/active return where fields exist.
- **Acceptance:** missing local fields for a mart remove the block with a warning rather than synthesizing conversions.

## Handoff to next phase
Phase 29 adds tax/FIRE reports.
