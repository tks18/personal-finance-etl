# Phase 01 — OperatorService Dependency Cleanup

**Sprint:** 2–3 hours  
**Goal:** keep the Phase-13 operator capability, but move concrete DB/network/filesystem inspection out of `application/operator.py`.

## Current implementation anchors

`src/personal_finance_etl/application/operator.py` currently owns both application models/use-case flow and infrastructure mechanics. It imports `sqlite3`, `duckdb`, `urllib.request`, `FileLock`, `PreferencesManager`, and executes SQL against `cp_runs` / `cp_sync_summaries`.

Existing public behavior to preserve:

- `SystemStatus`
- `SystemInfo`
- `DoctorCheckResult`
- `DoctorReport`
- `OperatorService.get_status()`
- `OperatorService.get_info()`
- `OperatorService.run_doctor()`
- façade methods in `application/facade.py`
- CLI `status`, `info`, `doctor`

## Target shape

Create a narrow cross-layer inspection contract and one infrastructure implementation:

```text
contracts/operator.py
  OperatorInspector protocol
  immutable inspection result records only if needed

application/operator.py
  SystemStatus / SystemInfo / Doctor models
  OperatorService orchestration and interpretation
  NO sqlite3/duckdb/urlopen/FileLock/raw SQL

infrastructure/operator/
  __init__.py
  inspector.py
    LocalOperatorInspector

bootstrap/container.py
  create_operator_inspector()
  create_operator_service(...)
```

Do not create separate repositories for every check.

## Implementation steps

1. Extract from `OperatorService` these concrete operations into `LocalOperatorInspector`:
   - discover recent/default config/rules paths through `PreferencesManager`;
   - inspect pipeline lock;
   - inspect DuckDB/Raw Store file existence and sizes;
   - read latest Control Plane run and sync summary;
   - count stale/recovery-required runs;
   - inspect warehouse schemas/table inventory if current `get_info` does so;
   - probe provider connectivity.
2. Define only the minimum protocol methods needed by the application service. Prefer cohesive methods such as `inspect_runtime(...)`, `inspect_control_plane(...)`, `probe_provider(...)`; do not mirror every SQL statement as a method.
3. Keep Settings/FinancialRules parsing decisions in `OperatorService`; concrete file access may be delegated if it avoids infrastructure imports.
4. Inject the inspector through `ServiceContainer`.
5. Update `PersonalFinanceEngine` to resolve the operator service through its container when available. Preserve fallback construction for direct/test use only if needed.
6. Remove direct imports of `sqlite3`, `duckdb`, `urllib.request`, `FileLock`, and `PreferencesManager` from `application/operator.py`.
7. Preserve user-facing doctor messages and remediation language unless the old text exposes a moved implementation detail incorrectly.

## Tests for this phase

Before the Phase-2 test demolition, use the existing Phase-13 tests as a temporary regression check. Add or adapt a focused assertion that:

- `application/operator.py` no longer imports the concrete infrastructure libraries above;
- status/info/doctor still return the same dataclass types;
- inspector read operations are read-only;
- CLI behavior is unchanged.

Do not build a new permanent architecture certification file here; Phase 2 replaces the test suite.

## Non-goals

- no Control Plane schema changes;
- no CLI redesign;
- no GUI work yet;
- no new operator metrics;
- no REST/service layer;
- no generic repository hierarchy.

## Exit criteria

- `application/operator.py` is application orchestration only;
- direct persistence/network/file-lock mechanics live under `infrastructure/operator`;
- bootstrap is the composition point;
- `pfetl status`, `pfetl info`, `pfetl doctor` remain behaviorally equivalent;
- current test suite passes before Phase 2 deletes/replaces it.
