# Phase 010 - Canonical Provenance Model

**Target release:** v9.6.2  
**Expected effort:** 3-4 hours  
**Previous:** Phase 009  
**Next:** Phase 011 - Silver Provenance Cleanup  
**Risk:** Medium-High  
**Runtime behavior change:** Additive lineage path  
**Schema/persistence change:** Additive provenance fields/contracts; no destructive cleanup yet

## 1. Outcome

Introduce one canonical provenance reference model that links extracted/canonical financial rows to Control Plane artifact/source/dataset identity without treating filenames/folder paths as canonical financial fields.

At phase end:
- explicit provenance identifiers exist;
- relevant Bronze/Silver production paths can populate them additively;
- downstream lineage can resolve artifact metadata through Control Plane;
- existing `__file_name__`, `__folder_path__`, and provenance-only `__file_category__` remain temporarily for compatibility;
- Phase 011 can remove those fields from canonical Silver safely.

This phase is expand + prove. It is deliberately not the destructive cleanup phase.

## 2. Why this phase exists

v9.5.3 uses provenance fields for several different jobs:

```text
__file_name__
  provider attribution
  Bronze changed-file deletion
  rename migration
  Meta healing
  Silver lineage/debug

__folder_path__
  provider attribution
  Silver lineage/debug

__file_category__
  source grouping/provenance
  formerly financial classification
```

Phase 009 removes the financial misuse of `__file_category__`.

The remaining lineage responsibility needs a stable model before source-path columns can leave Silver.

Important: Bronze operational `__file_name__` identity is **not** removed here. Its delete/rename/healing migration occurs much later after generalized ingestion is established.

## 3. Inherited state

Phase 009 guarantees:
- financial decisions no longer depend on `__file_category__`;
- protected financial identities remain unchanged;
- source category may still exist as provenance.

Control Plane still owns artifact truth.

## 4. Current Control Plane anchors

Use the existing artifact/file registry as the authority for:
- file/artifact ID;
- relative path;
- category;
- file type;
- content hash;
- payload;
- status/events;
- run association.

Do not create a competing provenance database.

## 5. Target provenance contract

Define a compact typed cross-boundary reference.

Conceptually:

```text
ProvenanceRef
├── artifact_id / file_id
├── source_id          # when available from Phase 002/004 topology
├── dataset_id
└── optional source_record_key only if required for row-level disambiguation
```

Do not embed:
- full path;
- folder path;
- raw configuration;
- provider-specific metadata;
- large payload details.

The Control Plane resolves the reference to operational metadata.

### Source-record key decision

Only add a record-level discriminator if one artifact can contain multiple rows and downstream lineage genuinely needs row-level traceability beyond artifact+canonical identity.

Do not invent one universally if dataset identity/financial row identity already provides sufficient drill-through.

## 6. Ownership

- contract type: `contracts`;
- creation/population: ingestion/transformation boundary;
- artifact lookup: Control Plane infrastructure/repository;
- financial domain may carry opaque provenance reference but must not query filesystem paths directly.

## 7. Implementation sequence

### Step 1 - Define provenance contract

Create typed immutable value object/dataclass.

Validate IDs are non-empty where required.

### Step 2 - Extend runtime dataset metadata

If Phase 001-004 introduced dataset/source metadata objects, attach provenance there rather than creating another parallel metadata bag.

For file-backed extraction, each frame/artifact must know:
- SourceId;
- DatasetId;
- Control Plane artifact ID.

### Step 3 - Add Control Plane lookup API

Provide a narrow method to resolve `artifact_id` to descriptive metadata needed by diagnostics/presentation.

Do not expose arbitrary SQL/connection access.

### Step 4 - Populate provenance additively

Choose the smallest common extraction/transform boundary that can populate provenance without row-wise Python work.

For multi-file concatenated frames, preserve the correct artifact association per row.

Do not replace `__file_name__` yet.

### Step 5 - Add canonical provenance field/reference to Silver families that currently carry path fields

Additively populate the reference for:
- household dimensions/facts carrying `__file_name__`/`__folder_path__`;
- investment purchase/sale/market rows where lineage is retained;
- reference/master datasets where useful.

Use the Phase 008 disposition manifest to determine exact tables.

### Step 6 - Prove lineage resolution

For representative rows:
1. read Silver provenance reference;
2. resolve Control Plane artifact;
3. recover original path/category/hash metadata;
4. prove it corresponds to the old path fields.

