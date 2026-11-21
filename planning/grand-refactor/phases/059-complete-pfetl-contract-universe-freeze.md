# Phase 059 - Complete PFETL Contract-Universe Freeze

**Target release:** v10.6.0  
**Expected effort:** 5-7 hours  
**Previous:** Phase 058  
**Next:** Phase 060  
**Risk:** Critical

## 1. Outcome

Freeze the complete PFETL Core contract universe after external topology certification, column-retirement archaeology and performance hardening.

This phase replaces the old narrow "public source-configuration v1" freeze with one authoritative, extraction-ready contract system covering:

- stable identifiers and enums;
- source-binding/configuration contracts;
- bounded semantic-rule vocabulary;
- canonical production/satisfiability descriptors;
- capability contracts;
- complete Bronze, Silver and Gold DatasetContracts;
- grain, keys, references, nullability and logical types;
- capability-owned datasets/columns;
- schema versions, stability classification and deterministic contract fingerprints;
- machine-readable export.

By phase end, DDL, Gate-2 canonical validation, semantic inventory and capability-column ownership must no longer maintain competing schema truth.

## 2. Why this phase exists

The repository currently contains overlapping contract knowledge in several places. In the v10.3.0 baseline this included:

- `contracts/datasets.py`;
- `contracts/semantic_inventory.py`;
- `contracts/capabilities.py`;
- `infrastructure/validation/canonical_schemas.py`;
- hand-authored Bronze/Silver/Gold DDL/schema declarations;
- capability column inventories used by plan-aware publication.

Tests can keep duplicated authorities synchronized, but that is not a stable ecosystem contract. Future `pfetl-contracts`, Config Studio and Analytics Studio need a dependency-light declarative source of truth.

Phase 059 therefore freezes **one contract vocabulary**, while PFETL Core retains implementation adapters for Polars, Pandera, DuckDB and execution.

## 3. Inherited repository state

Phase 058 guarantees:

- the source-binding -> semantic route -> canonical production architecture is the sole runtime path;
- external household and investment topologies are certified;
- consumer-backed Bronze/Silver retirement is complete;
- performance gates are accepted;
- no known structural redesign is required for performance;
- no migration-only runtime compatibility path remains.

Phase 059 is therefore allowed to stabilize names/versions and delete duplicate metadata authority. It is not allowed to redesign source semantics or financial methodology.

## 4. Current codebase anchors

Use the post-058 equivalents of these v10.3.0 anchors:

### Contract/configuration

- `contracts/datasets.py`;
- `contracts/capabilities.py`;
- `contracts/semantic_inventory.py`;
- `contracts/canonical_fields.py`;
- `contracts/provenance.py`;
- `contracts/market.py`;
- `config/sources/model.py`;
- selectors, mapping, normalization, identity, change-detection and fingerprint modules.

### Validation/warehouse

- `infrastructure/validation/canonical_schemas.py`;
- `infrastructure/warehouse/contracts.py`;
- `pre_bronze.py`, `bronze.py`, `silver.py`, `gold.py`;
- plan-aware schema/catalog code introduced in Phase 043.

### Planning/application

- capability contracts/ExecutionPlan;
- SourceBindingPlan;
- CanonicalProductionPlan and satisfiability descriptors;
- derivation recipe descriptors;
- diagnostics schema/contract preview.

### Transitional debt scheduled for final closure

- inert `COMMON_COLUMN_MASTER` if still present;
- deprecated Settings source-path compatibility fields;
- obsolete FileHashPolicy fallback if superseded by per-binding/source policy;
- any remaining hand-maintained schema inventories proven redundant by unified contracts.

## 5. Exact target state after this phase

### 5.1 One authoritative `DatasetContract` family

Every canonical Bronze, Silver and Gold `DatasetId` has exactly one authoritative `DatasetContract`.

Pre-Bronze is explicitly excluded because its schema is source-binding/configuration-defined.

A DatasetContract must be able to express, where applicable:

```text
DatasetId
Layer
schema_version
physical/public name
human description
stability classification
allows_empty
duplicate policy
grain
columns
primary/unique keys
foreign/reference keys
identity requirements
capability owner
column capability ownership
producer/derivation metadata descriptor
```

### 5.2 Complete `ColumnContract`

Each canonical column has one declarative definition containing at least:

- canonical name;
- logical type;
- nullability;
- concise semantic description;
- role such as IDENTITY / EVIDENCE / DERIVED / PROVENANCE / METADATA where useful;
- capability ownership where applicable.

Public serialization must not contain Polars, Pandera or DuckDB objects.

### 5.3 Base versus effective contract

The base DatasetContract describes the complete supported contract.

The active `ExecutionPlan` derives an immutable effective contract for the current capability set. Capability-driven physical pruning does not mutate the base contract.

```text
Base DatasetContract
        +
ExecutionPlan
        -> EffectiveDatasetContract
        -> physical DDL / publication / Meta
```

### 5.4 Contract-generated adapters

The authoritative contract must drive:

