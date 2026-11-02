# Phase 027 - DatasetCollection Consumer Migration and ExtractionResult Demolition

**Target release:** v9.9.6  
**Expected effort:** 3-4 hours  
**Previous:** Phase 026  
**Next:** Phase 028  
**Risk:** High

## 1. Outcome

Migrate every production consumer from `ExtractionResult` attribute access to stable `DatasetId` access through `DatasetCollection`, then delete `ExtractionResult` and its compatibility adapter after repository-wide zero production references.

At phase end the runtime dataset universe is extensible without editing a fixed dataclass.

## 2. Why this phase exists

Phase 026 introduced the replacement transport but deliberately left consumers untouched. Keeping both transports beyond one migration phase would create two runtime truths and make later v10 source migrations unnecessarily complex.

## 3. Inherited repository state

Phase 026 guarantees:
- `DatasetCollection` represents every current Bronze frame;
- Bronze full-state reconstruction can build it;
- compatibility adapter is complete;
- current pipeline still uses legacy consumers.

Phase 025 guarantees one dataset is already generalized at ingestion.

## 4. Current codebase anchors

Mandatory consumer inventory on the current branch:
- `application/pipeline/transformer.py`
- `application/ingestion/asset_strategies.py`
- `application/pipeline/execution.py`
- `application/ingestion/coordinator.py`
- `infrastructure/warehouse/bronze.py`
- any tests/fixtures constructing `ExtractionResult`
- repository-wide imports/type annotations/attribute accesses.

Do a fresh symbol search at phase start. Do not rely solely on v9.5.3 reference counts because Phases 001-026 have changed the branch.

## 5. Exact target state after this phase

Production code has zero dependency on `ExtractionResult`.

All dataset access is:
```text
collection.require(DatasetId.X)
collection.get(DatasetId.Y)  # only when semantically optional
```

Transformer/service APIs accept `DatasetCollection` or explicit frames derived from it.

No consumer uses physical table names or legacy extraction attribute strings to identify a dataset.

`contracts/extraction.py::ExtractionResult` and temporary adapter are deleted if the file has no other valid contracts.

## 6. Detailed implementation sequence

### Step 1 - Freeze zero-reference baseline
Generate current consumer list and commit it into phase notes/test expectation if useful.

### Step 2 - Migrate Transformer
Replace dimension/reference/investment frame attribute access with DatasetId. Required datasets use `require()`. Do not convert everything to optional `get()` to avoid errors.

### Step 3 - Migrate investment asset strategies
Move MF/stock/US strategy inputs to DatasetCollection/DatasetId. Preserve exact schemas and protected IDs.

### Step 4 - Migrate PipelineExecutor
Execution phases pass DatasetCollection rather than fixed DTO. Completeness remains ExecutionPlan-driven.

### Step 5 - Migrate coordinator/extraction output
Legacy extractors may still be fixed internally, but coordinator emits/adds frames into DatasetCollection keyed by DatasetId. The generalized Phase-025 dataset follows the same transport.

### Step 6 - Migrate Bronze full-state API
Make DatasetCollection the sole public return type. Remove legacy-return branch.

### Step 7 - Migrate tests/fixtures
Use DatasetId builders/factories. Avoid raw dict fixtures that bypass collection validation.

### Step 8 - Repository-wide zero-reference proof
No production import, annotation, construction or field access to `ExtractionResult`.

### Step 9 - Delete DTO/adapter
Delete only now.

### Step 10 - Architecture guard
Add test preventing reintroduction of fixed dataset-universe dataclasses in ingestion transport. New configured DatasetIds must flow through registry/collection.

### Step 11 - Full regression
Run all financial domains and compare outputs/IDs.

## 7. Files and symbols in scope

Modify all current `ExtractionResult` consumers, Bronze API, coordinator transport and tests.

Delete:
- `ExtractionResult`;
- Phase-026 compatibility adapter;
- obsolete field mapping helpers used only for DTO compatibility.

Do not migrate physical source paths or remaining datasets.

## 8. Cross-cutting impacts

**Persistence:** none.

**Identity:** protected financial IDs unchanged.

**Provenance:** DatasetRuntimeMetadata remains bounded and canonical.

**Observability:** dataset context should use DatasetId where transport context is emitted.

**Performance:** no eager materialization; dictionary/enum lookup overhead negligible.

**Compatibility:** this is an internal breaking contract intentionally completed before v10 ingestion expansion.

## 9. Tests and verification

Required:
- repository search: zero `ExtractionResult` production references;
- Transformer equivalence;
- asset strategy equivalence;
- coordinator collection coverage;
- Bronze full-state coverage;
- required-vs-optional access tests;
- full Shan financial outputs identical;
- PURCHASE/SALE/LOT/REALIZED/RECON/TAX IDs identical;
- runtime benchmark within noise.

## 10. Explicit non-goals

Do not:
- generalize new sources;
- remove folder locator;
- retire column_master;
- make Bronze strict globally;
- change financial formulas.

## 11. Completion checklist

- [ ] All production consumers use DatasetCollection.
- [ ] Required datasets use explicit required access.
- [ ] Coordinator emits DatasetIds.
- [ ] Bronze returns DatasetCollection only.
- [ ] `ExtractionResult` deleted.
- [ ] Compatibility adapter deleted.
- [ ] Architecture guard added.
- [ ] Full financial/ID regression green.

## 12. Commit boundary

```text
refactor(ingestion): replace fixed extraction result
```

## 13. Handoff to Phase 028

Phase 028 may assume there is no fixed Python dataset universe. Every current/new source migration can now land directly into DatasetCollection by DatasetId. Phase 028 begins scaling the Phase-025 migration template across household reference evidence.

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
