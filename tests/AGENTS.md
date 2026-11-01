# AGENTS.md — Testing Workspace Guidelines

> **Directory:** `tests/`  
> **Test Runner:** Pytest via Astral `uv` (`uv run pytest`)  
> **Target Python:** `>=3.13`

---

## 1. Test Suite Structure & Philosophy

The test suite directly mirrors the 7-layer clean architecture of `src/personal_finance_etl/`, alongside dedicated test suites for architecture boundaries and fixtures:

| Layer Folder | Key Files | What It Protects |
|---|---|---|
| **Architecture** (`tests/architecture/`) | `test_boundaries.py`, `test_legacy_demolition.py`, `test_constitutional_certification.py` | **Sacred Ground.** Enforces 7-layer clean architecture, AST-level forbidden import checks, package structure, zero `TYPE_CHECKING` blocks, zero inline imports, and product invariants. |
| **Contracts** (`tests/contracts/`) | `test_primitives.py`, `test_data_transport.py`, `test_datasets.py`, `test_sources.py`, `test_observability.py` | Immutability, Pydantic validation, stable dataset/source schemas, deterministic identity, and data transport integrity. |
| **Config** (`tests/config/`) | `test_settings.py`, `test_financial_rules.py` | Configuration provenance, environment loading, rules fingerprinting, and Pydantic configuration schemas. |
| **Domain** (`tests/domain/`) | `test_canonical_domains.py`, `test_investments_quant.py`, `test_status_unification.py`, `test_tax_domain.py`, `test_household_wealth_fire.py` | FIFO lot matching, corporate actions, XIRR/CAGR quant math, tax schedules, net worth, Numba Monte Carlo FIRE simulations. Pure numerical/business logic. |
| **Infrastructure** (`tests/infrastructure/`) | `test_warehouse_and_cp.py`, `test_control_plane.py`, `test_providers.py`, `test_observability_emitter.py`, `test_forensic_debuggability.py`, `test_redaction_retention.py`, `test_legacy_logging_demolition.py`, `test_observability_certification.py` | DuckDB warehouse, SQLite Control Plane transactions, Raw Document Store, external providers, fan-out event emission, JSONL audit trails, PII/PAN redaction. |
| **Application** (`tests/application/`) | `test_ingestion.py`, `test_pipeline_observability.py`, `test_forensic_pipeline.py`, `test_orchestration_bootstrap.py` | `ETLOrchestrator`, `ServiceContainer`, pipeline stages, file parsers, provider adapters, Pre-Bronze completeness checks. |
| **Presentation** (`tests/presentation/`) | `test_desktop_app.py`, `test_narrative.py` | CLI argument parsing, CustomTkinter tabs, rich narrative rendering, doc browser. |
| **Fixtures** (`tests/fixtures/`) | `config.toml`, `financial_rules.toml`, `run_headless.py` | Shared test fixtures, mock configurations, and headless execution profiling script. |

---

## 2. Test Execution Commands

Always run pytest via `uv`:

```powershell
# Run the complete test suite
uv run pytest

# Run architectural boundary enforcement tests (< 1 second)
uv run pytest tests/architecture/test_boundaries.py

# Run a specific layer or test file with concise tracebacks
uv run pytest tests/domain/test_investments_quant.py -v --tb=short
uv run pytest tests/contracts/

# Run tests matching a specific name pattern
uv run pytest -k "test_fifo"

# Run headless ETL execution profile
uv run python tests/fixtures/run_headless.py
```

---

## 3. Test Authoring Rules for AI Agents

1. **Mirror Layer Placement:**
   - When writing tests for code in `src/personal_finance_etl/<layer>/`, always place the test in `tests/<layer>/`.
   - Never create flat or unorganized test files directly in `tests/`.
2. **Self-Documenting Test Names:**
   - Follow the naming pattern: `test_<feature_or_component>_<condition>_<expected_outcome>()`.
   - Per `ruff.toml`, docstrings are optional in `tests/` (`lint.per-file-ignores."tests/**" = ["D"]`). Self-documenting function names and readable assertions are preferred.
3. **Never Touch or Weaken `tests/architecture/test_boundaries.py`:**
   - If an import fails in `test_boundaries.py`, **do not alter the test to allow the import**. Instead, fix your code to respect the layer hierarchy (e.g. move domain logic out of infrastructure, or use `application.facade` instead of direct DB imports).
4. **Database & File Isolation:**
   - Always use `tmp_path` (or `pytest.MonkeyPatch`) when testing file persistence, DuckDB, or SQLite databases. Never write test outputs directly into production paths or repository roots.
5. **Network Call Prohibition:**
   - Tests must run 100% offline. Never make real HTTP/network calls (e.g. to `yfinance` or external market providers) during tests. Mock network boundaries or inject synthetic test fixtures.
6. **Deterministic Assertions:**
   - Avoid floating-point equality checks (`assert a == b`). Use `math.isclose()` or `pytest.approx()` with explicit tolerances when validating financial metrics (XIRR, CAGR, returns, tax amounts).
