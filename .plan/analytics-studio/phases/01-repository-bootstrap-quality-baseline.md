# Phase 01 — Repository Bootstrap and Quality Baseline

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
None. This is the first Studio sprint.

## Phase outcome
Create a new installable Python repository with the frozen package layout, one quality workflow, a runnable `pfetl-studio` command and no product functionality beyond a health shell.

## Inherited state
- The product constitution, stack, dependency rules and target tree are frozen by the README.
- PFETL Core is external upstream data; this repository starts empty and must not vendor Core code.

## Files in scope
- `pyproject.toml`
- `uv.lock`
- `.python-version`
- `.gitignore`
- `ruff.toml`
- `mypy.ini`
- `.github/workflows/quality.yml`
- `src/pfetl_analytics_studio/__init__.py`
- `src/pfetl_analytics_studio/__main__.py`
- `src/pfetl_analytics_studio/cli.py`
- `src/pfetl_analytics_studio/app.py`
- package `__init__.py` files for `data/`, `semantic/`, `analytics/`, `pages/`, `reports/`, `ui/`
- `tests/test_smoke.py`

## Grounded PFETL / Studio inputs
- Python >=3.13.
- NiceGUI 4.x, Plotly 7.x, DuckDB 1.x, Polars 2.x, Pydantic 2.x, ReportLab 5.x, Kaleido 1.x and XlsxWriter 3.x compatible major ranges.
- No PFETL database is needed for the bootstrap smoke test.

## Required contracts at phase exit
- `pfetl_analytics_studio.__version__ = "0.1.0-dev"`.
- Console script `pfetl-studio = pfetl_analytics_studio.cli:main`.
- `cli.main()` starts the NiceGUI application bound to localhost only and may accept `--host`, `--port`, `--no-browser` only if needed for local development.
- `app.create_app()` owns page registration; it must not open databases in this phase.

## Data and query semantics
- No finance or data semantics exist yet.
- Dependencies use compatible ranges in `pyproject.toml`; `uv.lock` freezes exact versions.
- Ruff and mypy are the only static-quality tools in v1.

## UI / interaction specification
- Render a minimal shell containing product name, version and “No PFETL profile selected”.
- No navigation pages beyond the placeholder shell are required yet.
- The app must fail with a clear message when started on a non-loopback host unless explicitly enabled for development.

## Implementation sequence
1. Create the repository files and exact package directories from the README.
2. Declare runtime and dev dependencies; generate `uv.lock`.
3. Implement `cli.main()` and `app.create_app()` with a minimal localhost NiceGUI shell.
4. Configure Ruff and strict-enough mypy for `src/`; do not suppress broad error classes.
5. Add CI steps: install with uv, Ruff, mypy, pytest.
6. Add a smoke test importing the package and constructing the app without touching PFETL.

## Focused verification
- `uv run ruff check .` passes.
- `uv run mypy src` passes.
- `uv run pytest` passes.
- `uv run pfetl-studio --no-browser` can start far enough to prove the console entrypoint is valid.

## Edge cases and failure behaviour
- Missing browser is not fatal when `--no-browser` is used.
- Port-in-use errors must surface clearly; do not silently choose arbitrary ports.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not add Docker, Node, React, FastAPI routes, authentication, PyInstaller or desktop/native packaging.

## Exit criteria
- [ ] Repository installs from a clean environment using `uv sync`.
- [ ] Console entrypoint exists and imports only Studio code.
- [ ] Quality workflow is green.
- [ ] Target source/test directory skeleton exists with no speculative implementation.

## Handoff to next phase
Phase 02 may assume a runnable typed repository, stable package names, and the console/application shell.
