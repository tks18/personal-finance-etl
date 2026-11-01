# PFETL Grand Refactor Architecture

## 1. Target data spine

```text
Configured evidence
  -> SourcePlan
  -> Control Plane / Raw Store
  -> provider extraction
  -> source validation
  -> Pre-Bronze
  -> configured normalization
  -> identity resolution where required
  -> canonical Bronze validation
  -> Bronze
  -> capability-resolved financial execution
  -> Silver canonical financial state
  -> Gold analytical/decision state
```

## 2. Configuration boundaries

### Settings
Retains runtime/environment concerns such as target database location, Raw Store location, logs, retention and operational switches.

### SourceConfiguration
Will own external source topology: sources, datasets, selectors, mapping, bounded normalization, change detection, identity strategy and capability selection.

### FinancialRules
Remains separate and owns financial meaning/assumptions. Source configuration must not absorb financial methodology.

## 3. Ownership

- `contracts`: stable typed cross-boundary vocabulary such as DatasetId, SourceId, CapabilityId and runtime messages.
- `config`: user-authored validated configuration.
- `application`: source/capability planning and orchestration.
- `domain`: financial meaning and algorithms; no source-provider topology.
- `infrastructure`: providers, hashing, Pandera execution, Control Plane and warehouse persistence.
- `bootstrap`: concrete dependency assembly.
- `presentation`: CLI/Desktop interaction only.

## 4. Stable identities

### DatasetId
Canonical PFETL dataset identity. It is independent of frame key, physical table, source category and filename.

### SourceId
Stable configured physical-source identity, independent of provider type.

### CapabilityId
Stable financial execution capability identity.

Existing financial identities PURCHASE, SALE, LOT, REALIZED, RECON_LOT_GROUP, RECON_GROUP, RECON_EVENT and TAX remain owned by their current downstream financial stages.

## 5. Provider boundary

CSV, Excel and SQLite providers eventually own only physical extraction. They do not own canonical financial mappings or financial classification.

## 6. Change detection

Future policy separates:
- fingerprint strategy;
- drift strategy;
- rename strategy;
- synchronization strategy.

Provider type does not determine policy.

## 7. Persistence and recovery

Pre-Bronze joins the existing DuckDB transaction. Commit order remains DuckDB first, SQLite Control Plane second. Existing `RECOVERY_REQUIRED` semantics remain authoritative. No third commit truth is introduced.

## 8. Canonical layer semantics

- Raw Store: exact received evidence and operational provenance.
- Pre-Bronze: source-shaped extracted tabular evidence.
- Bronze: strict PFETL canonical evidence.
- Silver: canonical reconstructed financial state.
- Gold: PFETL-owned analytical/decision surfaces.

## 9. Migration discipline

Every phase must explicitly state:
- inherited state;
- exact target state;
- files/symbols to change;
- files/symbols forbidden to change;
- compatibility state;
- tests;
- deletion condition;
- handoff to the next phase.

No phase may leave a knowingly broken architecture for the next day.

## 10. Program-level closure rules

- `SourcePlanner` is an application service that compiles validated SourceConfiguration + ExecutionPlan into deterministic, non-I/O DatasetPlans.
- Legacy Gatekeeper validation is deleted after all production datasets use the Pandera admission boundaries.
- Temporary Phase-001 keys (`extraction_attribute`, `sync_category`, `contract_id`) require an explicit terminal disposition; DatasetId is the logical dataset authority.
- Removing/disabling a configured DatasetId cannot leave stale current-state Pre-Bronze/Bronze evidence, while historical Raw/Control Plane provenance remains governed by retention policy.
- Configured-but-empty datasets are semantically distinct from absent/disabled datasets.
- Existing multiprocessing observability correlation remains a final regression invariant.
- Final acceptance covers both clean installation and supported upgrade from existing pre-refactor operational state.
- Existing Desktop/presentation surfaces in the core application must remain compatible with capability-aware runtime state; companion Config Studio remains out of scope.
