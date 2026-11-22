# Phase 048 - Binding-Aware Source Planning and Pre-Bronze Cutover

**Target release:** v10.3.3  
**Expected effort:** 4-5 hours  
**Previous:** Phase 047  
**Next:** Phase 049  
**Risk:** Very High

## 1. Outcome

Move physical acquisition and Pre-Bronze persistence from canonical `DatasetId` ownership to `SourceBindingId` ownership.

At phase end:

```text
SourceBindingConfig -> SourceBindingPlan -> provider read -> Gate 1
        -> Pre-Bronze keyed by SourceBindingId
```

is authoritative for physical evidence acquisition. Downstream canonical admission still targets the transitional v10.3.0 Bronze DatasetIds so financial behavior remains unchanged.

## 2. Why this phase exists

N:M canonical production is impossible while Pre-Bronze itself is keyed by canonical DatasetId. Phase 047 proved the new binding model can represent every current source without behavioral change. Phase 048 cuts over the first runtime ownership boundary while deliberately leaving canonical semantics alone.

This is a persistence/recovery phase, not a financial-model phase.

## 3. Inherited repository state

Phase 047 guarantees:
- complete current topology compiles to deterministic SourceBindingIds/routes;
- transitional production still maps 1:1 to old DatasetIds;
- binding/route fingerprints are available;
- compatibility compiler is temporary and deletion-owned by Phase 055.

## 4. Current codebase anchors

Inspect exact persistence and lifecycle boundaries:
- `application/pipeline/source_planner.py`;
- `infrastructure/warehouse/pre_bronze.py`;
- `infrastructure/warehouse/schema/pre_bronze.py`;
- source/provider file adapters under `infrastructure/providers/files/`;
- Control Plane artifact/run repositories and provenance contracts;
- `application/pipeline/replay.py`;
- pipeline executor transaction ordering;
- backup/restore and integrity checks that enumerate Pre-Bronze tables;
- diagnostics dry-run path.

## 5. Exact target state after this phase

`DatasetPlan` no longer owns physical acquisition. Replace that responsibility with `SourceBindingPlan`.

`CompiledSourcePlan` becomes binding-oriented:
- lookup by `SourceBindingId`;
- deterministic ordered binding plans;
- no API that requires a canonical DatasetId to discover physical evidence.

Pre-Bronze state becomes dynamic/configuration-owned:

```text
SourceBindingId -> pre_bronze.<binding physical name>
```

The fixed Pre-Bronze registry derived from Bronze contracts is no longer authoritative.

Gate 1 validates binding/source shape. Existing normalization/admission then continues through the transitional route to the same old Bronze DatasetId.

Existing Raw Store/Control Plane evidence is preserved. Current Pre-Bronze may be rebuilt rather than migrated in place.

## 6. Detailed implementation sequence

### Step 1 - Split `DatasetPlan` responsibility
Introduce/activate `SourceBindingPlan` for provider, selector, source schema and change-policy concerns. Leave canonical target metadata outside this physical plan.

### Step 2 - Cut SourcePlanner to binding plans
Compile from the Phase-047 binding representation. Remove DatasetId-based physical lookup from new runtime call sites.

### Step 3 - Replace Pre-Bronze registry ownership
Generate Pre-Bronze persistence plans from active binding plans. Do not synthesize them from `BRONZE_CONTRACT_REGISTRY`.

### Step 4 - Change Pre-Bronze read/write keys
All current-state Pre-Bronze APIs use `SourceBindingId`. Preserve artifact/run provenance and current transaction semantics.

### Step 5 - Preserve Gate-1 validation
Gate 1 remains source-contract validation. Errors/observability now identify source + binding, not canonical DatasetId as the source identity.

### Step 6 - Existing-state upgrade
On first run after this phase, safely detect DatasetId-keyed Pre-Bronze state. Rebuild active Pre-Bronze from retained Raw/source evidence under binding keys. Avoid brittle in-place renames when rebuild is deterministic.

### Step 7 - Recovery and split-commit behavior
Re-run failure injection across Raw/Pre-Bronze/Bronze boundaries. A failure while rebuilding binding-keyed Pre-Bronze must converge under the existing recovery state machine.

### Step 8 - Backup/restore and integrity
Backups/restores must capture the binding-keyed Pre-Bronze state and validate it against the active binding plan, not a global fixed registry.

### Step 9 - Replay remapping
Configuration changes now identify affected source bindings first. Continue mapping them to transitional DatasetIds for downstream rebuild until Phase 051 production-graph replay replaces that mapping.

### Step 10 - Diagnostics cutover
`check-sources`, mapping/identity preview and dry-run admission must select/label bindings correctly. Dry run remains non-mutating.

### Step 11 - Demolish old physical ownership
Delete runtime paths that require DatasetId to locate/read/persist a source binding. Keep only compatibility data needed to target transitional Bronze.

