# AGENTS.md — Testing Workspace Guidelines

> **Directory:** `tests/`  
> **Test Runner:** Pytest via Astral `uv` (`uv run pytest`)  
> **Target Python:** `>=3.13`

---

## 1. Test Suite Structure & Philosophy

The test suite is structured around architectural validation, forensic observability, and phased milestone regressions:

| Test Group | Key Files | What It Protects |
|---|---|---|
| **Architectural Boundaries** | `test_architecture_boundaries.py` | **Sacred Ground.** Enforces 7-layer clean architecture, AST-level forbidden import checks, package structure, and `Owns`/`Does not own` docstrings. |
| **Contracts & Primitives** | `test_phase1_contracts.py`, `test_data_transport.py`, `test_phase2_config_and_primitives.py`, `test_configuration_provenance.py` | Immutability, Pydantic configuration validation, deterministic identity, and data transport integrity. |
| **Infrastructure & Persistence** | `test_phase3_infrastructure.py`, `test_control_plane_observability.py` | DuckDB warehouse creation, SQLite Control Plane transactions, Raw Document Store, backup/restore. |
| **Ingestion & Extraction** | `test_phase4_extraction_and_ingestion.py`, `test_provider_worker_diagnostics.py` | File parsers (CSV/Excel), provider adapters, Pre-Bronze completeness checks. |
| **Domain & Financial Logic** | `test_phase5_canonical_domains.py`, `test_phase6_investments_and_quant.py`, `test_phase6_status_unification.py`, `test_phase7_tax_domain.py`, `test_phase8_household_wealth_fire.py` | FIFO lot matching, corporate actions, XIRR/CAGR math, tax schedules, net worth, Numba Monte Carlo FIRE simulations. |
| **Orchestration & Presentation** | `test_phase9_orchestration_and_bootstrap.py`, `test_phase10_presentation.py`, `test_presentation_narrative.py` | `ETLOrchestrator`, `ServiceContainer`, CLI arguments, CustomTkinter tabs, doc browser. |
| **Forensic Observability** | `test_observability_*.py`, `test_forensic_debuggability.py`, `test_redaction_and_retention.py`, `test_legacy_logging_demolition.py` | Event emitter fan-out, JSONL file traces, PII/PAN redaction, log retention. |
| **Constitutional Certification** | `test_phase11_legacy_demolition.py`, `test_phase12_constitutional_certification.py` | Guarantees legacy modules remain demolished and the complete financial engine adheres to product invariants. |

---

## 2. Test Execution Commands

Always run pytest via `uv`:

```powershell
# Run the complete test suite
uv run pytest

# Run architectural boundary enforcement tests (< 1 second)
uv run pytest tests/test_architecture_boundaries.py

# Run a specific test file with concise tracebacks
uv run pytest tests/test_phase6_investments_and_quant.py -v --tb=short

# Run tests matching a specific name pattern
uv run pytest -k "test_fifo"

# Run headless ETL execution profile
uv run python tests/run_headless.py
```

---

## 3. Test Authoring Rules for AI Agents

1. **Self-Documenting Test Names:**
   - Follow the naming pattern: `test_<feature_or_component>_<condition>_<expected_outcome>()`.
   - Per `ruff.toml`, docstrings are optional in `tests/` (`lint.per-file-ignores."tests/**" = ["D"]`). Self-documenting function names and readable assertions are preferred.
2. **Never Touch or Weaken `test_architecture_boundaries.py`:**
   - If an import fails in `test_architecture_boundaries.py`, **do not alter the test to allow the import**. Instead, fix your code to respect the layer hierarchy (e.g. move domain logic out of infrastructure, or use `application.facade` instead of direct DB imports).
3. **Database & File Isolation:**
   - Always use `tmp_path` (or `pytest.MonkeyPatch`) when testing file persistence, DuckDB, or SQLite databases. Never write test outputs directly into production paths or repository roots.
4. **Network Call Prohibition:**
   - Tests must run 100% offline. Never make real HTTP/network calls (e.g. to `yfinance` or external market providers) during tests. Mock network boundaries or inject synthetic test fixtures.
5. **Deterministic Assertions:**
   - Avoid floating-point equality checks (`assert a == b`). Use `math.isclose()` or `pytest.approx()` with explicit tolerances when validating financial metrics (XIRR, CAGR, returns, tax amounts).
