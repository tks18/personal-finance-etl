# Personal Finance ETL --- Remaining Production Hardening

> **Scope:** only the remaining system-level weaknesses identified
> during the v6.2.2 / v6.2.3 code archaeology.
>
> This is **not** a generic production checklist. Packaging, repository
> metadata, documentation, and already-completed hardening are
> intentionally excluded.

## Guiding Rule

Unless a change intentionally modifies financial methodology:

**financial truth must remain unchanged.**

The remaining work is about making execution, recovery, synchronization,
and persistence harder to break.

------------------------------------------------------------------------

## 1. Recover Stale / Interrupted Runs

**What remains weak**

The Control Plane now tracks the full run lifecycle:

`STARTED → RUNNING → COMMITTING → SUCCESS / FAILED`

But a hard process termination can still leave the latest run
permanently sitting in an unfinished state such as `STARTED`, `RUNNING`,
or `COMMITTING`.

**What to harden**

At application startup, detect unfinished runs from previous processes
and close them explicitly as interrupted/failed before starting a new
run.

The recovery should:

-   preserve the old run record,
-   record why it was closed,
-   never modify a completed run,
-   allow the next run to proceed normally.

**Done when**

Kill the application during a run, restart it, and the system recovers
without manual database edits or a false `SUCCESS`.

------------------------------------------------------------------------

## 2. Harden the SQLite ↔ DuckDB Commit Window

**What remains weak**

SQLite and DuckDB are two independent embedded databases.

The orchestrator coordinates their transactions, but there is still a
small failure window around final commits because this is not a
distributed atomic transaction.

**What to harden**

Keep the existing application-coordinated transaction model.

Do **not** introduce distributed transaction machinery.

Instead:

-   make commit ordering explicit,
-   preserve the original exception if commit/rollback cleanup also
    fails,
-   ensure failed commit state is visible in the Control Plane,
-   ensure the next run can deterministically repair/rebuild analytical
    state.

**Done when**

A forced failure during final commit cannot leave the system looking
successful, and the next run restores a correct analytical state.

------------------------------------------------------------------------

## 3. Verify `SYNCED` Against Real Bronze State

**What remains weak**

The Control Plane can say an artifact is `SYNCED`, while DuckDB
analytical state could theoretically be missing or inconsistent because
of corruption, manual modification, interrupted persistence, or restore
mismatch.

This is the most important remaining Control Plane ↔ warehouse
consistency edge case.

**What to harden**

Add a lightweight consistency check around the analytical registry /
Bronze state.

If the Control Plane says an artifact is synchronized but the required
analytical representation is missing:

`SYNCED → PENDING_BRONZE → normal synchronization path`

The Control Plane remains authoritative.

Do not reconstruct operational history from DuckDB.

**Done when**

Delete or invalidate a known Bronze representation, run the pipeline,
and the system repairs itself from Control Plane evidence.

------------------------------------------------------------------------

## 4. Make `PENDING_BRONZE` Replay Fully Idempotent

**What remains weak**

`PENDING_BRONZE` is already the recovery seam between persisted raw
evidence and analytical synchronization.

The remaining risk is edge-case replay behaviour after a failure occurs
partway through Bronze synchronization.

**What to harden**

Prove that replaying the same pending artifact:

-   does not duplicate historical rows,
-   correctly replaces file-owned Bronze state,
-   leaves unrelated history untouched,
-   transitions to `SYNCED` only after successful persistence.

**Done when**

Force a failure during Bronze synchronization, rerun, and get exactly
the same Bronze and financial state as a clean run.

------------------------------------------------------------------------

## 5. Define Source Rename / Delete Behaviour

**What remains weak**

New and changed files are well defined through discovery + hashing.

Rename and deletion semantics are less explicit.

A renamed historical file could potentially look like a new artifact
while the old artifact remains registered, creating a duplicate-history
risk depending on Bronze ownership semantics.

Deletion has the opposite question: should previously ingested history
remain or disappear?

**What to harden**

Make the behaviour explicit by source type.

For **historical/event sources**, prioritize preservation of valid
historical evidence and prevention of duplicate partitions.

For **current/reference sources**, define whether source disappearance
means retain-last-known-state, clear state, or fail.

Avoid clever global hash deduplication unless it matches the actual
source semantics.

**Done when**

Rename and delete tests have deterministic outcomes and cannot silently
duplicate or erase financial history.

------------------------------------------------------------------------

## 6. Harden Worker Failure Propagation at the Process Boundary

**What remains weak**

The major worker-failure path has already been hardened: an ISIN failure
should fail the investment stage rather than silently publish an
incomplete portfolio.

The remaining concern is process-boundary edge cases such as worker
death, serialization failure, pool cleanup, or an exception occurring
outside the normal worker result path.

**What to harden**

