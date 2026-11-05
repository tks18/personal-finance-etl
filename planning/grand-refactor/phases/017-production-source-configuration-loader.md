# Phase 017 - Production Source Configuration Loader

**Target release:** v9.8.0  
**Expected effort:** 3-4 hours  
**Previous:** Phase 016  
**Next:** Phase 018  
**Risk:** Medium

## 1. Outcome

Promote the declarative source topology built in Phases 002-005 from test/example models into a versioned production-loaded `SourceConfiguration`, including capability selection, while keeping the current fixed ingestion path active.

At phase end PFETL can load, validate and expose the complete Shan source configuration at runtime, but discovery/extraction still follows the legacy topology until later phases.

## 2. Why this phase exists

The architecture now has stable dataset/source/capability identities and a proven planner. The next prerequisite for generalized ingestion is a production configuration boundary. Loading configuration must be separated from consuming it so invalid configuration can be rejected before persistence changes.

## 3. Inherited repository state

Available:
- `SourceId`, `ProviderType`, `SourceConfig`, `SourceDatasetConfig`, typed selectors;
- declarative Shan topology fixture;
- explicit change policy model;
- Bronze identity strategy models;
- CapabilityIds and operational ExecutionPlan.

Still legacy:
- source paths in `Settings`;
- folder discovery;
- `_inject_configuration_assets`;
- `ExtractionCoordinator`;
- `ExtractionResult`;
- column mappings from `column_master.csv`.

## 4. Current codebase anchors

Current config ownership:
- `config/settings.py`: runtime + source paths + `FILE_HASH_POLICY` compatibility;
- `config/financial_rules/*`: financial policy;
- Phase-002/003 source config models;
- Phase-004 Shan topology fixture;
- bootstrap/container/facade loading paths;
- current CLI/Desktop config validation entry points.

Do not merge `FinancialRules` into source configuration.

## 5. Exact target state after this phase

Root production model conceptually:
```text
SourceConfiguration
  schema_version
  sources: tuple[SourceConfig, ...]
  datasets: tuple[SourceDatasetConfig, ...]
  capabilities: CapabilitySelection
```

Validation must cover:
- schema version supported;
- SourceId uniqueness;
- `(SourceId, DatasetId)` uniqueness;
- referenced source exists;
- selector/provider compatibility;
- policy validity;
- identity strategy structural validity;
- requested CapabilityIds valid.

Mapping completeness waits for Phases 018-019 because mapping contracts are not yet production-complete.

## 6. Detailed implementation sequence

### Step 1 - Freeze schema-version convention
Use an explicit configuration schema version independent of PFETL package version.

### Step 2 - Create loader
Load from the chosen supported serialization format already consistent with project configuration conventions. Avoid supporting multiple formats without need.

### Step 3 - Validate aggregate semantics
Implement cross-object validators listed above. Error messages must identify source/dataset and remediation.

### Step 4 - Promote Shan fixture to canonical example/runtime test config
It must represent every current external source and current full capability selection.

### Step 5 - Wire bootstrap loading
Load `Settings`, `FinancialRules`, and `SourceConfiguration` as three distinct objects. Inject source config into application boundary/planner but do not let ingestion consume it yet.

### Step 6 - Feed capability selection into planner
For Shan config request full-current capabilities. Preserve the Phase-016 optional-capability test through alternate test config.

### Step 7 - Add startup fingerprint placeholder
Canonical configuration fingerprint is Phase 020. For now ensure serialization order is deterministic enough to test round-trip, but do not persist an ad hoc hash.

### Step 8 - Implement the non-I/O SourcePlanner
Create the application-level `SourcePlanner` now, while source configuration is still additive. It must compile validated `SourceConfiguration` + the resolved `ExecutionPlan` + canonical dataset contracts into immutable `SourcePlan` / `DatasetPlan` objects without opening files or calling providers.

Each file-backed `DatasetPlan` must resolve at least:
- SourceId and DatasetId;
- ProviderType and physical location reference;
- typed selector;
- resolved change-detection policy;
- mapping/normalization plan reference where already defined or a typed unresolved placeholder owned by the later compiler phase;
- identity-strategy reference where already defined;
- canonical Bronze contract reference;
- enabled/required status from the ExecutionPlan.

Planner validation must fail for an enabled/required dataset that cannot be satisfied by the configuration. It must not perform I/O. Provider-generated evidence remains explicitly classified and is extended by `ProviderDatasetPlan` in Phase 034.

