# Phase 060 - Final PFETL Core Acceptance

**Target release:** v10.6.1  
**Expected effort:** certification phase; finish only when every mandatory gate is green  
**Previous:** Phase 059  
**Next:** Grand Refactor complete; ecosystem extraction/readiness archaeology may begin separately  
**Risk:** Critical

## 1. Outcome

Execute the final acceptance of the complete 60-phase PFETL Core from a clean installation and from a representative v10.3.0 operational state.

The acceptance must prove the entire final architecture as one lifecycle:

```text
SourceConfiguration v1 + FinancialRules + runtime Settings
        -> Capability / ExecutionPlan
        -> SourceBindingPlan
        -> CanonicalSatisfiabilityPlanner
        -> Raw / Control Plane
        -> Gate 1 / binding-keyed Pre-Bronze
        -> semantic interpretation / CanonicalRoute
        -> CanonicalProductionPlan
        -> canonical identity / Gate 2 / integrity
        -> Bronze DatasetContracts
        -> Silver financial state
        -> Gold analytical state
        -> Meta/effective contract catalog
```

If this phase passes, the PFETL Core Grand Refactor is complete. Future `pfetl-contracts`, Config Studio, Analytics Studio and documentation portal work become separate ecosystem programs rather than hidden continuation phases.

## 2. Why this phase exists

The preceding phases prove individual architecture, migration, external topology, performance and contract concerns. Final acceptance asks a harsher product question:

> Can a supported user install PFETL, describe evidence whose topology differs from Shan's, prove the plan before execution, run deterministically, change evidence/configuration/capabilities, recover from failure, restore state, inspect lineage and obtain contract-correct financial outputs without editing PFETL source?

The answer must be demonstrated through public interfaces and frozen contracts, not inferred from unit-test count.

## 3. Inherited repository state

Phase 059 guarantees:

- SourceConfiguration v1 is frozen on the SourceBinding/route/production model;
- every Bronze/Silver/Gold canonical DatasetId has one authoritative DatasetContract;
- Gate-2 validation and physical DDL derive from unified contracts;
- base versus effective contract semantics are explicit;
- external household/investment topologies are golden fixtures;
- performance gates are accepted;
- duplicate schema authority and planned transitional debt are removed;
- no migration-only runtime path remains.

The post-059 repository is the implementation authority. Earlier releases remain regression/upgrade oracles only.

## 4. Current codebase anchors

Acceptance uses only supported/public surfaces:

- package install/import and CLI help;
- SourceConfiguration v1 and machine-readable schema/export;
- diagnostic commands/services from Phase 045 updated through 051/059;
- normal pipeline/application facade;
- backup/restore/recovery interfaces;
- Desktop presentation smoke where currently supported;
- JSONL/observability outputs and Control Plane;
- contract/effective-contract/Meta catalog introspection;
- golden Shan and external static evidence fixtures.

Do not call internal functions manually to rescue an acceptance scenario.

## 5. Exact target state after this phase

A clean supported user can complete:

```text
install
 -> launch modernized Desktop GUI or CLI
 -> author/select config triad (settings, rules, sources)
 -> validate-config
 -> check-sources
 -> preview-mapping / identity / satisfiability
 -> dry-run-admission
 -> first committed run (with live telemetry streaming)
 -> inspect active canonical/effective contracts & capabilities
 -> unchanged rerun
 -> evidence-change rerun
 -> semantic-mapping change/replay
 -> identity-policy change/rebuild
 -> capability disable/re-enable (via UI toggle or CLI flag)
 -> controlled failure/remediation
 -> backup/restore (GUI snapshot/restore modal or CLI)
 -> observability reconstruction
```

PFETL must also upgrade a representative v10.3.0 operational state by rebuilding the intentionally changed Pre-Bronze/canonical Bronze layers and converge to the same financial result as a clean final-version run.

## 6. Detailed implementation sequence

### Step 1 - Build a release-candidate acceptance matrix

Define the exact scenarios and expected outputs before execution:

- Shan full configuration;
- external household topology;
- external domestic investment topology;
- external foreign/multi-broker topology;
- reduced capability plan;
- failure/remediation case;
- v10.3.0 upgrade case.

Record which performance/contract/financial oracle applies to each.

### Step 2 - Clean install/import/CLI smoke

Install from the release-candidate packaging state into a clean environment/workspace. Verify import, CLI help, schema export and public configuration examples without relying on repository-relative source execution.

### Step 3 - Validate frozen configuration contract

Load golden SourceConfiguration v1 examples and machine-readable schema. Verify deterministic canonical serialization/fingerprint and actionable failure for unsupported schema versions/invalid discriminators.

