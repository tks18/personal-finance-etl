# Phase 11 — Household Transaction and Classification Explorer

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 10.

## Phase outcome
Provide one deep canonical household evidence surface spanning income, expense, transfer facts and their dimensions.

## Inherited state
- All high-level Household tabs are complete.

## Files in scope
- `analytics/household.py`
- `pages/household.py`
- `tests/test_semantic_queries.py`

## Grounded PFETL / Studio inputs
- Silver income/expense/transfer facts.
- Income/expense/asset/currency dimensions.
- Opening balances available for context but not mixed into transaction rows.

## Required contracts at phase exit
- `HouseholdTransactionQuery` typed filter model: transaction_kind, date range, asset, category/subcategory, currency, text search, transfer type, core/active/passive flags, amount range.
- `household_transactions(query, limit, offset)` returns normalized common columns plus kind-specific fields; include source UID and transfer UID.

## Data and query semantics
- Normalize display schema in SQL with `UNION ALL` only for common columns; preserve raw kind-specific columns in detail drawer.
- Base/local/account amounts remain distinct.
- Text search applies only to description/paid fields with bound pattern.
- Pagination is server/query-side; never load all transactions to browser.

## UI / interaction specification
- Transactions tab: filter bar, paged table, detail drawer.
- Detail drawer shows classification lineage: category/subcategory labels, asset/group, currency, income/expense flags, transfer linkage.
- Click transfer UID can show linked rows if present.

## Implementation sequence
1. Implement normalized transaction query.
2. Implement per-kind detail fetch by UID.
3. Add bounded pagination and export-current-result-to-CSV hook placeholder for Phase 25 integration.
4. Render table and detail drawer.
5. Test filtering/pagination/linkage.

## Focused verification
- Returned transaction count/order stable (`DATE`,`TIME`,`UID`).
- Filters never interpolate raw SQL identifiers/values.
- Linked transfer rows resolve in fixture.

## Edge cases and failure behaviour
- Duplicate descriptions are normal; UID is identity.
- Null currency/transfer/category fields render gracefully.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not add transaction editing/tagging/categorization.

## Exit criteria
- [ ] Household area now supports summary-to-transaction evidence drill end-to-end.

## Handoff to next phase
Phase 12 starts Wealth as a separate domain page.
