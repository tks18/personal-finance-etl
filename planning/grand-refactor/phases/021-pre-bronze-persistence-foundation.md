# Phase 021 - Pre-Bronze Persistence Foundation

**Target release:** v9.9.0  
**Expected effort:** 3-4 hours  
**Previous:** Phase 020  
**Next:** Phase 022  
**Risk:** High

## 1. Outcome

Introduce `pre_bronze` as a first-class DuckDB warehouse layer with typed contracts and both full-replace and artifact-keyed incremental persistence, participating in the existing run-wide DuckDB transaction. No production source is migrated to it yet.

The layer must be usable against controlled fixtures at phase end, not merely an empty schema/class scaffold.

## 2. Why this phase exists

Phase 020 completed the interpretation side of generalized ingestion: source configuration, mapping, identity, change policy, capability selection and provenance are all validated and fingerprinted. The next architectural responsibility is durable source-shaped tabular state.

Pre-Bronze must be proven transactionally before any real dataset depends on it.

## 3. Inherited repository state

Phase 020 guarantees:
- validated/fingerprinted SourceConfiguration per run;
- current fixed ingestion remains authoritative;
- existing DuckDB transaction covers Bronze/Silver/Gold/Meta;
- SQLite Control Plane and DuckDB use existing split-commit/recovery semantics;
- canonical provenance model exists;
- no Pandera or production generalized admission exists.

Do not change commit order.

## 4. Current codebase anchors

Current warehouse anchors:
- DuckDB schema initialization in `infrastructure/warehouse/schema/*`
- `infrastructure/warehouse/bronze.py::BronzeLayer`
- warehouse connection/transaction APIs
- `PipelineLifecycle.initialize/commit/handle_failure`
- Bronze full-replace and changed-file behavior
- Control Plane artifact IDs/provenance
- warehouse registry/contracts.

Use Bronze patterns only where semantics match. Pre-Bronze is source-shaped and must not inherit Bronze's future canonical assumptions.

## 5. Exact target state after this phase

DuckDB schemas include:
```text
pre_bronze   NEW
bronze
silver
gold
meta
```

Define `PreBronzeDataContract` keyed by stable `DatasetId` with persistence concerns only:
```text
dataset_id
physical_table
sync_strategy
provenance requirements
```

Pre-Bronze table schema is derived from validated/configured source shape, not PFETL canonical Bronze schema.

`PreBronzeLayer` supports:
- full replace;
- artifact-keyed incremental replacement/upsert semantics needed by current evidence;
- retrieval by DatasetId for normalization;
- provenance columns/metadata sufficient to associate rows with Control Plane artifact/source/dataset.

All writes occur inside the existing DuckDB transaction.

## 6. Detailed implementation sequence

### Step 1 - Add `pre_bronze` schema initialization
Create schema idempotently with existing warehouse bootstrap conventions. Add schema-presence tests.

### Step 2 - Define persistence contract
Add `PreBronzeDataContract`. Keep mapping, identity strategy and Pandera schema out of this persistence contract.

### Step 3 - Define physical-table naming
Use deterministic names derived from stable DatasetId/configured binding according to the target architecture. Prevent SQL injection/unsafe identifiers from user source names. Physical names are PFETL-controlled.

### Step 4 - Implement full-replace write
For a controlled fixture:
- create/replace table;
- preserve source-shaped columns;
- attach explicit artifact/source/dataset provenance;
- remain inside caller transaction.

### Step 5 - Implement artifact-keyed incremental write
Use stable Control Plane artifact identity, not filename, as replacement key.
For changed artifact:
1. delete rows belonging to that artifact identity;
2. insert current extracted rows.
For renamed-but-same artifact semantics, provenance remains stable according to Control Plane identity rules.

### Step 6 - Implement read API
Return source-shaped frame for one DatasetId or dataset/source binding. Do not construct `ExtractionResult`.

### Step 7 - Transaction proof
Begin DuckDB transaction, write Pre-Bronze fixture, raise deliberately, rollback, assert no partial state.

### Step 8 - Coexistence proof
Run existing pipeline with no production Pre-Bronze writes. Financial outputs unchanged.

## 7. Files and symbols in scope

Create/modify:
- warehouse schema initialization;
- `pre_bronze.py`;
- Pre-Bronze contract/registry;
- warehouse exports/bootstrap;
- focused persistence/transaction tests.

Read only:
- Bronze implementation for patterns;
- lifecycle commit order;
- Control Plane artifact repository.

Do not wire `PipelineExecutor` production extraction to Pre-Bronze.

## 8. Cross-cutting impacts

**Persistence:** new DuckDB schema/tables for tests/fixtures. Existing databases must initialize schema additively.

**Transactions:** Pre-Bronze uses existing DuckDB transaction. It never commits independently.

**Provenance:** artifact/source/dataset identity is explicit; filename is not the row replacement key.

**Identity:** Pre-Bronze does not generate financial/canonical IDs.

**Observability:** no production events required yet; layer methods may use existing component logging conventions.

**Performance:** writes should use DuckDB/Polars bulk paths, not row inserts.

## 9. Tests and verification

Required:
- schema initialization idempotent;
- full-replace fixture write/read;
- incremental changed-artifact replacement;
- unchanged artifact does not duplicate;
- rollback removes partial Pre-Bronze mutation;
- unsafe physical identifier rejected/sanitized by PFETL-owned naming;
- provenance retained;
- existing pipeline run unchanged;
- no independent commit call inside PreBronzeLayer.

## 10. Explicit non-goals

Do not:
- add Pandera;
- migrate a real source;
- alter Bronze;
- add financial mappings;
- add a third commit protocol;
- copy Bronze dynamic schema evolution blindly;
- use filename as new operational identity.

## 11. Completion checklist

- [ ] `pre_bronze` schema exists additively.
- [ ] Typed persistence contract exists.
- [ ] Full-replace persistence works.
- [ ] Artifact-key incremental persistence works.
- [ ] Reads return source-shaped data.
- [ ] Rollback is proven.
- [ ] No independent commit exists.
- [ ] Production pipeline still bypasses Pre-Bronze.

## 12. Commit boundary

```text
feat(warehouse): add pre-bronze persistence
```

## 13. Handoff to Phase 022

Phase 022 may assume Pre-Bronze can persist/read controlled source-shaped datasets transactionally. It must make that layer operationally first-class in Meta, backup/restore and recovery before any production dataset is allowed to depend on it.

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
