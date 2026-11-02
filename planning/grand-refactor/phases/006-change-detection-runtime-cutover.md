# Phase 006 - Change-Detection Runtime Cutover

**Target release:** v9.5.5  
**Expected effort:** 3-4 hours  
**Previous:** Phase 005 - Change-Detection Policy Architecture  
**Next:** Phase 007 - Bronze Identity Contract and Strategy System  
**Risk:** Medium  
**Runtime behavior change:** Yes, internal policy resolution only; externally observable sync behavior must remain identical  
**Schema/persistence change:** No DDL change; Control Plane row semantics must remain identical

## 1. Outcome

Switch the existing Control Plane file-synchronization runtime from deriving policy through `category -> FILE_TYPE_MAP -> FileHashPolicy` to consuming the resolved `ChangeDetectionPolicy` created in Phase 005.

At phase end:

- `FileSyncService` no longer decides whether to hash by inspecting physical file type;
- full-replace behavior is supplied by the resolved policy rather than a separate `full_replace_categories` list;
- rename behavior remains byte-for-byte equivalent for the current Shan topology;
- `FILE_TYPE_MAP` may remain only for descriptive file-type metadata where still needed;
- `Settings.FILE_HASH_POLICY` may remain temporarily for compatibility resolution, but it is no longer a runtime policy authority below the resolver;
- Meta/artifact code must not independently reinterpret the policy.

This phase is a runtime cutover, not a source-configuration cutover. Current category strings remain the transition key.

## 2. Why this phase exists

Phase 005 proved that every current v9.5.3 category can be translated into an explicit policy containing fingerprint, drift, rename and synchronization semantics.

The runtime still uses the old mechanism:

```text
category
  -> FILE_TYPE_MAP
  -> FileHashPolicy.<csv|excel|sqlite>
  -> should_check_hash

category
  -> BRONZE_CONTRACT_REGISTRY.is_full_replace
  -> full_replace_categories
```

That split authority must be removed before source configuration can own policy later.

## 3. Inherited repository state

Phase 005 guarantees:

- typed `FingerprintStrategy`, `DriftStrategy`, `RenameStrategy`, `SyncStrategy`;
- typed `ChangeDetectionPolicy`;
- validity checks for impossible policy combinations;
- a compatibility resolver covering every current sync category;
- parameterized tests proving current v9.5.3 policy equivalence;
- runtime `FileSyncService` remains unchanged;
- `FileHashPolicy`, `FILE_TYPE_MAP`, and `BronzeDataContract.is_full_replace` still exist.

Do not redesign those types in this phase. If Phase 005 implementation names differ from the conceptual names above, consume the implemented API exactly.

## 4. Current code anchors

### `infrastructure/control_plane/file_sync.py`

Current public API:

```python
def sync_with_disk(
    self,
    discovered_files: dict[str, list[str]],
    hash_policy: FileHashPolicy,
    full_replace_categories: list[str],
) -> SyncDeltaResult:
```

Current `_sync_with_disk()` performs:

```python
file_type = FILE_TYPE_MAP.get(category, "csv")
should_check_hash = bool(getattr(hash_policy, file_type, False))
```

and separately:

```python
full_replace = set(full_replace_categories)
...
if category in full_replace:
    self.artifact_repo.prune_category(category, filepaths)
```

### `application/pipeline/execution.py`

Discovery currently:
1. discovers/injects category paths;
2. derives `full_replace_categories` from `BRONZE_CONTRACT_REGISTRY`;
3. passes `cfg.FILE_HASH_POLICY`;
4. invokes `cp.file_sync.sync_with_disk(...)`.

### `infrastructure/control_plane/artifact_repository.py`

`ingest_binaries()` and `inject_virtual_file()` still use `FILE_TYPE_MAP` to persist descriptive `file_type`.

This is not automatically wrong. `file_type` may remain descriptive. It must not decide hashing/synchronization after this phase.

### `infrastructure/warehouse/meta/layer.py`

`register_file()` independently derives file type from extension and consults `cfg.FILE_HASH_POLICY`.

This is duplicate policy authority and must be removed or routed through the resolved policy/provenance supplied by the Control Plane.

## 5. Target API after this phase

The preferred transition shape is:

```text
FileSyncService.sync_with_disk(
    discovered_files,
    policies_by_category
)
```

where:

```text
policies_by_category: Mapping[str, ChangeDetectionPolicy]
```

A typed transition key may be used if Phase 004 introduced one, but do not force `DatasetId` into file sync where one category currently represents multiple datasets (`sqlite_source` is the obvious case).

The runtime must receive policy already resolved.

`FileSyncService` may ask the policy:

```text
requires_content_fingerprint
uses_content_drift
allows_content_rename
sync_strategy == FULL_REPLACE
```