### Step 4 - Run diagnostics and satisfiability preview

For each representative configuration, verify:

- source reachability/selectors;
- SourceBinding plans;
- semantic mapping/identity preview;
- canonical producer resolution;
- capability dependencies;
- missing/ambiguous producer diagnostics;
- effective contract summary.

### Step 5 - Non-mutating admission dry run

Prove Gate 1, semantic routing/canonical candidate preparation and Gate 2 admission checks through the supported dry-run path without creating committed production state.

### Step 6 - First committed clean run

Execute a representative external scenario. Assert:

- expected Raw/Control Plane artifacts;
- binding-keyed Pre-Bronze;
- canonical Bronze datasets;
- canonical integrity;
- active Silver/Gold only;
- expected financial values/identities;
- Meta/effective contract catalog.

### Step 7 - Unchanged rerun

Verify no duplicate canonical/financial rows, stable identities, correct cache/change-detection behavior, stable plan/contract fingerprints and Phase-058 cached performance envelope.

### Step 8 - Evidence change

Modify one supported source artifact/record. Verify source/binding change detection, canonical dependency closure, replay and exact downstream changes while unrelated state remains stable.

### Step 9 - Semantic mapping change

Change one bounded source semantic mapping without changing financial methodology. Verify configuration/route fingerprint change triggers the affected canonical rebuild and corresponding downstream replay.

### Step 10 - Identity strategy change

Change an allowed Bronze identity strategy in a fixture where the contract permits alternatives. Verify the replay classifier requires identity rebuild rather than mixing generations. Confirm protected downstream financial IDs behave according to unchanged canonical financial evidence after rebuild.

### Step 11 - Capability disable/re-enable

Disable a supported optional capability such as benchmark, Tax or FIRE according to the scenario. Verify:

- execution work is skipped at source-of-calculation;
- effective contracts/physical analytical tables prune correctly;
- unrelated financial outputs remain unchanged;
- re-enable recreates required state without stale-table contamination.

### Step 12 - Controlled failure and remediation

Exercise at least one failure each at meaningful boundaries where existing tests support it:

- Gate 1/source schema;
- semantic/unmapped enum or route;
- canonical identity/Gate 2/integrity;
- analytical publication/recovery.

Verify atomic state, actionable diagnostics and successful rerun after correction.

### Step 13 - Backup/restore

Backup generalized state including Control Plane/config fingerprints and warehouse layers. Restore into a clean target, verify contract/catalog state and perform the next incremental run successfully.

### Step 14 - v10.3.0 operational-state upgrade

Start from a representative v10.3.0-style state/config. Apply the supported upgrade/rebuild path:

- preserve Raw/Control Plane evidence where valid;
- migrate/translate supported configuration state;
- rebuild binding-keyed Pre-Bronze;
- rebuild canonical Bronze under new contracts;
- regenerate Silver/Gold.

Compare final protected IDs and financial outputs against a clean v10.6.1 run from the same evidence.

### Step 15 - Contract-to-warehouse parity certification

For every active Bronze/Silver/Gold dataset in representative capability plans:

```text
base DatasetContract
 + ExecutionPlan
 = EffectiveDatasetContract
 = physical warehouse schema / Meta catalog
```

Verify inactive capability-owned datasets/columns are absent exactly as specified.

### Step 16 - Shan financial oracle

Run Shan's full accepted evidence. Compare protected IDs and financially meaningful outputs across household, investments, FIFO, realized gains, reconciliation, Tax, wealth, FIRE and deterministic simulations where applicable.

Any unexplained paise-level difference blocks completion.

### Step 17 - External topology golden matrix

Re-run 056/057 household/domestic/foreign/multi-broker scenarios without production-code changes. Confirm source-semantic/topology agnosticism remains intact after contract freeze.

### Step 18 - Observability forensic reconstruction

Using JSONL plus Control Plane, reconstruct at least one committed run through:

```text
run/config fingerprint
 -> execution/canonical production plans
 -> SourceId / SourceBindingId / artifact or provider request
 -> Gate 1 / Pre-Bronze
 -> route / semantic interpretation
 -> canonical DatasetId / Gate 2 / integrity
 -> financial engines
 -> Silver/Gold/Meta
 -> commit state
```

Certify multiprocessing worker lineage, including the ISIN worker path where applicable, under the one-emitter/existing-consumer architecture.

### Step 19 - Desktop GUI & Terminal CLI Modernization and Acceptance

Modernize and certify the built-in Tkinter Desktop UI (`presentation.desktop`) and Terminal CLI (`presentation.cli`) so that all PFETL Core user surfaces are clean, modern, and fully integrated with the final generalized engine:

