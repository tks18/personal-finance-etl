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

- [x] Old `benchmark_mapping` is no longer a runtime concept.
- [x] `instrument_master` owns the pre-existing instrument enrichment fields with unchanged values.
- [x] All seven reference files load with explicit validation.
- [x] A migrated v11.0.0 reference set produces equivalent downstream finance before any warehouse rename.
- [x] No long-lived legacy filename adapter remains.

## 10. Explicit non-goals

- Do not rename Bronze/Silver/Gold tables yet.
- Do not invent new instrument classifications or Tax methodology.

## 11. Completion checklist

- [x] Exit assertion: Old `benchmark_mapping` is no longer a runtime concept.
- [x] Exit assertion: `instrument_master` owns the pre-existing instrument enrichment fields with unchanged values.
- [x] Exit assertion: All seven reference files load with explicit validation.
- [x] Exit assertion: A migrated v11.0.0 reference set produces equivalent downstream finance before any warehouse rename.
- [x] Exit assertion: No long-lived legacy filename adapter remains.

## 12. Commit boundary

Commit the completed phase in semantically coherent groups. Use the repository `pfetl-conventional-commits` Skill to preview/stage/group changes and produce Commitlint-compliant messages. Do not force a single phase-wide commit and do not create artificial file-by-file commits.

## 13. Handoff to Phase 004

The next phase may assume only the verified state above. It begins **Semantic Bronze Naming and Rebuild Cutover** from this green boundary; it must not reopen this phase unless new implementation evidence proves a contradiction.

## Phase completion record

```text
Phase: 003
Target release: v11.1.0
Files changed:
- src/personal_finance_etl/contracts/extraction.py
- src/personal_finance_etl/infrastructure/providers/files/csv.py
- src/personal_finance_etl/infrastructure/providers/files/__init__.py
- src/personal_finance_etl/application/ingestion/coordinator.py
- src/personal_finance_etl/application/pipeline/execution.py
- src/personal_finance_etl/application/pipeline/transformer.py
- src/personal_finance_etl/application/ingestion/asset_strategies.py
- src/personal_finance_etl/domain/investments/transforms/common.py
- src/personal_finance_etl/domain/investments/transforms/mutual_funds.py
- src/personal_finance_etl/infrastructure/control_plane/hashing.py
- src/personal_finance_etl/infrastructure/warehouse/contracts.py
- src/personal_finance_etl/infrastructure/warehouse/bronze.py
- scripts/migrate_reference_files.py
- tests/config.toml
- tests/test_phase3_reference_data_and_instrument_master.py
- tests/test_core_pipeline_observability.py
- tests/test_forensic_debuggability.py
- tests/test_phase2_config_and_primitives.py
- tests/test_phase4_extraction_and_ingestion.py
External files migrated:
- g:/My Drive/Docs/Financial Docs/Financial Planner/Analysis/__dependencies__/column_master.csv
- g:/My Drive/Docs/Financial Docs/Financial Planner/Analysis/__dependencies__/mutual_fund_instrument_mapping.csv
- g:/My Drive/Docs/Financial Docs/Financial Planner/Analysis/__dependencies__/instrument_master.csv
- g:/My Drive/Docs/Financial Docs/Financial Planner/Analysis/__dependencies__/benchmark_master.csv
- g:/My Drive/Docs/Financial Docs/Financial Planner/Analysis/__dependencies__/currency_reference.csv
- g:/My Drive/Docs/Financial Docs/Financial Planner/Analysis/__dependencies__/financial_year_parameters.csv
- g:/My Drive/Docs/Financial Docs/Financial Planner/Analysis/__dependencies__/opening_balances.csv
- g:/My Drive/Docs/Financial Docs/Financial Planner/Analysis/ETL App/shan_personal_finance_ETL.toml
- g:/My Drive/Docs/Financial Docs/Financial Planner/Analysis/ETL App/shan_personal_finance_ETL_Test.toml
Contracts/schema changed: Retired benchmark_mapping in favor of instrument_master; standardized all 7 reference datasets across ExtractionResult, CSV parsers, Control Plane sync categories, and domain transforms
Financial formulas changed: None
Protected identity comparison: N/A
Focused tests: tests/test_phase3_reference_data_and_instrument_master.py (5 passed)
Full regression: 200/200 passed across entire pytest suite
Architecture tests: tests/test_architecture_boundaries.py (passed)
Real-data verification: Migrated live Google Drive files, verified identical row counts, and validated live configurations
Power BI verification: N/A
Observability/recovery verification: ExtractionResult stream validation and pipeline execution verified
Static analysis verification:
- pyright: 0 errors, 0 warnings, 0 informations
- pylint src: 10.00/10 rating
- mypy: 0 issues in 199 source files
- ruff: all checks passed, formatting clean
- documentation: 100% documented, 0 AST violations
Compatibility/transitional state remaining: None. Zero legacy benchmark_mapping runtime concepts remain.
Semantic commit groups:
- refactor(ingestion): retire benchmark_mapping and establish instrument_master
- refactor(transforms): align reference data schemas across domain and pipeline
- feat(scripts): add deterministic reference file migration script
- test(ref-data): add phase 3 reference data and instrument master test suite
Exit assertions green: yes
```
