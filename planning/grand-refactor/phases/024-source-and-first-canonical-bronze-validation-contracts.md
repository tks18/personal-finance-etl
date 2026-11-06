# Phase 024 - Source and First Canonical Bronze Validation Contracts

**Target release:** v9.9.3  
**Expected effort:** 3-4 hours  
**Previous:** Phase 023  
**Next:** Phase 025  
**Risk:** Medium-High

## 1. Outcome

Select the exact low-risk dataset for the first production vertical migration, compile its SourceDatasetConfig into a source/Pandera contract, and define its PFETL-owned canonical Bronze schema including types, nullability, grain, identity and uniqueness.

At phase end both trust gates are executable in memory for the selected dataset.

## 2. Why this phase exists

Phase 025 must be a migration exercise, not a schema-design exercise. Both source and canonical contracts must be frozen and tested before the first production path is rewired.

## 3. Inherited repository state

Phase 023 provides the validation adapter. Phase 019 provides normalization/identity composition. Phase 021/022 provide operational Pre-Bronze.

No production source has migrated.

## 4. Current codebase anchors

Use the Phase-004 source topology and 20-row Bronze ledger to choose the first dataset.

Selection criteria:
- externally sourced current dataset;
- small schema;
- low downstream financial blast radius;
- no provider-generated market complexity;
- preferably full-replace or simple sync semantics;
- current downstream equivalence easy to assert.

Do not choose a transaction-heavy investment dataset merely to be ambitious.

Anchors for chosen dataset:
- current `ExtractionResult` field;
- sync category;
- Bronze table/contract;
- provider extractor;
- current transform consumer;
- source config/selector/mapping/identity policy.

## 5. Exact target state after this phase

Two distinct contracts:

### Source contract
Generated from user config:
- required source fields;
- declared/coercible source types;
- source nullability;
- source uniqueness only if configured/meaningful.

It validates what the user claimed.

### Canonical Bronze contract
PFETL-owned:
- exact canonical fields;
- canonical Polars/Pandera types;
- nullability;
- canonical row grain;
- Phase-007 identity requirement;
- uniqueness;
- bounded evidence invariants.

User cannot weaken it.

The selected dataset and rationale are recorded in the phase file implementation notes/tests so Phase 025 has no ambiguity.

## 6. Detailed implementation sequence

### Step 1 - Select dataset and record exact current route
Write the route in test/docstring:
`discovery -> category -> provider -> ExtractionResult.<field> -> Bronze table -> downstream consumer`.

### Step 2 - Extend SourceDatasetConfig schema declaration
If source field/type/nullability declarations are not yet represented, add the minimum typed model required to compile source validation.

### Step 3 - Implement source-contract compiler
Compile selected dataset config into Pandera schema. Unknown/missing declaration fails before extraction/admission.

### Step 4 - Define canonical Bronze schema
Add PFETL-owned schema metadata for selected DatasetId. Do not derive canonical requirements from the user's source declaration.

### Step 5 - Integrate identity/grain rules
If identity REQUIRED, assert normalized fields/strategy satisfy it. If NONE, explicitly test no synthetic ID.

### Step 6 - In-memory happy path
source-shaped fixture -> source validation -> normalization -> identity -> Bronze validation.

### Step 7 - Freeze empty-dataset semantics
For the selected DatasetId, explicitly declare whether a configured-but-zero-row dataset is valid. Test the distinction between:
- dataset absent/not configured;
- configured dataset with zero rows;
- configured dataset with malformed rows.

A valid empty dataset must preserve its schema and must not be treated as a missing required DatasetId. If the canonical financial contract requires at least one row, encode that invariant explicitly rather than relying on downstream failure.

### Step 8 - In-memory failure matrix
Missing source column, bad type, invalid date/cast, missing canonical field, null violation, uniqueness/identity violation.

### Step 9 - Observability/error contract
Ensure each failure says SOURCE vs BRONZE stage and remediation.

## 7. Files and symbols in scope

Modify:
- source schema declaration/config;
- source-contract compiler;
- canonical Bronze schema registry for selected dataset;
- validation tests;
- selected dataset fixture.

Do not wire provider/persistence production path yet.

## 8. Cross-cutting impacts

**Persistence:** none.

**Identity:** selected dataset follows Phase-007 requirement exactly.

**Provenance:** source/artifact metadata survives normalization and is not treated as canonical financial columns.

**Observability:** validation stage/contract IDs tested.

**Performance:** validate representative row count for selected dataset within acceptable overhead from Phase-023 benchmark.

## 9. Tests and verification

Required:
- selected dataset/rationale explicit;
- source contract generated from config;
- Bronze contract independent/PFETL-owned;
- happy path passes both gates;
- source failures fail at source stage;
- canonical failures fail at Bronze stage;
- identity/uniqueness rules enforced;
- absent vs valid-empty vs malformed semantics tested;
- user cannot omit/weaken canonical field;
- no production runtime change.

## 10. Explicit non-goals

Do not:
- define all Bronze schemas;
- migrate the dataset;
- add arbitrary source constraints to canonical contract;
- change downstream financial transformation;
- delete legacy Bronze contract.

## 11. Completion checklist

- [x] First migration dataset is frozen.
- [x] Exact legacy route documented.
- [x] Source schema compiles from config.
- [x] Canonical Bronze schema exists.
- [x] Both gates execute in memory.
- [x] Failure stages/remediation are precise.
- [x] Identity/grain semantics enforced.
- [x] Empty-dataset semantics explicit and tested.
- [x] Production path unchanged.

## 12. Commit boundary

```text
feat(validation): define first admission contracts
```

## 13. Handoff to Phase 025

Phase 025 may assume every component of the final vertical path already exists independently: source config/selector/change policy, provider, validation adapter, Pre-Bronze, normalization, identity and canonical Bronze contract. Its job is solely to wire one real dataset through them and delete that dataset's legacy route after equivalence.

## Phase completion record

```text
Phase: 024 - Source and First Canonical Bronze Validation Contracts
Target release: v9.9.3
Files changed:
  - src/personal_finance_etl/config/sources/model.py
  - src/personal_finance_etl/config/sources/loader.py
  - src/personal_finance_etl/config/sources/__init__.py
  - src/personal_finance_etl/infrastructure/validation/compiler.py
  - src/personal_finance_etl/infrastructure/validation/canonical_schemas.py
  - src/personal_finance_etl/infrastructure/validation/__init__.py
  - tests/config/test_source_selectors.py
  - tests/infrastructure/test_admission_contracts.py
Schema changed: NO
Runtime behavior changed: NO
Financial formulas changed: NO
Focused tests: 20 passed (tests/config/test_source_selectors.py, tests/infrastructure/test_admission_contracts.py)
Architecture tests: 12 passed (tests/architecture/test_boundaries.py)
Real-data run: N/A (in-memory contracts phase; production wiring in Phase 025)
Performance check: Dual-gate in-memory validation executes in 0.16s across 10 scenarios
Compatibility path still present: YES (legacy Gatekeeper and BronzeLayer completely untouched)
Old path deleted: NO (Phase 025 owns vertical slice wiring and legacy route deprecation)
Exit assertions green: YES (Ruff Check, Ruff Format, Mypy, Pyright, Pylint, Pytest all 100% green)
Commit: [pending user confirmation]
```

A phase is incomplete if any required exit assertion is false.