## 7. Files and symbols in scope

Expected changes:
- SourcePlanner and plan contracts;
- Pre-Bronze persistence/schema planning;
- pipeline execution around source acquisition;
- Control Plane provenance references where binding identity is persisted;
- replay affected-binding mapping;
- backup/restore/integrity;
- diagnostics services and tests.

Do not change Silver/Gold or canonical financial schemas.

## 8. Cross-cutting impacts

**Persistence:** major. Pre-Bronze physical state is rebuilt/rekeyed by binding identity.

**Recovery:** high-risk. The existing DuckDB-first/SQLite-second commit and `RECOVERY_REQUIRED` semantics must remain intact.

**Provenance:** add SourceBindingId to operational lineage without making it financial identity.

**Performance:** unchanged-source reruns must still benefit from existing artifact/change detection. Re-keying Pre-Bronze must not force permanent full rereads.

**Diagnostics:** source and binding become the primary pre-canonical context.

## 9. Tests and verification

Required:
- one source with several bindings compiles and persists distinct Pre-Bronze tables/state;
- same canonical transitional DatasetId may be referenced by different bindings without Pre-Bronze collision;
- Gate-1 failure names the failing binding;
- existing v10.3.0 state upgrades by rebuild without losing Raw/Control Plane truth;
- interrupted Pre-Bronze rebuild recovers deterministically;
- backup then restore reproduces binding-keyed Pre-Bronze exactly;
- unchanged rerun performs no unnecessary semantic rebuild;
- mapping/normalization change still reaches the correct transitional Bronze target;
- diagnostics dry run leaves production Pre-Bronze/Control Plane unchanged;
- full Shan Silver/Gold outputs and protected IDs are identical.

## 10. Explicit non-goals

Do not:
- introduce semantic include/exclude rules yet;
- emit multiple canonical fragments from one binding yet;
- enable UNION;
- activate new canonical DatasetIds;
- delete the compatibility compiler;
- modify financial formulas.

## 11. Completion checklist

- [x] Physical source planning is keyed by `SourceBindingId`, with no new runtime call requiring DatasetId to acquire evidence.
- [x] Active Pre-Bronze persistence is generated from binding plans rather than the Bronze contract registry.
- [x] Existing v10.3.0 Pre-Bronze state upgrades by deterministic rebuild while Raw/Control Plane history remains intact.
- [x] Recovery, split-commit, backup and restore are green with binding-keyed Pre-Bronze state.
- [x] Replay identifies changed bindings and still reaches the correct transitional Bronze datasets.
- [x] Phase-045 diagnostics operate on source/binding identity and dry-run admission remains non-mutating.
- [x] Full Shan canonical Bronze/Silver/Gold behavior is unchanged after the persistence cutover.

## 12. Commit boundary

Use `pfetl-conventional-commits` to group the planner cutover, Pre-Bronze persistence/recovery changes and diagnostics/test adjustments into coherent commits after preview. Commit groupings should follow semantic ownership, not individual files.

## 13. Handoff to Phase 049

Phase 049 may assume physical evidence is completely binding-owned through Gate 1 and Pre-Bronze. It must **not** revisit persistence identity. Its job is to transform one binding's source-shaped rows into one or more canonical fragments through bounded, row-local semantic interpretation while still targeting transitional Bronze contracts.

## Phase completion record

```text
Phase: 048
Target release: v10.3.3
Files changed: 20
Schema changed: YES (Pre-Bronze DuckDB lakehouse tables keyed by SourceBindingId with __binding_id__ provenance column)
Runtime behavior changed: YES (Physical planning and Pre-Bronze persistence operate on SourceBindingId)
Financial formulas changed: NO
Focused tests: tests/architecture/test_boundaries.py tests/architecture/test_table_naming_guards.py tests/application/test_source_binding_planning.py tests/infrastructure/test_pre_bronze_binding_persistence.py tests/infrastructure/test_pre_bronze_upgrade_and_recovery.py tests/application/test_binding_replay_and_diagnostics.py tests/infrastructure/test_pre_bronze_persistence.py tests/infrastructure/test_pre_bronze_operational.py (51 passed)
Architecture tests: tests/architecture/test_boundaries.py tests/architecture/test_table_naming_guards.py (21 passed)
Real-data run: tests/application/test_generalized_vertical_slice.py (17 passed)
Performance check: Fast quality gate in 1.10s, focused tests in 5.86s
Compatibility path still present: YES (Transitional legacy dataset config fallback and compatibility compiler preserved until Phase 055)
Old path deleted: Direct canonical DatasetId Pre-Bronze persistence cut over to SourceBindingId
Exit assertions green: YES
Commits: 4 planned conventional commit groups
```

A phase is incomplete if any required exit assertion is false.
