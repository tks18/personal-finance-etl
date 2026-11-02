# Phase 026 - Typed DatasetCollection Introduction

**Target release:** v9.9.5  
**Expected effort:** 3-4 hours  
**Previous:** Phase 025  
**Next:** Phase 027  
**Risk:** Medium

## 1. Outcome

Introduce the typed `DatasetCollection` runtime transport beside `ExtractionResult` and make Bronze full-state reconstruction available by stable `DatasetId`, without migrating all consumers yet.

At phase end both transports coexist intentionally. The new collection is complete enough that Phase 027 can migrate consumers one by one without changing ingestion or financial semantics.

## 2. Why this phase exists

`ExtractionResult` statically enumerates the current dataset universe and therefore makes configurable ingestion impossible to finish cleanly. Phase 025 proved one generalized dataset, but keeping a fixed DTO would force every future configured dataset back through a Python field declaration.

The replacement must be additive first because `ExtractionResult` is load-bearing across Bronze, Transformer, investment strategies, coordinator and executor.

## 3. Inherited repository state

Phase 025 guarantees:
- one production dataset uses the final generalized vertical path;
- Phase-025 migration template is frozen for later datasets;
- the other datasets remain legacy;
- `ExtractionResult` still exists for full-state/runtime compatibility;
- stable `DatasetId` and registry lookups already exist.

## 4. Current codebase anchors

Historical/current anchors to inspect before implementation:
- `contracts/extraction.py::ExtractionResult`
- `infrastructure/warehouse/bronze.py::get_full_dataset`
- `application/ingestion/coordinator.py`
- `application/pipeline/transformer.py`
- `application/ingestion/asset_strategies.py`
- `application/pipeline/execution.py`
- all construction sites using `ExtractionResult(...)`
- all attribute reads such as `result.zcategory`, `result.mf_transactions_raw`, etc.

Use repository-wide symbol search against the current post-Phase-025 branch before coding; the exact reference list is part of the phase completion record.

## 5. Exact target state after this phase

Create an immutable/controlled runtime collection conceptually:

```text
DatasetCollection
  frames: DatasetId -> LazyFrame | DataFrame
  metadata: DatasetId -> DatasetRuntimeMetadata

require(dataset_id) -> frame
get(dataset_id) -> frame | None
contains(dataset_id) -> bool
dataset_ids() -> immutable collection
```

Rules:
- callers cannot mutate the underlying mapping accidentally;
- unknown required dataset raises a typed, contextual error;
- optional lookup is explicit;
- source mappings/configuration are not smuggled into the frame collection;
- metadata references source/artifact/configuration provenance without duplicating Control Plane state.

A compatibility adapter converts current `ExtractionResult` to `DatasetCollection` and, only where unavoidable during this phase, vice versa. The adapter is temporary and has a named deletion target: Phase 027.

## 6. Detailed implementation sequence

### Step 1 - Inventory current `ExtractionResult`
Record every field, type and production consumer on the post-Phase-025 branch. Classify fields as canonical dataset frames versus non-frame metadata/mappings.

### Step 2 - Define `DatasetRuntimeMetadata`
Minimum fields should reuse already-defined identifiers:
- DatasetId;
- SourceId where externally sourced;
- artifact/provenance references;
- configuration fingerprint/reference if needed.
Do not duplicate mapping rules or whole config objects.

### Step 3 - Define `DatasetCollection`
Use a read-only mapping or encapsulated private mapping. Enforce supported Polars frame types.

### Step 4 - Implement explicit accessors
`require()` raises a typed missing-dataset error naming DatasetId and, where available, ExecutionPlan/capability context. `get()` is the only optional path.

### Step 5 - Build compatibility adapter
Map each legacy `ExtractionResult` field to its Phase-001 DatasetId. Add a coverage assertion so a new/removed legacy field cannot silently escape the adapter.

### Step 6 - Extend Bronze full-state reconstruction
`BronzeLayer.get_full_dataset()` or its successor must be able to construct/return `DatasetCollection` keyed by DatasetId. During coexistence, preserve the legacy result API for unmigrated consumers.

### Step 7 - Integrate Phase-025 generalized dataset
Ensure the already-migrated dataset appears in the same collection as legacy Bronze datasets. Consumers must not need to know which ingestion architecture produced a frame.

### Step 8 - Add collection invariants
Reject duplicate DatasetId insertion, unsupported frame types and metadata/frame mismatches.

### Step 9 - Prove zero financial change
Run Transformer/engines through legacy path while independently asserting collection content equality for all current datasets.

## 7. Files and symbols in scope

Create/modify:
- `contracts/dataset_collection.py` or equivalent;
- typed dataset errors/metadata;
- `contracts/extraction.py` compatibility adapter;
- `warehouse/bronze.py` full-state reconstruction;
- registry mapping helpers;
- tests.

Read only in this phase:
- Transformer;
- asset strategies;
- PipelineExecutor/coordinator consumers that Phase 027 will migrate.

## 8. Cross-cutting impacts

**Persistence:** none. Bronze physical tables unchanged.

**Identity:** DatasetId is transport identity, not row identity.

**Provenance:** runtime metadata references canonical provenance; do not add path strings.

**Observability:** missing required DatasetId errors may carry DatasetId/plan context through existing error machinery.

**Performance:** collection construction must not collect LazyFrames or copy full frames. It is a metadata/mapping operation.

**Compatibility:** `ExtractionResult` remains supported until Phase 027.

## 9. Tests and verification

Required:
- every current legacy frame maps to exactly one DatasetId;
- adapter coverage equals current `ExtractionResult` frame universe;
- `require()`/`get()` semantics tested;
- duplicate/unknown/type errors tested;
- Bronze full-state collection contains same frames/schema as legacy result;
- Phase-025 migrated dataset appears normally;
- no eager collection introduced;
- full Shan financial run unchanged.

## 10. Explicit non-goals

Do not:
- migrate Transformer/asset strategies/executor yet;
- delete `ExtractionResult`;
- change source ingestion;
- migrate another dataset;
- change Bronze DDL;
- alter mappings/financial formulas.

## 11. Completion checklist

- [ ] DatasetCollection exists and is typed.
- [ ] Runtime metadata is bounded.
- [ ] Legacy adapter covers every current field.
- [ ] Bronze can reconstruct collection by DatasetId.
- [ ] Migrated and legacy datasets coexist transparently.
- [ ] No frame materialization/copy regression.
- [ ] `ExtractionResult` intentionally remains.
- [ ] Full pipeline unchanged.

## 12. Commit boundary

```text
feat(contracts): add typed dataset collection
```

## 13. Handoff to Phase 027

Phase 027 may assume `DatasetCollection` is a complete representation of the current full Bronze dataset universe and that an adapter preserves legacy behavior. Phase 027 must migrate every production consumer and delete the compatibility DTO only after zero-reference proof.

## Phase completion record

```text
Phase:
Target release:
Files changed:
Schema changed:
Runtime behavior changed:
Financial formulas changed: NO
Focused tests:
Architecture tests:
Real-data run:
Performance check:
Compatibility path still present:
Old path deleted:
Exit assertions green:
Commit:
```

A phase is incomplete if any required exit assertion is false.
