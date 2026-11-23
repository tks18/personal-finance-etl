# Phase 03 — Maintenance-Debt Demolition

**Sprint:** 2–3 hours  
**Goal:** remove documentation/tooling surfaces Shan no longer wants to maintain, without breaking runtime assets or packaging.

## Delete requested root files

```text
.bandit
.codacy.yml
.coderabbit.yaml
.flake8
.prospector.yml
```

## Delete documentation corpus

Delete the entire `docs/` directory after relocating the two runtime brand assets.

Current runtime/package couplings that must be fixed first:

1. `presentation/desktop/app.py::_build_title_block` uses `resource_path("docs/assets/images/logo.png")`.
2. `DesktopApp.__init__` uses `resource_path("docs/assets/images/logo.ico")`.
3. `main.spec` includes `('docs/assets/images', 'docs/assets/images')`.
4. `main.spec` sets `icon='docs/assets/images/logo.ico'`.
5. `MANIFEST.in` includes `docs/manifest.json`.
6. `pyproject.toml` Documentation URL points to `docs/README.md`.
7. root README contains numerous `docs/...` links and Codacy/CodeRabbit/DeepWiki badges.

## Asset relocation

Create:

```text
src/personal_finance_etl/presentation/assets/
├── logo.png
└── logo.ico
```

Update `app.py`, `main.spec`, and package resource inclusion accordingly. Confirm `resource_path()` resolves the new packaged location in dev and PyInstaller modes.

## Tooling reference cleanup

- Remove `[tool.bandit]` from `pyproject.toml`.
- Inspect `main.spec` hidden imports and remove `flake8` if it exists only as historical tool baggage.
- Remove `# flake8: noqa` comments from surviving `scripts/*.py` and any newly retained tests.
- `scripts/auto_commit.py` currently lists `.flake8`, `.codacy.yml`, `.coderabbit.yaml`; remove those entries.
- Search the repository for `bandit`, `codacy`, `coderabbit`, `flake8`, `prospector` and remove only stale references caused by this deletion.

Do not remove Ruff/mypy/Pyright/Pyrefly/Pylint in this phase; the user explicitly scoped only the five root files above.

## Wiki

PFETL code should no longer advertise or require a Wiki. Remove Wiki/DeepWiki references from repository files when encountered. Physically deleting GitHub Wiki content is an external repository action and is not required for local code completion.

## README handling

Do **not** spend this phase rewriting the 737-line README. Remove only links/badges that would become broken. Phase 8 replaces the README after the final UI exists.

## Verification

Run:

```text
search for docs/
search for removed tool names
package build / PyInstaller smoke if locally available
launch GUI and verify logo/icon
```

Allowed remaining `docs` text: ordinary English references in comments/messages that do not point at a deleted path. No runtime file path may reference `docs/`.

## Exit criteria

- `docs/` is gone;
- the five requested root config files are gone;
- GUI branding still works;
- packaging no longer bundles docs assets;
- `MANIFEST.in`, `pyproject.toml`, `main.spec`, scripts and README contain no broken references caused by the deletion;
- golden suite from Phase 2 remains green.