Ensure every abnormal worker outcome reaches the orchestrator with
enough context to identify:

-   failed ISIN where known,
-   stage,
-   exception type,
-   message / traceback.

The parent must never continue to successful publication with a missing
worker result.

**Done when**

Artificially kill/fail one worker and confirm:

`worker failure → orchestrator failure → rollback → persisted failure → run FAILED`

No partial portfolio is published.

------------------------------------------------------------------------

## 7. Prevent Overlapping Production Runs

**What remains weak**

The architecture assumes one authoritative production run is mutating
the local Control Plane and DuckDB at a time.

If CLI/GUI/headless execution can accidentally start two runs together,
that assumption can break.

**What to harden**

If there is no protection already, add a simple single-run guard.

It can be based on an application lock or an active-run mechanism, but
stale-lock recovery must be possible after a crash.

Do not build a distributed scheduler.

**Done when**

Starting a second production run while one is active is rejected
cleanly, while a stale lock from a dead process can be recovered.

------------------------------------------------------------------------

## 8. Validate Data Contracts Before Publication

**What remains weak**

`DataContract` is now the correct source for analytical identity, grain,
physical table, producer, and publication order.

The remaining risk is configuration/code drift being discovered only
when a table is written or consumed.

**What to harden**

Add one fail-fast registry validation covering the important invariants:

-   unique `contract_id`,
-   valid layer,
-   physical table identity,
-   non-empty grain,
-   producer,
-   deterministic publication order,
-   expected Silver / Gold contract population.

Where practical, validate builder output against the expected physical
contract before publication.

**Done when**

A deliberately broken contract or mismatched output fails immediately
with a clear error instead of creating a partially valid warehouse.

------------------------------------------------------------------------

## 9. Treat SQLite + DuckDB as One Recovery Unit

**What remains weak**

The architecture changed when SQLite became the authoritative Control
Plane.

A DuckDB-only snapshot no longer represents the complete recoverable
system.

The logical production state is now:

`Raw_Documents.sqlite + Personal_Finance_DB.duckdb`

**What to harden**

Update the snapshot/restore concept so both databases belong to one
logical backup.

The important part is consistency, not sophistication.

A backup should make it clear which SQLite and DuckDB files belong
together.

**Done when**

Restore both databases into a clean location, run the pipeline, and
recover the same financial state without reconstructing Control Plane
history manually.

------------------------------------------------------------------------

## 10. Final Idempotency + Financial Regression

This is the release gate after the above fixes.

Run the complete production corpus.

Then immediately run it again with unchanged inputs.

Verify:

-   no duplicate artifacts,
-   no duplicate Bronze history,
-   no unexpected reprocessing,
-   Control Plane state remains clean,
-   expected **20 Silver / 17 Gold** contracts remain intact,
-   financial outputs reconcile with the known-good baseline.

At minimum compare:

-   investment quantities,
-   FIFO lot state,
-   realized / unrealized tax state,
-   benchmark state,
-   ISIN and portfolio XIRR,
-   book / market / after-tax wealth,
-   cash-flow reconciliation,
-   FIRE outputs.

Runtime can be recorded, but it is not the correctness criterion.

------------------------------------------------------------------------

# Recommended Order

1.  **Stale run recovery**
2.  **SQLite ↔ DuckDB commit-window handling**
3.  **`SYNCED` ↔ Bronze self-healing**
4.  **`PENDING_BRONZE` replay**
5.  **Rename / delete semantics**
6.  **Worker process-boundary failures**
7.  **Single-run protection**
8.  **DataContract validation**
9.  **Coordinated SQLite + DuckDB backup**
10. **Full production regression**

------------------------------------------------------------------------

# What Not to Touch

Unless one of the tests above exposes a real defect, do not reopen:

-   FIFO methodology,
-   XIRR methodology,
-   shadow benchmark methodology,
-   tax methodology,
-   household wealth methodology,
-   FIRE methodology,
-   Silver / Gold architecture,
-   Control Plane ownership model.

Those are not the target of this pass.

------------------------------------------------------------------------

# Definition of Done

The system is production-hardened for this cycle when:

-   interrupted executions recover cleanly,
-   a failed commit cannot masquerade as success,
-   Control Plane / Bronze drift repairs through the normal pipeline,
-   pending artifacts replay without duplication,
-   rename/delete behaviour is deterministic,
-   worker failures cannot produce incomplete portfolios,
-   overlapping production runs are prevented,
-   broken analytical contracts fail before publication,
-   SQLite and DuckDB can be recovered as one logical system,
-   repeated unchanged runs are idempotent,
-   and the full production corpus produces the same financial truth as
    the known-good baseline.

> **Target state:** the remaining failure modes are boring, visible,
> recoverable, and incapable of silently changing financial truth.
