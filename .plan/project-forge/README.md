# Project Forge — Authoritative Extraction & Integration Program

## Authority

This README and the active phase file are the only planning documents required to implement this program.

For any implementation phase:

1. Read this README.
2. Read only the active phase file.
3. Inspect the current repository source before editing.
4. Implement only the active phase scope.
5. Finish with the phase exit checks green before moving forward.

The active source authority for extraction is **PFETL v11.3.1**, specifically its current `scripts/` folder. The program is intentionally small: **two implementation phases only**.

---

## 1. Purpose

PFETL currently carries a reusable engineering-tooling suite inside `scripts/`. The objective is to extract that reusable capability into a standalone package so PFETL Core and future projects, especially PFETL Analytics Studio, can consume one shared CLI instead of copying project-management utilities from repository to repository.

The standalone package is a developer workflow utility, not a new product platform.

Working identity:

```text
Distribution: project-forge
Import:       project_forge
CLI:          pforge
```

Before first public publication, verify the final distribution name is available on PyPI. If the name is unavailable, change only the distribution/project branding while preserving the CLI and architecture unless there is a strong reason not to.

---

## 2. Current PFETL scripts archaeology

PFETL v11.3.1 currently contains approximately 2.5k LOC of reusable scripts:

| Current file | Role | Extraction decision |
| --- | --- | --- |
| `scripts/quality_gate.py` | Ruff/Mypy/Pyright/Pylint/Pytest orchestration, parsers, Rich output | Extract and generalize |
| `scripts/auto_commit.py` | changed-file grouping, scope/type inference, Conventional Commit generation/execution | Extract and generalize |
| `scripts/create_pr.py` | changelog-backed PR preview/create/update using `gh` | Extract and generalize |
| `scripts/create_releases.py` | changelog-backed GitHub release preview/publish | Extract and generalize |
| `scripts/install_hooks.py` | pre-commit/pre-push quality hooks | Extract and generalize |
| `scripts/audit_documentation.py` | AST documentation/package ownership audit | Extract as configurable policy |
| `scripts/tasks.py` | mixed orchestration facade | Extract only reusable orchestration; leave PFETL-specific commands behind |
| `scripts/run_pipeline.bat` | PFETL unattended pipeline launcher | **Do not extract** |

Current reusable LOC is approximately 2,500 lines, but the standalone implementation should consolidate duplicated logic instead of copying these files one-for-one.

---

## 3. Current PFETL-specific assumptions that must disappear

The extracted package must not retain any of these assumptions:

### Package-path assumptions

`auto_commit.py` currently special-cases:

```text
src/personal_finance_etl/
```

Scope inference must become repository-neutral and configurable.

### Branch assumptions

Current PR/release orchestration assumes:

```text
dev -> master
```

Branch defaults must come from configuration or Git repository state.

### Poe assumptions

Current utilities call commands such as:

```text
uv run poe audit-fast
uv run poe audit-full
```

Project Forge must invoke its own services directly. Poe may call `pforge`, but `pforge` must not require Poe.

### PFETL branding

Generated hooks currently contain `Personal Finance ETL` wording. All generated text must be project-neutral and use detected/configured project names.

### Hardcoded changelog location

Current PR/release tooling assumes `CHANGELOG.md`. Keep `CHANGELOG.md` as the zero-config default, but allow configuration.

### Hardcoded quality tool set

Current quality flow assumes some combination of:

```text
ruff
mypy
pyright
pylint
pytest
```

Keep these as built-in supported engines, but select them through resolved project configuration instead of fixed PFETL logic.

### PFETL-only tasks

Do not migrate:

- `tkreload` development server behavior;
- `main.spec`/PyInstaller PFETL build behavior;
- PFETL pipeline execution;
- PFETL-specific publish/release sequencing that is not generally reusable.

---

## 4. Product boundary

Project Forge exists to standardize common Python repository workflows:

```text
quality
commit
hooks
changelog
pull requests
GitHub releases
package publication
doctor/status
optional documentation audit
```

It does **not** become:

- a generic CI platform;
- a plugin ecosystem;
- a build system;
- a dependency manager;
- a replacement for Git;
- a replacement for GitHub Actions;
- a project scaffolding framework;
- a task runner competing with Make/Poe/Nox;
- an application runtime.

