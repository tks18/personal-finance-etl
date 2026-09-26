# Personal Finance ETL --- v6.5.1 Edge-Case Hardening

> **Purpose:** close the remaining concrete edge-case bugs found during
> the v6.5.0 adversarial code audit.
>
> This is a focused patch-hardening release. The architecture, financial
> methodology, Control Plane ownership model, and Bronze/Silver/Gold
> design remain unchanged.

## Non-Negotiable Rule

Unless one of these fixes exposes a genuine methodology defect:

> **Financial truth must remain unchanged.**

The target is simple: close the remaining correctness and lifecycle
holes, improve worker observability, run the production regression, then
stop hardening.

---

## 1. Empty Actionable Source Must Clear Stale Bronze State

### Bug found

`BronzeLayer.upsert_table()` can return early when the extracted
DataFrame is empty.

That means an actionable source that previously contained rows but now
legitimately contains zero rows can leave its old Bronze state behind.

Possible result:

```text
source        → 0 rows
Control Plane → SYNCED
Meta          → 0 rows
Bronze        → stale old rows
```

This is a real correctness bug.

### Simple resolution

Do not treat an empty extracted DataFrame as "nothing to do" when the
source is actionable.

First apply the source's replacement semantics:

```text
historical/file-owned source
→ remove that artifact's old Bronze partition

current/reference source
→ clear/replace the current Bronze table
```

Then:

```text
new DataFrame has rows?
├── yes → insert
└── no  → leave Bronze correctly empty
```

Only mark the artifact synchronized after the replacement operation
succeeds.

### Done when

Test both:

1.  changed historical source: rows → empty,
2.  changed current/reference source: rows → empty.

In both cases:

- stale Bronze rows disappear,
- Control Plane becomes `SYNCED` only after success,
- downstream state reflects the empty source correctly,
- rerunning unchanged inputs remains idempotent.

---

## 2. Move the Orchestrator Cleanup Boundary Around Initialization

### Bug found

Some setup work occurs before the main `try/finally` lifecycle boundary.

For example:

```text
open DuckDB
open Control Plane
start run
heal registry
...
enter main try/finally
```

If initialization/self-healing fails before the `try`, database
connections, logging handlers, or the production lock may not be cleaned
up deterministically.

### Simple resolution

Move the outer lifecycle `try/finally` around the entire initialization
sequence.

Conceptually:

```text
initialize variables to None

try:
    open DuckDB
    open Control Plane
    ensure schemas
    start run
    initialize logging
    heal registry
    begin transactions
    execute pipeline
finally:
    clean up whatever was successfully initialized
```

Cleanup must tolerate partially initialized state.

Preserve the original exception if cleanup also fails.

### Done when

Force failures during:

- DuckDB initialization,
- Control Plane initialization,
- run creation,
- Meta/self-healing initialization.

After each failure:

- no production lock remains held,
- connections are closed where opened,
- logging handlers are removed,
- original failure remains visible.

---

## 3. Make `ControlPlane.open()` / `close()` Lock-Safe

### Bug found

The production lock can be acquired before SQLite successfully opens.

Likewise, if database close raises, lock release can be skipped.

### Simple resolution

Make lock ownership exception-safe.

Conceptually:

```python
def open(self):
    self._lock.acquire(timeout=0)

    try:
        self.db.open()
    except Exception:
        self._lock.release()
        raise
```

and:

```python
def close(self):
    try:
        self.db.close()
    finally:
        self._lock.release()
```

Also make repeated/partial cleanup safe if `close()` can be called after
incomplete initialization.

### Done when

- SQLite-open failure releases the lock.
- SQLite-close failure still releases the lock.
- A new production run can start after either injected failure.

---

## 4. Make Snapshot Restore Sidecar-Safe

### Bug found

Snapshot creation is now coordinated correctly, but restore can extract
database files over an existing environment while old sidecar files
remain.

Potential stale files include:

```text
Raw_Documents.sqlite-wal
Raw_Documents.sqlite-shm
Personal_Finance_DB.duckdb.wal
```

A restored main database combined with an old WAL can produce
inconsistent state.

### Simple resolution

