# Personal Finance ETL --- v6.4.0 Production Hardening

> **Purpose:** consolidate the remaining runtime and recovery weaknesses
> found during the v6.3.0 archaeology into one deliberate hardening
> release.
>
> This is not another architecture redesign. The current Control Plane,
> Bronze/Silver/Gold model, and financial engines remain the baseline.

## Non-Negotiable Rule

Unless a change intentionally fixes a proven financial-methodology
defect:

> **Financial truth must remain unchanged.**

The goal of v6.4.0 is to make the existing architecture more
deterministic under failure, replay, corruption, rename, restore, and
concurrent execution.

---

## 1. Make `PENDING_BRONZE` Replay Part of the Normal Pipeline

### Quirk found

The v6.3.0 self-healing path can change an artifact from `SYNCED` to
`PENDING_BRONZE`.

However, normal discovery primarily builds actionable work from **new +
changed files**.

An unchanged file that was requeued to `PENDING_BRONZE` can therefore
remain pending without being picked up by the normal execution path.

### Simple resolution

After discovery, merge Control Plane pending artifacts into the
actionable set before extraction/Bronze synchronization.

Conceptually:

```text
new files
+
changed files
+
Control Plane PENDING_BRONZE
        ↓
deduplicate
        ↓
normal extraction / Bronze synchronization
```

Do not create a separate recovery pipeline.

### Done when [IMPLEMENTED]

- A `SYNCED` artifact is manually/self-healed to `PENDING_BRONZE`.
- Its source file is unchanged.
- The next normal production run replays it.
- Bronze is restored.
- The artifact returns to `SYNCED`.
- Financial outputs remain unchanged.

---

## 2. Make `PENDING_BRONZE` Replay Idempotent

### Quirk found

Once pending artifacts are replayed normally, the replay itself must be
proven safe after partial Bronze failures.

The risk is duplicate historical rows or mixed old/new state.

### Simple resolution

Use the existing Bronze ownership semantics.

For historical/file-owned sources:

```text
remove/replace that artifact's owned Bronze partition
→ write current artifact state
```

For current/reference sources:

```text
prepare replacement successfully
→ replace current state
```

Only mark the artifact `SYNCED` after successful Bronze persistence.

### Done when [IMPLEMENTED]

A forced failure during Bronze synchronization followed by a rerun
produces exactly the same Bronze and downstream financial state as a
clean run.

---

## 3. Fix Rename Identity Migration

### Quirk found

Artifact identity is path-derived:

```text
file_id = SHA256(relative_path)
```

v6.3.0 rename handling updates the path/name but can leave the original
`file_id`.

That breaks the identity invariant and can disconnect the registry
record from payload lookup.

### Simple resolution

Make rename a first-class `ArtifactRepository` operation.

A rename should migrate all path-derived identity consistently:

```text
old relative path
old file_id
old payload relationship
old analytical registry identity

        ↓ rename

new relative path
new file_id
payload preserved
analytical identity updated
```

Perform the migration inside the existing Control Plane transaction.

Do not update `relative_path` alone.

### Done when [IMPLEMENTED]

After a rename:

- `file_id` matches the new normalized path,
- raw payload remains accessible,
- no duplicate artifact exists,
- old identity is gone,
- new identity is present,
- Bronze ownership remains correct,
- downstream financial state does not change.

---

## 4. Scope Rename Detection by Source Category

### Quirk found

Rename detection can match files primarily by content hash across the
wider registry.

Two unrelated source categories can legitimately contain identical
bytes.

That creates a theoretical false-rename path.

### Simple resolution

Match rename candidates by:

```text
(source category, content hash)
```

rather than:

```text
content hash only
```

Optionally include other existing identity context if already available,
but avoid overengineering.

### Done when [IMPLEMENTED]

Identical files in different source categories cannot be classified as
renames of one another.

---

## 5. Define Rename Behaviour in Bronze and Meta

### Quirk found

A filesystem rename is the same evidence with a different location/name.

Historical Bronze ownership and analytical registry state may still
reference the old filename/path even after the Control Plane rename.

### Simple resolution

Treat a pure same-content rename as an identity migration, not a
financial-data change.

For historical/file-owned Bronze:

- migrate the ownership marker such as `__file_name__`, or
- deliberately replay the artifact while removing the old owned
  partition.

For DuckDB Meta/current registry projection:

- update the path/name/file identity consistently.

Choose one deterministic approach and use it everywhere.

### Done when [IMPLEMENTED]

A rename changes only provenance/identity metadata.

Row counts and financial outputs remain identical.

---

## 6. Make Delete Semantics Explicit

### Quirk found

Rename work exposes the related question of source deletion.

The correct behaviour is not necessarily the same for historical
evidence and current/reference state.

### Simple resolution

Define deletion by source semantics.

For historical/event evidence, prefer preserving already-ingested valid
history unless the domain explicitly says source deletion means
financial deletion.

For current/reference sources, explicitly choose whether disappearance
means:

- retain last known state,
- clear current state,
- or fail the run.

Do not let filesystem absence accidentally decide financial meaning.

### Done when [IMPLEMENTED]

Delete tests for each source class have deterministic outcomes and
cannot silently erase or duplicate financial history.

---

## 7. Strengthen Control Plane ↔ Bronze Self-Healing

### Quirk found

v6.3.0 self-healing primarily checks registry/table presence.

A Bronze table can exist while one specific historical artifact's rows
are missing.

That means table-level presence is weaker than artifact-level integrity.

### Simple resolution

For historical/file-owned Bronze contracts, validate that each `SYNCED`
artifact has its expected ownership marker represented in Bronze, where
the contract supports such a marker.

Conceptually:

```text
Control Plane says artifact = SYNCED
        ↓
Bronze table exists?
        ↓
artifact-owned partition exists?
        ↓
yes → healthy
no  → PENDING_BRONZE
```

For current/reference tables where artifact-level ownership does not
apply, retain table/state-level checks.

### Done when [IMPLEMENTED]

Deleting one historical artifact's Bronze rows, while leaving the table
itself intact, causes that artifact to be requeued and restored
automatically.

---

## 8. Harden the SQLite ↔ DuckDB Commit Window

### Quirk found

SQLite and DuckDB remain independent databases.

The current orchestrator coordinates their transactions, but a process
failure between final commits can still leave operational and analytical
state temporarily inconsistent.

This is an architectural limitation, not a reason to introduce
distributed transactions.

### Simple resolution

Keep the current application-coordinated transaction model.

Harden it by making the recovery contract explicit:

```text
DuckDB commit succeeds
SQLite finalization fails
        ↓
next startup/run detects inconsistency
        ↓
Control Plane remains operational authority
        ↓
requeue/rebuild analytical state as needed
```

Also ensure:

- original exceptions survive cleanup,
- rollback failures are logged separately,
- `SUCCESS` is impossible before required finalization succeeds,
- stale `COMMITTING` runs are recoverable.

### Done when [IMPLEMENTED]

Injected failures around each final commit never produce a false
successful run, and the next execution reaches the same correct state
without manual database surgery.

---

## 9. Strengthen Interrupted-Run Recovery

### Quirk found

v6.3.0 added stale-run recovery, which is good.

The remaining hardening is to make the recovery decision fully
deterministic across all unfinished states and related artifact state.

### Simple resolution

At startup:

```text
find stale STARTED / RUNNING / COMMITTING
        ↓
close them explicitly as interrupted/failed
        ↓
record recovery reason
        ↓
reconcile pending analytical work
        ↓
start new run
```

Never mutate completed `SUCCESS`/`FAILED` history.

### Done when [IMPLEMENTED]

Hard-killing the process at different lifecycle stages and restarting
always produces an explainable previous run plus a clean new run.

---

## 10. Harden Worker Process-Boundary Failures

### Quirk found

Normal per-ISIN exceptions now propagate correctly.

The remaining risk is abnormal process behaviour outside the normal
result path:

- worker termination,
- serialization/deserialization failure,
- pool failure,
- cleanup failure.

### Simple resolution

Treat any missing/abnormal worker result as fatal.

The parent should retain as much context as possible and propagate
failure to the orchestrator.

```text
abnormal worker
→ investment stage fails
→ rollback
→ persisted failure
→ run FAILED
```

Never infer success from the workers that did return.

### Done when [IMPLEMENTED]

Force-killing one worker cannot result in a successfully published
partial portfolio.