The package should be small enough that maintaining it is cheaper than copying the current scripts into each repository.

---

## 5. Target CLI

The stable initial CLI surface is:

```text
pforge doctor
pforge status

pforge quality
pforge quality --fast
pforge quality --fix

pforge commit
pforge commit --preview
pforge commit --interactive

pforge hooks install
pforge hooks status
pforge hooks uninstall

pforge changelog validate
pforge changelog latest
pforge changelog show <version>

pforge pr preview
pforge pr create

pforge release preview
pforge release publish

pforge publish
```

Do not add commands merely because the current PFETL scripts contain helper functions. Expose only workflows worth reusing across repositories.

---

## 6. Target package structure

Keep the project deliberately flat and understandable:

```text
project-forge/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── project_forge/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── project.py
│       ├── process.py
│       ├── quality.py
│       ├── commits.py
│       ├── hooks.py
│       ├── changelog.py
│       ├── pull_requests.py
│       ├── releases.py
│       ├── publishing.py
│       └── documentation.py
└── tests/
    ├── test_config.py
    ├── test_commits.py
    ├── test_changelog.py
    ├── test_quality.py
    └── test_integration.py
```

Do not introduce `domain/application/infrastructure/presentation` layers. This is a focused utility package.

If one module becomes genuinely unwieldy during implementation, it may become a small package, but do not pre-split the codebase into architecture for architecture's sake.

---

## 7. Core dependencies

Keep runtime dependencies small:

```text
typer
rich
pydantic
tomlkit
packaging
```

External project tools remain external executables and are discovered at runtime:

```text
git
uv
gh
ruff
mypy
pyright
pylint
pytest
```

Project Forge must clearly distinguish:

- required external commands for the selected operation;
- optional commands not configured for the repository;
- commands unavailable on the current machine.

Do not install or silently modify external tools.

---

## 8. Configuration model

Use `pyproject.toml` as the optional project-level configuration surface.

Example target:

```toml
[tool.project-forge]
source = ["src"]
tests = ["tests"]
changelog = "CHANGELOG.md"

[tool.project-forge.git]
development_branch = "dev"
default_branch = "main"

[tool.project-forge.quality]
fast = ["ruff-check", "ruff-format", "mypy"]
full = ["ruff-check", "ruff-format", "mypy", "pyright", "pytest"]

[tool.project-forge.commits]
header_max_length = 72

[tool.project-forge.docs]
require_module_docstrings = true
require_package_ownership = false
```

Requirements:

- configuration is optional for ordinary Python repositories;
- defaults are conservative and discoverable;
- unknown config keys fail clearly;
- relative paths resolve from the detected repository root;
- the resolved configuration can be shown by `pforge status`/`doctor`.

---

## 9. Shared internal primitives

Phase 1 must centralize logic currently duplicated across scripts:

### Repository discovery

One implementation for locating project root and reading project metadata.

### Process execution

One subprocess wrapper supporting:

- cwd;
- captured output;
- exit code;
- optional streaming;
- command display/redaction;
- predictable error handling.

### Git repository access

Central helpers for:

- current branch;
- changed files;
- porcelain/status parsing;
- staged files;
- tags;
- remote presence;
- pushing when explicitly requested.

### Changelog parsing

`create_pr.py` and `create_releases.py` currently parse release notes separately. Consolidate this into one changelog parser/model used by both workflows.

### Rich presentation

Keep consistent status/result rendering, but do not embed business logic in Rich formatting functions.

---

## 10. Quality engine

Preserve the useful behavior from `quality_gate.py`:

- fast/full tiers;
- Ruff check;
- Ruff format check;
- Mypy;
- Pyright;
- Pylint where configured;
- Pytest;
- optional fix mode;
- diagnostic parsing;
- Rich summary;
- machine-readable result option where practical.

The engine list is internal/config-driven, not a third-party plugin system.

Built-in engine identifiers should be stable:

```text
ruff-check
ruff-format
mypy
pyright
pylint
pytest
```

---

## 11. Commit workflow

Preserve the strongest parts of `auto_commit.py`:

- inspect changed files;
- understand add/modify/delete/rename state;
- infer Conventional Commit type and scope;
- group related changes;
- preview before execution;
- interactive override;
- dry-run/preview mode;
- enforce maximum header length;
- execute atomic commits only when requested.

Generalize scope inference:

1. detect source roots from configuration;
2. derive first meaningful package/module segment;
3. use configured scope overrides when supplied;
4. fall back to neutral scopes such as `build`, `ci`, `docs`, `test`, `config`, or repository-level scope.

Never encode `personal_finance_etl` in the standalone package.

---

## 12. Hooks

Generated hooks should call Project Forge directly, for example:

```text
pforge quality --fast
pforge quality
```

The hook installer must support:

```text
pforge hooks install
pforge hooks status
pforge hooks uninstall
```

Do not overwrite unrelated user hook content without explicit confirmation/defined ownership. Prefer installing tracked or clearly marked Project Forge-managed hooks.

---

## 13. PR and release workflows

Use `gh` as an external backend.

PR flow:

- resolve head/base branches;
- select changelog version;
- include quality evidence when available;
- preview body;
- create or update PR only on explicit command.

Release flow:

- parse changelog once through shared parser;
- compare existing Git tags/GitHub releases;
- preview release notes;
- publish one selected release or configured latest release;
- support draft mode where useful.

No GitHub REST SDK is required for the first release.

---

## 14. Publishing

`pforge publish` should remain intentionally small:

1. verify repository cleanliness/version metadata;
2. run configured quality gate unless explicitly skipped;
3. execute `uv build`;
4. verify `dist/` artifacts exist;
5. execute `uv publish` only after explicit confirmation/non-interactive flag.

Do not store PyPI tokens. Use the environment/uv authentication mechanisms already supported by the user's setup.

---

## 15. Doctor and status

`pforge doctor` should validate the current environment:

- Git available;
- repository detected;
- `pyproject.toml` readable;
- configured source/test paths valid;
- configured quality tools available;
- `uv` available when publish/build features are used;
- `gh` available and authentication state visible for GitHub operations;
- changelog available when configured;
- current branch/remote state;
- hook status.

`pforge status` should provide a compact non-diagnostic snapshot:

```text
Project
Version
Repository root
Current branch
Dirty files
Configured quality tier
Hooks
GitHub CLI availability
Changelog latest version
```

Neither command should mutate the project.

---

## 16. Testing philosophy

Unlike PFETL's financial tests, Project Forge is mostly deterministic text/process orchestration and should have small focused tests.

Minimum coverage:

- config defaults and overrides;
- project-root discovery;
- Git porcelain parsing;
- Conventional Commit type/scope/group inference;
- changelog parsing;
- quality-output parsers;
- hook generation/status;
- PR/release body selection;
- one integration test using a temporary Git repository.

Mock external destructive actions such as PR creation, release publishing and PyPI publication.

---

## 17. Versioning and release sequence

First standalone public release:

```text
0.1.0
```

Do not start at `0.5.0` merely because the extracted scripts are mature inside PFETL. The new package has its own public history.

Suggested progression:

```text
0.1.x  extraction/generalization fixes
0.2.x  proven through PFETL dogfooding
0.3.x  proven in Analytics Studio
0.5.0  stable across Shan's active repositories
1.0.0  CLI/config contract considered stable
```

This is guidance, not a requirement to manufacture releases.

---

## 18. Two-phase program

### Phase 01 — Extract, generalize and build standalone CLI

Create the standalone package, remove PFETL coupling, consolidate duplicate logic, expose the initial `pforge` CLI, and make focused tests green.

### Phase 02 — Publish, integrate PFETL and delete duplication

Publish the first package, install/dogfood it in PFETL, replace reusable PFETL scripts/wrappers with Project Forge commands, remove duplicated implementations, and leave PFETL-specific automation only.

After Phase 02, the package is ready to be used from day one in PFETL Analytics Studio.

---

## 19. Program completion state

At completion:

```text
project-forge
    ↓ reusable engineering workflow CLI
PFETL Core
PFETL Analytics Studio
future Python projects
```

PFETL no longer owns reusable commit/quality/PR/release/hook infrastructure.

Project Forge remains intentionally small enough to be maintained as shared tooling rather than becoming another major product.
