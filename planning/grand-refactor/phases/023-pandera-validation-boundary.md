# Phase 023 - Pandera Validation Boundary

**Target release:** v9.9.2  
**Expected effort:** 3-4 hours  
**Previous:** Phase 022  
**Next:** Phase 024  
**Risk:** Medium-High

## 1. Outcome

Introduce Pandera behind one PFETL infrastructure validation boundary, establish the supported Polars materialization strategy, define typed bounded validation failures, and integrate semantic validation observability. No production dataset contract is compiled yet.

## 2. Why this phase exists

Generalized user sources are untrusted. Before source/config-derived schemas are implemented, PFETL needs one controlled validation mechanism whose performance and error behavior are understood. Pandera must not leak through domain/application code.

## 3. Inherited repository state

Phase 022 guarantees Pre-Bronze operational safety. Phase 018/019 provide mapping and identity contracts. Current Gatekeeper only proves Polars schema/executability and does not enforce dataframe contracts.

## 4. Current codebase anchors

Anchors:
- current ingestion Gatekeeper / `_validate_extracted_streams`
- Polars LazyFrame/DataFrame usage
- existing `ErrorDetails`
- observability emitter/context/event-code architecture
- exception translation patterns
- project dependency configuration (`pyproject.toml`).

## 5. Exact target state after this phase

Create infrastructure validation adapter conceptually:
```text
DataFrameValidator
  validate(frame, contract, context) -> ValidationResult
```

Application depends on a PFETL protocol/result, not Pandera exceptions.

`ValidationResult/Error` contains:
- validation stage;
- source_id;
- dataset_id;
- contract id/version;
- failed checks;
- affected row count;
- bounded examples;
- remediation.

Supported stages:
- SOURCE / PRE_BRONZE admission
- CANONICAL_BRONZE admission

The adapter owns Pandera-specific schema/error translation.

## 6. Detailed implementation sequence

### Step 1 - Add dependency
Pin/declare Pandera version compatible with current Polars version and Python baseline.

### Step 2 - Define PFETL validation protocol/results
Place cross-boundary result types under contracts. No Pandera type in signatures outside infrastructure adapter.

### Step 3 - Implement minimal adapter
Validate controlled Polars fixture. Translate Pandera errors to typed bounded result.

### Step 4 - Benchmark materialization
Measure representative LazyFrame/DataFrame validation:
- collect behavior;
- memory;
- execution time.
Choose and document the one allowed validation boundary. Do not scatter `.collect()` calls.

### Step 5 - Error bounding
Large invalid fixture must produce bounded examples/counts, not serialized full failure DataFrame.

### Step 6 - Observability
Add semantic event codes/context for validation start/success/failure only if consistent with current event taxonomy. Include run/source/dataset/stage/contract, not raw sensitive rows beyond bounded safe examples.

### Step 7 - Gatekeeper coexistence
Keep current Gatekeeper for production fixed ingestion. Document that Pandera will supersede its contract-validation responsibility dataset-by-dataset; do not delete it yet. **Phase 035 owns final Gatekeeper / `_validate_extracted_streams` deletion after every production dataset has migrated.**

### Step 8 - Architecture test
Only infrastructure validation module imports Pandera (except test fixtures/schema builders if explicitly allowed).

## 7. Files and symbols in scope

Modify:
- `pyproject.toml`
- validation contracts/protocol
- `infrastructure/validation/pandera_adapter.py`
- observability event vocabulary/context if required
- focused tests/benchmark fixture.

Do not create production source/Bronze schemas yet.

## 8. Cross-cutting impacts

**Persistence:** none.

**Identity:** none.

**Observability:** semantic validation events reuse existing emitter/three consumers.

**Performance:** this phase must record a chosen validation materialization strategy; unacceptable eager duplication must be fixed before Phase 024.

**Privacy:** bounded invalid examples; no full financial frame in JSONL.

## 9. Tests and verification

Required:
- valid fixture passes;
- invalid type/null/uniqueness fixture translates cleanly;
- large failure bounded;
- LazyFrame/DataFrame strategy benchmarked;
- no Pandera exception leaks across adapter;
- observability event correlated to run/source/dataset;
- architecture import guard;
- current Gatekeeper/current pipeline unchanged.

## 10. Explicit non-goals

Do not:
- define all 20 Bronze schemas;
- remove Gatekeeper;
- migrate a source;
- change financial transforms;
- create another observability sink/emitter.

## 11. Completion checklist

- [ ] Pandera dependency integrated.
- [ ] PFETL validation protocol/result exists.
- [ ] Adapter isolates Pandera.
- [ ] Materialization boundary measured and frozen.
- [ ] Failures are bounded/actionable.
- [ ] Observability integrated without redesign.
- [ ] Current production ingestion unchanged.

## 12. Commit boundary

```text
feat(validation): add pandera dataframe boundary
```

## 13. Handoff to Phase 024

Phase 024 may assume a performance-characterized, observable validation service exists. It will compile the first config-derived source contract and define the corresponding PFETL-owned canonical Bronze contract for the dataset selected for Phase 025.

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
