# Phase 050 - Fresh-Install Final PFETL Acceptance

**Target release:** v10.4.1  
**Expected effort:** 3-4 hours  
**Previous:** Phase 049  
**Next:** Grand Refactor complete  
**Risk:** Critical

## 1. Outcome

Execute the final end-to-end acceptance of the Grand Refactor from a clean installation/workspace using only PFETL's public configuration and CLI/application interfaces.

The acceptance journey must cover configuration creation from a prepared golden example, validation, source diagnostics, admission dry run, first financial run, incremental rerun, a controlled failure and remediation, capability change, backup/restore, observability lineage and final output verification.

If this phase passes, the core Grand Refactor is complete. No architectural requirement from this program may be deferred to an invented v11 milestone merely to close the plan.

## 2. Why this phase exists

Unit/integration/certification phases prove components and scenarios. The final question is simpler and harsher: can a new supported user operate the generalized PFETL core from zero state without source-code edits, legacy knowledge or hidden Shan assumptions?

## 3. Inherited repository state

Phase 049 guarantees a frozen public source-config v1 and golden external configurations. All architecture, recovery, capability, performance and diagnostic work is complete.

The accepted implementation baseline at phase start is the post-Phase-049 repository, not v9.5.3. v9.5.3 remains only the historical financial regression oracle for unchanged methodologies.

## 4. Current codebase anchors

Use:
- clean virtual environment/install according to project-supported packaging;
- empty working data/control-plane/warehouse directories;
- permanent Generic Golden User benchmark scenario (`tests/fixtures/external/golden_user/`) featuring:
  - `sources.toml` mapping completely novel/generic Excel, CSV, and SQLite schemas;
  - `settings.toml` and `financial_rules.toml` with generic user parameters;
  - generic evidence files across household budgeting, banking, domestic equities, mutual funds, and foreign assets;
- canonical sample evidence repository (`tests/fixtures/evidence/`) serving as the public-facing golden reference dataset for new users and automated fresh-install acceptance runs;
- frozen machine-readable config schema;
- PFETL CLI/help;
- backup/restore commands;
- observability JSONL output.

Do not call internal Python services manually to rescue the acceptance journey.

## 5. Exact target state after this phase

A clean user can perform:

```text
install PFETL
 -> obtain/create valid source_config v1
 -> validate-config
 -> check-sources
 -> preview mapping/identity/plan
 -> dry-run admission
 -> run
 -> inspect expected outputs
 -> rerun unchanged
 -> modify evidence and rerun
 -> encounter controlled invalid config/source
 -> remediate using diagnostic
 -> rerun successfully
 -> change capability selection
 -> observe correct warehouse contract set
 -> backup
 -> restore
 -> rerun
 -> reconstruct run lineage
```

No source code modification, legacy folder naming, column-master file, hidden feature flag or manual database surgery.

## 6. Detailed implementation sequence

### Step 1 - Create clean acceptance workspace
Install from the exact release candidate/package state. No reused Control Plane, DuckDB or caches unless the scenario explicitly tests cache creation.

### Step 2 - Validate public contract
Use frozen schema/golden config. Run CLI validation and plan preview. Confirm expected active DatasetIds/capabilities.

### Step 3 - Source diagnostics
Reachability/selectors/mapping/identity preview all succeed. Record expected output summary.

### Step 4 - Admission dry run
Must leave production state empty/unchanged while proving both validation gates.

### Step 5 - First committed run
Execute selected scenario. Assert expected Pre-Bronze/Bronze/Silver/Gold/Meta active state, financial values and identities.

### Step 6 - Unchanged rerun
Verify incremental/cache behavior, stable IDs, no duplicate rows and accepted performance.

### Step 7 - Evidence change
Modify one supported source record/artifact. Rerun; verify exact expected changed downstream state and unchanged unrelated state.

### Step 8 - Controlled failure/remediation
Introduce one invalid mapping/source schema/identity collision. Run diagnostics, confirm actionable failure and atomic state, repair config/source, rerun successfully.

### Step 9 - Capability switch
Change from full/combined scenario to a supported reduced plan. Verify provider work skipped and Phase-043 stale analytical tables removed. Switch back and verify recreation.

### Step 10 - Backup/restore
Backup generalized state including Pre-Bronze/config provenance. Restore into clean target and verify outputs/next incremental run.

### Step 11 - Observability forensic reconstruction
From JSONL + Control Plane, trace one committed run:
configuration fingerprint -> plan -> source/artifact/provider request -> validation -> Pre-Bronze -> normalization/identity -> Bronze -> engines -> Silver/Gold/Meta -> commit state.

Repeat the lineage check for at least one multiprocessing/worker operation and prove worker/run/parent-operation correlation survives process boundaries.

