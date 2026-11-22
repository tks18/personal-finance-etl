# Phase 001 - Remove Documentation Portal and Runtime Web Baggage

**Target release:** v11.0.1  
**Expected effort:** 2–3 focused hours  
**Previous:** v11.0.0 baseline  
**Next:** Phase 002  
**Risk:** Low-Medium

## 1. Outcome

Remove the entire embedded/web documentation product while preserving useful Markdown documentation and all non-doc release tooling.

## 2. Why this phase exists

- The docs renderer is one of the largest low-value presentation modules in v11.0.0.
- `pywebview`, runtime Markdown rendering, Mermaid/svg-pan-zoom assets, MkDocs/ReadTheDocs packaging and docs launch hooks add dependencies the primary user does not need.
- This is the safest opening sprint because it has almost no financial blast radius.

## 3. Inherited repository state

- v11.0.0 is the rollback baseline and implementation authority.
- Grand Refactor planning has been intentionally discarded/archived.
- Observability, Raw Store, Control Plane, recovery and financial engines are healthy and protected.

## 4. Current codebase anchors

- `src/personal_finance_etl/presentation/docs/`
- `src/personal_finance_etl/presentation/launcher.py` (`--docs`)
- `src/personal_finance_etl/presentation/desktop/app.py` Guides/About entry
- `pyproject.toml` docs/runtime dependencies, package data and project URLs
- `main.spec`, `mkdocs.yml`, `.readthedocs.yaml`, docs frontend assets
- documentation-specific tests/tasks/auditors

## 5. Exact target state after this phase

Remove the entire embedded/web documentation product while preserving useful Markdown documentation and all non-doc release tooling.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Remove the runtime `presentation

Remove the runtime `presentation.docs` package and all imports/callers.

### Step 2 - Remove CLI `--docs` and Desktop Guides/About runtime launch behavior

Remove CLI `--docs` and Desktop Guides/About runtime launch behavior.

### Step 3 - Remove `pywebview` and runtime `markdown` dependencies if no surviving caller requires them

Remove `pywebview` and runtime `markdown` dependencies if no surviving caller requires them.

### Step 4 - Remove MkDocs/ReadTheDocs portal configuration, portal CSS/JS/overrides, bundled Mermaid and svg-pan-zoom assets

Remove MkDocs/ReadTheDocs portal configuration, portal CSS/JS/overrides, bundled Mermaid and svg-pan-zoom assets.

### Step 5 - Keep useful Markdown under `/docs`; update links so no surviving code/README points to a dead portal URL

Keep useful Markdown under `/docs`; update links so no surviving code/README points to a dead portal URL.

### Step 6 - Remove portal packaging hooks from wheel/PyInstaller while preserving non-doc Node/release tooling

Remove portal packaging hooks from wheel/PyInstaller while preserving non-doc Node/release tooling.

### Step 7 - Run import, packaging smoke and presentation tests

Run import, packaging smoke and presentation tests.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Packaging and documentation links change; finance/runtime data paths do not.

## 9. Tests and verification

- [x] No runtime import under `personal_finance_etl.presentation.docs` remains.
- [x] `pywebview`, portal-only Markdown runtime and bundled Mermaid/svg-pan-zoom assets are absent from the runtime/package graph.
- [x] `pfetl`/current launcher still starts CLI/Desktop paths without docs-specific failure.
- [x] README and retained `/docs` links resolve to repository Markdown rather than the removed portal.
- [x] PyInstaller spec contains no docs/browser assets or hidden imports.

## 10. Explicit non-goals

- Do not rewrite the documentation corpus.
- Do not alter observability, finance, Settings, warehouse schemas or CLI product naming yet.

## 11. Completion checklist

- [x] Exit assertion: No runtime import under `personal_finance_etl.presentation.docs` remains.
- [x] Exit assertion: `pywebview`, portal-only Markdown runtime and bundled Mermaid/svg-pan-zoom assets are absent from the runtime/package graph.
- [x] Exit assertion: `pfetl`/current launcher still starts CLI/Desktop paths without docs-specific failure.
- [x] Exit assertion: README and retained `/docs` links resolve to repository Markdown rather than the removed portal.
- [x] Exit assertion: PyInstaller spec contains no docs/browser assets or hidden imports.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 002

The next phase may assume only the verified state above. It begins **Shan-First Settings Model and Dataset-Level Hash Ownership** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 001
Target release: v11.0.1
Files changed:
- src/personal_finance_etl/presentation/launcher.py
- src/personal_finance_etl/presentation/cli/app.py
- src/personal_finance_etl/presentation/desktop/app.py
- src/personal_finance_etl/presentation/__init__.py
- pyproject.toml
- uv.lock
- main.spec
- poe_tasks.toml
- README.md
- tests/test_architecture_boundaries.py
- tests/test_phase10_presentation.py
Files deleted:
- src/personal_finance_etl/presentation/docs/*
- mkdocs.yml
- .readthedocs.yaml
- .github/workflows/deploy-docs.yml
- docs/manifest.json
- docs/requirements.txt
- docs/overrides/*
- docs/assets/javascripts/*
- docs/assets/stylesheets/*
Contracts/schema changed: None
Financial formulas changed: None
Protected identity comparison: N/A
Focused tests: tests/test_phase10_presentation.py, tests/test_architecture_boundaries.py (PASS)
Architecture tests: tests/test_architecture_boundaries.py (PASS)
Real-data verification: N/A
Power BI verification: N/A
Observability/recovery verification: N/A
Compatibility/transitional state remaining: None
Semantic commit groups:
- refactor(presentation): remove docs viewer and CLI --docs flag
- chore(deps): prune pywebview, markdown, mkdocs dependencies
- chore(docs): remove portal generators and update README links
- test(presentation): update tests for docs runtime removal
Exit assertions green: yes
```
