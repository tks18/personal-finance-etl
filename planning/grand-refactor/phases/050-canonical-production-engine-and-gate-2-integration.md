# Phase 050 - Canonical Production Engine and Gate-2 Integration

**Target release:** v10.3.5  
**Expected effort:** 4-5 hours  
**Previous:** Phase 049  
**Next:** Phase 051  
**Risk:** Very High

## 1. Outcome

Introduce the canonical production runtime that turns one or more `CanonicalFragment`s into one validated Bronze DatasetId.

At phase end PFETL supports source `DIRECT` and explicit `UNION`, provider production, PFETL-owned derived recipes, post-assembly canonical identity, grain/duplicate enforcement, Gate 2 on the final assembled dataset and canonical cross-dataset integrity checks.

## 2. Why this phase exists

Phase 049 solved 1-to-N source interpretation. The remaining N-to-1 problem cannot be hidden inside SourcePlanner or Polars concatenation. Canonical production needs its own typed ownership so identity, duplicate behavior, validation and provenance are deterministic across multiple contributing sources.

## 3. Inherited repository state

Phase 049 guarantees:
- physical evidence is binding-keyed;
- each route can emit canonical fragments;
- fragments already contain canonical semantics and target projection;
- source/vendor fields are removed before production;
- current financial behavior still uses transitional targets.

## 4. Current codebase anchors

Inspect:
- current Bronze admission service and where Gate 2 is invoked;
- `contracts/dataset_collection.py`;
- `config/sources/identity.py` and current Bronze identity compiler;
- `infrastructure/validation/canonical_schemas.py`;
- `infrastructure/warehouse/contracts.py` and Bronze DDL;
- provider-generated market ingestion paths;
- transaction/recovery orchestration in the pipeline executor;
- existing uniqueness/grain tests and artifact provenance.

## 5. Exact target state after this phase

For each target DatasetId:

```text
CanonicalDatasetPlan
   SOURCE/DIRECT -> one fragment
   SOURCE/UNION  -> explicit ordered fragment set
   PROVIDER      -> provider canonical fragment
   DERIVED       -> PFETL-owned recipe over canonical dependencies
        ↓
schema alignment
        ↓
canonical identity
        ↓
duplicate/grain checks
        ↓
Gate 2
        ↓
Bronze
```

Rules:
- UNION is explicit; merely having two routes target one DatasetId does not imply union;
- required columns must be present before assembly; optional columns may be typed-null according to the target contract;
- duplicate canonical identity fails unless the DatasetContract explicitly permits identical-evidence collapse;
- `KEEP_FIRST`, `KEEP_LAST`, implicit summing or ordering-dependent dedupe are forbidden;
- missing, disabled, empty and malformed remain distinct states;
- derived recipes are registered PFETL code with typed metadata, never user executable code;
- cross-dataset references are checked by `CanonicalIntegrityValidator` after individual Gate-2 success and before Silver.

## 6. Detailed implementation sequence

### Step 1 - Add canonical production executor boundary
Keep orchestration/application-owned. It consumes plans/fragments and delegates to existing validation/warehouse adapters rather than importing presentation or domain financial engines.

### Step 2 - Align fragments to target contract
Compile each fragment to required/optional target columns. Fail before union if a required field is absent or incompatible.

### Step 3 - Implement DIRECT and explicit UNION
DIRECT accepts exactly one source fragment. UNION accepts the exact routes listed in production configuration and uses deterministic fragment ordering independent of filesystem/thread order.

### Step 4 - Move canonical identity after assembly
Separate source-row identity from canonical-row identity. Support current trusted/derived identity strategies with explicit scope so duplicate source-local IDs from different bindings cannot collide accidentally.

### Step 5 - Enforce duplicate policy and grain
Detect equal-identity identical rows versus conflicting rows. Default to failure. Add only the minimum explicit identical-evidence policy required by a proven dataset contract.

### Step 6 - Move Gate 2 to final canonical candidate
Gate 2 validates the complete assembled DatasetId. Fragment compile checks are not a third Pandera trust gate.

### Step 7 - Add derived-recipe registry
Define typed metadata (`recipe_id`, version, target, canonical dependencies). Implement only recipes required by the locked canonical model; arbitrary user recipes are forbidden.

