# Phase 003 - Reference Data Cleanup and Instrument Master Migration

**Target release:** v11.1.0  
**Expected effort:** 2–3 focused hours  
**Previous:** Phase 002  
**Next:** Phase 004  
**Risk:** Medium

## 1. Outcome

Make manually maintained reference files tell the truth about their responsibilities and perform the one-time instrument-master migration.

## 2. Why this phase exists

- `benchmark_mapping.csv` currently owns instrument classification, tax attributes, geography and market ticker data beyond benchmark mapping.
- Reference filenames should be self-explanatory for the primary maintainer.
- This is an accepted one-time local migration with no compatibility adapter afterward.

## 3. Inherited repository state

- Phase 002 has completed green and its handoff is authoritative.
- No later phase has been partially implemented.
- Financial truth and protected identities remain at the last accepted oracle.

## 4. Current codebase anchors

- current Settings reference paths
- CSV ingestion in `application/ingestion/coordinator.py` and file providers
- investment master transforms/consumers
- Silver benchmark/instrument/currency/macro producers
- tests/static reference fixtures if present

## 5. Exact target state after this phase

Make manually maintained reference files tell the truth about their responsibilities and perform the one-time instrument-master migration.

The phase must leave a coherent runnable repository. Transitional state is allowed only where explicitly handed to the next phase.

## 6. Detailed implementation sequence

### Step 1 - Freeze and implement the seven reference filenames: column master, MF instrument mapping, instrument master, benchmark master, currency reference, financial-year parameters, opening balances

Freeze and implement the seven reference filenames: column master, MF instrument mapping, instrument master, benchmark master, currency reference, financial-year parameters, opening balances.

### Step 2 - Create/validate the target `instrument_master

Create/validate the target `instrument_master.csv` schema by moving the current benchmark-mapping enrichment responsibilities without changing meaning.

### Step 3 - Rename MF ISIN mapping, currency mapping and macro-parameters concepts to the frozen vocabulary

Rename MF ISIN mapping, currency mapping and macro-parameters concepts to the frozen vocabulary.

### Step 4 - Update Settings paths and ingestion attributes to the new reference concepts

Update Settings paths and ingestion attributes to the new reference concepts.

### Step 5 - Provide a deterministic one-time migration script/checklist for Shan’s local reference files

Provide a deterministic one-time migration script/checklist for Shan’s local reference files.

### Step 6 - Update tests/fixtures and verify the resulting Silver instrument/benchmark/currency/macro outputs are financially equivalent

Update tests/fixtures and verify the resulting Silver instrument/benchmark/currency/macro outputs are financially equivalent.

## 7. Files and symbols in scope

Use the anchors above as the minimum inspection set. Add only directly affected files discovered by archaeology; do not widen scope for opportunistic cleanup.

## 8. Cross-cutting impacts

- Local reference files require a one-time migration before the next production run.

## 9. Tests and verification

- [ ] Old `benchmark_mapping` is no longer a runtime concept.
- [ ] `instrument_master` owns the pre-existing instrument enrichment fields with unchanged values.
- [ ] All seven reference files load with explicit validation.
- [ ] A migrated v11.0.0 reference set produces equivalent downstream finance before any warehouse rename.
- [ ] No long-lived legacy filename adapter remains.

## 10. Explicit non-goals

- Do not rename Bronze/Silver/Gold tables yet.
- Do not invent new instrument classifications or Tax methodology.

## 11. Completion checklist

- [ ] Exit assertion: Old `benchmark_mapping` is no longer a runtime concept.
- [ ] Exit assertion: `instrument_master` owns the pre-existing instrument enrichment fields with unchanged values.
- [ ] Exit assertion: All seven reference files load with explicit validation.
- [ ] Exit assertion: A migrated v11.0.0 reference set produces equivalent downstream finance before any warehouse rename.
- [ ] Exit assertion: No long-lived legacy filename adapter remains.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 004

The next phase may assume only the verified state above. It begins **Semantic Bronze Naming and Rebuild Cutover** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 003
Target release: v11.1.0
Files changed:
Contracts/schema changed:
Financial formulas changed:
Protected identity comparison:
Focused tests:
Architecture tests:
Real-data verification:
Power BI verification:
Observability/recovery verification:
Compatibility/transitional state remaining:
Semantic commit groups:
Exit assertions green: yes/no
```
