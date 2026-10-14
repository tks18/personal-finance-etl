# Personal Finance ETL — Architecture Bugs, Hardening & Features

> **Purpose:** increase lineage, stability, recovery, and operational clarity.
>
> Architecture stays deterministic. **No ML or AI belongs in this file.**

---

# 1. Architecture hardening

## SYS-HARD-01 — Explicit cross-database commit state machine

**Priority:** High

Build transaction state into orchestration rather than inferring it from logs.

```text
STARTED
  ├─ rollback → ROLLED_BACK
  └─ DuckDB commit → DUCKDB_COMMITTED
                      ├─ SQLite commit → FULLY_COMMITTED
                      └─ SQLite failure → RECOVERY_REQUIRED
                                            ↓
                                         CONVERGED
```

Persist the final state in the Control Plane.

This becomes the authority for recovery messaging and run status.

---

## SYS-HARD-02 — Special handling for stale `COMMITTING`

**Priority:** High

A stale `STARTED` run and stale `COMMITTING` run have different risk.

Recovery logic should:

```text
STARTED / RUNNING stale
    → no commit expected; mark interrupted using normal policy

COMMITTING stale
    → inspect known commit state / analytical state
    → classify as committed, recovery-required, or uncertain
```

Never downgrade uncertain commit state to an ordinary pre-commit failure.

---

## SYS-HARD-03 — Structured external-provider provenance

**Priority:** High

For every market/FX/benchmark request persist:

```text
provider
entity / ticker / ISIN
requested_start
requested_end
attempt_count
status
failure_class
final_error
```

Attach it to existing run/error provenance.

Do not create a separate logging subsystem.

---

## SYS-HARD-04 — Artifact synchronization completeness

**Priority:** High

Add a run-level synchronization summary:

```text
Actionable_Count
Synced_Count
Healed_Count
Failed_Count
Deferred_Count
Sync_Status
```

Suggested status:

```text
COMPLETE
PARTIAL
FAILED
NOT_REQUIRED
```

This separates:

```text
pipeline process ended
```

from:

```text
all actionable source evidence synchronized
```

---

## SYS-HARD-05 — First-class healing lineage

**Priority:** Medium–High

Healing should record:

- inconsistency detected;
- artifact/table affected;
- previous sync state;
- state reset performed;
- detecting run;
- replay run;
- convergence result.

Use normal artifact/run events so healing remains part of one provenance model.

---

## SYS-HARD-06 — Snapshot / restore outcome model

**Priority:** Medium–High

Replace generic outcomes with explicit states:

```text
SNAPSHOT_STARTED
SNAPSHOT_VALIDATED
SNAPSHOT_PUBLISHED
SNAPSHOT_FAILED

RESTORE_VALIDATION_FAILED
RESTORE_INSTALL_STARTED
RESTORE_SUCCEEDED
RESTORE_INSTALL_FAILED_ROLLED_BACK
RESTORE_STATE_UNCERTAIN
```

The final state must tell an operator whether production still contains the old pair, the new pair, or requires inspection.

---

## SYS-HARD-07 — Machine-readable failure taxonomy

**Priority:** Medium

Add a failure-domain field alongside exception type/message/traceback:

```text
CONFIGURATION
SOURCE_DISCOVERY
SOURCE_VALIDATION
EXTERNAL_PROVIDER
BRONZE_SYNC
TRANSFORMATION
FINANCIAL_INVARIANT
PUBLICATION
DUCKDB_COMMIT
SQLITE_COMMIT
RECOVERY
SNAPSHOT
RESTORE
WORKER
UNKNOWN
```

Do not replace detailed errors. Add classification for filtering and diagnosis.

---

## SYS-HARD-08 — Consistent parallel-workload policy

**Priority:** Medium

For every executor/thread/process workload explicitly define:

1. Does one worker failure invalidate the whole batch?
2. Are pending workers cancelled?
3. Can completed partial results publish?
4. What worker context reaches the parent?
5. How is executor shutdown guaranteed?

Use a small shared policy/result abstraction where practical.

---

## SYS-HARD-09 — Runtime guarantee-language audit

**Priority:** Medium

Search user-facing logs/messages for:

```text
atomic
rolled back
recovered
validated
complete
synchronized
successful
```

For each message identify the state that proves the claim.

Replace vague success text with exact state where needed.

Example:

```text
bad:
"Transactions completely rolled back"

better:
"DuckDB committed; SQLite commit failed. Recovery required."
```

