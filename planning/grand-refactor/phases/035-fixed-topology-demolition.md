# Phase 035 - Fixed-Topology Demolition

**Target release:** v10.0.0-rc8  
**Expected effort:** 3-4 hours  
**Previous:** Phase 034  
**Next:** Phase 036  
**Risk:** High

## 1. Outcome

Delete the remaining fixed source-topology infrastructure now that every current Bronze evidence stream has a generalized production route. `SourceConfiguration` + `ExecutionPlan` + `Source/Provider DatasetPlan` become the sole authorities for what evidence exists and how it is acquired.

This phase removes compatibility architecture; it does not yet make Bronze globally strict or replace Bronze operational filename identity.

## 2. Why this phase exists

Phases 025 and 028-034 migrated every evidence family but deliberately allowed shared legacy discovery/injection infrastructure to coexist until zero dataset depended on it. Keeping it now would create two topology authorities and undermine external-user configurability.

## 3. Inherited repository state

Phase 034 guarantees all 20 Bronze streams have generalized routes. DatasetCollection is authoritative. `column_master` is retired. File/provider change policies are explicit.

Potential legacy pieces still present:
- `categorize_statement_files`
- folder-name maps in `locator.py`
- `_inject_configuration_assets`
- Settings source-path fields retained for compatibility
- category->provider maps
- dedicated extractor functions with zero callers
- compatibility resolver branches for legacy categories.

## 4. Current codebase anchors

Fresh repository-wide archaeology at phase start is mandatory.

Search for:
- `STATEMENTS_FOLDER`
- `SOURCE_DB_FOLDER`
- individual source CSV path Settings
- `_inject_configuration_assets`
- `categorize_statement_files`
- old folder literals (`Stock PL Statements`, `Mutual Funds - Holdings`, etc.)
- `FILE_TYPE_MAP`
- legacy category strings
- dedicated extraction functions
- compatibility policy resolver
- old source-path validation.

Classify each reference: delete, descriptive migration compatibility, test fixture, or legitimate historical metadata.

## 5. Exact target state after this phase

Production topology flow is only:

```text
SourceConfiguration + ExecutionPlan
 -> SourcePlanner / ProviderDatasetPlanner
 -> required dataset plans
 -> Control Plane sync/provider requests
 -> generalized admission
```

No folder name or special Settings path determines dataset existence.

Runtime Settings contains environment/installation concerns only. Source locations live in SourceConfiguration.

Legacy category strings may remain only in historical Control Plane records/migrations if required for backward compatibility; new runs use SourceId/DatasetId.

## 6. Detailed implementation sequence

### Step 1 - Produce legacy-topology zero-consumer ledger
Every candidate symbol/path gets disposition before deletion.

### Step 2 - Remove folder discovery authority
Delete or demote `locator.py` folder-name categorization. If a generic filesystem glob/discovery helper remains, it must be driven by SourceConfig and contain no financial dataset names.

### Step 3 - Delete manual configuration injection
Remove `_inject_configuration_assets` and special source-path insertion.

### Step 4 - Clean Settings
Remove source topology fields that have zero runtime consumers. Keep only environment/runtime settings. Provide config migration/error message if existing user settings still contain deprecated fields.

### Step 5 - Remove category/provider authority
Delete `FILE_TYPE_MAP` if no descriptive compatibility consumer remains. New artifact metadata uses ProviderType/SourceId/DatasetId.

### Step 6 - Remove dead dedicated extractors
Any function superseded by generic provider + normalization and with zero callers is deleted.

### Step 7 - Remove compatibility policy resolver
If all datasets now resolve policy directly from SourceConfiguration, delete the v9.5.x compatibility resolver and `FileHashPolicy`.

### Step 8 - Retire the legacy Gatekeeper
After all current datasets use SOURCE Pandera validation, prove `_validate_extracted_streams` / the legacy Gatekeeper has zero production responsibility. Delete it and any tests/helpers that only certify the old `collect_schema()+head(1)` contract gate. Retain only genuinely distinct execution-smoke checks if they still have a named owner and purpose.

