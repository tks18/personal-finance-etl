# Phase 044 - Generalized Recovery and Replay Semantics

**Target release:** v10.2.1  
**Expected effort:** 3-4 hours  
**Previous:** Phase 043  
**Next:** Phase 045  
**Risk:** High

## 1. Outcome

Complete recovery semantics for the generalized architecture: certify failures at every major persistence boundary, define explicit replay behavior for source/mapping/configuration changes, and guard identity-policy changes from silently reinterpreting historical IDs.

At phase end PFETL has one documented and tested recovery/replay state machine for generalized ingestion + capability-aware analytics.

## 2. Why this phase exists

v10.0 certified ordinary recovery, but later capability/warehouse work and configuration-driven interpretation introduce a new class of risk: the same raw evidence can mean something different after mapping or identity configuration changes. PFETL must detect and deliberately rebuild/replay rather than silently mixing interpretations.

## 3. Inherited repository state

Phase 043 guarantees plan-aware physical warehouse. Phase 020 persisted configuration fingerprints and detected changes but intentionally deferred remediation. Artifact/source/plan provenance is complete.

## 4. Current codebase anchors

Inspect:
- PipelineLifecycle commit/failure/recovery;
- run `commit_state`;
- config snapshot/fingerprint repository;
- Raw payload retention;
- Pre-Bronze/Bronze rebuild APIs;
- identity strategy fingerprints;
- backup/restore;
- stale-run recovery;
- plan-aware Meta/catalog.

Create a state-transition table before implementation.

## 5. Exact target state after this phase

Classify change types:

```text
SOURCE LOCATION/SELECTOR metadata change
CHANGE-DETECTION policy change
MAPPING/NORMALIZATION semantic change
BRONZE IDENTITY strategy change
CAPABILITY selection change
SOURCE/DATASET removed or disabled
FINANCIAL RULES change (existing separate semantics)
```

Define explicit action per class:
- no replay;
- re-extract from retained Raw/current source;
- rebuild Pre-Bronze/Bronze/downstream;
- require explicit identity migration/rebuild confirmation;
- rebuild analytical layers only.

Identity-policy change must never silently preserve old IDs beside newly interpreted IDs.

## 6. Detailed implementation sequence

### Step 1 - Freeze recovery/replay matrix
For each change type define affected layers, whether Raw re-read is sufficient, and user/operator action.

### Step 2 - Failure-window certification
Inject failures after:
- Control Plane/Raw sync;
- source validation;
- Pre-Bronze;
- Bronze;
- Silver;
- Gold/Meta;
- DuckDB commit before SQLite commit.

Assert existing rollback/RECOVERY_REQUIRED convergence.

### Step 3 - Mapping change replay
Change one mapping semantically with same Raw payload. Detect config fingerprint change and rebuild affected canonical layers according to policy. Prove old interpretation does not remain mixed.

### Step 4 - Normalization change replay
Same for cast/date/null rule.

### Step 5 - Change-detection policy change
Policy affects future sync behavior; define whether historical Raw needs replay. Do not rebuild finance unnecessarily if semantics unchanged.

### Step 6 - Capability change replay
Use Phase-043 table cleanup/rebuild; source/Bronze state may remain reusable.

### Step 7 - Removed/disabled source-dataset replay
When a DatasetId disappears from or is disabled in the current SourceConfiguration, retain historical Raw/Control Plane provenance according to retention policy but remove/rebuild any current-state Pre-Bronze/Bronze/analytical state that would otherwise keep the dataset logically active. Test re-enabling the dataset and compare with a clean run. Distinguish this from an enabled dataset that legitimately contains zero rows.

### Step 8 - Identity-policy guard
On Bronze identity strategy semantic change:
- detect fingerprint delta;
- refuse silent incremental continuation;
- require explicit full affected-dataset rebuild/migration path;
- record reason/provenance.
Test stable-ID -> derived-ID and derived-field changes.

### Step 9 - FinancialRules coexistence
Do not merge source replay semantics with existing FinancialRules provenance. Ensure downstream analytical rebuild rules remain correct.

### Step 10 - Backup/restore around replay
Restore prior backup then apply new config; resulting state must match clean run under new config.

### Step 11 - Document state machine in code/tests
Machine-readable enums/results preferred over prose-only behavior.

## 7. Files and symbols in scope

Modify:
- lifecycle/recovery/replay coordinator;
- config-change classifier;
- affected-layer rebuild planner;
- identity-policy guard;
- Meta/run provenance;
- tests.

Do not redesign Raw Store or commit order.

## 8. Cross-cutting impacts

**Persistence:** controlled layer rebuilds; no mixed semantic generations.

**Identity:** strongest guard in this phase; policy changes require explicit rebuild/migration.

**Observability:** replay reason, old/new config fingerprints, affected DatasetIds/layers and recovery state are correlated. Do not log full sensitive config.

**Performance:** replay can be expensive by design; ordinary unchanged runs must not pay replay cost.

## 9. Tests and verification

Required:
- failure matrix across all boundaries;
- split-commit recovery;
- mapping-change replay equals clean new-config run;
- normalization-change replay;
- capability-switch replay;
- removed/disabled DatasetId cleanup and re-enable replay;
- valid empty dataset is not confused with removed dataset;
- identity-policy change blocks unsafe incremental continuation;
- explicit full rebuild succeeds;
- backup/restore + new config equals clean run;
- unchanged config incurs no rebuild;
- full Shan regression.

## 10. Explicit non-goals

Do not:
- auto-migrate identity semantics heuristically;
- merge FinancialRules and SourceConfiguration;
- weaken recovery to keep runs going;
- change financial formulas.

## 11. Completion checklist

- [ ] Recovery matrix frozen.
- [ ] All failure windows converge.
- [ ] Mapping/normalization replay deterministic.
- [ ] Capability changes clean stale state.
- [ ] Removed/disabled datasets cannot leave stale current-state evidence.
- [ ] Empty-enabled and removed/disabled semantics are distinct.
- [ ] Identity changes cannot silently mix generations.
- [ ] Backup/restore replay equivalent.
- [ ] Unchanged runs remain incremental.

## 12. Commit boundary

```text
feat(recovery): define generalized replay semantics
```

## 13. Handoff to Phase 045

Phase 045 may assume configuration/replay behavior is safe and deterministic. It will expose PFETL-native diagnostics so a user can validate and preview configuration/admission without modifying source code or discovering errors halfway through a financial run.

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