---

## 11. Make Single-Run Protection Crash-Safe

### Quirk found

v6.3.0 introduced a production `FileLock`, which closes the normal
overlapping-run problem.

The remaining concern is stale/crash behaviour and ensuring every
production entry point uses the same lock.

### Simple resolution

Verify that:

- CLI uses the lock,
- GUI uses the lock,
- headless/backend production entry points use the lock,
- backup/snapshot uses the same lock where required,
- stale locks recover according to the file-lock library's actual
  semantics.

Keep one lock identity for the production database pair.

### Done when [IMPLEMENTED]

Two live runs cannot overlap, but a dead process does not permanently
block future execution.

---

## 12. Make SQLite + DuckDB Snapshot Actually Consistent

### Quirk found

v6.3.0 correctly recognizes that the recoverable system is now:

```text
Raw_Documents.sqlite
+
Personal_Finance_DB.duckdb
```

But copying live database files directly is not enough.

SQLite uses WAL mode, so committed state can exist in the WAL rather
than only in the main `.sqlite` file.

A snapshot can also race a production writer.

### Simple resolution

Use the same production lock before snapshotting.

Then:

- create SQLite copy using SQLite's backup API,
- create DuckDB copy only while no production writer is active,
- package the two copies into one snapshot,
- record enough metadata to identify the pair.

No elaborate backup framework is required.

### Done when [IMPLEMENTED]

A snapshot restored into a clean location contains both operational and
analytical state and can successfully run/reconcile without needing the
original databases.

---

## 13. Add Snapshot Restore Verification

### Quirk found

Creating a ZIP proves files were copied, not that the system is
recoverable.

### Simple resolution

Add a simple verification path/test:

```text
create coordinated snapshot
        ↓
restore into clean temp location
        ↓
open SQLite
open DuckDB
        ↓
run basic integrity/contract checks
        ↓
optionally execute production pipeline
```

This can be a test/tool rather than part of every production run.

### Done when [IMPLEMENTED]

A real snapshot has been restored and proven usable.

---

## 14. Complete DataContract Registry Validation

### Quirk found

v6.3.0 added useful fail-fast registry validation.

The remaining gap is that some invariants are stronger for Bronze than
Silver/Gold.

### Simple resolution

Validate across the relevant registry:

- unique `contract_id`,
- valid layer,
- unique physical table where required,
- non-empty grain,
- non-empty producer,
- deterministic publication order,
- expected contract counts.

For the current baseline:

```text
15 Bronze
20 Silver
17 Gold
```

If duplicate publication order is not intentionally supported within a
layer, reject it.

### Done when [IMPLEMENTED]

A deliberately duplicated physical table, contract ID, or invalid
publication order fails before pipeline execution.

---

## 15. Validate Builder Output Against Persisted Contract

### Quirk found

Registry validation proves metadata consistency.

It does not necessarily prove that the DataFrame a producer emits still
matches the physical table contract.

Builder ↔ DDL drift can therefore surface late.

### Simple resolution

Before publication, perform a lightweight contract check where
practical:

- required columns present,
- unexpected/missing persisted columns handled intentionally,
- physical table exists,
- types are compatible enough for the current loader.

Do not build a second schema framework if DuckDB/loader metadata can
provide the check.

### Done when [IMPLEMENTED]

A deliberately broken builder output fails with a clear contract error
before partial publication.

---

## 16. Validate Meta Projection From the Same Contract Authority

### Quirk found

The system has intentionally made `DataContract` the authority for
analytical identity.

Any remaining Meta/row-count logic that derives layer/table identity
from names or parallel mappings would reintroduce drift.

### Simple resolution

Ensure all Silver/Gold row-count and current analytical projection logic
resolves identity through `DataContract`.

Remove or avoid parallel manual mapping tables for the same identity.

### Done when [IMPLEMENTED]

Renaming a physical table in the registry produces one obvious set of
required changes rather than hidden secondary mappings.

---

## 17. Prove Raw-Payload Recovery End-to-End

### Quirk found

Raw payload persistence is a core recovery feature, but design intent is
weaker than a proven recovery test.

### Simple resolution

Use a synthetic source:

```text
ingest file
→ payload persisted
→ remove original source
→ invalidate/requeue analytical state
→ recover from Control Plane evidence
```

