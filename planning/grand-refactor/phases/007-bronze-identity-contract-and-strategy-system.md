# Phase 007 - Bronze Identity Contract and Strategy System

**Target release:** v9.5.6  
**Expected effort:** 3-4 hours  
**Previous:** Phase 006  
**Next:** Phase 008 - Canonical Silver/Gold Semantic Inventory  
**Risk:** Medium  
**Runtime behavior change:** No production Bronze ID generation yet  
**Schema/persistence change:** Contract metadata only

## 1. Outcome

Make Bronze identity requirements explicit and implement the complete typed strategy/compiler/executor needed for future configurable sources, without changing current production Bronze rows.

At phase end PFETL can answer, before ingestion:

```text
Does this canonical Bronze dataset require stable row identity?
If yes, may the source provide it?
If not, which deterministic canonical fields create it?
What uniqueness rule must hold?
```

The identity executor is tested and production-ready, but generalized ingestion does not invoke it until later mapping/Pre-Bronze phases.

## 2. Why this phase is next

Phases 001-006 separated stable dataset identity, source identity and change policy from the old overloaded category model.

Identity is the next contract PFETL must own before configurable mapping can be designed safely.

The current codebase has two very different identity classes:
- source UIDs in household SQLite evidence;
- financial identities created later (`PURCHASE`, `SALE`, `LOT`, `REALIZED`, reconciliation, `TAX`).

The new Bronze identity system must solve only the first class for arbitrary sources. It must not pull downstream financial identities into Bronze.

## 3. Inherited state

Phase 006 guarantees runtime change detection is explicit and provider-neutral.

Phase 001 guarantees stable `DatasetId`.

Phase 004 guarantees every current externally sourced Bronze dataset is representable in configuration.

No production Bronze identity behavior has changed.

## 4. Current code anchors

### `infrastructure/warehouse/contracts.py::BronzeDataContract`

Current historical fields include extraction/category/table/full-replace plus Phase-001 DatasetId.

It has no identity requirement.

### `domain/common/identity.py`

Current canonical deterministic identity implementation owns stable serialization and hashing. This is the only identity primitive to reuse.

### Protected financial namespaces

Current calls include:
- `PURCHASE`
- `SALE`
- `LOT`
- `REALIZED`
- `RECON_LOT_GROUP`
- `RECON_GROUP`
- `RECON_EVENT`
- `TAX`

These are explicitly outside Bronze identity.

### Household source

The current SQLite household source carries stable IDs used downstream. The future architecture must preserve those IDs when configured as trusted source identity.

## 5. Target contracts

### PFETL-owned requirement

Add typed Bronze metadata conceptually equivalent to:

```text
IdentityRequirement
  NONE
  REQUIRED
```

and a uniqueness/grain declaration sufficient to distinguish:
- no row identity requirement;
- unique stable identity required.

Do not encode user strategy inside `BronzeDataContract`.

### User strategy

Use a discriminated union conceptually:

```text
SourceFieldIdentity
  field

CompositeIdentity
  fields

DerivedDeterministicIdentity
  fields
  namespace/version if required
```

If source-field and composite-field strategies are semantically identical except field count, a single `FieldIdentity` model may be cleaner. Preserve explicit semantics in validation.

## 6. Dataset classification procedure

Review all 20 current Bronze contracts.

For each, record:
- row grain;
- whether downstream correctness requires stable identity in Bronze;
- whether current source already supplies a trusted stable ID;
- whether identity is intentionally established later.

Mandatory rule:
investment evidence must not be assigned synthetic Bronze IDs merely for uniformity if its financial identity is established later.

Market time-series datasets should use natural-grain uniqueness where appropriate rather than synthetic identity by default.

No Bronze contract may silently default identity requirement.

## 7. Implementation sequence

### Step 1 - Add identity requirement types

Place stable cross-boundary vocabulary under `contracts` or the existing canonical Bronze-contract module according to Phase-001 ownership.

### Step 2 - Extend Bronze contract metadata

Add explicit identity requirement and uniqueness/grain metadata.

Populate every current Bronze contract.

Registry validation must fail if either is omitted.

### Step 3 - Add source-configuration identity models

Create under the Phase-002/003 source configuration package.

Validation:
- field list non-empty;
- no duplicate fields;
- no reserved downstream financial namespace;
- no row-index/time/random strategy.

### Step 4 - Build `IdentityPlan`

Application-level compiler input:
- canonical Bronze contract;
- available normalized canonical fields;
- configured strategy.