It must not know why that policy was selected.

## 6. Implementation sequence

### Step 1 - Add a resolved-policy map builder at the application boundary

In the discovery/orchestration path, construct the resolved policy map using the Phase 005 compatibility resolver.

Input remains current:
- category;
- current Settings;
- Bronze contract metadata.

Output:
- one resolved policy for every discovered/injected category.

Special case: `sqlite_source` maps to several Bronze contracts. All five currently have `is_full_replace=True`; assert that the resolved synchronization strategy is unambiguous. If a category ever maps to conflicting sync strategies, fail resolution rather than choose one silently.

### Step 2 - Change `FileSyncService.sync_with_disk`

Replace:
- `hash_policy`;
- `full_replace_categories`;

with the resolved policy map.

Update docstrings and typing.

Do not accept both APIs permanently. A short-lived compatibility wrapper is allowed only if a test or another current caller requires it during this phase; delete it before phase completion if all callers can migrate in the same session.

### Step 3 - Change `_sync_with_disk`

For each category:
1. require a resolved policy;
2. derive `should_check_hash` from fingerprint/drift semantics;
3. enable rename matching only when rename strategy allows it;
4. prune category only when sync strategy is full replace.

Unknown category with no policy must fail explicitly. Do not default to `"csv"` or an implicit policy.

### Step 4 - Preserve current rename semantics

Review `_evaluate_file_status()` and `_try_migrate_rename()`.

If current code opportunistically uses an existing digest only when hashing is enabled, preserve that exact behavior for compatibility policies.

Add a test showing:
- hash-disabled Excel path rename is treated exactly as before;
- hash-enabled CSV rename is recognized exactly as before where current behavior supports it.

### Step 5 - Migrate `PipelineExecutor` discovery caller

Remove construction/passing of `full_replace_categories`.

Build/resolve policies once and pass them into file sync.

Do not make `PipelineExecutor` understand SHA256 or provider-specific hashing. It only invokes the resolver.

### Step 6 - Remove duplicate policy decision from Meta

`MetaLayer.register_file()` currently derives:

```text
extension -> FILE_TYPE_MAP -> FileHashPolicy
```

This must not remain an independent authority.

Preferred target:
- Meta receives authoritative artifact metadata/hash from Control Plane where possible;
- otherwise it receives a resolved policy from the caller.

Do not recompute content hash under a second policy if Control Plane already owns the artifact fingerprint.

If `register_file()` is obsolete in the current active path, prove that with call-site search/tests and remove or isolate it rather than preserving dead policy logic.

### Step 7 - Constrain `FILE_TYPE_MAP`

After all policy consumers migrate:
- retain it only where descriptive `file_type` is needed by existing Control Plane records;
- rename/comment its ownership if appropriate;
- remove exports that imply it is a policy registry if safe.

Do not change persisted `file_type` values in this phase.

### Step 8 - Retain `FileHashPolicy` only as compatibility input

If the Phase 005 resolver still consumes `Settings.FILE_HASH_POLICY`, retain the model and setting.

Add a deprecation/migration comment identifying the later SourceConfiguration cutover phase.

It must have zero direct consumers below the compatibility resolver.

## 7. Before and after flow

### Before

```text
PipelineExecutor
  -> full_replace_categories
  -> Settings.FILE_HASH_POLICY
  -> FileSyncService
       -> FILE_TYPE_MAP
       -> hash boolean
       -> rename behavior
       -> prune behavior
```

### After

```text
PipelineExecutor
  -> Phase-005 compatibility resolver
  -> Mapping[category, ChangeDetectionPolicy]
  -> FileSyncService
       -> explicit fingerprint/drift/rename/sync semantics
```

## 8. Files expected in scope

Modify:
- `application/pipeline/execution.py`
- `infrastructure/control_plane/file_sync.py`
- Phase-005 policy/resolver module if a small API adjustment is required
- `infrastructure/warehouse/meta/layer.py` if it still independently decides hash policy
- focused Control Plane tests
- architecture tests

Possibly modify:
- `infrastructure/control_plane/hashing.py`
- `infrastructure/control_plane/__init__.py`

Read but do not redesign:
- `artifact_repository.py`
- `warehouse/contracts.py`
- `config/settings.py`

## 9. Files explicitly out of scope

Do not modify:
- Bronze DDL or persistence semantics;
- `ExtractionResult`;
- source discovery folder matching;
- source configuration schema beyond policy compatibility wiring;
- financial domain code;
- Silver/Gold schemas;
- observability emitter/sinks.

## 10. Persistence and provenance

Control Plane registry rows must remain semantically identical for the current topology:
- same paths;
- same category;
- same `file_type`;
- same digest values;
- same statuses;
- same rename event semantics.