### Step 8 - Integrate provider production
Provider-generated evidence enters the same final identity/grain/Gate-2 path after provider-specific normalization. Do not pretend provider requests are file SourceBindings.

### Step 9 - Add `CanonicalIntegrityValidator`
Validate declared cross-dataset references/coverage after active Bronze datasets are produced. Keep this separate from Pandera Gate 2.

### Step 10 - Integrate transaction/recovery semantics
Canonical production and publication remain inside the existing DuckDB transaction and Phase-044 recovery model. Failure after assembly but before publication must not expose partial Bronze.

### Step 11 - Prove generic cardinalities
Create generic tests for 1->1, 1->N, N->1 and N->M using the same production runtime, without household/investment-specific branches.

## 7. Files and symbols in scope

Expected changes:
- application canonical production service/executor;
- identity compilation/use-site;
- Gate-2 invocation boundary;
- provider canonical output integration;
- canonical integrity service;
- production plan/result contracts and tests;
- replay/provenance hooks needed to record production fingerprints.

Do not migrate financial domains yet.

## 8. Cross-cutting impacts

**Identity:** major. Final identity is dataset-wide after assembly; source identity remains provenance/operational input.

**Validation:** Gate 2 moves to the assembled canonical boundary. Cross-dataset integrity becomes explicit before Silver.

**Recovery:** canonical production is transactional and rebuildable from Raw/Pre-Bronze inputs.

**Provenance:** many source bindings may contribute to one canonical DatasetId; lineage must preserve that relationship without making source binding part of financial meaning unless the identity contract explicitly requires namespacing.

**Performance:** UNION and integrity checks add overhead. Benchmark only for regression at this phase; optimization belongs to Phase 058.

## 9. Tests and verification

Required:
- DIRECT rejects zero/multiple fragments;
- UNION requires explicit configured routes and does not auto-union all matching routes;
- fragment order changes do not change canonical identity/output;
- same source-local ID in two bindings is handled according to identity scope, not accidental collision;
- conflicting duplicate canonical identity fails;
- allowed identical-evidence duplicate case preserves lineage if such a policy is used;
- required/optional column alignment is deterministic;
- empty-valid vs missing vs disabled vs malformed are distinguishable;
- derived recipe cycle is not executed here and dependency metadata is exposed for Phase 051;
- Gate 2 sees the final assembled frame;
- cross-dataset reference failure is caught before Silver;
- failure during production rolls back Bronze publication;
- 1->1, 1->N, N->1 and N->M generic fixtures are green;
- current Shan outputs remain unchanged on transitional targets.

## 10. Explicit non-goals

Do not:
- decide producer ambiguity globally yet;
- auto-select source vs derived producer;
- migrate capabilities to new canonical DatasetIds;
- optimize UNION aggressively;
- add generic configurable joins;
- change Silver financial methods.

## 11. Completion checklist

- [ ] Canonical production executes SOURCE/DIRECT, explicit SOURCE/UNION, PROVIDER and registered DERIVED paths through one target-side service.
- [ ] Final canonical identity is applied after assembly with explicit source/global scope semantics.
- [ ] Duplicate and grain violations fail deterministically; no ordering-dependent dedupe exists.
- [ ] Gate 2 validates final assembled Bronze rather than individual source fragments.
- [ ] Canonical cross-dataset integrity is checked before DatasetCollection reaches Silver.
- [ ] Production participates in existing transaction/recovery/provenance semantics without partial publication.
- [ ] Generic 1->1, 1->N, N->1 and N->M certification proves no domain-specific topology branch was introduced.

## 12. Commit boundary

Use `pfetl-conventional-commits` to create reviewable semantic groups around production execution, identity/validation boundary changes, and integrity/recovery tests. Preview groupings before execution; this plan does not prescribe exact messages.

## 13. Handoff to Phase 051

Phase 051 receives a production engine capable of executing a **known** CanonicalDatasetPlan. It must now determine whether the requested capability set is satisfiable, resolve exactly one producer per required DatasetId, reject ambiguity/cycles/missing producers and output a deterministic topologically ordered `CanonicalProductionPlan` before physical execution.

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
Commits:
```

A phase is incomplete if any required exit assertion is false.
