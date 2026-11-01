# Phase 049 - Public Source-Configuration Contract Freeze

**Target release:** v10.4.0  
**Expected effort:** 3-4 hours  
**Previous:** Phase 048  
**Next:** Phase 050  
**Risk:** High

## 1. Outcome

Freeze version 1 of PFETL's public source-configuration contract after reviewing every field against the external certification experience. Publish a machine-readable schema, explicit compatibility/deprecation rules, and stable identifier vocabularies needed by future companion tools.

This is a contract-freeze phase, not a documentation-portal or Config Studio phase.

## 2. Why this phase exists

Freezing configuration before external fixtures would fossilize design mistakes. Phases 046-048 have now exercised multiple topologies and performance. The core contract can be stabilized so future tools can safely consume PFETL's Pydantic models/schema.

## 3. Inherited repository state

Phase 048 guarantees:
- external household/investment configurations work;
- diagnostics are usable;
- performance is accepted;
- no known architecture migration remains.

Current SourceConfiguration has an explicit schema version but may still contain names/structures considered internal during refactor.

## 4. Current codebase anchors

Review all public models:
- SourceConfiguration;
- SourceConfig;
- SourceDatasetConfig;
- ProviderType;
- selectors;
- source schema declarations;
- mapping/normalization rules;
- change policies;
- identity strategies;
- CapabilityId/selection;
- DatasetId vocabulary;
- provider-generated dataset configuration where exposed.

Review CLI diagnostic output contracts only where they are intended for machine consumption.

## 5. Exact target state after this phase

Freeze `source_config` schema v1.

Required properties:
- stable serialized field names;
- documented required/default/optional semantics in model descriptions;
- discriminated unions have stable discriminator values;
- DatasetId/CapabilityId values stable;
- schema export is machine-readable (JSON Schema or Pydantic-native equivalent);
- unknown/removed fields follow explicit policy;
- future breaking changes require schema-version bump/migration;
- deprecation window/process defined for additive evolution.

Internal runtime classes such as ExecutionPlan internals need not become public merely because configuration references capabilities.

## 6. Detailed implementation sequence

### Step 1 - Public-surface inventory
Mark each model/field ENUM value PUBLIC or INTERNAL. Anything serialized in source config is public.

### Step 2 - Naming review from fixture experience
Fix awkward/ambiguous names now, before freeze. Update all fixtures/configs atomically.

### Step 3 - Validation/default review
Remove surprising implicit behavior. Defaults must be safe and semantically stable.

### Step 4 - Discriminator/version review
Ensure selector/normalization/identity unions serialize unambiguously.

### Step 5 - Export machine-readable schema
Generate deterministic schema artifact through supported project mechanism. Test it matches models and includes descriptions/constraints where available.

### Step 6 - Compatibility policy
Implement/test:
- current v1 loads;
- unsupported future/old breaking version fails with remediation;
- additive unknown-field behavior follows chosen policy;
- deprecated field handling explicit.

### Step 7 - Identifier freeze
DatasetId, ProviderType, CapabilityId and policy enum serialized values reviewed. Rename only now if essential.

### Step 8 - Golden configuration fixtures
Promote external household/investment configurations to schema-v1 golden examples/tests.

### Step 9 - Architecture guard
Future public model changes require schema/version/golden fixture updates.

### Step 10 - Final config migration test
If pre-freeze refactor configs differ, provide one-time migration guidance/tool only if users could plausibly have them; do not support every internal draft forever.

## 7. Files and symbols in scope

Modify:
- public Pydantic/source config models;
- schema export;
- version/compatibility validation;
- golden configs/tests;
- CLI schema/validation command if appropriate.

Do not build docs portal or companion applications.

## 8. Cross-cutting impacts

**Persistence:** run snapshots continue storing exact config/fingerprint; schema version explicit.

**Identity:** serialized identity-strategy contract frozen, not financial ID algorithms.

**Observability:** enum values used in context remain stable where public/forensic.

**Performance:** none.

**Ecosystem:** future Config Studio may import/use this contract, but no Studio code is created.

## 9. Tests and verification

Required:
- complete public-surface inventory;
- deterministic machine-readable schema export;
- golden Excel/CSV/SQLite/domestic/foreign configs validate;
- version incompatibility failure;
- discriminator round trips;
- canonical serialization/fingerprint stability under v1;
- architecture guard for public changes;
- full Shan/external regression after any final renames.

## 10. Explicit non-goals

Do not:
- freeze internal implementation classes unnecessarily;
- build Config Studio;
- build docs portal;
- add analytics application;
- make a v11 release merely for contract freeze.

## 11. Completion checklist

- [ ] Public config surface identified.
- [ ] Schema v1 field names finalized.
- [ ] Enum/discriminator values finalized.
- [ ] Machine-readable schema exported.
- [ ] Compatibility/deprecation policy implemented.
- [ ] Golden external configs pass.
- [ ] Fingerprinting remains deterministic.
- [ ] Future changes are guarded.

## 12. Commit boundary

```text
feat(config): freeze source configuration v1
```

## 13. Handoff to Phase 050

Phase 050 may assume the public configuration contract is stable and all supported topology fixtures are golden. The final phase validates the complete experience from a clean installation using only public interfaces and frozen contracts.

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