### Step 9 - Compatibility
Existing Settings source paths remain authoritative for actual ingestion. Add an assertion/test that Shan SourceConfiguration paths/selectors correspond to current Settings topology so drift is visible during transition. The newly compiled SourcePlan is diagnostic/dormant until the first vertical cutover.

## 7. Files and symbols in scope

Create/modify:
- `config/sources` root model/loader;
- bootstrap/container/facade wiring;
- capability selection config;
- canonical Shan config fixture/example;
- validation tests.

Do not modify providers, Bronze or Control Plane schema.

## 8. Cross-cutting impacts

**Persistence:** none.

**Identity:** validates strategy structure only; no runtime ID generation.

**Observability:** startup may report schema version/source/dataset counts, not raw paths/secrets.

**Performance:** configuration-scale only.

**Compatibility:** fixed ingestion remains authoritative; dual representation is intentional and checked.

## 9. Tests and verification

Required:
- round-trip configuration;
- unsupported schema version fails;
- duplicate SourceId fails;
- duplicate source/dataset binding fails;
- selector/provider mismatch fails;
- invalid capability fails;
- invalid policy/identity structure fails;
- Shan config covers current topology;
- SourcePlanner produces one deterministic DatasetPlan for every required configured file-backed dataset;
- SourcePlanner performs no I/O;
- missing required dataset fails during planning;
- planner receives full-current selection;
- current pipeline outputs unchanged.

## 10. Explicit non-goals

Do not:
- migrate discovery/extraction;
- remove source paths from Settings;
- implement mappings;
- persist configuration fingerprint;
- add Pre-Bronze/Pandera.

## 11. Completion checklist

- [x] Versioned root configuration loads in production bootstrap.
- [x] Settings/FinancialRules/SourceConfiguration remain separate.
- [x] Cross-object validation is complete.
- [x] Shan topology is represented.
- [x] Capability selection feeds planner.
- [x] SourcePlanner compiles deterministic non-I/O DatasetPlans.
- [x] Required configured datasets are satisfiable at planning time.
- [x] Fixed ingestion still owns runtime source access.
- [x] Pipeline behavior unchanged.

## 12. Commit boundary

```text
feat(config): load versioned source configuration
```

## 13. Handoff to Phase 018

Phase 018 may assume a validated `SourceConfiguration` is available at runtime and a deterministic non-I/O `SourcePlanner` can compile required file-backed DatasetPlans. It will define and execute bounded source-to-canonical mappings entirely in memory, still without changing persistence or ingestion topology.

## Phase completion record

```text
Phase: 017
Target release: v9.8.0
Files changed:
  - src/personal_finance_etl/config/sources/loader.py
  - src/personal_finance_etl/config/sources/__init__.py
  - src/personal_finance_etl/application/pipeline/source_planner.py
  - src/personal_finance_etl/application/pipeline/__init__.py
  - src/personal_finance_etl/application/pipeline/orchestrator.py
  - src/personal_finance_etl/application/facade.py
  - src/personal_finance_etl/bootstrap/container.py
  - src/personal_finance_etl/contracts/execution_plan.py
  - tests/fixtures/sources.toml
  - tests/conftest.py
  - tests/config/test_source_configuration.py
  - tests/application/test_source_planner.py
  - planning/grand-refactor/phases/017-production-source-configuration-loader.md
  - planning/grand-refactor/README.md
Schema changed: NO (configuration schema v1.0.0 introduced; warehouse DDL unchanged)
Runtime behavior changed: NO (fixed ingestion paths preserved; source configuration and planning run additively alongside execution plan)
Financial formulas changed: NO
Focused tests: tests/config/test_source_configuration.py (11 passed), tests/application/test_source_planner.py (7 passed)
Architecture tests: tests/architecture/test_boundaries.py (11 passed)
Real-data run: YES (live pipeline E2E passed with full plan)
Performance check: PASS (fast audit in 1.10s; full quality gate across 6 engines in 79.39s)
Compatibility path still present: YES (fallback to get_shan_baseline_source_configuration when sources.toml omitted)
Old path deleted: N/A
Exit assertions green: YES (all 368 tests passing; 6/6 quality engines green)
Commit: pending user confirmation
```

A phase is incomplete if any required exit assertion is false.
