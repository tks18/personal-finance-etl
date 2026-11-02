# AGENTS.md — Scripts & DevOps Automation Guidelines

> **Directory:** `scripts/`  
> **Orchestrator:** `poethepoet` via `poe_tasks.toml` and Astral `uv`  
> **Target Python:** `>=3.13`

---

## 1. Directory Purpose & Tool Index

The `scripts/` directory hosts developer orchestration tools, quality gates, release automation, and Conventional Commit tooling. These scripts are invoked via `uv run poe <task>`:

| Script | Poe Task Bindings | Responsibility |
|---|---|---|
| `quality_gate.py` | `audit`, `audit-fast`, `audit-fast:fix`, `audit-full`, `audit-csv`, `audit-json` | Multi-tier static analysis and test validation (Ruff, Mypy, Pyright, Pylint, Pytest). Exports structured CLI, JSON, and CSV audits. |
| `auto_commit.py` | `commit`, `commit:preview`, `commit:run`, `commit:interactive`, `commit:overrides` | Automated Conventional Commit wizard enforcing Commitlint standards (<= 72 char header), staging files atomic-by-semantic-group or using `.commit_overrides.json`. |
| `create_pr.py` | `pr:preview`, `pr:create` | Creates/updates GitHub Pull Requests from `dev` to `master` with attached Quality Gate certification tables. |
| `create_releases.py` | `release:preview`, `release:dry-run`, `release:latest`, `release:latest:draft`, `release:all` | Parses `CHANGELOG.md` versions and manages GitHub releases/tags. |
| `audit_documentation.py` | `audit-docs` | AST-level validator verifying NumPy docstring compliance across packages. |
| `install_hooks.py` | `install-hooks` | Installs Git pre-commit and pre-push quality hooks linking into fast/full quality gates. |
| `tasks.py` | (Internal dispatcher) | Entry-point routing for `poe_tasks.toml`. |

---

## 2. Quality Gate Architecture

Quality verification is split into two tiers to optimize developer velocity:

1. **Tier 1 — Fast Audit (`uv run poe audit-fast` / `< 2s`):**
   - **Ruff Check:** Fast linting across `src/`.
   - **Ruff Format Check:** Checks line length (100) and formatting.
   - **Mypy:** Strict static type analysis on `src/`.
   - *Use `uv run poe audit-fast:fix` to auto-correct safe lint and format errors.*
2. **Tier 2 — Full Audit (`uv run poe audit` / `~30-45s`):**
   - Runs all 6 verification engines: **Ruff Lint**, **Ruff Format**, **Mypy**, **Pyright**, **Pylint**, and **Pytest**.
   - Generates unified quality gate scores and optionally exports structured JSON/CSV reports.

---

## 3. Automation & Authoring Rules for AI Agents

1. **Cross-Platform Compatibility:**
   - Scripts must operate identically across **Windows PowerShell** (`pwsh`) and **Linux / macOS Bash**.
   - Use `pathlib.Path` exclusively instead of hardcoded `/` or `\` separators.
2. **Windows Terminal UTF-8 Encoding:**
   - Always ensure standard output and standard error reconfigure safely on Windows:
     ```python
     if sys.platform == "win32":
         if hasattr(sys.stdout, "reconfigure"):
             sys.stdout.reconfigure(encoding="utf-8", errors="replace")
         if hasattr(sys.stderr, "reconfigure"):
             sys.stderr.reconfigure(encoding="utf-8", errors="replace")
     ```
3. **Subprocess Invocations:**
   - Always use `sys.executable` when invoking Python scripts or modules to ensure execution within the active `uv` virtual environment.
   - Set sensible timeouts and capture both `stdout` and `stderr` for rich error reporting.
4. **Conventional Commits & Commitlint:**
   - All commits must strictly conform to Conventional Commits: `type(scope): subject`.
   - Subject line must be **<= 72 characters**, lowercase, without a trailing period.
   - Valid types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
5. **Ruff Docstring Exemption:**
   - Per `ruff.toml`, `scripts/**` is exempt from NumPy docstring rules (`lint.per-file-ignores."scripts/**" = ["D"]`). However, maintain top-of-file module docstrings documenting ownership.