If the normal production pipeline intentionally requires source presence
for some categories, document that boundary explicitly rather than
claiming universal raw replay.

### Done when [IMPLEMENTED]

The supported raw-evidence recovery path has been demonstrated
end-to-end.

---

## 18. Check Resource Cleanup Under Failure and Repeated Runs

### Quirk found

v6.3.0 focuses correctly on logical recovery.

The final operational concern is whether failure paths leave worker
pools, transactions, large frames, or temporary resources alive.

### Simple resolution

Run repeated executions in the same process where supported and inject
at least one worker/stage failure.

Observe:

- worker processes,
- database connections/transactions,
- temporary files,
- memory trend.

Do not chase normal allocator caching; look for clear monotonic leakage
or orphaned resources.

### Done when

Repeated successful/failed runs do not accumulate orphan workers, open
transactions, or obvious unbounded memory.

---

## 19. Final Clean-Rebuild Equivalence

### Quirk found

Self-healing and incremental replay are only trustworthy if they
converge to the same result as a clean analytical rebuild.

### Simple resolution

For a representative production state, compare:

```text
incremental/self-healed execution
        vs
clean Bronze-derived downstream rebuild
```

Compare financial outputs, not only row counts.

### Done when

Both paths converge to the same deterministic financial truth.

---

## 20. Final Production Regression

After all v6.4.0 hardening is complete:

1.  Run the complete production corpus.
2.  Immediately rerun with unchanged inputs.
3.  Exercise at least one recovery scenario.
4.  Restore at least one coordinated snapshot.
5.  Compare against the known-good financial baseline.

Verify:

- no duplicate Control Plane artifacts,
- no duplicate Bronze history,
- no stranded `PENDING_BRONZE`,
- no stale unfinished runs,
- no partial portfolio publication,
- expected **15 Bronze / 20 Silver / 17 Gold** contracts,
- investment quantities reconcile,
- FIFO lots reconcile,
- tax state reconciles,
- benchmark state reconciles,
- ISIN/portfolio XIRR reconciles,
- book/market/after-tax wealth reconciles,
- cash-flow reconciliation remains correct,
- FIRE outputs remain consistent with the existing methodology.

Runtime is an observation, not the correctness criterion.

---

# Recommended Implementation Order

```text
1. PENDING_BRONZE normal replay
2. PENDING_BRONZE idempotency
3. rename identity migration
4. category-scoped rename detection
5. Bronze/Meta rename ownership
6. explicit delete semantics
7. artifact-level Bronze self-healing
8. commit-window recovery
9. stale-run recovery verification
10. abnormal worker failure handling
11. crash-safe single-run protection
12. consistent coordinated snapshots
13. snapshot restore verification
14. complete DataContract validation
15. builder ↔ persisted-contract validation
16. Meta contract-authority cleanup
17. raw-payload recovery proof
18. resource cleanup tests
19. clean-rebuild equivalence
20. full production regression
```

---

# What v6.4.0 Is Not

Do **not** use this release to redesign working financial methodology
unless testing exposes an actual defect.

Keep stable:

- FIFO methodology,
- XIRR methodology,
- shadow benchmark methodology,
- tax methodology,
- household wealth methodology,
- cash-flow methodology,
- FIRE methodology,
- Control Plane ownership model,
- persistent Bronze + rebuilt Silver/Gold architecture.

This release should strengthen the shell around those systems.

---

# Definition of Done

v6.4.0 is hardened when:

- recovery work always re-enters the normal pipeline,
- replay is idempotent,
- rename/delete behaviour is deterministic,
- path-derived identity remains internally consistent,
- Control Plane can repair missing artifact-level Bronze state,
- commit-window failures are recoverable,
- stale runs are explainable,
- abnormal worker failure cannot publish partial finance,
- concurrent execution is safely rejected,
- snapshots are consistent and proven restorable,
- analytical contracts fail fast when broken,
- raw-evidence recovery has been demonstrated,
- repeated runs do not leak operational resources,
- incremental/self-healed state converges with clean rebuild state,
- and the full production corpus preserves the known-good financial
  truth.

> **v6.4.0 target:** no clever new architecture; just make the existing
> architecture boringly difficult to break.
