# Phase 046 - External Household Topology Certification

**Target release:** v10.3.1  
**Expected effort:** 3-4 hours  
**Previous:** Phase 045  
**Next:** Phase 047  
**Risk:** High

## 1. Outcome

Certify that PFETL's generalized household ingestion works for three genuinely different external source topologies, not merely Shan's topology expressed through configuration:

1. Excel household evidence without stable source UIDs;
2. CSV household evidence without stable source UIDs;
3. SQLite household evidence with stable IDs but a schema/table layout different from Shan's source.

Each fixture must configure PFETL without source-code changes and reach canonical household Silver/Gold outputs or the maximum household-only outputs allowed by the active capability plan.

## 2. Why this phase exists

The architecture has already proven individual no-UID and household-only cases. External certification now tests the product claim at topology level: can a new user describe materially different evidence and still enter the same canonical financial model? This phase should expose any hidden assumptions that survived the migration.

## 3. Inherited repository state

Phase 045 guarantees:
- PFETL-native configuration diagnostics and dry-run admission;
- generalized ingestion is authoritative;
- household-only capability works;
- trusted and derived Bronze identity strategies exist;
- mapping/normalization/Pandera/recovery are production paths;
- plan-aware warehouse is operational.

No companion configuration application is in scope.

## 4. Current codebase anchors

Use application/CLI interfaces from Phase 045 as the external user's entry point.

Build fixtures under the existing test/fixture conventions. They must not import Shan production data.

For each topology identify:
- SourceConfig(s);
- DatasetIds supplied;
- physical selectors;
- source schemas;
- mappings/normalization;
- identity strategies;
- household capability selection;
- expected canonical Bronze grains;
- expected Silver/Gold outputs.

Use current canonical contracts, never fixture-specific schema branches.

## 5. Exact target state after this phase

Three independent configurations satisfy the same canonical household contracts.

### Excel fixture
- realistic vendor-style column names;
- multiple sheets if useful to exercise selector behavior;
- no stable UID;
- deterministic Bronze identity from configured canonical fields.

### CSV fixture
- different source column names/order/date format from Excel;
- no stable UID;
- same canonical identity/grain outcome.

### SQLite fixture
- different table names from Shan;
- configured selectors;
- stable source IDs preserved;
- no hard-coded `zcategory`/legacy table-name dependency.

All run:
```text
validate-config
check-sources
dry-run-admission
full household run
incremental/no-change rerun
```

No source code changes between fixtures.

## 6. Detailed implementation sequence

### Step 1 - Define fixture contracts
Write expected source->DatasetId matrix and financial scenario. Keep fixture data small but relationally meaningful: categories, assets/currency, income/expense transactions, opening state as required.

### Step 2 - Build Excel fixture/config
Run diagnostics first, then full household-only pipeline.

### Step 3 - Build CSV fixture/config
Use intentionally different source vocabulary/date representation to prove normalization.

### Step 4 - Build SQLite fixture/config
Use non-Shan table names and stable IDs.

### Step 5 - Cross-topology canonical equivalence
Where fixtures represent the same financial scenario, compare canonical Bronze and downstream household results after sorting by canonical identity. Source provenance differs; financial meaning should not.

### Step 6 - Identity certification
Excel/CSV derived IDs stable across reordered rows/reruns. SQLite trusted IDs preserved.

### Step 7 - Failure pack
For each relevant topology exercise malformed schema, invalid mapping and identity collision/duplicate grain. Diagnostics must fail before invalid canonical publication.

### Step 8 - Empty and incremental/change proof
For at least one configured optional/transaction dataset, certify a valid zero-row input and prove it is not treated as missing. Then modify one transaction/source artifact and verify only expected state changes according to policy.

### Step 9 - Recovery/backup smoke
At least one external fixture exercises failure rollback + backup/restore.

### Step 10 - Hidden-assumption sweep
Any production branch checking Shan path/table/category names fails this phase and is removed.

## 7. Files and symbols in scope

Create external household fixtures/configs and certification tests.

Modify production code only to remove genuine hidden assumptions exposed by supported fixtures. Any broad architecture change must be reflected back into ARCHITECTURE/earlier phase assumptions before acceptance.

## 8. Cross-cutting impacts

**Persistence:** each fixture gets isolated Control Plane/warehouse.

**Identity:** cross-topology identity semantics tested; exact IDs need not match between trusted-source and derived strategies unless configured key semantics intentionally make them equivalent.

**Provenance:** SourceId/artifact differs while canonical finance remains stable.

**Observability:** lineage reconstructable for at least one external fixture.

**Performance:** fixture scale is correctness-focused; no optimization based on tiny fixtures.

## 9. Tests and verification

Mandatory:
- Excel config-only onboarding;
- CSV config-only onboarding;
- non-Shan SQLite config-only onboarding;
- diagnostics pass before full run;
- no source code changes between fixtures;
- canonical scenario equivalence where designed;
- stable derived IDs;
- preserved trusted IDs;
- malformed schema/mapping/collision failures;
- valid empty configured dataset;
- incremental rerun;
- rollback/backup restore smoke;
- zero hidden Shan topology assumptions.

## 10. Explicit non-goals

Do not:
- build a UI/config wizard;
- weaken canonical contracts to make fixtures pass;
- add fixture-specific provider logic;
- change financial formulas;
- require investment evidence.

## 11. Completion checklist

- [ ] Excel external household topology passes.
- [ ] CSV external household topology passes.
- [ ] SQLite external household topology passes.
- [ ] No source-code customization required.
- [ ] Identity semantics correct.
- [ ] Failure diagnostics actionable.
- [ ] Incremental behavior correct.
- [ ] Hidden Shan assumptions zero.

## 12. Commit boundary

```text
test(certification): add external household topologies
```

## 13. Handoff to Phase 047

Phase 047 may assume household generalization is proven across multiple physical source types and identity strategies. It will apply the same external-user standard to domestic and foreign investment topologies and capability dependency failures.

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