1. **Desktop Tkinter (`presentation.desktop`) Modernization:**
   - **Configuration Triad Support:** Upgrade `UnifiedETLTab` to accept the full configuration triad (`settings.toml`, `rules.toml`, and `sources.toml`) with persistent recent paths and automatic cross-config path detection.
   - **Interactive Diagnostics Suite:** Integrate native CTk buttons and status cards for `Validate Config` (`engine.validate_all_configs`), `Check Sources` (`engine.check_sources`), `Preview Plan / Satisfiability` (`engine.preview_plan`), and `Dry-Run Admission` (`engine.dry_run_admission`).
   - **Active Capabilities Viewer & Toggles:** Display the active capability set in the UI, allowing interactive toggling of optional capabilities (e.g. Benchmark, Foreign Assets, Tax, FIRE, Simulation) before running.
   - **Live Telemetry & Observability:** Ensure `desktop_sink.py` renders real-time pipeline phase transitions, progress bars, and structured forensic diagnostics directly in the console text box without UI freezing or multiprocessing deadlocks.
   - **Multi-Layer Backup/Restore:** Upgrade database snapshot and restore dialogs to safely handle both DuckDB analytical warehouse and SQLite Control Plane transactional state (`ActiveDatabaseState`).

2. **Terminal CLI (`presentation.cli`) Polish & Modernization:**
   - **Uniform Triad Options:** Ensure all CLI commands (`run`, `validate-config`, `check-sources`, `preview-plan`, `preview-mapping`, `preview-identity`, `dry-run-admission`, `snapshot`, `restore`) uniformly accept `--config`, `--rules`, and `--sources`.
   - **Headless / Cron Mode:** Ensure `pfetl run --cron` executes cleanly in unattended environments with zero interactive prompts, clean Rich narrative streaming, and deterministic exit codes (`0` = success, `1` = validation error, `2` = pipeline error, `3` = recovery required).
   - **Capability Overrides:** Allow CLI capability filtering (`--capabilities`) and pre-flight bypass (`--skip-preflight`) for scripted workflows.

3. **Strict Architecture Enforcement:**
   - Presentation layers must strictly consume `PersonalFinanceEngine` and application service contracts; no direct imports of DuckDB, SQLite, or Pandera internals are permitted in presentation code.

### Step 20 - Performance gate

Apply Phase-058 full/cached/external thresholds. Investigate regressions rather than waiving them. No last-minute optimization may weaken contract or validation guarantees.

### Step 21 - Legacy absence audit

Search/runtime tests must prove absence of retired architecture, including:

- SourceDatasetConfig->DatasetId runtime coupling;
- DatasetId-keyed Pre-Bronze;
- source-container Bronze DatasetIds;
- vendor semantic codes in Silver/domain logic;
- compatibility compiler;
- dynamic Bronze schema evolution;
- filename/folder topology identity;
- `COMMON_COLUMN_MASTER` authority;
- duplicated canonical schema authorities;
- deprecated Settings source-path runtime ownership.

### Step 22 - Final 60-phase closure audit

Verify every phase completion contract is either satisfied or explicitly superseded by stricter later behavior. Update the program tracker only after the final acceptance evidence is green.

If a defect exposes a missing architectural prerequisite, fix the owning architecture and re-run affected acceptance gates. Do not waive the defect or invent Phase 061 merely to avoid repairing the program.

## 7. Files and symbols in scope

Modify only:

- release/acceptance tests and fixtures;
- defects discovered by acceptance;
- final phase/progress metadata;
- architecture guards required to permanently capture a discovered regression.

If a defect changes an already frozen public contract, stop and assess whether Phase 059 was actually complete before altering it.

## 8. Cross-cutting impacts

**Financial correctness:** exact oracle is mandatory; no formula changes.

**Configuration:** only frozen SourceConfiguration v1/public interfaces are used.

**Persistence/recovery:** clean, incremental, rebuild, rollback, backup/restore and upgrade paths are all certified.

**Contracts/warehouse:** base/effective/physical parity becomes a release gate.

**Observability:** one emitter and existing downstream consumers remain intact, including multiprocessing lineage.

**Performance:** Phase-058 thresholds are release criteria, not advisory notes.

**Ecosystem:** after completion, contract extraction/readiness can be assessed as a new program; it is not Phase 061 by default.

## 9. Tests and verification

Final mandatory matrix:

### Packaging/public surface
- clean install/import/CLI help;
- SourceConfiguration v1 schema/export;
- no internal API required for normal acceptance.

### Planning/diagnostics
- binding/route/producer/capability preview;
- satisfiable and unsatisfied plans;
- dry-run non-mutating.