---

## SYS-HARD-10 — Deterministic source/schema drift guardrails

**Priority:** Medium

Before any source enters canonical transformation, compare its observed shape with expectations:

```text
required columns
unexpected columns
data types
null-rate limits where meaningful
category/domain values
date coverage
```

Classify differences:

```text
EXPECTED
WARNING
BREAKING
```

Breaking drift fails ingestion before malformed source changes leak downstream.

---

# 3. Architecture features

## SYS-FEAT-01 — Run health envelope

**Priority:** High · **Best next architecture feature**

### Goal

Give every run one compact operational health record.

Suggested dimensions:

```text
Run_Status
Artifact_Sync_Status
External_Evidence_Status
Financial_State_Status
Publication_Status
Recovery_Status
```

Overall status:

```text
HEALTHY
REVIEW
FAILED
RECOVERY_REQUIRED
```

### Implementation

Build it from existing Control Plane events, synchronization results, publication status, and domain status. Do not invent a second source of truth.

Expose in CLI/Desktop and persist with the run.

### Done when

A user can distinguish “the process exited” from “the complete system state is healthy” in one view.

---

## SYS-FEAT-02 — Run-to-run diff

**Priority:** High

### Goal

Explain what changed between two runs.

Compare:

- discovered/changed/removed artifacts;
- Settings / FinancialRules fingerprints;
- contract row counts;
- reconciliation-event counts;
- TaxEvent counts/status;
- publication changes;
- recovery/healing events.

Output a structured diff plus concise CLI/Desktop summary.

### Implementation

Use run IDs as the comparison boundary and existing snapshots/events as sources. Avoid comparing arbitrary current tables without provenance.

### Done when

A user can answer “what changed since the last successful run?” without reading raw logs.

---

## SYS-FEAT-03 — Lineage explorer

**Priority:** High

### Goal

Navigate the provenance chain:

```text
Gold output
→ Silver contract
→ financial event / lot
→ Bronze table/state
→ source artifact
→ artifact event
→ run
```

### Implementation

Start deterministic and metadata-driven:

1. contract registry gives producer/layer/grain;
2. deterministic financial IDs connect event state;
3. Bronze ownership/source columns connect evidence;
4. Control Plane connects artifact and run history.

Begin with CLI text/table output. Add Desktop graph visualization only after the lineage API is stable.

### Done when

A selected analytical object can be traced toward its source/run without manual SQL archaeology.

---

## SYS-FEAT-04 — Recovery dashboard

**Priority:** Medium–High

Show operational recovery state:

```text
stale runs
recovery-required runs
latest healing events
unsynchronized artifacts
latest valid snapshot
latest restore
restore outcome
```

Source everything from Control Plane/recovery metadata.

This is an operational surface, not a Gold finance mart.

---

## SYS-FEAT-05 — Contract evolution report

**Priority:** Medium

### Goal

Make warehouse evolution explicit.

Persist or generate a contract/schema fingerprint and compare it with the previous baseline.

Report:

```text
contract added / removed
column added / removed
type changed
grain changed
producer changed
publication order changed
```

Classify changes as informational or breaking according to simple deterministic rules.

### Done when

A schema change is visible as an intentional contract change instead of being discovered later by Power BI or downstream code.

---

## SYS-FEAT-06 — Source freshness dashboard

**Priority:** Medium

### Goal

Use existing artifact/observation provenance to show whether expected evidence is current.

Output:

```text
Source
Latest_Observation
Expected_Max_Age
Actual_Age
Status
```

Status:

```text
FRESH
STALE
MISSING
NOT_APPLICABLE
```

Freshness thresholds belong in configuration by source class.

This feature can feed the finance month-end close without duplicating freshness logic.

---

# Recommended architecture sequence

```text
SYS-BUG-01 truthful commit reporting
→ SYS-BUG-02 recovery marker
→ SYS-BUG-03 structured extractor outcomes
→ SYS-BUG-04 exception continuation audit
→ commit-state machine
→ stale COMMITTING recovery
→ provider / sync / healing provenance
→ snapshot / restore states
→ failure taxonomy
→ parallel policy
→ guarantee-language audit
→ schema drift
→ run health envelope
→ run diff
→ lineage explorer
→ recovery dashboard
→ contract evolution
→ source freshness
```

The architecture goal is intentionally boring:

> **More lineage. More truthful state. More deterministic recovery. Fewer ways for the application to look healthy when it is not.**
