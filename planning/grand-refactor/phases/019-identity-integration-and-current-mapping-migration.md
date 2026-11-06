# Phase 019 - Identity Integration and Current Mapping Migration

**Target release:** v9.8.2  
**Expected effort:** 3-4 hours  
**Previous:** Phase 018  
**Next:** Phase 020  
**Risk:** Medium-High

## 1. Outcome

Integrate Bronze identity planning/execution after canonical normalization and migrate the complete semantic content of `column_master.csv` into Shan's typed SourceConfiguration, proving equivalence while leaving the legacy production path intact.

At phase end the generalized in-memory admission pipeline can perform:
`source frame -> normalization -> identity resolution -> canonical-shaped frame` for current configured mappings.

## 2. Why this phase exists

Phase 018 produces canonical fields; identity strategies must operate on normalized canonical values, not raw vendor spellings. Before Pre-Bronze is introduced, the complete current household mapping system must be representable in the new configuration so `column_master.csv` can later be retired safely.

## 3. Inherited repository state

Available:
- Phase-007 identity requirement/strategy/compiler/executor;
- Phase-018 normalization compiler/executor;
- runtime SourceConfiguration;
- current `column_master.csv` still drives production household transforms.

No production Bronze identity generation occurs yet.

## 4. Current codebase anchors

Anchors:
- `COLUMN_MASTER_PATH`
- CSV column-master extraction
- `application/ingestion/coordinator.py::get_column_mapping`
- mapping keys `category`, `asset_group`, `assets`, `currency`, `inoutcome`, `opbal`
- household transforms consuming these mappings
- current SQLite stable IDs
- Phase-007 Bronze identity requirement registry.

## 5. Exact target state after this phase

For every configured dataset:
```text
source frame
  -> NormalizationPlan
  -> canonical fields
  -> IdentityPlanCompiler
  -> preserve trusted source ID OR derive deterministic Bronze ID if REQUIRED
  -> collision/uniqueness check
  -> canonical admission frame
```

Shan SourceConfiguration contains mappings equivalent to every current `column_master.csv` entry needed by production.

The old column-master path remains active until generalized ingestion cutover, but it is no longer semantically unique.

## 6. Detailed implementation sequence

### Step 1 - Define admission composition service
Compose normalization then identity. Keep compiler/executor responsibilities separated and testable.

### Step 2 - Preserve trusted source IDs
For current SQLite household datasets, configure source-field identity using existing stable UID/ZUID fields where the Bronze contract requires them. Do not regenerate different IDs.

### Step 3 - Derived-ID fixture
Use a non-production Excel/CSV household fixture lacking IDs and prove deterministic derived identity.

### Step 4 - Collision validation
Run uniqueness check after identity creation for REQUIRED datasets. Fail with bounded diagnostics.

### Step 5 - Translate column_master
Generate/author typed mapping configuration for all current table mappings. Compare every `(TABLE_NAME, OLD_COLUMN, NEW_COLUMN)` semantic mapping to the new config.

### Step 6 - Equivalence test
For current household source samples:
- old `get_column_mapping` + transform mapping;
- new normalization config;
must yield identical canonical column names/values before financial transformation.

### Step 7 - Mark compatibility ownership
Document/test that production still reads column_master until later source migration. Add a test preventing new mapping semantics from being added only to column_master without corresponding SourceConfiguration during transition.

### Step 8 - Update Shan config validation
Every Bronze REQUIRED identity dataset has a valid strategy and all strategy fields exist after normalization.

## 7. Files and symbols in scope

Modify:
- admission/identity integration service;
- Shan SourceConfiguration;
- mapping compatibility tests;
- identity tests.

Do not delete `column_master.csv`, its Bronze contract, or current coordinator mapping yet.

## 8. Cross-cutting impacts

**Persistence:** none.

**Identity:** current trusted household IDs must remain identical; derived fixture IDs deterministic; protected downstream financial IDs unchanged.

**Provenance:** admission composition preserves provenance metadata.

**Observability:** no production admission events yet.

**Performance:** identity generation must be vectorized/batched appropriately; no Python per-row hashing if existing canonical identity utilities support expression/vector patterns. Measure fixture if necessary.

## 9. Tests and verification

Required:
- trusted source IDs preserved;
- derived IDs stable across repeated runs/order;
- collisions fail;
- every current column-master mapping represented in typed config;
- mapping equivalence for all mapping groups;
- missing identity field fails before persistence;
- protected financial IDs unchanged;
- current production pipeline unchanged.

## 10. Explicit non-goals

Do not:
- remove column_master runtime path;
- write canonical Bronze through new admission service;
- change current SQLite IDs;
- create investment Bronze IDs where requirement is NONE;
- add Pre-Bronze/Pandera.

## 11. Completion checklist

- [x] Normalization -> identity composition is explicit.
- [x] Trusted household IDs preserved.
- [x] External no-ID fixture derives stable IDs.
- [x] Collision detection works.
- [x] Column-master semantics fully represented in config.
- [x] Transition parity guard exists.
- [x] No production persistence changed.

## 12. Commit boundary

```text
feat(ingestion): integrate canonical identity planning
```

## 13. Handoff to Phase 020

Phase 020 may assume the complete generalized configuration semantics now exist: sources, selectors, change policy, mappings, normalization, identity and capabilities. It will fingerprint and persist this exact configuration so later Pre-Bronze/replay behavior can prove which interpretation produced a run.

## Phase completion record

```text
Phase: 019 - Identity Integration and Current Mapping Migration
Target release: v9.8.2
Files changed:
  - src/personal_finance_etl/contracts/canonical_fields.py
  - src/personal_finance_etl/config/sources/loader.py
  - src/personal_finance_etl/application/ingestion/admission.py
  - src/personal_finance_etl/application/ingestion/__init__.py
  - tests/fixtures/sources.toml
  - tests/fixtures/COLUMN_MASTER.csv
  - tests/config/test_column_master_parity.py
  - tests/application/test_admission_service.py
  - .gitignore
Schema changed: NO (configuration and contracts expanded)
Runtime behavior changed: NO (pipeline paths preserved, admission service additive)
Financial formulas changed: NO
Focused tests: tests/application/test_admission_service.py, tests/config/test_column_master_parity.py
Architecture tests: tests/architecture/test_boundaries.py
Real-data run: N/A (non-I/O admission planning and mapping migration)
Performance check: Admission execution and parity validation runs in <0.10s
Compatibility path still present: YES (legacy column_master reading in coordinator remains active)
Old path deleted: NO
Exit assertions green: YES
Commit: pending
```

A phase is incomplete if any required exit assertion is false.
