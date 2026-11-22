# PFETL Grand Refactor Architecture

## 1. Target data spine

The post-Phase-055 runtime must distinguish physical evidence acquisition from PFETL canonical financial evidence.

```text
SourceConfiguration + FinancialRules + runtime Settings
        |
        +-> CapabilityPlanner -> ExecutionPlan
        |
        +-> SourcePlanner -> SourceBindingPlan(s)
        |
        +-> CanonicalSatisfiabilityPlanner
                -> CanonicalProductionPlan

Physical evidence path
----------------------
SourceId / provider configuration
        -> SourceBindingId
        -> provider extraction
        -> Gate 1 source-shape validation
        -> Pre-Bronze keyed by SourceBindingId
        -> bounded source normalization
        -> bounded semantic interpretation
        -> CanonicalRoute
        -> CanonicalFragment(s)

Canonical evidence path
-----------------------
CanonicalFragment(s)
        + provider-generated canonical evidence
        + PFETL-owned derived canonical evidence
        -> CanonicalDatasetPlan
        -> DIRECT / explicit UNION / registered derivation recipe
        -> canonical identity
        -> duplicate + grain enforcement
        -> Gate 2 canonical validation
        -> canonical Bronze
        -> CanonicalIntegrityValidator
        -> DatasetCollection
        -> capability-resolved Silver financial reconstruction
        -> Gold analytical / decision state
```

No layer may collapse `SourceBindingId` and `DatasetId` back into one identity.

## 2. Layer semantics

### Raw Store / Control Plane

Own exact received evidence and operational truth:

- artifact identity and location;
- bytes/payload or provider request evidence;
- hashes/fingerprints;
- run association;
- source/binding/configuration fingerprints;
- synchronization and replay state;
- backup/restore and recovery state;
- forensic provenance.

Raw/Control Plane does not own dataframe financial semantics.

### Pre-Bronze

Own source-shaped extracted tabular evidence.

Pre-Bronze is keyed by `SourceBindingId`, not canonical `DatasetId`. It may contain source column names, source-oriented types, source record grain and source-row identity. Its schema is declared by source configuration and validated at Gate 1.

There is no global fixed Pre-Bronze DatasetContract universe.

### Semantic interpretation

Own the bounded translation from source encoding to PFETL canonical evidence meaning.

Allowed initial primitives are deliberately small and deterministic:

- normalization already owned by source mapping;
- `MapValues`;
- `Constant`;
- `IncludeWhen`;
- `ExcludeWhen`;
- bounded predicates such as equality, membership, null and empty checks.

Semantic interpretation is row-local. It must not execute arbitrary Python, SQL, user Polars expressions, joins, aggregation, windows or financial formulas.

Source deletion flags, placeholder rows, numeric transaction/category codes and broker/vendor action strings must be resolved before canonical Bronze unless they have an independently valid canonical meaning.

### Bronze

Own PFETL canonical financial evidence: source-independent names, types, nullability, grain and identity semantics required to reconstruct Silver deterministically.

Bronze does not own FIFO, realized gains, Tax, XIRR, Wealth, FIRE or other financial derivation.

### Silver

Own canonical reconstructed financial state and PFETL financial methodology. Silver consumes canonical evidence and must not reinterpret source codes or provider topology.

### Gold

Own PFETL analytical and decision surfaces. Gold is the strongest downstream public analytical contract surface after the contract freeze.

### Meta

Own plan-aware catalog and contract metadata such as active datasets, schema versions, effective columns, capabilities and contract fingerprints. Meta is descriptive/operational metadata, not another schema authority.

## 3. Configuration boundaries

### Settings

Retains runtime/environment concerns such as target warehouse location, Raw Store location, logs, retention and operational switches.

Source topology does not belong in Settings after the canonicalization program closes.

### SourceConfiguration

Owns declarative evidence acquisition and canonical production intent:

```text
SourceConfiguration
├── sources: SourceConfig[]
├── bindings: SourceBindingConfig[]
├── canonical_production: CanonicalDatasetProductionConfig[]
└── capability selection
```

A `SourceConfig` identifies a physical evidence container/provider configuration. A `SourceBindingConfig` identifies one configured physical tabular stream inside that source and owns selector/source schema/normalization/semantic routes. Canonical production resolves how routes/providers/derived recipes produce PFETL `DatasetId`s.

`SourceDatasetConfig.dataset_id` is transitional architecture and must be gone before external certification.

### FinancialRules

Remains separate and owns financial meaning and assumptions. Source configuration may map source encodings into PFETL canonical enums; it must never redefine PFETL financial methodology.

## 4. Stable identities

### SourceId

Stable configured identity of a physical evidence container or provider configuration.

### SourceBindingId

Stable configured identity of a physical tabular evidence stream. It is independent of path/filename and independent of canonical `DatasetId`.

Examples include one table, one sheet, one CSV-shaped stream or one logical provider response stream.