Output:
- immutable plan;
- or typed configuration error.

Rules:
- REQUIRED + no strategy => fail;
- NONE + no strategy => valid;
- REQUIRED + referenced field absent => fail;
- derived fields empty => fail;
- strategy may not target a dataset that forbids/does not require Bronze identity unless explicit optional preservation is justified.

### Step 5 - Implement deterministic executor

Reuse `generate_deterministic_id()` canonical serialization.

Create a Bronze-specific namespace scheme that cannot collide conceptually with protected financial namespaces. Namespace must include stable dataset identity and a version if future algorithm evolution needs it.

Do not use Python `hash()`, UUID4, row order or current time.

### Step 6 - Collision detection

The executor/validation path must be able to detect duplicate generated IDs for a dataset whose contract requires uniqueness.

Return a bounded diagnostic:
- dataset;
- duplicate count;
- bounded sample;
- strategy fields.

Do not silently deduplicate.

### Step 7 - Protect existing financial namespaces

Add architecture/unit tests proving the Bronze identity module does not import/use `PURCHASE`, `SALE`, `LOT`, `REALIZED`, `RECON*`, or `TAX` namespace constants/strings.

## 8. Files expected in scope

Create/modify:
- canonical dataset/Bronze contract module;
- source config identity model;
- application identity compiler/executor service;
- registry validation;
- tests.

Read only:
- household transforms to understand UID usage;
- investment transforms/FIFO/reconciliation/Tax hashing.

## 9. Explicitly out of scope

Do not:
- add ID columns to production Bronze;
- alter current household UIDs;
- alter investment financial ID algorithms;
- change Silver/Gold DDL;
- add Pandera;
- add mapping execution;
- add Pre-Bronze.

## 10. Tests

Required:

### Contract coverage
All 20 Bronze datasets declare identity requirement.

### Strategy validation
- required + missing strategy fails;
- missing referenced field fails;
- duplicate configured fields fail;
- prohibited nondeterministic strategy impossible by type/model.

### Determinism
For derived identity:
- same canonical values => same ID;
- mapping/dict ordering does not change ID;
- changed identity field => changed ID;
- null semantics match canonical identity serializer;
- repeated execution identical.

### Collision
Duplicate identity inputs produce explicit collision failure where uniqueness is required.

### Protected financial identities
Existing PURCHASE/SALE/LOT/REALIZED/RECON/TAX tests remain byte-for-byte stable.

## 11. Real-data verification

No production path consumes new executor, so a full financial run is a regression gate rather than behavior validation.

Run current Shan data if standard release process requires it. All IDs must remain unchanged.

## 12. Observability

No production events required because executor is not wired.

Define typed error/result shape now if later validation observability needs it, but do not emit dormant fake events.

## 13. Performance

Unit benchmark only if deterministic executor is accidentally row-wise Python over large fixtures. Prefer Polars/vectorized integration later, but do not prematurely optimize an unwired service.

## 14. Delete / retain

Delete nothing.

Retain:
- current household source UIDs;
- all downstream financial ID generation;
- current Bronze physical schema.


## 15. Explicit non-goals

Do not:
- generate or persist new production Bronze IDs;
- alter current household source UIDs;
- change PURCHASE, SALE, LOT, REALIZED, RECON or TAX identity algorithms;
- add mapping execution, Pandera or Pre-Bronze;
- change Silver/Gold DDL;
- make identity strategy configurable for downstream financial identities.

## 16. Completion checklist

- [ ] Every Bronze contract has explicit identity requirement.
- [ ] Every Bronze contract has explicit uniqueness/grain semantics.
- [ ] Identity strategies are typed and validated.
- [ ] IdentityPlan compiler exists.
- [ ] Deterministic executor reuses canonical serialization.
- [ ] Collision failure is explicit.
- [ ] Protected financial IDs remain unchanged.
- [ ] No production Bronze rows changed.
- [ ] Tests and quality gates pass.

## 17. Commit

```text
feat(contracts): define bronze identity policies
```

## 18. Handoff to Phase 008

Phase 008 may assume PFETL has explicit stable dataset identity, source identity, change policy and Bronze identity policy.

It must not assume:
- configurable mapping runtime;
- canonical Silver vocabulary;
- provenance cleanup;
- Pre-Bronze;
- Pandera.

## Phase completion record

Before committing, record:

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

If any required exit assertion is false, this phase is not complete.