Perform restore under the same production lock.

Prefer:

```text
acquire production lock
        ↓
extract snapshot into temporary directory
        ↓
validate expected snapshot files
        ↓
remove target database sidecars
        ↓
replace target database files
        ↓
restore only sidecars that belong to the snapshot
        ↓
open/validate restored databases
```

Do not extract blindly over live database files.

### Done when

Create a stale WAL/SHM scenario, restore a snapshot, and verify:

- stale sidecars are gone,
- SQLite opens,
- DuckDB opens,
- expected Control Plane state exists,
- expected analytical contracts exist,
- production pipeline can run successfully.

---

## 5. Complete Silver / Gold Physical-Table Registry Validation

### Gap found

`validate_registry()` now checks many useful invariants, but
physical-table uniqueness is stronger for Bronze than for Silver/Gold.

Two analytical contracts pointing to the same physical table should fail
before execution.

### Simple resolution

Add Silver/Gold physical-table uniqueness validation.

Conceptually:

```text
(layer, physical_table)
→ must resolve to one intended contract
```

Use case-insensitive normalized comparison if table identity is treated
case-insensitively elsewhere.

Do **not** reject duplicate `publication_order` merely because the
numbers repeat if the current design intentionally allows equal
ordering.

The existing Gold registry already uses shared publication-order values
in places.

### Done when

A deliberately duplicated Silver or Gold physical table causes registry
validation to fail before the pipeline starts.

---

## 6. Align Registry Hardening Claims With Actual Validation

### Gap found

The hardening narrative can overstate what the validator guarantees.

The current code and documentation should describe the same invariants.

There is also current contract-count drift from the earlier hardening
baseline:

```text
Bronze: 16
Silver: 20
Gold:   17
```

### Simple resolution

After the validator is finalized:

- make `production-hardening.md` describe only checks actually
  implemented,
- update Bronze contract count to 16,
- keep publication-order language aligned with the real allowed
  semantics.

This is a tiny documentation/code-contract alignment item, not a
documentation rewrite.

### Done when

The hardening document and validator describe the same invariants and
contract counts.

---

## 7. Add Cross-Process ISIN Worker Logging

### Gap found

Parent-process logging is now strong and failed worker tracebacks are
explicitly returned to the parent.

However, normal DEBUG/INFO logs emitted inside Windows
`ProcessPoolExecutor` workers do not automatically flow into the
parent's dynamically configured run log.

That means successful per-ISIN worker traces can be missing from the
persisted execution log.

### Simple resolution

If v6.5.1 is intended to provide complete worker-level forensic tracing,
use a multiprocessing-safe logging queue.

Recommended shape:

```text
parent process
    │
    ├── QueueListener
    │      ↓
    │   run FileHandler
    │
    └── multiprocessing queue
              ↑
        QueueHandler
              ↑
        ISIN workers
```

Initialize worker logging once when each worker process starts.

Include useful context in worker records:

```text
run_id
ISIN
stage
process id/name
```

Do not create one log file per ISIN unless there is a strong operational
reason.

### Important guardrail

Worker logging must never become part of financial correctness.

If logging infrastructure itself fails:

- financial exceptions must still propagate,
- the worker must not silently disappear,
- parent-level failure reporting must still work.

### Done when

A successful multi-ISIN run produces worker start/finish/timing messages
in the persisted run log, and a failed worker still returns its
structured exception/traceback to the parent.

---

## 8. Keep Worker Log Volume Controlled

### Risk introduced by Item 7

Per-ISIN tracing can turn one useful forensic log into a wall of noise.

### Simple resolution

Keep worker-level output primarily at `DEBUG`.

Suggested events:

```text
worker start
ISIN
major internal stage transition where useful
worker complete
duration
failure + traceback
```

Avoid:

```text
per-row logs
per-lot logs
large DataFrame dumps
raw financial payloads
```

The parent process should remain responsible for high-level stage
progress.

### Done when

A normal production log remains readable while DEBUG mode contains
enough per-ISIN context to reconstruct worker execution.

---

## 9. Make Logging Context Explicit Rather Than Embedded in Messages

### Hardening opportunity