### Step 9 - Close Phase-001 compatibility keys
Make an explicit final disposition for `BronzeDataContract.extraction_attribute`, `BronzeDataContract.sync_category`, and `DataContract.contract_id`:
- delete them if they have zero production/public responsibility; or
- rename/retain them only as a documented internal/public compatibility alias with tests proving why they still exist.

No field may remain merely because Phase 001 once said RETAIN. DatasetId is the logical dataset authority after this phase.

### Step 10 - Reconcile removed/disabled configured datasets
Compare the previous successful SourceConfiguration/plan with the current one. If a SourceDatasetConfig is removed or disabled, its historical Raw/Control Plane provenance may remain for audit, but current-state Pre-Bronze/Bronze data must not continue feeding the run. Define and test the managed cleanup/rebuild behavior so stale evidence from a no-longer-configured DatasetId cannot survive as current truth.

### Step 11 - Architecture guards
Fail if production code reintroduces known folder literals, special source Settings paths, category-based provider/policy routing, the legacy Gatekeeper, or unresolved Phase-001 compatibility keys without an explicit approved purpose.

### Step 12 - Fresh-config run
Run Shan entirely from SourceConfiguration with legacy topology disabled/removed.

### Step 13 - Existing-data compatibility
Open existing Control Plane/warehouse state and prove historical category/path metadata does not break new runs.

## 7. Files and symbols in scope

Delete/modify legacy discovery, Settings, compatibility resolver, dead provider functions and tests.

Do not touch:
- Bronze dynamic schema evolution (Phase 036);
- Bronze `__file_name__` operational identity (Phase 037);
- financial formulas.

## 8. Cross-cutting impacts

**Persistence:** no destructive historical Control Plane migration required merely to rename old metadata. New writes use canonical source/dataset/provider identity.

**Identity:** unchanged.

**Observability:** new runs should report SourceId/DatasetId rather than legacy categories where context has migrated.

**Performance:** source planning should be configuration-scale and discovery no slower than legacy folder walk.

**Compatibility:** historical records remain readable; legacy configuration fields may fail with explicit migration guidance rather than silently ignored.

## 9. Tests and verification

Required:
- zero production dependency on folder literals;
- zero `_inject_configuration_assets`;
- zero source topology Settings authority;
- zero category->provider/policy runtime routing;
- zero dead dedicated extractor callers;
- zero legacy Gatekeeper production references;
- Phase-001 compatibility keys deleted or explicitly justified;
- removed/disabled DatasetId cannot leave stale current-state Pre-Bronze/Bronze evidence;
- Shan run using SourceConfiguration only;
- existing Control Plane DB opens/runs;
- full financial/ID equivalence;
- architecture guards.

## 10. Explicit non-goals

Do not:
- delete historical Control Plane columns solely for cleanliness;
- make Bronze strict yet;
- migrate operational filename identity yet;
- change capability composition;
- alter source config public schema beyond necessary cleanup.

## 11. Completion checklist

- [ ] SourceConfiguration is sole file-source topology authority.
- [ ] ProviderDatasetPlan is sole provider-evidence topology authority.
- [ ] Folder-name semantics removed.
- [ ] Manual injection removed.
- [ ] Runtime Settings source paths removed.
- [ ] Legacy policy/category routing removed.
- [ ] Legacy Gatekeeper removed.
- [ ] Phase-001 compatibility keys have terminal disposition.
- [ ] Removed/disabled dataset cleanup is deterministic.
- [ ] Historical state remains readable.
- [ ] Full Shan run uses generalized topology only.

## 12. Commit boundary

```text
refactor(ingestion): remove fixed source topology
```

## 13. Handoff to Phase 036

Phase 036 may assume there is no legacy ingestion topology left. Every evidence stream enters through generalized planning/admission. It can now remove Bronze dynamic schema evolution globally and make canonical Bronze contracts strict without risking unmigrated sources.

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
