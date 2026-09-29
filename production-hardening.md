# Architecture & Reproducibility Freeze

## Goal
Extend v6.5.3 with better lineage and replayability without redesigning the architecture that already works.

## 1. Artifact lifecycle against runs
### Change
Extend the file registry with:
```text
first_seen_run_id / first_seen_at
last_seen_run_id / last_seen_at
last_changed_run_id / last_changed_at
last_synced_run_id / last_synced_at
```
### Impact
The registry directly explains when an artifact entered, was observed, changed, and synchronized.
### Implementation
New artifact sets first/last seen. Unchanged updates last seen only. Changed updates last seen + last changed. Successful Bronze sync/replay updates last synced. A PENDING_BRONZE replay without source modification must not update last changed.
### Done when
Current artifact lifecycle is understandable without reading execution logs.

## 2. Historical artifact-run lineage
### Change
Add `cp_artifact_run_events`.
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
Supports Run → Artifacts and Artifact → Runs queries.
### Implementation
Write only meaningful lifecycle transitions. Detailed debugging remains in execution logs.
### Done when
Run-to-artifact history is directly queryable.

## 3. Preserve rename semantics
### Change
Record rename history without treating a path change as new evidence.
### Impact
Lineage improves without duplicate financial state.
### Implementation
Write `RENAMED` and preserve existing identity migration across Control Plane, raw payload ownership, Bronze `__file_name__`, and Meta. Mark changed only when content changes.
### Done when
Pure renames never cause duplicate ingestion.

## 4. Reproducible FIRE / Monte Carlo
### Change
Persist a minimal simulation context:
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
result_fingerprint  # optional
```
### Impact
Historical FIRE simulations become explainable and replayable.
### Implementation
Persist one root seed and derive deterministic random streams for market regimes, returns, jumps, inflation, human-capital shocks, etc. Do not persist every random draw.
### Done when
Same inputs + model + seed reproduce the same material result.

## 5. Simulation fingerprints
### Change
Add `input_fingerprint` and `model_fingerprint`.
### Impact
A changed replay can be attributed to changed inputs/model rather than unexplained randomness.
### Implementation
Hash canonicalized simulation inputs and behavior-controlling model configuration. Optionally hash material results.
### Done when
Ordering-only differences do not change fingerprints.

## 6. Historical simulation provenance in SQLite
### Change
Add `cp_simulation_runs`.
### Impact
Simulation history follows the existing SQLite historical-authority model.
### Implementation
Link simulation context to pipeline run and Settings/FinancialRules snapshots. Do not persist the full Monte Carlo distribution here.
### Done when
Historical simulation executions can be inspected/replayed.

## 7. Latest simulation context in DuckDB Meta
### Change
Add `meta.m_Simulation_Run`.
### Impact
Latest FIRE output can be traced from the analytical database.
### Implementation
Keep only the latest successful context needed for inspection:
```text
simulation_id
run_id
root_seed
iterations
horizon
input_fingerprint
model_fingerprint
```
Preserve:
```text
SQLite → historical authority
DuckDB Meta → latest analytical projection
```
### Done when
Latest FIRE output connects to its simulation context.

## 8. Reproducibility Envelope including finance/tax
### Change
Extend the existing provenance model to the new financial-domain contracts.
Important outputs should be explainable by:
```text
source evidence
run identity
Settings snapshot
FinancialRules / TaxConfig snapshot
Macro FY parameters
model/algorithm context
random seed where stochastic
```
Investment/tax lineage should preserve:
```text
source transaction
→ FIFO lot
→ realized investment event
→ tax event
→ FY tax state
→ Gold tax output
```
### Impact
Finance, tax, and FIRE share one reproducibility model. No separate tax-lineage system is required.
### Implementation
Preserve stable IDs such as Sale/Transaction ID, Lot ID, Realized Event ID, Tax Event ID, Source Type/ID, and FY through the new Silver contracts.

Macro Parameters remain FY-grain analytical reference state; they do not move into the Control Plane.

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
same envelope + same seed
→ same material output
```
### Done when
Investment realization, tax calculation, and FIRE outputs can all be traced/reproduced through one provenance model.

## Do not build
```text
new orchestration framework
new warehouse layer
event-sourcing rewrite
distributed transactions
cloud infrastructure
generic lineage platform
separate tax-lineage platform
persistence of every Monte Carlo draw
```

## Freeze checklist
- Artifact lifecycle pointers exist.
- Artifact-run history is queryable.
- Rename remains identity migration.
- FIRE persists replay context/seed.
- Simulation fingerprints exist.
- Simulation history lives in SQLite.
- Latest simulation context lives in Meta.
- Financial/tax contracts preserve downstream lineage IDs.
- Reproducibility Envelope covers finance, tax, and FIRE.
