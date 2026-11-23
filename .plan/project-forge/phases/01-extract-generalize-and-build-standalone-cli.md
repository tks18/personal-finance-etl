# Phase 01 — Extract, Generalize and Build the Standalone CLI

**Timebox:** 2–3 focused hours  
**Authority:** Program `README.md` + this phase file  
**Source authority:** PFETL v11.3.1 `scripts/`

## 1. Outcome

Create a new standalone `project-forge` repository/package containing the reusable engineering utilities currently embedded in PFETL, with all PFETL-specific assumptions removed and a working `pforge` CLI.

This phase does **not** modify PFETL to consume the package yet. That happens in Phase 02.

## 2. Current source files to inspect

Use these PFETL v11.3.1 files as extraction sources:

```text
scripts/quality_gate.py
scripts/auto_commit.py
scripts/create_pr.py
scripts/create_releases.py
scripts/install_hooks.py
scripts/audit_documentation.py
scripts/tasks.py
```

Explicitly do not extract:

```text
scripts/run_pipeline.bat
```

From `tasks.py`, extract only reusable workflow logic. Do not migrate PFETL-specific development server, PyInstaller `main.spec`, or application execution behavior.

## 3. Known coupling that must be removed

The new package must contain no behavior dependent on:

```text
src/personal_finance_etl/
Personal Finance ETL
uv run poe audit-fast
uv run poe audit-full
main.spec
dev -> master as a mandatory branch model
```

Specific current anchors:

- `auto_commit.py` special-cases `src/personal_finance_etl/` for scope inference.
- `auto_commit.py` directly invokes `uv run poe audit-fast`.
- `install_hooks.py` generates PFETL-branded hooks and Poe commands.
- `audit_documentation.py` hardcodes `src/personal_finance_etl`.
- `create_pr.py` defaults to `dev`/`master` and parses `CHANGELOG.md` locally.
- `create_releases.py` separately parses `CHANGELOG.md`.
- `tasks.py` contains PFETL/Poe/release orchestration that must not be copied wholesale.

## 4. Create repository/package

Create:

```text
project-forge/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/project_forge/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── project.py
│   ├── process.py
│   ├── quality.py
│   ├── commits.py
│   ├── hooks.py
│   ├── changelog.py
│   ├── pull_requests.py
│   ├── releases.py
│   ├── publishing.py
│   └── documentation.py
└── tests/
    ├── test_config.py
    ├── test_commits.py
    ├── test_changelog.py
    ├── test_quality.py
    └── test_integration.py
```

Register:

```toml
[project.scripts]
pforge = "project_forge.cli:app"
```

Use Typer for command routing and Rich for presentation.

## 5. Implement shared primitives first

### `config.py`

Implement typed optional configuration loaded from `[tool.project-forge]`.

Required capabilities:

- source roots;
- test roots;
- changelog path;
- development/default branch names;
- quality fast/full engine lists;
- commit header maximum;
- documentation-audit policy.

Defaults must support a conventional Python `src/` + `tests/` repository without configuration.

### `project.py`

Own:

- repository-root discovery;
- project name/version extraction from `pyproject.toml`;
- source/test path resolution;
- current branch and dirty-state summary;
- configured changelog path resolution.

### `process.py`

Own subprocess execution and result modeling. Do not duplicate `subprocess.run` wrappers throughout modules.

Required result data:

```text
command
exit_code
stdout
stderr
duration if cheap to capture
```

## 6. Consolidate changelog parsing

Move changelog parsing into `changelog.py` once.

Required model:

```text
ReleaseNotes
- version
- heading/date when present
- body
```

Required operations:

```text
parse changelog
list versions
latest release
get release by version
validate parseability
```

Both PR and release modules must reuse this implementation.

## 7. Port quality orchestration

Port the useful behavior of `quality_gate.py` into `quality.py`.

Built-in engine IDs:

```text
ruff-check
ruff-format
mypy
pyright
pylint
pytest
```

Preserve:

- fast/full tiers;
- fix mode for supported tools;
- diagnostic parsing where already implemented;
- Rich summary;
- nonzero exit when configured checks fail.

Do not require all supported tools to exist. Only tools selected by the resolved configuration are required for that quality run.

Expose:

```text
pforge quality
pforge quality --fast
pforge quality --fix
```

## 8. Port and generalize commit automation

Move reusable `auto_commit.py` behavior into `commits.py`.

Preserve:

- changed-file inspection;
- add/modify/delete/rename handling;
- type/scope inference;
- grouping;
- Conventional Commit formatting;
- preview;
- interactive override;
- explicit execution only.

