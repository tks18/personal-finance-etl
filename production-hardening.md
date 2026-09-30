# Architecture & Reproducibility Freeze

## Goal

Extend the current architecture with better lineage, deterministic analytical identity, and replayability without redesigning the Control Plane, Bronze/Silver/Gold model, recovery model, or orchestration.

This sprint adds:

```text
Artifact ↔ Run lineage
Deterministic analytical IDs
FIRE / Monte Carlo replayability
One Reproducibility Envelope across finance, tax, and simulation
```

---

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

The registry can directly answer:

```text
When did this artifact first enter the system?
Which run last observed it?
Which run last changed its content?
Which run last synchronized it to Bronze?
```

`seen`, `changed`, and `synced` remain separate events.

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

A `PENDING_BRONZE` replay without source modification updates `last_synced`, not `last_changed`.

### Done when

The current lifecycle of an artifact can be understood from the registry without reading execution logs.

---

## 2. Add historical artifact-run lineage

### Change

Add:

```text
cp_artifact_run_events
```

Suggested fields:

```text
event_id
run_id
file_id
event_type
event_at
observed_path
content_hash
previous_status
new_status
event_reason
```

Recommended event vocabulary:

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

The system can answer both:

```text
Run X → which artifacts participated?
Artifact Y → which runs touched it?
```

`event_reason` explains the lifecycle transition without turning this table into another execution log.

Examples:

```text
HEALED  → "Bronze partition rebuilt"
RENAMED → "Path changed; content hash unchanged"
REMOVED → "Full-replace source no longer discovered"
```

### Implementation

`event_id` is the row identity of the operational event and does not need to be a deterministic financial ID.

Write rows only for meaningful lifecycle transitions.

Keep parser errors, stack traces, and detailed debugging in the existing execution logs.

### Done when

Run-to-artifact and artifact-to-run history are directly queryable and lifecycle events are understandable without reading stack traces.

---

## 3. Preserve rename semantics

### Change

Record rename history without treating a path change as new financial evidence.

### Impact

Lineage improves without duplicate ingestion or duplicate financial history.

### Implementation

On a pure rename:

```text
write RENAMED event
preserve file identity
migrate path-dependent Bronze / Meta identity
do not mark content changed
```

Keep the existing migration across:

```text
Control Plane
raw payload ownership
Bronze __file_name__
DuckDB Meta
```

### Done when

A rename remains an identity migration and never creates duplicate financial state.

---

## 4. Add deterministic analytical identity

### Change

Introduce one shared deterministic-ID mechanism for rebuild-derived financial entities.

The first identity chain is:

```text
Canonical Purchase
→ Purchase_ID
→ Lot_ID

Canonical Sale
→ Sale_ID

Sale_ID + Lot_ID
→ Realized_Event_ID

Source_Type + Source_ID + Tax_Sub_Head
→ Tax_Event_ID
```

Reconciliation adds:

```text
Reconciliation_Group_ID
→ one reconciliation operation

Reconciliation_Event_ID
→ one affected lot mutation
```

### Impact

Silver and Gold are fully replaced on every analytical rebuild. Random UUIDs, run IDs, timestamps, or dataframe row positions would therefore destroy stable lineage even when the financial evidence is unchanged.

Deterministic IDs make the rebuilt analytical state referentially stable.

### Implementation

Create one shared utility for:

```text
Purchase_ID
Sale_ID
Lot_ID
Realized_Event_ID
Reconciliation_Group_ID
Reconciliation_Event_ID
Tax_Event_ID
```

Use:

```text
fixed namespace/prefix
canonical value serialization
stable cryptographic hash
```

Example prefixes may be:

```text
PUR_
SALE_
LOT_
REAL_
RECON_GRP_
RECON_
TAX_
```

The exact digest length is an implementation choice, but it must have an intentionally chosen collision policy.

### Canonical values

Use stable representations:

```text
ISO dates
normalized strings
canonical numeric/decimal representation
stable IDs
```

Do not hash display formatting or arbitrary float string representations.

### Identity is not provenance

Never include volatile execution metadata in deterministic financial identity:

```text
run_id
run timestamp
machine hostname
temporary path
working directory
process ID
log path
```

Those remain provenance attributes.

### Done when

The same canonical financial evidence rebuilt twice produces the same analytical IDs.

---

## 5. Keep source and canonical grains separate

### Change

Do not redesign Bronze or preserve every broker order merely to create IDs.

### Impact

The current transformation model intentionally creates canonical aggregated purchase/sale facts before the Quant Engine. The identity layer should identify those entities rather than inventing a new transaction grain.

### Implementation

Keep existing source transformations and canonical aggregation.

Define:

```text
Purchase_ID
→ one canonical aggregated row in f_Investment_Purchase_Data

Sale_ID
→ one canonical aggregated row in f_Investment_Sale_Data
```

Do not call them broker transaction IDs.

Market and benchmark data keep their existing grains and do not receive Lot_ID merely for consistency.

### Done when