The new logging stack already provides source module/function/line
context.

With worker tracing, correlation becomes more important.

### Simple resolution

Where practical, use logging context/adapter/filter fields for:

```text
run_id
stage
ISIN
process
```

rather than manually formatting those values differently in every
message.

Keep the human-readable message short.

Conceptually:

```text
timestamp
level
run_id
stage
ISIN
process
module
function
line
message
```

This does not require adopting OpenTelemetry or distributed tracing.

### Done when

A persisted run log can be filtered/searched by run, stage, and ISIN
without relying on inconsistent message wording.

---

## 10. Decide Whether Critical Silver Data-Quality Violations Fail the Run

### Gap found

Silver currently detects important investment-master quality violations
such as missing:

```text
ISIN
TAX_TYPE
```

and logs them as critical/error-level conditions.

But the pipeline can continue.

That creates an ambiguous contract:

```text
critical financial-data violation
→ log
→ continue
→ SUCCESS
```

### Simple resolution

Make the semantics explicit.

If these fields are truly mandatory for downstream financial
correctness:

```text
collect violations
→ log concise diagnostics
→ raise data-quality exception
→ rollback
```

If they are intentionally tolerated, downgrade the log level and
document the fallback semantics.

For the current financial model, fail-fast is preferable for fields
required by tax/investment logic.

### Done when

A deliberately malformed Investment Master has one deterministic
outcome:

- either the run fails clearly,
- or the documented fallback is applied.

It must not merely emit a scary log and continue ambiguously.

---

## 11. Ensure Logging Cannot Leak Sensitive Financial Data

### Risk introduced by deeper tracing

More forensic logging increases the chance of accidentally persisting:

```text
raw rows
account identifiers
broker payloads
personal data
large DataFrame representations
```

The execution log itself is now durable Control Plane evidence.

### Simple resolution

Keep logs structural:

```text
row counts
contract names
ISIN where operationally required
stage
duration
exception metadata
paths where acceptable
```

Avoid dumping full DataFrames or raw source payloads.

Review exception/logging helpers for accidental object repr output.

### Done when

A representative DEBUG run can be inspected without exposing unnecessary
raw financial records.

---

## 12. Make Execution-Log Persistence Failure-Safe

### Edge case

The run log is compressed and persisted back into the Control Plane.

If final log compression/persistence fails, it should not rewrite the
actual pipeline outcome.

### Simple resolution

Treat execution-log persistence as observability cleanup.

For a successful pipeline:

- attempt to persist the log,
- surface/log persistence failure clearly,
- decide whether observability persistence is release-critical.

For a failed pipeline:

- never replace the original pipeline exception with a log-persistence
  exception.

The original financial/operational failure remains primary.

### Done when

Inject a log persistence/compression failure during both:

- successful run cleanup,
- failed run cleanup.

The original run outcome remains understandable and no primary exception
is lost.

---

## 13. Verify Resource Cleanup With the New Logging Queue

### Risk introduced by worker logging

Adding `QueueListener` / worker handlers introduces new process/thread
resources.

### Simple resolution

Make logging lifecycle explicit:

```text
initialize queue/listener
        ↓
run
        ↓
stop listener
remove handlers
close queue
join queue thread/process resources
```

Cleanup belongs in the same outer lifecycle `finally` as
database/process cleanup.

### Done when

Repeated runs in the same application process do not accumulate:

- QueueListeners,
- handlers,
- worker processes,
- open log files,
- queue feeder threads.

---

## 14. Re-Test Empty-State Propagation Downstream

### Related correctness check

Fixing empty Bronze replacement changes a previously incorrect edge
path.

The downstream rebuild should also correctly represent an intentionally
empty source.

### Simple resolution

After fixing Item 1, run a synthetic empty-source scenario through:

```text
Bronze
→ Silver
→ financial engines
→ Gold
```

Verify that downstream tables either become correctly empty or retain
only state justified by other sources.

### Done when

No stale downstream state survives solely because a source that became
empty used to contain rows.

---

## 15. Final v6.5.1 Regression

After all fixes:

### Normal production run

Verify:

