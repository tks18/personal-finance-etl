# Phase 037 - Artifact-Key Operational Provenance Cutover

**Target release:** v10.0.0-rc10  
**Expected effort:** 3-4 hours  
**Previous:** Phase 036  
**Next:** Phase 038  
**Risk:** High

## 1. Outcome

Replace Bronze and Meta-healing operational dependence on `__file_name__` with explicit stable artifact/source provenance keys, then remove filename as an operational row identity after dual-write equivalence.

At phase end filenames/paths are descriptive Control Plane metadata only. Rename, changed-artifact replacement and healing operate through stable provenance identity.

## 2. Why this phase exists

The current architecture historically used filename for both human provenance and row ownership. Phase 010/011 cleaned canonical Silver lineage, but Bronze deliberately retained filename because deletion/rename/healing depended on it. With all ingestion generalized and Pre-Bronze artifact-keyed, that final operational coupling can now be removed safely.

## 3. Inherited repository state

Phase 036 guarantees strict canonical Bronze. Phase 021+ use artifact-keyed Pre-Bronze. Control Plane artifact identity/change/rename truth is stable. Silver no longer relies on path fields.

Still current:
- Bronze delete changed-file rows may filter `__file_name__`;
- rename migration may rewrite filename;
- Meta healing may query/delete by filename.

## 4. Current codebase anchors

Fresh current-branch search required for:
- `__file_name__`
- filename-based delete predicates
- rename migration helpers
- Meta healing
- Bronze grouping/filtering
- provider provenance projections
- tests around changed/renamed files.

Trace exact Control Plane artifact identity semantics after Phases 006/025-035. Determine whether current `file_id` remains stable across rename or whether a stable logical artifact/content lineage key introduced earlier is authoritative. Do not assume; use implemented behavior.

## 5. Exact target state after this phase

Bronze operational provenance contains an explicit stable key, conceptually:
```text
artifact_id / artifact_lineage_id
source_id
dataset_id
```

Changed-artifact replacement:
```text
delete Bronze rows WHERE artifact_key = authoritative artifact
insert canonical rows for current artifact version
```

Rename:
- descriptive path/name changes in Control Plane;
- Bronze row ownership does not require rewriting a filename identity;
- if artifact ID itself versions across content change, use the implemented lineage/replacement relationship deliberately.

Meta healing references the same authoritative key.

`__file_name__` may be absent from canonical Bronze unless a specific dataset contract retains it as descriptive evidence for a justified reason.

## 6. Detailed implementation sequence

### Step 1 - Freeze artifact identity semantics
Document/test how NEW, CHANGED and RENAME affect file/artifact IDs after current Control Plane implementation. Choose the stable operational key from actual semantics.

### Step 2 - Add Bronze provenance key additively
If not already persisted from generalized admission, add stable artifact key to every file-backed Bronze row. Provider-generated datasets use provider-request provenance variant, not fake artifact IDs.

### Step 3 - Dual-run changed-file deletion
For controlled fixtures, compute rows selected by old filename predicate and new artifact predicate; assert identical ownership before switching.

### Step 4 - Switch changed-artifact replacement
Bronze delete/replace uses artifact provenance only.

### Step 5 - Switch rename handling
Rename updates Control Plane descriptive metadata. Bronze rows remain associated through stable key. Remove filename rewrite logic where obsolete.

### Step 6 - Migrate Meta healing
Replace filename predicates with artifact/source/dataset provenance. Healing must reconstruct truth from Control Plane identifiers, not path text.

### Step 7 - Remove operational filename column
After repository-wide proof, remove `__file_name__` from canonical Bronze where it exists solely for operations. Preserve filename in Control Plane.

### Step 8 - Failure/recovery matrix
Changed artifact + failure after delete/before insert; rename + failure; split commit; restore/heal. All must converge.

### Step 9 - Architecture guard
No Bronze/Meta operational predicate may key row ownership by filename/path.

### Step 10 - Full regression/performance
Row counts, financial outputs, IDs, rename behavior and runtime.

## 7. Files and symbols in scope

Modify:
- Bronze persistence/delete/rename;
- Meta healing;
- canonical operational provenance fields;
- provider-generated provenance variant if necessary;
- tests.

Control Plane descriptive filename/path storage remains.

## 8. Cross-cutting impacts

**Persistence:** Bronze operational provenance schema changes. Existing Bronze is rebuildable; define upgrade/rebuild behavior.

**Identity:** artifact provenance is not financial identity. Protected IDs unchanged.

**Recovery:** highest-risk concern; all failure windows tested.

**Observability:** events can display filename for humans while correlating artifact/source/dataset IDs.

**Performance:** artifact-key delete should be indexed/efficient for DuckDB usage; compare with filename predicate.

## 9. Tests and verification

Required:
- artifact identity semantics test;
- old/new ownership equivalence before switch;
- changed artifact replacement;
- rename without Bronze filename rewrite;
- removed file/full-replace as applicable;
- Meta healing by artifact key;
- rollback/split-commit recovery;
- backup/restore;
- repository guard against filename operational predicates;
- full Shan outputs/IDs unchanged.

## 10. Explicit non-goals

Do not:
- delete filename/path from Control Plane;
- change source config;
- alter financial identity;
- make analytical DDL plan-aware;
- redesign recovery protocol.

## 11. Completion checklist

- [ ] Stable operational artifact key frozen.
- [ ] Bronze rows carry it.
- [ ] Changed-file deletion migrated.
- [ ] Rename migrated.
- [ ] Meta healing migrated.
- [ ] Operational filename identity removed.
- [ ] Recovery matrix green.
- [ ] Full financial/ID regression green.

## 12. Commit boundary

```text
refactor(lineage): key bronze operations by artifact
```

## 13. Handoff to Phase 038

Phase 038 may assume the generalized ingestion architecture is complete end-to-end: no fixed topology, strict canonical Bronze, explicit operational provenance, Pre-Bronze validation/recovery and all current evidence families migrated. Phase 038 is certification, not new architecture.

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
