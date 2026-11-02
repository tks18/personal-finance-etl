# Phase 005 - Change-Detection Policy Architecture

**Target release:** v9.5.5  
**Expected effort:** 3-4 hours  
**Previous:** Phase 004  
**Next:** Phase 006 - Change-Detection Runtime Cutover  
**Risk:** Low-Medium  
**Runtime behavior change:** None in this phase  
**Schema/persistence change:** None

## 1. Outcome

Define the future change-detection/synchronization policy model and an exact compatibility resolver that translates current v9.5.3 behavior into that model. No runtime consumer is switched yet.

At phase end PFETL can answer, for every current dataset/category, four separate questions:

1. Is a content fingerprint produced?
2. How is drift/change determined?
3. May content identity be used for rename detection?
4. Is the Bronze synchronization mode full-replace or incremental?

## 2. Why this phase follows topology modeling

Current v9.5.3 policy is split across:
- `Settings.FILE_HASH_POLICY` keyed by CSV/Excel/SQLite;
- `FILE_TYPE_MAP` mapping category to format;
- `BronzeDataContract.is_full_replace`;
- file-sync rename behavior using content hashes.

The new policy must attach to configured sources/datasets eventually, but runtime migration is unsafe until current semantics are reproducible exactly.

## 3. Inherited state

Phase 004 guarantees:
- SourceConfig/SourceDatasetConfig can represent current topology;
- each canonical Bronze DatasetId is classified;
- runtime still uses old categories/settings.

Phase 001 guarantees DatasetId, allowing policy resolution to be dataset-oriented rather than category-oriented in the future.

## 4. Current v9.5.3 anchors

### `config/settings.py`

```python
class FileHashPolicy(BaseModel):
    csv: bool = True
    excel: bool = False
    sqlite: bool = False
```

### `infrastructure/control_plane/hashing.py`

`FILE_TYPE_MAP` maps current categories to format strings such as `excel`, `sqlite`, `csv`, plus internal parquet history.

### `BRONZE_CONTRACT_REGISTRY`

`is_full_replace` currently determines full replacement versus incremental Bronze behavior.

### File synchronization

Current file sync derives whether hashing is enabled by resolving category -> file type -> `FileHashPolicy` boolean. Content hash also participates in rename identity logic, so "hash off" cannot be treated as an isolated optimization flag.

## 5. Target policy model

Create typed policy vocabulary under source configuration, not infrastructure.

Conceptual model:

```text
FingerprintStrategy
  NONE
  SHA256

DriftStrategy
  METADATA
  CONTENT

RenameStrategy
  DISABLED
  CONTENT_FINGERPRINT

SyncStrategy
  FULL_REPLACE
  INCREMENTAL

ChangeDetectionPolicy
  fingerprint_strategy
  drift_strategy
  rename_strategy
  sync_strategy
```

Exact enum names may differ, but the four responsibilities must remain separate.

## 6. Validity rules

At minimum:
- `DriftStrategy.CONTENT` requires a content fingerprint;
- `RenameStrategy.CONTENT_FINGERPRINT` requires a content fingerprint;
- `SyncStrategy` is independent of provider type;
- provider type cannot silently override an explicitly resolved dataset policy;
- the compatibility resolver must reproduce current v9.5.3 semantics, including rename behavior.

Do not invent unsupported strategies such as mtime+size combinations unless current code or a concrete target requirement justifies them.

## 7. Files in scope

### Create
- `config/sources/change_detection.py` (or equivalent within the Phase 002 source-config package)
- compatibility resolver in an application/config service location that does not make infrastructure own user policy

### Modify
- source configuration model only to allow future policy attachment if this can be done without premature runtime semantics
- focused tests

### Read/ground against but do not modify runtime yet
- `config/settings.py::FileHashPolicy`
- `infrastructure/control_plane/hashing.py::FILE_TYPE_MAP`
- `infrastructure/control_plane/file_sync.py`
- `infrastructure/warehouse/contracts.py::BronzeDataContract.is_full_replace`
- Meta/artifact repository hash consumers

### Explicitly do not modify
- `FileSyncService` behavior;
- Control Plane schema;
- Bronze persistence;
- file registry rows;
- rename implementation;
- Settings fields.

## 8. Compatibility resolver

Implement a resolver whose input is sufficient to reproduce current behavior, for example:

```text
current sync category
current ProviderType/file type mapping
Settings.FileHashPolicy
BronzeDataContract.is_full_replace
```

and whose output is a fully resolved `ChangeDetectionPolicy`.

The resolver is transitional. Phase 006 will make runtime consume resolved policy; later phases will resolve directly from SourceConfiguration.

## 9. Current-policy matrix test

Create a parameterized matrix for every current sync category. For each category assert:
- current provider/file type;
- current hash enabled/disabled state;
- expected fingerprint strategy;
- expected drift strategy;
- expected rename strategy;
- expected full/incremental sync strategy.

Do not leave provider-generated categories unexplained. If their sync semantics differ from file-backed artifacts, document/test that distinction explicitly.

## 10. Data flow

Before runtime remains:

```text
category -> FILE_TYPE_MAP -> FileHashPolicy -> file sync
category -> BronzeDataContract -> full/incremental
```

New dormant resolution path:

```text
current category + current settings + Bronze contract
    -> compatibility resolver
    -> ChangeDetectionPolicy
```

Phase 006 will switch runtime to the second path.

## 11. Persistence / identity / provenance / observability

No persistence changes.

No artifact ID or file hash values change.

No observability events change.

## 12. Tests

Required:
- invalid content-drift-without-fingerprint rejected;
- invalid content-rename-without-fingerprint rejected;
- same provider type can resolve different policy when explicit dataset policy is later supplied;
- compatibility matrix covers every current category;
- compatibility resolver reproduces CSV/Excel/SQLite current hash behavior;
- full-replace flag maps correctly;
- no runtime service imports the new model unless only for type-safe dormant wiring explicitly approved in this phase.

## 13. Real-data/performance

No real-data behavior test required beyond standard release regression because runtime is unchanged.

No performance impact.

## 14. Delete / retain

Retain completely:
- `FileHashPolicy`;
- `FILE_TYPE_MAP`;
- current FileSync logic;
- Bronze `is_full_replace`.

They are removed/migrated only after Phase 006 proves runtime equivalence.

## 15. Non-goals

Do not:
- switch FileSyncService;
- change hash calculation;
- change artifact IDs;
- change rename semantics;
- persist policy snapshots;
- implement source config fingerprinting yet.

## 16. Completion checklist

- [x] Four policy responsibilities are modeled separately.
- [x] Invalid combinations are rejected.
- [x] Compatibility resolver exists.
- [x] Every current category is covered by a policy matrix.
- [x] Current behavior is reproduced exactly in tests.
- [x] Runtime behavior is unchanged.
- [x] Phase fits the 3-4 hour boundary without pulling Phase 006 runtime migration forward.

## 17. Commit

`feat(config): model dataset change detection policy`

## 18. Handoff to Phase 006

Phase 006 may assume:
- every current category can be resolved to an explicit ChangeDetectionPolicy;
- the policy model separates fingerprint/drift/rename/sync semantics;
- current FileSync/Meta/artifact code still derives behavior from FileHashPolicy/FILE_TYPE_MAP;
- no persisted artifact behavior has changed.

Phase 006's sole responsibility is to migrate runtime consumers to the already-proven resolved policy while preserving exact Control Plane behavior.