### Step 12 - Existing-state upgrade acceptance
Start from a preserved pre-refactor/v9.5.3-era operational state (Control Plane/Raw Store and a representative warehouse/backup according to supported migration policy), upgrade to the final code using Shan's production configuration in `G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\ETL App\`:
- `--config "G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\ETL App\shan_personal_finance_ETL.toml"`
- `--rules "G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\ETL App\shan_personal_finance_rules.toml"`
- `--sources "G:\My Drive\Docs\Financial Docs\Financial Planner\Analysis\ETL App\shan_personal_finance_sources.toml"`
Execute the pipeline against real live evidence (with `shan_personal_finance_sources.toml` dynamically resolving the latest modified backup in `G:\My Drive\MoneyManager`), perform documented migrations, and prove the resulting financial state (FIFO lots, capital gains, tax liabilities, net worth, FIRE projections) equals the historical v9.5.3 regression oracle down to the penny. Historical run/artifact provenance must remain readable. No manual SQL surgery or hardcoded Python fallbacks are allowed.

### Step 13 - Desktop & Telemetry Presentation Acceptance
Because Desktop and CLI are the primary presentation layers of PFETL, run full acceptance against the modern core:
- launch against the migrated configuration/runtime contracts;
- execute the supported default/current run path without assuming fixed source topology;
- UI progress bars receive smooth live updates per-file during generalized ingestion (`PresentationKind.PROGRESS` events with file name, row count, and percentage);
- Stage narrative displays modern Medallion architecture stages (Discovery -> Ingestion -> Harmonization -> Analytics -> Gold Marts);
- tolerate capability-specific Silver/Gold absence rather than reporting corruption;
- expose run and snapshot/restore outcomes through the existing presentation contract;
- append-only forensic logging in `outputs/logs/` captures complete end-to-end lineage from Ingestion to Monte Carlo without raw tracebacks;
- avoid importing configuration/planning/validation implementation internals directly.

This is compatibility and telemetry certification of the existing Desktop, not a new Config Studio or GUI redesign.

### Step 14 - Performance acceptance
Apply Phase-048 durable thresholds to first/full/cached relevant runs.

### Step 15 - Legacy absence audit
Repository/runtime acceptance proves:
- zero hardcoded configuration dictionaries in `loader.py` (configuration loaded exclusively from `sources.toml`);
- zero references to `column_master` or `COMMON_COLUMN_MASTER` across `src/` and public configuration schemas;
- canonical Bronze catalog contains exactly 19 active contracts (all 19 true financial evidence streams) and zero transitional configuration contracts;
- no fixed ExtractionResult;
- no column-master data path or transitional configuration bypasses;
- no folder-name topology;
- no dynamic Bronze schema evolution;
- no filename operational identity;
- no source-category financial semantics;
- no provider-specific canonical vocabulary;
- no mandatory full analytical warehouse;
- no hidden source-code customization.

### Step 16 - Release-state audit
All 50 phase completion contracts satisfied or superseded by stricter later behavior. README phase tracker updated. Any discovered gap is fixed in the owning architecture/phase, not waived.

### Step 17 - Decide whether v11 exists
Default: no. Create a future major only for a separately justified breaking product/contract boundary, not because the Grand Refactor ended.

## 7. Files and symbols in scope

Modify only:
- defects discovered by final acceptance;
- release/progress metadata;
- tests needed to permanently capture a discovered regression.

If a defect reveals an architectural gap, amend `ARCHITECTURE.md` and the owning phase specification before implementing the correction.

## 8. Cross-cutting impacts

**Persistence:** full clean lifecycle, incremental lifecycle, capability switch, backup/restore certified.

**Identity:** stable across rerun/change according to semantics; protected financial IDs remain deterministic.

**Provenance:** source/config/plan/artifact/provider/financial lineage reconstructable.

**Observability:** one emitter/three consumers remains intact; no special acceptance-only instrumentation.

**Performance:** Phase-048 thresholds are release gates.

**Public contract:** only schema-v1/public interfaces used.

**Scope:** core PFETL only.

## 9. Tests and verification

Final mandatory acceptance matrix:

### Installation/public interface
- clean install/import/CLI help;
- config v1 validation;
- no internal API required.

### Configuration
- source checks;
- mapping/identity preview;
- plan/contract preview;
- dry run non-mutating.

### First run
- exact active warehouse layers/tables;
- expected financial values;
- stable IDs;
- configuration/plan provenance.

### Incremental
- unchanged rerun;
- changed evidence;
- no duplicates/stale outputs.

### Failure/recovery
- invalid input/config atomic failure;
- remediation and rerun;
- split-commit/recovery suite remains green.

### Capability
- reduced plan;
- provider skipping;
- stale-table cleanup;
- re-enable.

### Backup/restore
- complete generalized state;
- post-restore rerun.

### Existing-state upgrade
- pre-refactor operational state upgrades without manual SQL surgery;
- migrated state equals clean final-version rebuild;
- historical provenance remains readable.