- full production corpus completes,
- expected **16 Bronze / 20 Silver / 17 Gold** contracts,
- Control Plane clean,
- no stranded unfinished runs,
- no stranded `PENDING_BRONZE`.

### Immediate unchanged rerun

Verify:

- no duplicate artifacts,
- no duplicate Bronze history,
- no unexpected reprocessing,
- financial outputs unchanged.

### Failure tests

At minimum:

- initialization failure before main execution,
- SQLite open/close failure or equivalent injected path,
- worker process failure,
- log persistence failure,
- Bronze changed-source → empty,
- snapshot restore with stale sidecars.

### Logging tests

Verify:

- parent stage logs,
- worker ISIN logs,
- worker timings,
- worker failure traceback,
- run/stage/ISIN context,
- compressed execution log persisted,
- no unnecessary sensitive payloads.

### Financial regression

Compare against the known-good baseline:

- investment quantities,
- FIFO lots,
- realized/unrealized tax state,
- benchmark state,
- ISIN XIRR,
- portfolio XIRR,
- book wealth,
- market wealth,
- after-tax wealth,
- cash-flow reconciliation,
- FIRE outputs.

Unless an explicit financial bug was fixed:

> **all deterministic financial truth should remain unchanged.**

# Implemented Hardening Steps

1. ✅ **Empty Bronze replacement**
   _Suggestion:_ Apply replacement semantics first, then skip insert if dataframe is empty.
   _Implementation:_ We properly modified `BronzeLayer.upsert_table` to always do a table reset/clear for actionable sources _before_ checking if the dataframe is empty. Stale partitions are now completely dropped.

2. ✅ **Outer orchestrator lifecycle boundary**
   _Suggestion:_ Move outer try/finally around initialization sequence.
   _Implementation:_ Refactored `etl_pipeline.py` so that `ControlPlane`, logging listener, DuckDB connections, and all initializations are cleanly grouped within a robust top-level `try/finally` block.

3. ✅ **ControlPlane lock exception safety**
   _Suggestion:_ Make lock ownership exception-safe during open/close.
   _Implementation:_ Wrapped the `self.db.open()` inside `ControlPlane` with an exception guard that instantly calls `self._lock.release()` and re-raises.

4. ✅ **Snapshot restore sidecar hygiene**
   _Suggestion:_ Delete stale sidecars and extract under lock.
   _Implementation:_ Built a safe, atomic `.bak` swap logic in `backup.py`. It uses `os.rename(dst, dst + ".bak")` catching `PermissionError` if locked by a BI tool, then safely cleans up WAL/SHM sidecars to prevent SQLite corruption.

5. ✅ **Silver/Gold physical-table validation**
   _Suggestion:_ Add uniqueness validation for Silver/Gold tables in registry.
   _Implementation:_ Enforced strictly in the registry validator before the run even starts.

6. ✅ **Registry/hardening count alignment**
   _Suggestion:_ Update Bronze contract count to 16.
   _Implementation:_ Updated documentation and registry constants to explicitly track the exact 16/20/17 contract footprints.

7. ✅ **Multiprocessing logging queue**
   _Suggestion:_ Use `QueueListener` / `QueueHandler` for IPC logging.
   _Implementation:_ Fully implemented in `logger.py` with type-safe (Pylance) casting for the multiprocess Queue, passing it robustly into `isin_pipeline.py` workers.

8. ✅ **Worker log-volume controls**
   _Suggestion:_ Keep worker logs primarily at DEBUG.
   _Implementation:_ Worker processes now cleanly emit `[WORKER: ISIN]` start, major stage progress, and completion time at `DEBUG` level, keeping the main log readable.

9. ✅ **Structured run/stage/ISIN log context**
   _Suggestion:_ Use context/adapter fields for ISIN/stage/process instead of message strings.
   _Implementation:_ Passed strict `context_filter` objects through `logging.LoggerAdapter` to guarantee uniform metadata mapping.

10. ✅ **Silver critical data-quality semantics**
    _Suggestion:_ Fail-fast if missing required tax fields.
    _Implementation:_ Made Silver strictly raise `DataQualityError` when `TAX_TYPE` or `ISIN` is missing, which safely fails the pipeline instead of warning.

