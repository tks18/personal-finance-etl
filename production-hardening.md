# Architecture & Reproducibility Sprint

## Goal

Extend v6.5.3 with better lineage and replayability without redesigning the Control Plane, warehouse, recovery model, or orchestration.

Each item below states the change, why it matters, and the simplest implementation.

## 1. Track artifact lifecycle against runs

### Change

Extend the current file registry with:

```text
first_seen_run_id
first_seen_at
last_seen_run_id
last_seen_at
last_changed_run_id
last_changed_at
last_synced_run_id
last_synced_at
```

### Impact

The registry can directly answer when an artifact entered the system, when it was last observed, when its content last changed, and which run last synchronized it.

`seen`, `changed`, and `synced` remain different events.

### Implementation

During discovery:

```text
new artifact
→ set first_seen + last_seen

unchanged artifact
→ update last_seen only

changed artifact
→ update last_seen + last_changed

successful Bronze sync/replay
→ update last_synced
```

A `PENDING_BRONZE` replay without source modification must update `last_synced`, not `last_changed`.

## 2. Add historical artifact-run lineage

### Change

Add a small Control Plane history table such as:

```text
cp_artifact_run_events
```

Suggested fields:

```text
run_id
file_id
event_type
event_at
observed_path
content_hash
previous_status
new_status
```

Suggested events:

```text
DISCOVERED
CHANGED
RENAMED
PENDING_BRONZE
SYNCED
HEALED
REMOVED
```

### Impact

The system can answer:

```text
Run X → which artifacts participated?
Artifact Y → which runs touched it?
```

### Implementation

Write rows only for meaningful artifact lifecycle transitions. Keep detailed diagnostics in the existing execution log.

Do not turn `cp_file_registry` into a history table.

## 3. Preserve rename semantics

### Change

Record rename history without treating a path change as new financial evidence.

### Impact

Lineage improves without creating duplicate ingestion or duplicate financial history.

### Implementation

On a pure rename, write a `RENAMED` event and keep the existing identity migration across:

```text
Control Plane
raw payload ownership
Bronze __file_name__
DuckDB Meta
```

Only mark the artifact changed if the content actually changed.

## 4. Make FIRE / Monte Carlo runs reproducible

### Change

Create a minimal simulation-run context:

```text
simulation_id
run_id
created_at
root_seed
iterations
horizon
input_as_of_date
settings_snapshot_id
rules_snapshot_id
input_fingerprint
model_fingerprint
status
result_fingerprint   # optional
```

### Impact

FIRE stops being a stochastic black box. A historical simulation can be explained and replayed.

### Implementation

Persist one root seed per simulation and derive deterministic random streams from it for the stochastic components such as:

```text
market regime
returns
jump events
inflation
human-capital shocks
```

Do not persist every random draw.

## 5. Add simulation fingerprints

### Change

Create:

```text
input_fingerprint
model_fingerprint
```

Optionally add a material `result_fingerprint`.

### Impact

If a replay differs, I can tell whether inputs, model configuration, rules, or stochastic context changed.

### Implementation

Hash canonicalized simulation inputs for `input_fingerprint`.

Hash the FIRE / Monte Carlo configuration that controls behavior for `model_fingerprint`.

Ordering-only differences must not change the hashes.

## 6. Persist simulation history in SQLite

### Change

Add a Control Plane table such as:

```text
cp_simulation_runs
```

### Impact

Historical simulation provenance follows the existing rule that SQLite owns operational history.

### Implementation

Persist the simulation context above and link it to the pipeline run plus Settings/FinancialRules snapshots.

Do not store the complete Monte Carlo distribution in the Control Plane.

## 7. Project the latest simulation context into DuckDB Meta

### Change

Add a lean table such as:

```text
meta.m_Simulation_Run
```

### Impact

The latest published FIRE output can be connected to its simulation context from the analytical database.

### Implementation

Keep only the latest successful context required for inspection:

```text
simulation_id
run_id
root_seed
iterations
horizon
input_fingerprint
model_fingerprint
```

Preserve the existing ownership rule:

```text
SQLite → historical authority
DuckDB Meta → latest analytical projection
```

## 8. Introduce the Reproducibility Envelope

### Change

Make this a system invariant, not a new framework.

An important analytical output should be explainable by:

```text
source evidence
run identity
Settings snapshot
FinancialRules snapshot
macro/reference state
model/algorithm context
random seed where stochastic
```

### Impact

The project gets one consistent definition of reproducibility.

### Implementation

Reuse existing provenance plus the new artifact/simulation lineage.

For deterministic outputs:

```text
same envelope → same material output
```

For stochastic outputs:

```text
same envelope + same seed → same material output
```

The QA sprint will make this invariant executable.

## Do not build

Do not add:

```text
new orchestration framework
new warehouse layer
event-sourcing rewrite
distributed transactions
cloud infrastructure
generic lineage platform
persistence of every Monte Carlo draw
```

## Sprint completion

The sprint is complete when:

1. Current artifact lifecycle pointers are available.
2. Artifact-to-run history is queryable.
3. Rename remains an identity migration.
4. FIRE runs persist replay context and root seed.
5. Input/model fingerprints exist.
6. Historical simulation provenance lives in SQLite.
7. Latest simulation context is projected into DuckDB Meta.
8. The Reproducibility Envelope is ready for automated testing.
