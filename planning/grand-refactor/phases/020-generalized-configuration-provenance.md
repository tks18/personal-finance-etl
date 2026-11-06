# Phase 020 - Generalized Configuration Provenance

**Target release:** v9.8.3  
**Expected effort:** 3-4 hours  
**Previous:** Phase 019  
**Next:** Phase 021  
**Risk:** Medium

## 1. Outcome

Define deterministic canonical serialization/fingerprinting for the complete generalized SourceConfiguration and persist the snapshot/fingerprint with each run using existing Control Plane provenance patterns. Extend observability with bounded configuration identity.

This phase closes configuration architecture before any new persistence layer is introduced.

## 2. Why this phase exists

Pre-Bronze and future replay must know not merely which files were received but exactly which mapping, identity, change-detection and capability configuration interpreted them. Without this provenance, changing configuration between runs could silently reinterpret evidence.

## 3. Inherited repository state

Phase 019 guarantees SourceConfiguration now fully represents:
- sources and provider types;
- dataset selectors;
- change policies;
- mappings;
- normalization;
- identity strategies;
- capability selection.

`FinancialRules` remains a separate existing snapshot/fingerprint.

Current Control Plane already persists settings/rules snapshots and run provenance patterns.

## 4. Current codebase anchors

Anchors:
- Control Plane schema tables for settings/rules snapshots and runs
- lifecycle initialization/run creation
- existing settings/rules fingerprint code
- observability `ObservabilityContext` settings/rules fingerprints
- Phase-017 source configuration loader
- Phase-015 execution-plan fingerprint.

## 5. Exact target state after this phase

Canonical source-configuration provenance consists of:
```text
source_config_schema_version
source_config_fingerprint
canonical source_config snapshot/reference
execution_plan_fingerprint
```

Fingerprint includes semantic configuration:
- SourceIds/provider/location references as appropriate;
- dataset selectors;
- mapping/normalization;
- identity strategies;
- change policies;
- capability selection.

Canonical serialization rules:
- deterministic key ordering;
- deterministic collection ordering where order is semantically irrelevant;
- preserve order where normalization operation order is semantic;
- exclude ephemeral runtime values;
- no secrets/raw payloads.

`FinancialRules` fingerprint remains separate.

## 6. Detailed implementation sequence

### Step 1 - Define canonical serialization
Use Pydantic/model serialization plus explicit canonicalization. Add tests proving semantically equivalent unordered config yields same fingerprint while semantic changes alter it.

### Step 2 - Define fingerprint algorithm/version
Use existing project hashing convention where suitable. Include schema/fingerprint version so future canonicalization changes are explicit.

### Step 3 - Add Control Plane snapshot persistence
Prefer normalized snapshot/reference pattern consistent with existing settings/rules tables. Additive migration only.

Store one snapshot per unique fingerprint where current design supports deduplication; runs reference fingerprint/snapshot.

### Step 4 - Attach to run lifecycle
At run creation/initialization, persist/resolve source config snapshot and associate fingerprint with run.

### Step 5 - Persist ExecutionPlan relationship
Record plan fingerprint/resolved capability selection without duplicating the whole graph on every artifact.

### Step 6 - Extend observability context
Add bounded source-config fingerprint and plan fingerprint at run context. SourceId/DatasetId remain operation-level context later.

### Step 7 - Detect configuration change
Compare current fingerprint to previous successful run and record that it changed. Do not yet implement automatic replay/rebuild; Phase 044 owns replay semantics.

### Step 8 - Regression
Existing settings/rules provenance remains intact and separately queryable.

## 7. Files and symbols in scope

Modify:
- source configuration canonicalization/fingerprint module;
- Control Plane schema/repository with additive migration if needed;
- lifecycle/run repository;
- observability context;
- tests.

Do not alter Raw payload or warehouse schema.

## 8. Cross-cutting impacts

**Persistence:** additive SQLite Control Plane provenance. Migration must preserve existing databases and historical runs.

**Identity:** configuration fingerprint is not financial identity.

**Observability:** add fingerprints, not full configuration payload.

**Performance:** hash once per run; snapshot config-scale only.

**Privacy:** avoid emitting source absolute paths or sensitive configuration into JSONL unless existing policy explicitly permits it. Fingerprint is preferred context.

## 9. Tests and verification

Required:
- canonical serialization deterministic;
- reordered semantically unordered collections same fingerprint;
- mapping/identity/policy/capability semantic change changes fingerprint;
- normalization order change changes fingerprint when order matters;
- snapshot persists and run references it;
- old Control Plane DB migrates additively;
- settings/rules fingerprints remain separate;
- observability contains bounded fingerprints;
- previous-run change detection recorded;
- current Shan financial outputs unchanged.

## 10. Explicit non-goals

Do not:
- trigger automatic rebuild on config change;
- add Pre-Bronze;
- move Raw Store;
- merge FinancialRules into source config;
- store full config in every event;
- redesign observability.

## 11. Completion checklist

- [x] Complete SourceConfiguration has deterministic fingerprint.
- [x] Fingerprint version/schema explicit.
- [x] Snapshot persisted in Control Plane.
- [x] Run references exact source config.
- [x] ExecutionPlan fingerprint linked.
- [x] Config changes detected, not auto-remediated.
- [x] Observability context bounded.
- [x] Existing settings/rules provenance preserved.
- [x] Current pipeline outputs unchanged.

## 12. Commit boundary

```text
feat(control-plane): persist source configuration provenance
```

## 13. Handoff to Phase 021

Phase 021 may assume every run has a validated, fully expressive and fingerprinted generalized configuration plus a resolved ExecutionPlan. It can introduce the `pre_bronze` DuckDB layer without reopening source/configuration semantics.

Still intentionally present after Phase 020:
- fixed production discovery/extraction;
- `ExtractionResult`;
- `column_master` production path;
- no Pandera;
- no production generalized admission;
- current Bronze remains authoritative.

## Phase completion record

```text
Phase: 020
Target release: v9.8.3
Files changed:
  - src/personal_finance_etl/config/sources/fingerprint.py (created)
  - src/personal_finance_etl/config/sources/__init__.py
  - src/personal_finance_etl/contracts/observability.py
  - src/personal_finance_etl/infrastructure/observability/emitter.py
  - src/personal_finance_etl/infrastructure/control_plane/schema.py
  - src/personal_finance_etl/infrastructure/control_plane/run_repository.py
  - src/personal_finance_etl/application/pipeline/lifecycle.py
  - src/personal_finance_etl/application/pipeline/orchestrator.py
  - tests/config/test_source_config_fingerprint.py (created)
  - tests/infrastructure/test_source_config_provenance.py (created)
Schema changed: YES (additive cp_source_config_snapshots table and cp_runs.source_config_snapshot_id column)
Runtime behavior changed: NO (backward-compatible snapshotting, ambient provenance context propagation, non-remediating change notification)
Financial formulas changed: NO
Focused tests: 14 passed (tests/config/test_source_config_fingerprint.py, tests/infrastructure/test_source_config_provenance.py)
Architecture tests: 11 passed (tests/architecture/test_boundaries.py)
Real-data run: N/A
Performance check: <0.6s test run, <1ms SHA-256 fingerprinting per execution run
Compatibility path still present: YES (default fallback to Shan baseline if source_config omitted)
Old path deleted: NO
Exit assertions green: YES (100% pass across all 6 quality engines: Ruff, Mypy, Pyright, Pylint, Pytest 426/426)
Commit: Pending user approval
```

A phase is incomplete if any required exit assertion is false.
