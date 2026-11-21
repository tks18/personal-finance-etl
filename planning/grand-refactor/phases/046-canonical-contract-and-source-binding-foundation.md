# Phase 046 - Canonical Contract and Source-Binding Foundation

**Target release:** v10.3.1  
**Expected effort:** 3-4 hours  
**Previous:** Phase 045  
**Next:** Phase 047  
**Risk:** Medium-High

## 1. Outcome

Introduce the typed vocabulary required to separate physical source evidence from PFETL canonical evidence without changing the v10.3.0 runtime path.

At phase end the codebase can describe `SourceBindingId`, canonical routes, canonical producers and the future canonical Bronze DatasetIds, but the existing `SourceDatasetConfig -> DatasetPlan -> Pre-Bronze -> Bronze` execution remains authoritative.

## 2. Why this phase exists

v10.3.0 overloads `DatasetId` across two different meanings:

```text
physical source binding
        and
PFETL canonical financial dataset
```

That 1:1 assumption prevents one source binding from contributing to several canonical datasets and prevents several source bindings from assembling one canonical dataset. Before configuration or persistence changes, PFETL needs typed contracts that make those identities impossible to confuse.

This phase is deliberately additive. It establishes vocabulary first so later phases can migrate one runtime ownership boundary at a time.

## 3. Inherited repository state

Phase 045 guarantees:
- `SourceConfiguration` can be validated without a financial run;
- `SourcePlanner` compiles the current source topology;
- mapping, normalization and identity previews are available through application diagnostics;
- dry-run admission reaches canonical Bronze validation without mutating production state;
- replay and recovery behavior are deterministic from Phase 044;
- the current v10.3.0 path remains financially accepted.

Phase 046 must not weaken any of those guarantees.

## 4. Current codebase anchors

Inspect and extend the current symbols rather than creating parallel concepts:
- `src/personal_finance_etl/contracts/datasets.py` - `DatasetId` and canonical dataset identity;
- `src/personal_finance_etl/contracts/sources.py` - source/provider plan contracts;
- `src/personal_finance_etl/config/sources/model.py` - `SourceConfiguration` and `SourceDatasetConfig`;
- `src/personal_finance_etl/config/sources/topology.py` - topology validation;
- `src/personal_finance_etl/application/pipeline/source_planner.py` - current `DatasetPlan` compilation;
- `src/personal_finance_etl/infrastructure/warehouse/contracts.py` - current `DataContract` ownership;
- `src/personal_finance_etl/contracts/capabilities.py` and `config/capabilities.py` - capability identifiers and dataset requirements;
- `src/personal_finance_etl/contracts/semantic_inventory.py` - current dataset/column semantic inventory;
- architecture tests guarding dependency direction and retired topology.

## 5. Exact target state after this phase

Additive contracts exist for the future architecture:

```text
SourceId
    identifies source/container

SourceBindingId
    identifies one configured physical tabular evidence stream

CanonicalRouteId
    identifies one row-local route from a binding to a canonical target

DatasetId
    identifies PFETL canonical financial evidence only
```

Introduce typed declarative vocabulary for:
- `SourceBindingId`;
- `CanonicalRouteId` or an equivalent typed route reference;
- `CanonicalProducerKind` with `SOURCE`, `PROVIDER`, `DERIVED`;
- source assembly vocabulary with `DIRECT` and `UNION`;
- the minimum canonical enums already proven by the v10.3.0 archaeology, including household transaction/category semantics and investment action semantics;
- additive `SourceBindingConfig`, `CanonicalRouteConfig` and `CanonicalDatasetProductionConfig` contracts;
- additive `SourceBindingPlan`, `CanonicalDatasetPlan`, `CanonicalProductionPlan` and `CanonicalFragment` contracts.

Declare candidate canonical Bronze DatasetIds needed by Phases 052-054 without switching consumers yet. At minimum the contract vocabulary must support the intended families:
- household categories, asset categories, assets, currencies, transactions and opening balances;
- investment transactions, holdings and instruments;
- benchmark/provider/reference and market evidence concepts required by the current Silver producers.

No new contract is runtime-authoritative yet.

## 6. Detailed implementation sequence

### Step 1 - Record the current identity overload explicitly
Add focused tests that demonstrate the current coupling between `SourceDatasetConfig.dataset_id`, `DatasetPlan.dataset_id`, Pre-Bronze naming and canonical Bronze target. These tests are migration evidence, not permanent desired behavior.

### Step 2 - Add `SourceBindingId`
Use a small serializable typed value consistent with current identifier conventions. It must be stable in configuration/fingerprints and must not derive from a file path at runtime.

### Step 3 - Add route identity
Define a deterministic route reference scoped to a source binding. It must be possible for one binding to own more than one route without inventing additional `DatasetId` values.

### Step 4 - Add canonical semantic enums
Add only semantics already required by current financial reconstruction. Do not create speculative taxonomy. Source numeric/string codes must not appear in these enums.

