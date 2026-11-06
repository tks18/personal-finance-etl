# Phase 018 - Mapping and Normalization Engine

**Target release:** v9.8.1  
**Expected effort:** 3-4 hours  
**Previous:** Phase 017  
**Next:** Phase 019  
**Risk:** Medium-High

## 1. Outcome

Define the complete typed source-to-canonical mapping contract and bounded normalization vocabulary, then implement a deterministic Polars compiler/executor that can transform source-shaped frames into canonical-shaped frames in memory.

No production Bronze write path changes yet.

## 2. Why this phase exists

Source configuration is now production-loaded, but it cannot describe how arbitrary user columns become PFETL canonical evidence. `column_master.csv` proves PFETL already needs this concept; this phase generalizes it into typed configuration rather than arbitrary transformation code.

## 3. Inherited repository state

Phase 017 provides runtime `SourceConfiguration` and typed dataset selectors. Phase 007 provides identity strategy contracts, but identity execution is not yet connected to mappings.

Current household mapping semantics still come from `column_master.csv` and `get_column_mapping()`.

## 4. Current codebase anchors

Anchors:
- `application/ingestion/coordinator.py::get_column_mapping`
- `COLUMN_MASTER_PATH`
- household transforms consuming `mappings[...]`
- CSV provider extracting column master
- Phase-008 canonical Silver/Bronze target vocabulary
- current Polars casting/date helpers in domain/common/providers.

Trace existing source cleanup in CSV/Excel/SQLite providers; distinguish physical parsing from canonical normalization.

## 5. Exact target state after this phase

Typed configuration:
```text
ColumnMapping
  source_field
  canonical_field

NormalizationRule (discriminated)
  Cast
  ParseDate
  Trim
  NormalizeCase (bounded)
  Default/Constant
  NormalizeNull
```

Compiler input:
- SourceDatasetConfig;
- target canonical Bronze field vocabulary/schema metadata.

Compiler output:
```text
NormalizationPlan
  dataset_id
  ordered operations
  expected output fields
```

Executor:
`source-shaped LazyFrame/DataFrame -> canonical-shaped frame`

No arbitrary Python, eval, callbacks or SQL expressions.

## 6. Detailed implementation sequence

### Step 1 - Define mapping model
Validate unique canonical target unless contract explicitly permits merge semantics. Source fields may not map to arbitrary Silver/Gold names.

### Step 2 - Define normalization union
Each rule has typed operands/options. Reject unsupported cast/date format at config validation/compile time where possible.

### Step 3 - Define target-field vocabulary interface
Compiler must validate mapping targets against canonical Bronze contract metadata or a temporary target schema registry if Bronze schemas arrive later. Do not validate against Silver DDL.

### Step 4 - Implement compiler
Produce deterministic operation ordering. Mapping/normalization config order must not accidentally change semantics unless order is explicitly part of the rule contract.

### Step 5 - Implement Polars executor
Prefer lazy/vectorized expressions. Avoid Python row UDFs.

### Step 6 - Extract provider cleanup candidates
For one representative CSV and Excel dataset, identify cleanup currently inside provider functions that belongs in normalization. Do not migrate production provider behavior yet; create equivalent plan fixtures/tests.

### Step 7 - Error semantics
Missing required source field, invalid cast/date parse and unknown canonical target must return typed configuration/admission errors with dataset/source context.

### Step 8 - In-memory equivalence fixtures
Run current source-shaped samples through old cleanup/mapping and new plan; compare canonical values.

## 7. Files and symbols in scope

Create:
- mapping/normalization config modules;
- application compiler/executor service;
- typed errors/results;
- tests.

Read:
- provider extraction cleanup;
- household mapping consumers.

Do not modify Bronze persistence or production provider output.

## 8. Cross-cutting impacts

**Persistence:** none.

**Identity:** identity execution remains Phase 019.

**Provenance:** normalization must preserve runtime provenance metadata/columns needed later; mapping rules may not accidentally rename/drop provenance.

**Observability:** no production events yet; typed errors ready for later validation events.

**Performance:** compiler once per dataset/run; executor vectorized/lazy. Benchmark representative frame to reject row-wise design.

## 9. Tests and verification

Required:
- mapping target validation;
- duplicate/unknown mapping failures;
- each normalization rule tests valid/invalid cases;
- deterministic plan compilation;
- source column order does not change output;
- representative current household mapping equivalence;
- representative Excel cleanup equivalence;
- no Python row UDF in hot path;
- pipeline unchanged because executor is not production-wired.

## 10. Explicit non-goals

Do not:
- add arbitrary expression language;
- move financial transformations into mapping;
- execute identity generation;
- retire column_master yet;
- add Pandera;
- write Pre-Bronze/Bronze.

## 11. Completion checklist

- [x] Mapping model is typed.
- [x] Normalization vocabulary is bounded.
- [x] Compiler validates canonical targets.
- [x] Executor is deterministic/vectorized.
- [x] Typed errors identify source/dataset.
- [x] Current representative mappings can be reproduced.
- [x] No production persistence changed.

## 12. Commit boundary

```text
feat(ingestion): add mapping normalization engine
```

## 13. Handoff to Phase 019

Phase 019 may assume canonical normalization plans can be compiled/executed in memory. It will attach Phase-007 identity planning after normalization and encode all current `column_master.csv` mapping semantics into Shan SourceConfiguration.

## Phase completion record

```text
Phase: 018
Target release: v9.8.1
Files changed:
  - src/personal_finance_etl/contracts/canonical_fields.py
  - src/personal_finance_etl/contracts/__init__.py
  - src/personal_finance_etl/config/sources/mapping.py
  - src/personal_finance_etl/config/sources/normalization.py
  - src/personal_finance_etl/config/sources/model.py
  - src/personal_finance_etl/config/sources/loader.py
  - src/personal_finance_etl/config/sources/__init__.py
  - src/personal_finance_etl/application/normalization/errors.py
  - src/personal_finance_etl/application/normalization/models.py
  - src/personal_finance_etl/application/normalization/compiler.py
  - src/personal_finance_etl/application/normalization/executor.py
  - src/personal_finance_etl/application/normalization/__init__.py
  - tests/contracts/test_canonical_fields.py
  - tests/config/test_mapping_config.py
  - tests/config/test_source_selectors.py
  - tests/application/test_normalization_compiler.py
  - tests/application/test_normalization_executor.py
Schema changed: NO (In-memory configuration models and compiler/executor added; Bronze persistence unchanged)
Runtime behavior changed: NO (Active extraction/transformation unchanged; legacy coordinator preserved)
Financial formulas changed: NO
Focused tests: tests/contracts/test_canonical_fields.py, tests/config/test_mapping_config.py, tests/application/test_normalization_compiler.py, tests/application/test_normalization_executor.py (28/28 passed)
Architecture tests: tests/architecture/test_boundaries.py (11/11 passed)
Real-data run: N/A (Non-I/O in-memory engine)
Performance check: Sub-millisecond non-I/O compilation and vectorized native Polars execution
Compatibility path still present: YES (column_master.csv preserved in coordinator)
Old path deleted: NO (demolition scheduled for Phase 030/035)
Exit assertions green: YES
Commit: feat(ingestion): add mapping normalization engine
```

A phase is incomplete if any required exit assertion is false.
