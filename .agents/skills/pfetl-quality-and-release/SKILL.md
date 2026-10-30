---
name: pfetl-quality-and-release
description: >-
  Use this skill when executing Quality Gate audits, diagnosing and resolving Mypy/Pyright/Ruff
  lint and type errors, updating docstrings, generating pull requests with Quality Gate
  certification, or publishing GitHub releases.
---

# PFETL Quality Gate & Release Management Runbook

This skill outlines the standard operating procedures for auditing code quality, enforcing static analysis standards, preparing automated pull requests, and publishing releases.

---

## 1. Quality Gate Tiers & Execution

Quality verification is split into fast and full tiers:

### Tier 1 — Fast Audit (< 2s)
Run frequently during local development:
```powershell
uv run poe audit-fast
```
- **Ruff Lint:** Fast syntax and rule check.
- **Ruff Format Check:** Checks 100-character line lengths and style.
- **Mypy:** Strict type checking across `src/`.

### Tier 1 Auto-Fix
Automatically correct safe Ruff formatting and import issues:
```powershell
uv run poe audit-fast:fix
```

### Tier 2 — Full Audit (~30-45s)
Mandatory before creating pull requests or releasing:
```powershell
uv run poe audit
# or full suite with structured exports:
uv run poe audit-full
```
Runs 6 verification engines:
1. `ruff check src`
2. `ruff format --check src`
3. `mypy src`
4. `pyright src`
5. `pylint src`
6. `pytest tests/`

---

## 2. Resolving Common Quality Failures

### NumPy Docstrings (`D` and `D417`)
- Convention: **NumPy Docstrings** are mandatory across all `src/` modules, classes, and public functions.
- Parameters section must document all parameters and types:
  ```python
  def calculate_cagr(start_value: float, end_value: float, years: float) -> float:
      """Calculate the Compound Annual Growth Rate.

      Parameters
      ----------
      start_value : float
          Initial portfolio value.
      end_value : float
          Terminal portfolio value.
      years : float
          Number of years elapsed.

      Returns
      -------
      float
          Annualized compound growth rate.
      """
  ```
- Package `__init__.py` files require explicit `Owns` and `Does not own` docstrings:
  ```python
  """Package summary.

  Owns
  ----
  - List of responsibilities.

  Does not own
  -------------
  - List of out-of-scope concerns.
  """
  ```
- Run AST docstring verification:
  ```powershell
  uv run poe audit-docs
  ```

### Mypy Strict Mode in Python 3.13
- Use modern type unions: `int | None` instead of `Optional[int]`.
- Avoid `Any`: Use explicit protocols, TypedDicts, or generics.
- Polars DataFrames: Annotate expressions and schemas explicitly.

### Architecture Boundary Failures
- If `tests/test_architecture_boundaries.py` reports a forbidden import:
  1. Inspect the import violation in the test output.
  2. Verify which layer is prohibited from importing the target (e.g. `domain` importing `duckdb` or `sqlite3`).
  3. Never alter the test assertions. Move storage queries into `infrastructure/warehouse` and expose data to the domain via pure Polars frames or contract dataclasses.

---

## 3. Pull Request Generation (`create_pr.py`)

PRs are generated with automated Quality Gate certification attached.

### Step 1: Preview PR
```powershell
uv run poe pr:preview
```
Inspects:
- Target branch (`dev` into `master`).
- Version and release notes from `CHANGELOG.md`.
- Attached Quality Gate certification table.

### Step 2: Create or Update PR
```powershell
uv run poe pr:create
```
Uses the GitHub CLI (`gh`) to idempotently create or update the PR.

---

## 4. GitHub Release Management (`create_releases.py`)

Releases extract release notes from `CHANGELOG.md` matching Git tags.

### Step 1: Dry-Run Matching Tags
```powershell
uv run poe release:dry-run
```

### Step 2: Preview Latest Release Notes
```powershell
uv run poe release:preview
```

### Step 3: Publish Draft Release on GitHub
```powershell
uv run poe release:latest:draft
```

### Step 4: Full Release Execution
```powershell
uv run poe release:latest
```
