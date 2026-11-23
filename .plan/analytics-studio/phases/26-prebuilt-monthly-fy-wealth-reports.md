# Phase 26 — Prebuilt Monthly, FY and Wealth Reports

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 25.

## Phase outcome
Implement and certify Monthly Financial Review, Financial Year Review, and Net Worth & Wealth Attribution as immutable built-in templates.

## Inherited state
- Report runtime/exporters exist.
- Overview/Household/Wealth/Investments/Tax/FIRE services exist.

## Files in scope
- `reports/templates/monthly.py`
- `reports/templates/financial_year.py`
- `reports/templates/wealth.py`
- `reports/registry.py`
- `tests/test_reports.py`

## Grounded PFETL / Studio inputs
- Monthly report combines Overview, household cashflow, portfolio, tax, FIRE and data-health services.
- FY report uses selected FY semantics and tax/realized/wealth summaries.
- Wealth report uses WealthAnalytics and attribution components.

## Required contracts at phase exit
- Stable built-in IDs: `monthly_financial_review`, `financial_year_review`, `net_worth_wealth_attribution`.
- Built-ins are immutable definitions but cloneable later.

## Data and query semantics
- Monthly default = latest complete month; comparison previous month optionally.
- FY default = selected/current completed-to-date FY using calendar.
- Wealth default = rolling 12M; custom period allowed.
- All blocks inherit common provenance and filters; missing optional domain data becomes warning block.

## UI / interaction specification
- Reports page Built-in list shows cards, description, default timeline, supported filters, Preview/Export.

## Implementation sequence
1. Define exact ordered blocks for each of three reports.
2. Wire to existing analytics registry only.
3. Add report-specific filter allowlists.
4. Generate fixture PDF/XLSX snapshots structurally (page/sheet/block presence, not pixel screenshots).
5. Test custom period and filter propagation.

## Focused verification
- Each report renders deterministic block IDs/order.
- Monthly includes net worth, attribution, income/expense/cashflow, portfolio, tax, FIRE, data health.
- FY includes FY household/wealth/investment/tax evidence.
- Wealth includes book/market NW, attribution, liquidity and asset breakdown.

## Edge cases and failure behaviour
- Missing domain rows produce explicit unavailable/warning sections.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not duplicate query code inside templates.

## Exit criteria
- [ ] Three built-ins are production-usable and exported with provenance.

## Exact report composition
### Monthly Financial Review
- **Default period:** latest complete month; allow selected month and optional previous-month comparison.
- **Required blocks in order:** title/provenance; data-health strip; net-worth KPI group; net-worth attribution waterfall; income/expense/net-cashflow chart; budget/cashflow health table; portfolio KPI group + allocation snapshot; indicative tax card; FIRE coverage/probability card; concise exceptions/warnings section.
- **Filters:** asset/account where supported; investment dimensions must not silently affect household blocks.
- **Acceptance:** every headline number must equal the corresponding Overview/Household/Wealth/Investment/Tax/FIRE service for the same ReportContext.

### Financial Year Review
- **Default period:** selected FY using `silver.dim_calendar`; current FY may be FYTD.
- **Required blocks:** provenance + FY context; income composition; expense/core/non-core; savings/investment rate; cashflow statement; opening/closing net worth and attribution; portfolio performance/realized gains; Tax Position summary; FIRE progress change.
- **Appendices:** bounded category tables and realized-tax summary; full transaction/event detail belongs XLSX/CSV.
- **Acceptance:** FY filters propagate consistently to all compatible services and tax/FY sections use the same selected FY.

### Net Worth & Wealth Attribution
- **Default period:** rolling 12 months; custom range supported.
- **Required blocks:** book/market NW KPI group; book-vs-market trend; assets/liabilities/liquidity; attribution waterfall; asset-subcategory contribution table; Asset_PnL vs Forex_PnL; drawdown/runway; data/provenance footer.
- **Acceptance:** `Net_Savings_Flow + Market_Return_Flow + Attribution_Residual` visually reconciles to Core's `Asset_Market_Delta`; never hide the residual.

## Handoff to next phase
Phase 27 adds three household operating reports.