### Step 5 - Add additive configuration contracts
Define the new binding/route/production models without removing `SourceDatasetConfig`. Cross-object validation should reject duplicate binding IDs and malformed route references, but the legacy configuration model remains accepted in this phase.

### Step 6 - Add additive planning contracts
Introduce immutable plan/result contracts needed by later phases. Keep implementation-free metadata in contracts; no Polars, Pandera, DuckDB or provider client objects belong here.

### Step 7 - Declare the candidate canonical DatasetId vocabulary
Add the new canonical names required by the target architecture while keeping old v10.3.0 DatasetIds available for compatibility. Mark transitional status in code comments/tests rather than aliases that hide migration work.

### Step 8 - Add dependency guards
Ensure new contract modules import only approved contract/config primitives. They must not import warehouse repositories, Pandera adapters, domain transforms or presentation code.

### Step 9 - Prove zero runtime change
Run the Phase-045 diagnostic suite and full accepted Shan path. No planner, persistence, Bronze, Silver, Gold or capability behavior may change because the new contracts exist.

## 7. Files and symbols in scope

Expected changes:
- `contracts/datasets.py`;
- `contracts/sources.py` or a narrowly scoped new contracts module if existing ownership is clearer;
- `config/sources/model.py` and topology validation for additive models;
- tests for serialization, equality, validation and dependency boundaries.

Expected to remain untouched at runtime:
- `application/pipeline/source_planner.py` behavior;
- Pre-Bronze persistence;
- Bronze admission;
- Silver/Gold transforms;
- capability resolution.

## 8. Cross-cutting impacts

**Configuration:** additive only. Existing v10.3.0 configuration remains valid and authoritative.

**Persistence:** none. No new table naming or schema behavior.

**Identity:** new source-binding vocabulary is declarative only; existing Bronze identity remains unchanged.

**Contracts:** this phase creates the type boundary later phases migrate toward. Avoid implementation dependencies so Phase 059 can eventually extract contract modules cleanly.

**Observability:** no event changes required. New identifiers are not emitted until runtime owns them.

## 9. Tests and verification

Required focused proof:
- `SourceBindingId` round-trip serialization and uniqueness validation;
- route references cannot point at unknown bindings;
- one binding can declaratively contain multiple routes;
- multiple routes can target the same canonical DatasetId at the contract level;
- new semantic enum values reject source-specific numeric/vendor aliases as canonical values;
- candidate canonical DatasetIds are centrally registered and layer-valid;
- contract modules have no infrastructure/domain/presentation imports;
- current SourceConfiguration examples still load unchanged;
- Phase-045 diagnostics output is unchanged for the current configuration;
- full Shan pipeline financial outputs and protected IDs are unchanged.

## 10. Explicit non-goals

Do not:
- compile v10.3.0 configuration into the new model yet;
- change Pre-Bronze identity;
- execute canonical routes;
- union fragments;
- change capability requirements;
- delete any old DatasetId;
- redesign Silver or Gold schemas.

## 11. Completion checklist

- [x] `SourceBindingId` and route identity are typed, serializable and validation-covered.
- [x] Canonical producer/assembly vocabulary exists without runtime implementation imports.
- [x] The minimum canonical semantic enums required by known v10.3.0 source assumptions are defined.
- [x] Additive binding, route and production configuration contracts validate independently of the legacy model.
- [x] Additive source-binding and canonical-production plan contracts are immutable and dependency-clean.
- [x] Candidate canonical Bronze DatasetIds required by later migration phases are registered without switching consumers.
- [x] Existing v10.3.0 configuration, Phase-045 diagnostics and full financial run behave identically.

## 12. Commit boundary

Commit this phase in semantically coherent groups, for example identifier/contract vocabulary separately from additive configuration/test changes when that keeps each commit reviewable. Use the repository `pfetl-conventional-commits` skill for preview, grouping and final Commitlint-compliant messages. Do not force one phase-wide commit or file-by-file commits.

## 13. Handoff to Phase 047

Phase 047 may assume the new contract vocabulary exists and is fully tested, but **none of it is runtime-authoritative**. Phase 047 owns the first bridge: compile the existing v10.3.0 `SourceConfiguration` deterministically into `SourceBindingConfig + CanonicalRouteConfig + CanonicalDatasetProductionConfig` while preserving exactly the current 1:1 behavior.

## Phase completion record

```text
Phase: 046
Target release: v10.3.1
Files changed: 12
Schema changed: NO
Runtime behavior changed: NO
Financial formulas changed: NO
Focused tests: tests/contracts/test_source_dataset_identity_coupling.py, tests/contracts/test_source_bindings.py, tests/config/test_source_bindings_config.py
Architecture tests: tests/architecture/test_boundaries.py
Real-data run: N/A (pure additive contracts/vocabulary, tested with full application test suite 197/197 passing)
Performance check: FAST audit 0.98s
Compatibility path still present: YES (SourceDatasetConfig -> DatasetPlan remains 100% authoritative)
Old path deleted: NO (Phase 055 owns deletion)
Exit assertions green: YES
Commits:
```

A phase is incomplete if any required exit assertion is false.