Replace PFETL-specific scope inference with:

1. configured source roots;
2. relative package/module path;
3. known repository-level scopes such as `docs`, `test`, `ci`, `build`, `config`;
4. optional configured overrides.

Expose:

```text
pforge commit --preview
pforge commit
pforge commit --interactive
```

Default behavior must not create commits without an explicit execution path/confirmation.

## 9. Port hooks

`hooks.py` must generate project-neutral hooks calling:

```text
pforge quality --fast
pforge quality
```

Expose:

```text
pforge hooks install
pforge hooks status
pforge hooks uninstall
```

Hooks must not contain PFETL branding or Poe commands.

## 10. Port PR and release workflows

### Pull requests

Port current `create_pr.py` behavior into `pull_requests.py`.

Use:

- shared repository/branch resolution;
- shared changelog parser;
- `gh` CLI;
- preview before mutation.

Expose:

```text
pforge pr preview
pforge pr create
```

### Releases

Port current `create_releases.py` behavior into `releases.py`.

Use shared changelog parsing and Git/GitHub discovery.

Expose:

```text
pforge release preview
pforge release publish
```

No duplicated changelog parser is allowed.

## 11. Port documentation audit

Move the reusable AST checks from `audit_documentation.py` into `documentation.py`.

Replace hardcoded `src/personal_finance_etl` with configured/detected source roots.

Make PFETL-specific ownership conventions optional policy:

```text
require_module_docstrings
require_package_ownership
```

Expose:

```text
pforge docs audit
```

## 12. Implement `doctor` and `status`

### `pforge doctor`

Read-only checks:

- Git available;
- project root found;
- `pyproject.toml` valid;
- configured paths exist;
- selected quality tools available;
- `uv` presence;
- `gh` presence/auth state when GitHub commands are relevant;
- changelog status;
- hook status.

### `pforge status`

Compact summary:

```text
project
version
root
branch
dirty file count
configured quality tiers
hooks
changelog latest version
GitHub CLI availability
```

## 13. Implement publishing wrapper

Move only the generic build/publish behavior from `tasks.py`:

```text
quality gate
uv build
validate dist artifacts
uv publish
```

Expose:

```text
pforge publish
```

No PFETL-specific tag/PR choreography is part of this command.

## 14. Tests

Minimum assertions:

### `test_config.py`

- zero-config defaults;
- `pyproject.toml` overrides;
- invalid key/value behavior;
- relative path resolution.

### `test_commits.py`

- Git porcelain states;
- add/modify/delete/rename classification;
- conventional type/scope inference;
- grouping;
- max header length.

### `test_changelog.py`

- parse multiple releases;
- latest selection;
- version lookup;
- malformed changelog behavior.

### `test_quality.py`

- existing Ruff/Mypy/Pyright/Pylint parser behavior;
- configured engine selection;
- missing configured executable fails clearly.

### `test_integration.py`

Using a temporary Git repository:

- detect repository;
- inspect dirty files;
- `pforge status` equivalent service works;
- commit preview generates deterministic groups;
- no destructive external actions occur.

## 15. Documentation for the package

Keep the new package README concise:

- what Project Forge is;
- installation;
- CLI examples;
- optional `[tool.project-forge]` configuration;
- supported external tools;
- development/testing instructions.

Do not create a documentation portal or Wiki.

## 16. Explicit non-goals

Do not add:

- plugin/entry-point ecosystem;
- project scaffolding;
- CI-provider abstractions;
- GitHub REST SDK;
- background daemon;
- GUI;
- PFETL-specific commands;
- analytics-studio-specific commands;
- generic task-runner DSL.

## 17. Exit criteria

Phase 01 is complete only when:

- [ ] new repository/package installs locally;
- [ ] `pforge --help` works;
- [ ] `pforge doctor` works in the new repository;
- [ ] `pforge status` works;
- [ ] quality commands work against configured tools;
- [ ] commit preview works in a temporary/non-PFETL repository;
- [ ] hooks contain no PFETL/Poe assumptions;
- [ ] PR/release previews use the shared changelog parser;
- [ ] documentation audit uses configured source roots;
- [ ] `pforge publish` can reach build preview/guard path without publishing;
- [ ] focused tests are green;
- [ ] grep/search finds no `personal_finance_etl` or `Personal Finance ETL` in package source/tests;
- [ ] no PFETL repository files have been replaced yet.

## 18. Handoff to Phase 02

Phase 02 may assume a locally installable, project-neutral `project-forge` package with the complete initial CLI surface and passing focused tests.