- Bronze Gate-2 Pandera schema generation;
- Bronze/Silver/Gold physical DDL/schema generation;
- capability-owned column pruning/indexing;
- grain/uniqueness/reference validation metadata;
- diagnostic contract preview;
- deterministic machine-readable export.

Generated convenience indexes may exist; independent manual authorities may not.

### 5.5 Contract stability surfaces

Freeze explicit compatibility expectations:

- Bronze: canonical evidence/configuration target surface;
- Silver: advanced analytical contract surface with explicit evolution policy;
- Gold: strongest stable public analytical surface;
- Pre-Bronze: dynamic/private to each SourceBinding.

Exact labels may differ, but the compatibility semantics must be explicit.

### 5.6 Extraction readiness

The internal contract package intended for future extraction should depend only on lightweight contract/model dependencies such as stdlib/Pydantic/typing. Core-specific adapters point inward from PFETL Core to the contracts, never vice versa.

No separate `pfetl-contracts` repository is created in this phase.

## 6. Detailed implementation sequence

### Step 1 - Inventory every current contract authority

Create a one-time authority ledger covering:

- DatasetId definitions;
- complete Bronze/Silver/Gold columns;
- logical/physical types;
- nullability;
- grains/keys/uniqueness;
- references;
- identity metadata;
- capability dataset/column ownership;
- Pandera schemas;
- DDL declarations;
- semantic inventory metadata.

For each item name the final authoritative field and the old source to delete or derive.

### Step 2 - Finalize identifier and enum vocabulary

Review serialized/public values for:

- DatasetId;
- SourceId / SourceBindingId;
- CapabilityId;
- ProviderType;
- Layer;
- canonical semantic enums;
- producer/assembly kinds;
- semantic rule/predicate discriminators;
- identity/change-detection policies;
- derivation recipe IDs/descriptors.

Rename only if external certification proved a defect. Every rename here must update golden configs and fingerprints atomically.

### Step 3 - Define the unified DatasetContract/ColumnContract model

Evolve the existing contract model rather than maintaining parallel `DataContract`/`DatasetContract` hierarchies. Preserve current registry semantics where useful, but make the complete canonical schema declarative.

### Step 4 - Migrate Bronze contracts

Populate complete canonical Bronze contracts from the post-056/057 minimal evidence surfaces. Include grain, identity allowance, empty/duplicate policy and canonical references.

Compile Gate-2 Pandera schemas from these contracts. Remove manually duplicated Bronze field declarations from `canonical_schemas.py` once parity is proven.

### Step 5 - Migrate Silver contracts

Bring the complete Silver schema into DatasetContracts, including intentional advanced analytical fields and capability ownership. Use the completed column-disposition ledgers from 056/057 as authority for what survives.

### Step 6 - Migrate Gold contracts

Define complete Gold contracts with strongest stability expectations. Record grain, keys and descriptions required by downstream analytics without embedding financial formula implementations.

### Step 7 - Derive physical DDL/schema adapters

Make warehouse schema generation consume DatasetContracts/effective contracts. Physical type conversion belongs in Core adapter code. Add contract <-> generated DDL parity tests before deleting manual column authorities.

### Step 8 - Fold capability column inventory into contracts

Move authoritative dataset/column capability ownership into DatasetContract/ColumnContract. If a generated `CapabilityColumnIndex` remains useful, derive it from the registry and test deterministic generation.

### Step 9 - Fold semantic inventory into contracts

Migrate useful semantic descriptions, grain/role/disposition information into contracts. Delete the old semantic inventory as an authority once no unique information remains; retain only generated/reporting views if genuinely useful.

### Step 10 - Add structured references/integrity metadata

Represent cross-dataset references machine-readably. Make `CanonicalIntegrityValidator` compile/consume that metadata rather than maintaining a disconnected reference map where practical.

### Step 11 - Add deterministic contract serialization and fingerprints

Export the complete contract universe in a stable machine-readable representation. Serialization order must be canonical; fingerprints must ignore irrelevant declaration ordering.

The export must contain no runtime classes/callables or Polars/Pandera/DuckDB types.

### Step 12 - Freeze SourceConfiguration v1 on the new architecture

Finalize public serialized shape for:

- sources;
- source bindings;
- selectors/source schema;
- normalization and semantic rules;
- routes;
- canonical production choices;
- identity/change policy;
- capabilities.

Add schema/version compatibility/deprecation policy and deterministic JSON Schema/Pydantic schema export. Golden external configurations become public-v1 fixtures.

### Step 13 - Remove duplicate/transitional authorities

After parity tests, delete or demote:

- hand-maintained canonical Pandera field authority;
- hand-maintained Bronze/Silver/Gold schema authority;
- independent capability column authority;
- semantic inventory authority;
- inert `COMMON_COLUMN_MASTER`;
- deprecated Settings source paths;
- obsolete FileHashPolicy fallback where per-source/binding policy is final;
- any transitional canonical/source aliases still discovered.

### Step 14 - Architecture guards