### Desktop/presentation
- existing Desktop smoke path works against final core;
- capability-specific table absence is handled correctly;
- run/snapshot/restore outcomes remain exposed.

### Observability
- end-to-end lineage reconstruction;
- multiprocessing/worker lineage reconstruction.

### Performance
- thresholds pass.

### Legacy
- zero prohibited architecture references;
- zero references to `column_master` or `COMMON_COLUMN_MASTER` across `src/` and configuration schemas;
- canonical Bronze catalog contains strictly 19 active contracts.

### Regression & End-to-End Continuum
- Shan full financial oracle remains green;
- external household/investment golden fixtures remain green;
- static sample evidence suite (`tests/fixtures/evidence/`) executes end-to-end verifying zero-defect execution of FIFO lot matching, capital gains tax, FIRE simulations, and Wealth reporting on clean installs;
- **Generic Golden User End-to-End Acceptance (`tests/application/test_generic_user_e2e_acceptance.py`):**
  - Executes a clean-install run using purely generic external evidence (`tests/fixtures/external/golden_user/`) and public TOML configurations without any Shan data or hardcoded Python configuration;
  - Asserts complete source-agnostic pipeline execution from Discovery and Pre-Bronze raw admission through Monte Carlo stochastic simulation;
- **Full End-to-End Multi-Layer Assertion Suite (From Ingestion to Monte Carlo):**
  - **Ingestion & Control Plane:** Assert file discovery, SHA-256 fingerprinting, binary file payload storage in `Raw_Documents.sqlite`, file registration, and run manifest logging;
  - **Meta Layer:** Assert `_meta_file_registry`, `_meta_ingestion_manifest`, `_meta_schema_catalog`, and `_meta_capability_state` correctly track all artifact IDs, row counts, and schema versions;
  - **Pre-Bronze Layer:** Assert exact source-shaped raw admissions, dunder metadata columns (`__file_name__`, `__folder_path__`, `__source_file_id__`, `__ingested_at__`), and dry-run non-mutation;
  - **Bronze Layer:** Assert Gate 1 & Gate 2 Pandera schema validations, dunder provenance admission (`__artifact_id__`), atomic delta replacement, and artifact-level deduplication;
  - **Silver Layer:** Assert transformed and normalized financial facts across household transactions, asset groupings, currencies, investment orders, trade executions, lot allocations, realized capital gains, and tax events;
  - **Gold Layer:** Assert final analytical marts across Household Budgeting, Investment Portfolio Summary, Tax Year Summary, Tax Income Breakdown, Tax Reconciliation, Wealth Net Worth curves, FIRE Milestones, and Monte Carlo stochastic survival distributions.

## 10. Explicit non-goals

Do not:
- add new architecture to make the acceptance demo prettier;
- build companion applications;
- migrate documentation to a portal;
- add new financial features;
- change formulas;
- declare success with waived mandatory gates;
- create v11 as a ceremonial finish line.

## 11. Completion checklist

- [ ] Clean installation works.
- [ ] Public config v1 is sufficient.
- [ ] Diagnostics/dry run work.
- [ ] First committed run correct.
- [ ] Incremental rerun correct.
- [ ] Evidence change correct.
- [ ] Failure/remediation atomic and actionable.
- [ ] Capability switch correct.
- [ ] Backup/restore correct.
- [ ] Existing pre-refactor state upgrades correctly.
- [ ] Desktop/presentation compatibility smoke passes (live per-file progress loader, modern Medallion stages, forensic logging).
- [ ] JSONL lineage reconstructable.
- [ ] Multiprocessing/worker lineage reconstructable.
- [ ] Performance gates pass.
- [ ] Legacy architecture absent (zero references to column_master, ExtractionResult, or legacy folder topology; exactly 19 Bronze contracts verified; loader.py hardcoded baseline deleted).
- [ ] Shan oracle green.
- [ ] External golden fixtures green.
- [ ] Generic Golden User end-to-end acceptance green (source-agnostic proof from Ingestion to Monte Carlo on clean install).
- [ ] All 50 phase contracts closed.
- [ ] No unresolved core requirement deferred.

## 12. Commit boundary

```text
chore(release): certify grand refactor completion
```

## 13. Final handoff and completion contract

The Grand Refactor is complete when every checklist item above is green.

The resulting PFETL core is:
- source-configurable;
- provider-aware but canonical-model provider-neutral;
- Raw -> Pre-Bronze -> canonical Bronze -> Silver -> Gold;
- Pandera-validated at source and canonical admission boundaries;
- deterministic and dataset-specific in identity;
- capability-composable;
- plan-aware in physical analytical state;
- recoverable/replay-safe;
- fully observable through the existing one-emitter/three-consumer architecture;
- diagnosable through PFETL-native CLI;
- usable by supported external source topologies without source-code changes.

Future companion Config Studio, documentation portal and analytics application remain separate programs. A future v11 requires a new justified breaking boundary.

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
