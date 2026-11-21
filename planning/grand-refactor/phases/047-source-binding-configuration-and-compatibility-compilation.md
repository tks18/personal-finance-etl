# Phase 047 - Source-Binding Configuration and Compatibility Compilation

**Target release:** v10.3.2  
**Expected effort:** 3-4 hours  
**Previous:** Phase 046  
**Next:** Phase 048  
**Risk:** High

## 1. Outcome

Make the new source-binding configuration model executable at compile time while preserving the v10.3.0 configuration surface through one temporary, deterministic compatibility compiler.

At phase end every accepted legacy `SourceDatasetConfig` has one explicit compiled representation in the new model, but runtime source acquisition and Pre-Bronze persistence still use the current path.

## 2. Why this phase exists

Phase 046 introduced new contracts only. The migration now needs a single bridge from the current public-in-practice configuration shape to the future N:M model.

The bridge must not become a second configuration authority. Its purpose is:

```text
legacy SourceConfiguration
        -> compile once
new binding/route/production representation
        -> later runtime cutover
```

This allows Phase 048 to migrate physical planning without simultaneously forcing a handwritten rewrite of every existing configuration fixture and production baseline.

## 3. Inherited repository state

Phase 046 guarantees:
- `SourceBindingId`, route identity and canonical production contracts exist;
- candidate canonical DatasetIds are declared but not active;
- v10.3.0 runtime behavior is unchanged;
- legacy SourceConfiguration remains the sole runtime input.

## 4. Current codebase anchors

Trace current loading and fingerprint behavior in:
- `config/sources/loader.py`;
- `config/sources/model.py`;
- `config/sources/validation.py` and `topology.py`;
- `config/sources/fingerprint.py`;
- `config/sources/mapping.py`, `normalization.py`, `identity.py`, `change_detection.py`;
- Shan baseline construction still present in the loader;
- `application/diagnostics/service.py` previews that currently resolve by DatasetId;
- replay classification in `application/pipeline/replay.py`.

## 5. Exact target state after this phase

For every current v10.3.0 dataset binding:

```text
SourceDatasetConfig
        -> CompatibilitySourceBindingCompiler
SourceBindingConfig
CanonicalRouteConfig(target = current transitional DatasetId)
CanonicalDatasetProductionConfig(strategy = DIRECT)
```

The compiler must be deterministic:
- stable input produces byte/structure-equivalent compiled output;
- binding IDs are derived from stable configuration identity, never current file enumeration;
- route IDs are stable;
- fingerprints are canonical-order independent;
- no current financial meaning is changed.

The compiled representation is inspectable by diagnostics but is not yet the source acquisition authority.

The compatibility compiler has a named demolition owner: **Phase 055**.

## 6. Detailed implementation sequence

### Step 1 - Define deterministic legacy-to-binding identity
Choose a deterministic rule using existing source identity plus stable binding identity. Prove path relocation/renaming does not silently manufacture a new binding when current semantics consider it the same configured stream.

### Step 2 - Implement the compatibility compiler
Compile every legacy `SourceDatasetConfig` into exactly one `SourceBindingConfig` and one transitional route. Preserve selector, source schema, mapping/normalization, identity and change-detection semantics.

### Step 3 - Compile transitional production definitions
For every legacy route produce `SOURCE/DIRECT` production targeting the same old DatasetId. Do not switch to the new canonical DatasetIds in this phase.

### Step 4 - Canonicalize fingerprints
Create deterministic fingerprints for binding, route and production declarations. Reordering equivalent configuration blocks must not alter fingerprints.

### Step 5 - Integrate with loader validation without dual authority
Loading a legacy config may compile the new representation for inspection, but validation must have one clearly defined source of truth. Do not independently mutate both models after load.

### Step 6 - Extend diagnostics
Allow `validate-config` / plan diagnostics to display compiled binding IDs and route targets while preserving existing user-facing DatasetId diagnostics.

### Step 7 - Define replay change classes
Teach the config-change classifier to distinguish future binding/route/production fingerprint changes even though runtime cutover happens later. Do not trigger new replay behavior yet.

### Step 8 - Freeze a migration matrix
For every current production binding, test:
`legacy dataset config -> binding id -> route id -> transitional DatasetId -> DIRECT production`.
This matrix becomes Phase 048's input contract.

### Step 9 - Add explicit deletion marker
Add tests/comments so the compatibility compiler cannot survive unnoticed past Phase 055. Do not mark it deprecated as if it were a public long-lived API.

## 7. Files and symbols in scope

Expected changes:
- `config/sources/loader.py`;
- `config/sources/model.py` and validation/fingerprint modules;
- a compatibility compiler owned under configuration/application planning, not infrastructure;
- diagnostics typed results where compiled binding/route information is exposed;
- replay classifier tests;
- baseline source-configuration fixtures.

Do not modify Pre-Bronze table keys or SourcePlanner acquisition yet.

## 8. Cross-cutting impacts

**Configuration:** meaningful internal representation change, but no external migration required yet.

**Replay:** new fingerprints are recorded/tested, but old runtime replay remains authoritative until Phase 048/051 integration.

**Diagnostics:** users can begin seeing binding identity without losing current DatasetId context.

**Compatibility:** exactly one compatibility compiler is allowed. No bidirectional converter, no legacy/new model synchronization service.

## 9. Tests and verification

Required:
- full Shan source config compiles deterministically;
- each current binding has one stable SourceBindingId;
- selector/mapping/normalization/identity/change-policy semantics survive compilation;
- equivalent config ordering yields same fingerprints;
- changed route mapping changes route fingerprint only where expected;
- changed canonical production declaration changes production fingerprint;
- diagnostics show compiled binding and route identity;
- malformed legacy configs fail before compatibility output is accepted;
- no runtime/source acquisition call consumes the new model yet;
- v10.3.0 full run remains identical.

## 10. Explicit non-goals

Do not:
- key Pre-Bronze by SourceBindingId yet;
- execute routes;
- activate UNION;
- change canonical Bronze schemas;
- migrate capability requirements;
- accept arbitrary new N:M user configuration as production-ready yet.

## 11. Completion checklist

- [ ] Every accepted v10.3.0 source dataset compiles to one stable binding and transitional route.
- [ ] Legacy selector, mapping, normalization, identity and change-detection semantics survive compilation exactly.
- [ ] Binding, route and production fingerprints are deterministic and ordering-insensitive.
- [ ] Diagnostics can inspect the compiled representation without changing runtime behavior.
- [ ] Replay classification recognizes future binding/route/production semantic deltas without activating new rebuild behavior.
- [ ] The legacy-to-new compatibility compiler has an explicit Phase-055 deletion contract and no reverse-sync path.
- [ ] Full Shan runtime remains on the old acquisition path and is financially identical.

## 12. Commit boundary

Use the repository `pfetl-conventional-commits` skill to preview and group semantically related compiler, fingerprint, diagnostics and test changes. Keep independent concerns reviewable; do not encode per-file commit instructions in this plan.

## 13. Handoff to Phase 048

Phase 048 receives a deterministic compiled binding model for the complete current topology. It may replace **physical acquisition and Pre-Bronze ownership** with `SourceBindingPlan`/`SourceBindingId`, while continuing to produce the same transitional Bronze DatasetIds through the compatibility routes.

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
Commits:
```

A phase is incomplete if any required exit assertion is false.