Add permanent guards requiring:

- one DatasetContract per canonical DatasetId;
- no canonical DatasetId without contract;
- no duplicate physical table names;
- keys/references point to valid columns/contracts;
- contract adapters are derived;
- public contract package has no forbidden heavy implementation imports;
- changing a public schema requires version/compatibility handling.

### Step 15 - Full parity/regression run

Run all external golden configs plus Shan. Verify:

- generated Gate 2 behaves identically;
- physical warehouse matches effective contracts;
- capability pruning remains correct;
- financial outputs/IDs unchanged;
- fingerprints stable and reproducible.

## 7. Files and symbols in scope

Expected changes include:

- `contracts/` identifiers, datasets, capabilities, semantic/provenance metadata;
- `config/sources/` public Pydantic models and schema versioning;
- validation schema compiler;
- warehouse schema/DDL compiler and Meta/catalog contract publication;
- diagnostics contract/schema export;
- architecture tests and machine-readable export tests;
- removal of duplicated/transitional schema authorities.

This phase may move modules to create an extraction-ready internal package boundary, but must not create or publish a separate repository/package.

## 8. Cross-cutting impacts

**Public configuration:** SourceConfiguration v1 is frozen only after new SourceBinding/route/production semantics are real and externally certified.

**Warehouse:** physical schema becomes derived from base/effective contracts by construction.

**Validation:** Bronze Gate 2 derives from the same contract that defines Bronze schema.

**Capabilities:** column/dataset ownership derives from contract metadata; Phase-043 plan-aware behavior remains unchanged.

**Analytics:** Gold receives strongest compatibility policy; Silver/Bronze compatibility surfaces are explicit.

**Ecosystem:** contract serialization becomes the future shared vocabulary, but extraction waits until after Phase 060.

## 9. Tests and verification

Required:

- every canonical Bronze/Silver/Gold DatasetId has exactly one DatasetContract;
- every declared column has logical type/nullability/description and valid ownership metadata;
- grains/keys/references validate structurally;
- generated Bronze Pandera schemas equal intended Gate-2 behavior;
- generated/effective DDL equals physical warehouse for capability combinations;
- capability column index, if retained, is derived only;
- deterministic contract/config schema export and fingerprint;
- golden external configurations validate against SourceConfiguration v1;
- unsupported schema-version handling actionable;
- no forbidden heavy imports in extraction-ready contract modules;
- duplicate schema authorities removed or explicitly generated-only;
- full Shan/external regression and performance gates remain green.

## 10. Explicit non-goals

Do not:

- create the external `pfetl-contracts` repository/package yet;
- move financial calculations into contracts;
- make Silver/Gold formulas user-configurable;
- force Pre-Bronze into a global DatasetContract schema;
- expose internal execution classes simply because a public config references capabilities;
- redesign the architecture after freeze to improve naming aesthetics.

## 11. Completion checklist

- [ ] One authoritative DatasetContract registry completely covers Bronze, Silver and Gold, while Pre-Bronze remains SourceBinding-defined and dynamic.
- [ ] DDL, Gate-2 canonical validation, capability-column ownership and semantic schema metadata derive from that contract universe rather than competing manual authorities.
- [ ] Base contracts and capability-derived effective contracts are distinct, immutable concepts and physical warehouse generation uses the effective contract.
- [ ] Grain, keys, uniqueness, references, identity/empty/duplicate semantics and schema versions are machine-readable for all relevant canonical datasets.
- [ ] SourceConfiguration v1 reflects SourceBindingId, semantic routes and canonical production, with deterministic machine-readable schema export and compatibility policy.
- [ ] Contract serialization/fingerprints are deterministic and contain no Core-only Polars/Pandera/DuckDB/callable objects.
- [ ] `COMMON_COLUMN_MASTER`, deprecated Settings source paths and other superseded schema/policy authorities are deleted where their replacement is proven.
- [ ] Full Shan and external financial regression, capability-aware physical schema parity and Phase-058 performance gates remain green after the freeze.

## 12. Commit boundary

Use `pfetl-conventional-commits`. Group the contract-model expansion, generated adapters, public-config freeze and old-authority demolition semantically. Keep each group green and reviewable; the commit skill owns exact staging/messages.

## 13. Handoff to Phase 060

Phase 060 may assume every public/configuration/canonical analytical contract required by PFETL Core is frozen, machine-readable and implemented through one source of truth. It must not discover or invent another schema authority. The final phase now certifies the complete 60-phase Core from clean install and representative pre-final operational state through canonical production, finance, recovery, observability and contract-to-warehouse parity.

## Phase completion record

```text
Phase:
Target release:
Public identifiers frozen:
DatasetContracts covered:
Duplicate authorities deleted:
Machine-readable exports:
Files changed:
Schema/config version changes:
Financial formulas changed: NO
Contract/physical parity:
Shan/external regression:
Performance gate:
Extraction-readiness check:
Exit assertions green:
Commits:
```

A phase is incomplete if any required exit assertion is false.