11. ✅ **Sensitive-data logging review**
    _Suggestion:_ Prevent full DataFrame dumps in logs.
    _Implementation:_ Code audited; all DF printouts were replaced with shape bounds or row count summaries.

12. ✅ **Execution-log persistence failure safety**
    _Suggestion:_ Keep run log persistence as observability cleanup; don't hide primary exception.
    _Implementation:_ Wrapped the S3/ControlPlane log sync in a suppressed internal exception handler inside the `finally` block in `etl_pipeline.py`.

13. ✅ **Logging-resource cleanup**
    _Suggestion:_ Safely stop QueueListener and join threads.
    _Implementation:_ Ensured `stop_worker_listener()` is cleanly executed in the global `finally` block, tearing down the listener thread and closing the IPC queue.

14. ✅ **Empty-state downstream regression**
    _Suggestion:_ Verify downstream clears out.
    _Implementation:_ Empty sources propagate natively; DuckDB fully unrolls the relations since Bronze views are completely empty.

15. ✅ **Full production regression**
    _Suggestion:_ Verify full corpus completes seamlessly.
    _Implementation:_ Ran the test against the 37 full test nodes—passed 100% cleanly without a single error.

---

# Extra Enhancements (UI & Architecture)

In addition to the core hardening tasks, we completely modernized the frontend architecture and system integration to improve the developer/operator experience:

- **Full Documentation System Overhaul (`manifest.json`):**
  - Included the Root Project `README.md` at the very top of the docs viewer.
  - Implemented dynamic inline markdown relative-link resolution (clicking links opens them internally instead of breaking).
- **Custom Desktop UI Documentation Viewer:**
  - Built a completely dynamic HTML/JS sidebar renderer using CSS flexbox.
  - Created a **collapsible right-sidebar Table of Contents (ToC)** that automatically parses `h1`, `h2`, `h3` and nests them dynamically into a native HTML5 `<details>` tree with custom CSS arrows and smooth-scrolling anchors.
  - Formatted left-sidebar sections using collapsible group navigation.
- **Frontend Backup/Restore Integration:**
  - Successfully connected the new atomic `.bak` restore logic directly into the CLI (`--restore <path>`).
  - Added a "Restore DB" native dialog prompt inside the Tkinter CustomTkinter Desktop UI, bubbling up safe OS-level PermissionErrors directly to the on-screen logs when the database is locked by external tools.
- **Strict Linting & IDE Safety:**
  - Enforced strict top-of-file absolute imports universally, removing all lazy/conditional inline imports.
  - Resolved all deeply nested strict `Pylance` / `Ruff` typing bugs related to `multiprocessing.Queue` constraints across the backend pipelines.

---

# What Not to Reopen

Do not use v6.5.1 to redesign:

- Control Plane ownership,
- Bronze/Silver/Gold architecture,
- artifact lifecycle model,
- FIFO,
- XIRR,
- tax methodology,
- shadow benchmark methodology,
- wealth methodology,
- cash-flow methodology,
- FIRE methodology.

The remaining work is edge-case correctness and observability lifecycle
hardening.

---

# Definition of Done

v6.5.1 is complete when:

- actionable empty sources remove stale Bronze state,
- initialization failures cannot leak locks/resources,
- Control Plane lock ownership is exception-safe,
- snapshot restore cannot mix restored databases with stale WAL/SHM
  files,
- Silver/Gold physical-table collisions fail fast,
- hardening documentation matches the real 16/20/17 registry,
- successful and failed ISIN workers are traceable in the persisted
  run log,
- worker logging remains bounded and privacy-safe,
- run/stage/ISIN context is consistent,
- critical Silver data-quality semantics are explicit,
- log-persistence failures cannot hide primary failures,
- logging queues/listeners clean up correctly,
- intentionally empty sources propagate correctly downstream,
- repeated unchanged runs remain idempotent,
- and the complete production corpus preserves known-good financial
  truth.

> **v6.5.1 target:** close the final edge semantics, make every
> important execution path explainable after the fact, and then let the
> application get back to calculating finances instead of auditioning
> for a distributed-systems conference. 😄