### CanonicalRouteId

Stable route identity inside a binding. One binding can have multiple routes, each targeting one canonical `DatasetId`.

### DatasetId

Canonical PFETL financial evidence/state identity. DatasetIds name PFETL concepts, not vendor tables, filenames or extraction attributes.

### CapabilityId

Stable financial execution capability identity.

### Protected financial identities

`PURCHASE`, `SALE`, `LOT`, `REALIZED`, `RECON_LOT_GROUP`, `RECON_GROUP`, `RECON_EVENT` and `TAX` remain owned by downstream PFETL financial stages. Canonicalization may change upstream representation but not these identities for equivalent evidence and rules.

## 5. N:M source-to-canonical topology

The architecture is explicitly N:M.

```text
one binding -> many routes -> many canonical fragments
many bindings/routes -> one canonical dataset through explicit production
```

Rules:

1. One `SourceBindingId` may contribute to zero, one or many canonical `DatasetId`s.
2. One canonical `DatasetId` may be produced from zero, one or many routes/providers/registered derived recipes.
3. Multiple source routes targeting one dataset require an explicit source assembly definition. Do not infer union from declaration order.
4. Source ordering, filesystem enumeration and thread completion must never define financial identity.
5. A user configures supported evidence topology. PFETL owns the canonical evidence contract and financial meaning.

## 6. Canonical production

`CanonicalProductionPlan` resolves one producer definition for each active canonical `DatasetId`.

Producer kinds:

- `SOURCE`: consumes canonical fragments through `DIRECT` or explicit `UNION`.
- `PROVIDER`: consumes PFETL-supported provider evidence without pretending it is a user file.
- `DERIVED`: executes a registered, versioned PFETL-owned canonical derivation recipe over other canonical datasets.

Canonical production may align schemas, assemble fragments, establish canonical identity, enforce grain/duplicates, run Gate 2 and validate canonical references. It must not become a second financial transformation engine.

A derived canonical recipe may infer canonical evidence concepts only. FIFO, Tax, realized gains, Wealth, FIRE and other downstream calculations remain outside this layer.

## 7. Identity model

Source-row identity and canonical Bronze identity are separate concepts.

- Gate 1 / Pre-Bronze may use trusted source keys or source-row fingerprints.
- Canonical identity is established after canonical assembly so collisions are detected across the complete target dataset, not merely inside one source fragment.
- Trusted source IDs require explicit scope semantics when they are not globally unique.
- Row order and randomness are forbidden identity inputs.

Duplicate canonical identity fails unless the target DatasetContract explicitly permits identical-evidence collapse. Ordering-dependent `KEEP_FIRST` / `KEEP_LAST` behavior is not an acceptable default.

## 8. Validation boundaries

### Gate 1

Validates one source binding against its configured source-shaped schema before semantic interpretation.

### Gate 2

Validates the final assembled canonical Bronze dataset against the authoritative Bronze DatasetContract. Fragments are statically compiled against the target contract but are not independently published as canonical datasets.

### Canonical integrity

After required Bronze datasets pass Gate 2, `CanonicalIntegrityValidator` checks cross-dataset relationships such as references and coverage before Silver executes. This is not a third source trust gate.

Missing, disabled, valid-empty and malformed remain distinct states.

## 9. Capability and satisfiability planning

`ExecutionPlan` answers: **what financial capabilities and analytical contracts are active?**

`CanonicalSatisfiabilityPlanner` answers: **how can this configuration produce every required canonical evidence dataset?**

The satisfiability planner consumes:

- active capability requirements;
- compiled source bindings/routes;
- provider production descriptors;
- registered derivation recipe descriptors;
- canonical DatasetContracts.

It resolves exactly one producer definition per required active DatasetId or fails before physical execution. It must detect missing producers, ambiguous producers, invalid explicit production selections and derived dependency cycles.

Existing/stale Bronze state may accelerate execution but can never prove current configuration satisfiable.

## 10. Replay and recovery

The existing split-commit invariant remains unchanged:

1. DuckDB commits first.
2. SQLite Control Plane commits second.
3. Failure between them yields `RECOVERY_REQUIRED`.

Change/replay semantics become source-binding and canonical-production aware:

```text
changed SourceBinding / route / semantic rule
        -> affected canonical DatasetId(s)
        -> downstream canonical derivation closure
        -> Silver/Gold replay closure
```

Identity-policy changes that would mix incompatible generations require explicit identity rebuild semantics.

Pre-Bronze may be deterministically rebuilt under new binding identity rather than migrated in place. Raw/Control Plane evidence should be retained according to operational policy.

## 11. Unified DatasetContract universe

Before Phase 059 completes, every Bronze/Silver/Gold DatasetId must have one authoritative `DatasetContract` owning the complete schema vocabulary required by Core and future consumers.

A DatasetContract may own:

- DatasetId and layer;
- schema version and stability classification;
- physical name;
- description and machine-readable grain;
- complete `ColumnContract`s;
- logical types and nullability;
- primary/unique keys;
- foreign/reference contracts;
- identity semantics;
- empty/duplicate policy;
- dataset and column capability ownership;
- deterministic contract fingerprint.

Base DatasetContracts are immutable declarative truth. `ExecutionPlan` derives an effective contract for the active capability set; it does not mutate the base contract.

Derived adapters may compile DatasetContracts into DuckDB DDL, Bronze Pandera Gate-2 schemas, capability-column indexes, Meta catalog entries and machine-readable exports. Those adapters must not become independent schema authorities.

Pre-Bronze remains outside this fixed DatasetContract universe because its shape is source-configured.

## 12. Dependency direction and ownership

- `contracts`: stable, dependency-light identifiers, enums, DatasetContracts, capability descriptors, public provenance/error vocabulary and declarative recipe metadata.
- `config`: user-authored validated Settings/FinancialRules/SourceConfiguration models.
- `application`: SourcePlanner, CapabilityPlanner, satisfiability planning, canonical production orchestration, replay planning and diagnostics.
- `domain`: financial meaning and algorithms only; no source/provider topology.
- `infrastructure`: providers, hashing, Pandera execution, Control Plane and warehouse persistence.
- `bootstrap`: concrete dependency assembly.
- `presentation`: CLI/Desktop interaction through application services/facade.

Future `pfetl-contracts` extraction must be possible without moving Polars/Pandera/DuckDB/SQLite/provider implementations into the contract package.

## 13. Observability

The existing one-emitter / downstream-consumer architecture remains authoritative.

New context may include:

- `source_id`;
- `source_binding_id`;
- canonical route identity;
- canonical `dataset_id`;
- producer kind;
- production/contract fingerprints;
- row counts and bounded rule outcomes.

Do not emit sensitive financial rows merely to explain semantic mapping. Multiprocessing lineage must preserve run/parent-operation context.

## 14. Migration discipline for Phases 046-055

The canonicalization migration follows:

```text
introduce replacement
-> prove replacement independently
-> use bounded compatibility only where needed
-> migrate one ownership boundary
-> prove financial / identity equivalence
-> zero-reference old ownership
-> delete old ownership
```

Key cutovers:

- 046: typed canonical/source-binding vocabulary only;
- 047: deterministic compatibility compilation;
- 048: SourceBindingPlan + binding-keyed Pre-Bronze;
- 049: semantic routes/fragments;
- 050: canonical production + Gate 2 + integrity;
- 051: satisfiability and production DAG;
- 052-053: household canonical evidence then Silver cutover/demolition;
- 054-055: investment/reference/provider canonical evidence then financial consumer cutover/demolition.

Phase 055 must leave exactly one production architecture.

## 15. Certification and freeze discipline for Phases 056-060

Phases 056-060 certify and freeze the architecture; they do not create an alternate one.

- 056 certifies external household topologies and retires unused household columns through consumer archaeology.
- 057 certifies external investment topologies, provider/reference portability and protected identity equivalence, then retires unused columns.
- 058 profiles the final architecture and optimizes measured bottlenecks without weakening validation, observability or recovery.
- 059 freezes the complete identifier/configuration/capability/Bronze/Silver/Gold contract universe and eliminates duplicate schema authority.
- 060 certifies clean installation, supported v10.3.0-state upgrade, external topologies, Shan financial equivalence, replay/recovery, contract-to-warehouse parity, Tkinter Desktop GUI and Terminal CLI modernization, and multiprocessing observability.

Certification phases may repair a generic defect exposed by a fixture. They must never introduce fixture-specific financial semantics or hidden topology branches.

## 16. Program-level closure rules

- Temporary `SourceDatasetConfig -> DatasetId` compatibility has an explicit deletion owner and must not survive the Phase-055 cutover.
- `COMMON_COLUMN_MASTER`, deprecated Settings source paths and other transitional schema/config authorities must not survive the Phase-059 freeze unless explicitly re-justified as non-authoritative runtime inputs.
- Removing/disabling a source binding or canonical dataset cannot leave stale current-state evidence, while historical Raw/Control Plane provenance remains governed by retention policy.
- Configured-but-empty evidence is distinct from absent, disabled and malformed evidence.
- Built-in Desktop Tkinter GUI (`presentation.desktop`) and Terminal CLI (`presentation.cli`) are fully modernized within Core in Phase 060 to support the complete configuration triad, interactive diagnostics (validate, check-sources, preview-plan, dry-run), capability toggles, and live telemetry streaming; future standalone web/cloud "Studios" remain separate ecosystem programs.
- Final acceptance covers clean install and representative v10.3.0 operational-state upgrade.
- No post-060 Phase 061 is implied. Contract extraction into a future `pfetl-contracts` repository is an ecosystem program if Phase 059 made the boundary extraction-ready.
