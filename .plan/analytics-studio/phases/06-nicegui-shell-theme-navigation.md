# Phase 06 — NiceGUI Shell, Theme, Navigation and Global Context

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 05.

## Phase outcome
Build the complete polished application frame, shared theme/components and global profile/run/period context before implementing domain pages.

## Inherited state
- Profile, compatibility, semantics and cache exist.
- No domain page has business UI yet.

## Files in scope
- `src/pfetl_analytics_studio/app.py`
- `ui/theme.py`
- `ui/cards.py`
- `ui/tables.py`
- `ui/filters.py`
- page modules with placeholder bodies only
- `tests/test_smoke.py`

## Grounded PFETL / Studio inputs
- PFETL Core palette from README §19.
- Global context needs profile ID, latest/selected run, PeriodContext and compatibility/lock state.

## Required contracts at phase exit
- `AppContext`/session state object contains selected profile, selected PFETL run/as-of mode, PeriodContext, FilterSet and refresh token.
- Reusable components: KPI card, status badge, empty/error/locked panel, bounded data table, period selector, filter chips.
- Navigation pages fixed to Overview, Household, Wealth, Investments, Tax, FIRE, Operations, Explorer, Reports.

## Data and query semantics
- UI state is presentation state only; analytics services remain stateless/query-driven.
- Changing profile clears run/period/filter state and cache namespace.
- Changing selected run updates provenance context but does not mutate Core.

## UI / interaction specification
- Left navigation/sidebar, top profile/run/period bar, main content region.
- Dark theme uses exact Core status colors; chart palette may extend but success/warning/error meanings stay consistent.
- Locked warehouse shows a persistent non-modal banner; Operations/profile context remains accessible.
- Every page placeholder renders a descriptive empty state rather than “TODO”.

## Implementation sequence
1. Implement theme tokens and global stylesheet/Quasar props.
2. Implement session AppContext and profile/run/period selectors.
3. Register all nine routes/pages and common shell.
4. Implement common loading/error/empty/locked components.
5. Wire cache refresh when profile/run changes.
6. Add smoke tests constructing every page with a fake context.

## Focused verification
- All routes render without database when fake context supplied.
- Profile/run/period changes update AppContext deterministically.
- Locked compatibility states render without stack traces.

## Edge cases and failure behaviour
- Narrow screens: sidebar can collapse; no mobile-first redesign required.
- No profile selected: only profile picker/help available; pages show graceful empty state.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not add financial KPI logic to UI components.
- Do not add a JS build system; use NiceGUI/Quasar/Plotly from Python.

## Exit criteria
- [ ] All nine routes exist and share one consistent shell.
- [ ] Global profile/run/period context works.
- [ ] Reusable components cover loading/empty/error/locked states.

## Handoff to next phase
Phase 07 can focus only on Overview analytics/page content.