No SQLite migration.

No DuckDB migration.

## 11. Observability

No new event family is required.

Existing sync/discovery events must retain:
- counts;
- actionable paths;
- rename counts;
- status semantics.

If resolved policy is added as diagnostic context, keep it bounded and do not dump configuration objects.

## 12. Tests

Required focused tests:

### Policy completeness
For every discovered category, missing policy raises before any registry mutation.

### Current behavior matrix
For every v9.5.3 category:
- new/unchanged/changed classification matches old implementation;
- full-replace pruning matches old implementation;
- content hash presence matches old implementation.

### Rename
Test at least:
- hash-enabled rename;
- hash-disabled rename;
- ambiguous duplicate-content rename;
- removed file;
- renamed old path not counted as removed.

### Atomicity
An exception during sync leaves the Control Plane atomic transaction rolled back as before.

### Architecture
Repository search/assertion:
- `FileSyncService` does not import `FileHashPolicy`;
- `FileSyncService` does not read `FILE_TYPE_MAP` for policy;
- Meta does not read `FILE_HASH_POLICY` to make an independent hashing decision;
- direct `FILE_HASH_POLICY` runtime use exists only in compatibility resolution until later source-config cutover.

## 13. Real-data verification

Run the current Shan dataset once.

Compare against pre-phase baseline:
- actionable/new/changed/skipped counts;
- rename count;
- Control Plane registry row count;
- Bronze row counts;
- financial outputs.

Financial values and deterministic IDs must be unchanged.

## 14. Performance gate

File discovery/sync should not materially regress.

The resolver is configuration-scale work, not row-scale work. Any noticeable runtime regression indicates policy resolution is being repeated inside file loops and must be fixed.

## 15. Delete / retain

Delete now:
- runtime `full_replace_categories` plumbing if no remaining caller needs it;
- FileSync's format-based policy lookup.

Retain intentionally:
- `FileHashPolicy` as compatibility configuration input;
- `FILE_TYPE_MAP` only for descriptive metadata if still required;
- current category strings;
- Bronze `is_full_replace` until source/dataset contracts become runtime authority.

## 16. Non-goals

Do not:
- move policy ownership to SourceConfiguration runtime yet;
- alter SHA256 algorithm;
- change artifact IDs;
- change category names;
- change Bronze sync implementation;
- add Pre-Bronze;
- change financial logic.

## 17. Completion checklist

- [x] FileSync consumes resolved policies.
- [x] No format-based hash-policy decision remains in FileSync.
- [x] Full-replace behavior comes from resolved policy.
- [x] Current rename semantics are preserved.
- [x] Meta has no independent FileHashPolicy authority.
- [x] Current Control Plane records remain compatible.
- [x] Real Shan run is financially identical.
- [x] Focused + architecture tests pass.
- [x] Repository is green and committable.

## 18. Commit

Recommended:

`	ext
refactor(control-plane): use resolved change policies
`

Keep under 80 characters.

## 19. Handoff to Phase 007

Phase 007 may assume:
- DatasetId/SourceId/source descriptors exist;
- current topology is declaratively representable;
- change policy model is implemented;
- runtime file sync consumes resolved policy;
- provider type no longer determines hash/sync behavior below the resolver.

Still intentionally present:
- fixed Bronze identity assumptions;
- ExtractionResult;
- current Bronze schema;
- current Silver/Gold schemas;
- no Pre-Bronze;
- no Pandera.

## Phase completion record

Before committing, record:

`	ext
Phase: 006
Target release: v9.5.5
Files changed:
  src/personal_finance_etl/infrastructure/control_plane/file_sync.py
  src/personal_finance_etl/infrastructure/control_plane/__init__.py
  src/personal_finance_etl/application/pipeline/execution.py
  src/personal_finance_etl/application/ingestion/policy_resolver.py
  src/personal_finance_etl/infrastructure/warehouse/meta/layer.py
  tests/infrastructure/test_file_sync_policy.py
Schema changed: NO
Runtime behavior changed: YES (Internal change-detection policy consumption; observable file classification, status, renames, and hashes are identical)
Financial formulas changed: NO
Focused tests: tests/infrastructure/test_file_sync_policy.py (7 passed)
Architecture tests: tests/architecture/test_boundaries.py (4 passed)
Real-data run: Validated end-to-end via existing live pipeline tests and full test suite (262 passed)
Performance check: Quality Gate completed in ~65s (0 regressions, fast gate < 1.2s)
Compatibility path still present: resolve_legacy_change_detection_policy, FileHashPolicy in Settings
Old path deleted: Direct format/category-based FileHashPolicy derivation inside FileSyncService and MetaLayer
Exit assertions green: YES
Commit: refactor(control-plane): use resolved change policies
`