Identity hardening does not change the existing financial grain.

---

## 6. Make FIRE / Monte Carlo runs reproducible

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
model_implementation_version
status
result_fingerprint   # optional
```

### Impact

Historical FIRE simulations become explainable and replayable.

### Implementation

Persist one root seed per simulation and derive deterministic random streams from it.

Do not persist every generated random number.

### Done when

The same inputs, model configuration, implementation version, and seed reproduce the same material result.

---

## 7. Define simulation fingerprint scope

### Change

Separate:

```text
input_fingerprint
model_fingerprint
model_implementation_version
root_seed
```

### Impact

A changed simulation can be diagnosed cleanly:

```text
financial inputs changed?     → input_fingerprint
assumptions/config changed?    → model_fingerprint
implementation changed?        → model_implementation_version
randomness changed?            → root_seed
```

### Implementation

`input_fingerprint` includes canonical simulation inputs.

`model_fingerprint` includes:

```text
simulation assumptions
model configuration
behavior-controlling parameters
```

`model_implementation_version` identifies the relevant model/algorithm implementation version.

Exclude volatile values from fingerprints:

```text
run timestamp
run_id
temporary paths
machine hostname
working directory
output/log paths
process ID
```

### Done when

A replay difference can be attributed to input, assumptions, implementation, or seed.

---

## 8. Persist simulation history in SQLite

### Change

Add:

```text
cp_simulation_runs
```

### Impact

Simulation provenance follows the existing ownership model: SQLite owns historical operational truth.

### Implementation

Persist the simulation context and link it to:

```text
pipeline run
Settings snapshot
FinancialRules snapshot
```

Do not store the complete Monte Carlo result distribution in the Control Plane.

### Done when

Historical simulation executions can be inspected and replayed.

---

## 9. Project latest simulation context into DuckDB Meta

### Change

Add:

```text
meta.m_Simulation_Run
```

### Impact

The latest published FIRE output can be connected to its simulation context from DuckDB.

### Implementation

Keep only the latest successful context needed for inspection.

Preserve:

```text
SQLite → historical authority
DuckDB Meta → latest analytical projection
```

### Done when

The latest FIRE result can be traced to its simulation context.

---

## 10. Extend the Reproducibility Envelope to finance and tax

### Change

Make the new financial-domain contracts part of the same reproducibility invariant.

Important outputs should be explainable by:

```text
source evidence
run identity
Settings snapshot
FinancialRules / TaxConfig snapshot
Macro FY parameters
model/algorithm implementation
random seed where stochastic
```

Investment/tax lineage should preserve:

```text
canonical purchase / sale
→ Lot_ID
→ realized event
→ tax event
→ FY tax state
→ Gold tax output
```

### Impact

Finance, tax, and FIRE share one provenance model. No separate tax-lineage platform is required.

### Implementation

Preserve stable IDs through downstream contracts:

```text
Purchase_ID
Sale_ID
Lot_ID
Realized_Event_ID
Reconciliation_Group_ID
Reconciliation_Event_ID
Tax_Event_ID
Source_Type
Source_ID
FY
```

Deterministic invariant:

```text
same evidence
+ same Settings
+ same FinancialRules/TaxConfig
+ same Macro Parameters
+ same implementation
→ same material output
```

Stochastic invariant:

```text
same envelope
+ same seed
→ same material output
```

### Done when

Investment realization, reconciliation, tax calculation, and FIRE outputs can all be traced/reproduced through one provenance model.

---

## 11. Make the contract registry the inventory SSOT

### Change

Treat the Data Contract Registry as the only authoritative source for final Bronze/Silver/Gold contract inventory and counts.

### Impact

Release counts cannot drift between code, README, docs, and tests.

### Implementation

Planning documents may describe expected additions, but after implementation:

```text
registry
→ exact contract inventory
→ exact release counts
```

Tests should validate the implemented registry rather than manually repeated approximate counts.

Documentation should be updated from the final registry during the documentation pass.

### Done when

There is one authoritative contract inventory.

---

## Do not build

Do not add:

```text
new orchestration framework
new warehouse layer
event-sourcing rewrite
distributed transactions
cloud infrastructure
generic lineage platform
separate tax-lineage platform
source-row transaction redesign
random analytical UUIDs
persistence of every Monte Carlo draw
```

---

## Architecture freeze completion

The architecture freeze is complete when:

1. Artifact lifecycle pointers are available.
2. Artifact-run history is queryable with event reasons.
3. Rename remains an identity migration.
4. Deterministic analytical IDs are generated by one shared utility.
5. Identity and provenance are kept separate.
6. Current canonical investment grains remain unchanged.
7. FIRE persists seed, fingerprints, and implementation version.
8. Historical simulation provenance lives in SQLite.
9. Latest simulation context is projected into DuckDB Meta.
10. Financial/tax contracts preserve stable lineage IDs.
11. The Reproducibility Envelope covers finance, tax, and FIRE.
12. The contract registry is the inventory SSOT.
