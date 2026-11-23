# Phase 29 — Prebuilt Tax, Harvesting and FIRE Reports

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 28.

## Phase outcome
Implement Investment Tax & Harvesting, Tax Position Review, and FIRE & Planning Review with explicit indicative/scenario boundaries.

## Inherited state
- Tax/FIRE pages and nine reports complete.

## Files in scope
- `reports/templates/investment_tax.py`
- `reports/templates/tax_position.py`
- `reports/templates/fire.py`
- registry/tests

## Grounded PFETL / Studio inputs
- TaxAnalytics, Investment lot/realized services, FireAnalytics and simulation provenance.

## Required contracts at phase exit
- Stable IDs: `investment_tax_harvesting`, `tax_position_review`, `fire_planning_review`.

## Data and query semantics
- Tax reports always include indicative disclaimer.
- Harvesting report separates realized events from unrealized tax-if-sold/LTCG ladder.
- FIRE report uses canonical Gold outputs and provenance; any sensitivity block is labelled scenario-only.

## UI / interaction specification
- Filters: FY, ISIN, tax type/subtype, holding type for tax; comparison only for FIRE where supported.

## Implementation sequence
1. Define ordered blocks and mandatory disclaimers.
2. Include estimate completeness/reconciliation in Tax Position.
3. Include lot maturity/harvest evidence in Investment Tax.
4. Include FI target/gap/P10/P50/P90/probability/simulation provenance in FIRE.
5. Test disclaimers and values.

## Focused verification
- All tax outputs remain labelled indicative.
- Simulation/report values equal services, not recomputed.

## Edge cases and failure behaviour
- Missing tax estimate completeness produces visible warning.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- No statutory filing or new Monte Carlo.

## Exit criteria
- [ ] Twelve total built-ins are certified.

## Exact report composition
### Investment Tax & Harvesting
- **Default period:** selected FY + latest-close lot context.
- **Blocks:** realized gains/losses by holding/tax type; estimated realized investment tax; current unrealized LTCG/STCG; tax-if-sold; LTCL/STCL; harvestable-loss candidates; LTCG maturity 30/90/180/365/mature values; prioritized lot table with days-to-LTCG and harvest recommendation.
- **Mandatory text:** indicative-estimate disclaimer on cover and tax summary section.
- **Acceptance:** realized events remain distinct from unrealized tax-if-sold; no statutory-liability claim.

### Tax Position Review
- **Default period:** selected FY.
- **Blocks:** total ledger income; investment gain/loss; tax credits; estimated ledger/investment tax; completeness counts/flags; head/sub-head breakdown; ledger-vs-quant reconciliation; exclusions; indicative unrealized exposure/harvestable savings/net exposure; canonical tax-event appendix.
- **Acceptance:** incomplete estimates are visibly incomplete and are not presented as fully determined liability.

### FIRE & Planning Review
- **Default period:** latest month; allow comparison to prior period.
- **Blocks:** current FI coverage; target/Coast/Lean FI; FI gap; projected P50 date; P10/P50/P90 months-to-FI; probability of success; runway/withdrawal rate; actual vs required savings; wealth velocity/acceleration; simulation provenance/fingerprints; selected-run FIRE/Monte Carlo assumptions snapshot.
- **Acceptance:** no Studio Monte Carlo execution; any optional sensitivity block is labelled scenario-only.

## Handoff to next phase
Phase 30 finishes operations/forensic/evidence reports.