### Step 7 - Update migration manifest

Mark provenance-reference rows as migrated/dual-state.

Do not mark old source-path columns removed yet.

## 8. Data flow

### Before

```text
Silver row
  -> __file_name__
  -> __folder_path__
  -> human/debug interpretation
```

### After

```text
Silver row
  -> ProvenanceRef
  -> Control Plane artifact registry
  -> path/category/hash/run metadata

legacy path columns still present temporarily
```

## 9. Files expected in scope

Create/modify:
- `contracts` provenance type;
- dataset runtime metadata if applicable;
- Control Plane artifact lookup;
- relevant transform/projection helpers;
- Silver DDL additively where provenance reference is persisted;
- migration manifest;
- tests.

Read but do not alter operational semantics:
- `warehouse/bronze.py`;
- `warehouse/meta/healing.py`;
- file rename/delete logic.

## 10. Explicitly out of scope

Do not:
- remove Bronze `__file_name__`;
- change changed-file deletion;
- change rename migration;
- change Meta healing;
- delete Silver path fields;
- change provider-specific Yahoo symbols;
- change artifact IDs.

Those are later phases.

## 11. Persistence / migration

Any Silver DDL change is additive.

Because Silver is rebuilt, no complex in-place row migration should be necessary for normal pipeline execution. Still update schema/contract tests.

Control Plane schema should not need a new provenance table if current artifact IDs already provide the required authority.

If SourceId/DatasetId need additive columns on artifact/run records for future lookup, add them only if the current contract cannot reconstruct them reliably. Prefer run/config reference over duplication.

## 12. Identity

Provenance is not financial identity.

Do not include new provenance IDs in PURCHASE/SALE/LOT/REALIZED/RECON/TAX identity hashes unless they were already semantically part of the identity. They should not be.

## 13. Observability

Extend context only if existing event model supports bounded:
- source_id;
- dataset_id;
- artifact_id.

Do not redesign emitter/sinks.

Lineage event correlation remains run/operation based.

## 14. Tests

Required:

### Contract
- ProvenanceRef equality/serialization deterministic.
- invalid empty required IDs rejected.

### Population
- single-file frame gets correct artifact ID;
- multi-file concatenation preserves per-row artifact association;
- SourceId/DatasetId match configured topology.

### Resolution
- representative Silver row resolves to same path/category/hash as legacy fields.

### Non-regression
- financial outputs unchanged;
- protected deterministic IDs unchanged;
- Bronze rename/delete/healing tests unchanged.

### Manifest
- every Phase-008 column marked MOVE_TO_PROVENANCE has an implemented replacement or an explicitly documented later operational migration.

## 15. Real-data verification

Run Shan data and sample representative rows from:
- household transaction;
- household dimension;
- investment purchase/sale;
- market/reference dataset.

For each, verify provenance resolves correctly.

No paise-level output change.

## 16. Performance

Provenance must not perform one SQLite lookup per dataframe row during pipeline execution.

Carry identifiers columnarly; resolve descriptive metadata only for diagnostics/drill-through when needed.

Any N+1 Control Plane lookup in the hot path fails this phase.

## 17. Delete / retain

Retain:
- all legacy Silver path fields until Phase 011;
- Bronze operational filename fields;
- Control Plane category/path metadata.

Add:
- canonical provenance reference.

## 18. Non-goals

Do not:
- clean all Silver source residue;
- replace provider symbols;
- alter Bronze operational identity;
- add Pre-Bronze;
- change source configuration runtime.

## 19. Completion checklist

- [ ] Canonical ProvenanceRef exists.
- [ ] SourceId/DatasetId/artifact identity are represented without path semantics.
- [ ] Representative production frames populate provenance.
- [ ] Silver lineage can resolve through Control Plane.
- [ ] Legacy fields coexist intentionally.
- [ ] No N+1 artifact lookup exists in hot path.
- [ ] Financial values and protected IDs unchanged.
- [ ] Bronze operational semantics unchanged.
- [ ] Phase 008 manifest updated to dual-state.

## 20. Commit

```text
feat(lineage): add canonical artifact provenance
```

## 21. Handoff to Phase 011

Phase 011 may assume canonical provenance is populated and proven for every Silver family currently carrying source path fields.

Phase 011's job is destructive cleanup: migrate any final consumers and remove source-path residue from canonical Silver while leaving Bronze operational filename semantics untouched until the later generalized-ingestion provenance cutover.

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