### Canonical lifecycle
- Raw/Control Plane -> binding Pre-Bronze -> semantic routes -> canonical production -> Gate 2 -> integrity;
- empty/missing/disabled/malformed distinctions;
- no stale state.

### Financial lifecycle
- household/investment/Tax/wealth/FIRE representative runs;
- exact protected IDs;
- paise-level financial equivalence.

### Replay/recovery
- unchanged rerun;
- evidence change;
- semantic mapping change;
- identity rebuild;
- controlled failure/remediation;
- backup/restore;
- v10.3.0 upgrade convergence.

### Capability/warehouse
- disable/re-enable;
- source-of-calculation gating;
- base/effective/physical contract parity;
- stale inactive table cleanup.

### External usability
- household N:M topology;
- domestic investment;
- foreign/multi-broker investment;
- no source-code edits.

### Observability/presentation
- end-to-end JSONL reconstruction;
- multiprocessing lineage;
- Desktop run/snapshot/restore smoke.

### Performance/legacy
- Phase-058 gates;
- zero prohibited legacy architecture references.

## 10. Explicit non-goals

Do not:

- add new finance features;
- redesign contracts during final acceptance for aesthetics;
- build Config Studio, Analytics Studio or documentation portal;
- extract `pfetl-contracts` yet;
- create a ceremonial v11/Phase 061;
- waive mandatory gates to declare the program complete.

## 11. Completion checklist

- [ ] Clean installation can validate, preview and run a frozen SourceConfiguration v1 using only supported public interfaces.
- [ ] First run, unchanged rerun, evidence-change replay, semantic-mapping replay and identity-rebuild scenarios all converge without stale or duplicate state.
- [ ] Capability disable/re-enable changes only owned calculations/effective contracts and preserves unrelated financial outputs.
- [ ] Controlled failures at source/canonical/publication boundaries are atomic, diagnosable and recoverable; backup/restore resumes correctly.
- [ ] Representative v10.3.0 operational state upgrades/rebuilds to exactly the same final financial state as a clean final-version run.
- [ ] Every active Bronze/Silver/Gold physical schema and Meta entry matches its capability-derived EffectiveDatasetContract.
- [ ] Shan's protected IDs and financially meaningful outputs remain exact, including Tax/reconciliation and deterministic simulation semantics where applicable.
- [ ] External household and investment golden topologies still run without source-code changes after the contract freeze.
- [ ] End-to-end JSONL/Control Plane lineage and multiprocessing context are reconstructable through the final canonical architecture.
- [ ] Desktop GUI (Tkinter) and Terminal CLI modernization and acceptance: full configuration triad selection, interactive diagnostics (validate, check-sources, preview-plan, dry-run), capability toggles, live telemetry streaming, and multi-layer backup/restore verified.
- [ ] Phase-058 performance thresholds and zero-legacy architecture audits are green.
- [ ] All 60 phase contracts are closed with no unresolved Core requirement deferred to an invented continuation phase.

## 12. Commit boundary

Use `pfetl-conventional-commits`. Acceptance-discovered fixes, permanent regression tests and final release/progress metadata should be grouped semantically; let the commit skill determine staging and messages. Do not hide multiple unrelated acceptance defects inside one release commit.

## 13. Final handoff and completion contract

When every mandatory gate is green, the PFETL Core Grand Refactor is complete.

The resulting Core is:

- source-binding configurable rather than source-topology specific;
- bounded in source semantic interpretation;
- N:M in canonical production;
- satisfiability planned before financial execution;
- canonical at Bronze and source-independent in Silver;
- financially deterministic in protected investment/reconciliation/Tax identity;
- capability-composable and physically plan-aware;
- contract-driven across Bronze/Silver/Gold;
- replay/recovery/backup safe;
- observable through one emitter and existing consumers;
- externally certifiable without source-code edits;
- extraction-ready for a future dependency-light `pfetl-contracts` program.

The next activity is **ecosystem readiness archaeology**, not an automatic Phase 061. If the frozen internal contract boundary is extraction-ready, `pfetl-contracts` begins as its own Ecosystem Phase 001.

## Phase completion record

```text
Phase:
Target release:
Clean install:
Public config/diagnostics:
Canonical lifecycle:
Protected IDs / financial oracle:
Replay/recovery/backup:
v10.3.0 upgrade convergence:
Contract/physical parity:
External topology matrix:
Observability/multiprocessing:
Desktop smoke:
Performance gates:
Legacy absence audit:
Files changed:
Financial formulas changed: NO
All 60 phase contracts closed:
Exit assertions green:
Commits:
```

A phase is incomplete if any required exit assertion is false.
