# Phase 045 - Core Configuration Diagnostics CLI

**Target release:** v10.3.0  
**Expected effort:** 3-4 hours  
**Previous:** Phase 044  
**Next:** Phase 046  
**Risk:** Medium-High

## 1. Outcome

Add PFETL-native CLI diagnostics for configuration validation, source reachability/selectors, mapping/normalization preview, identity preview/collision diagnostics, capability/active-contract preview, and an admission dry run.

All commands must call existing application services. The CLI is a presentation surface, not a second implementation of planning/validation.

## 2. Why this phase exists

The generalized core is technically configurable, but external usability requires actionable diagnostics before a full financial run. This is deliberately inside PFETL, not Config Studio. A future companion UI can call the same contracts/services.

## 3. Inherited repository state

Phase 044 guarantees deterministic configuration/replay semantics. All underlying services already exist:
- SourceConfiguration loader/validation;
- Source/Provider planners;
- mapping/normalization compiler;
- identity planner;
- Pandera validation;
- ExecutionPlan;
- provenance/recovery.

CLI must compose these, not duplicate them.

## 4. Current codebase anchors

Inspect current presentation/CLI structure and command conventions after v10:
- existing run/snapshot/restore commands;
- error rendering;
- bootstrap/container/facade;
- application-facing service APIs.

Do not import infrastructure repositories directly into command handlers if facade/application service exists.

## 5. Exact target state after this phase

Provide commands/subcommands conceptually:

```text
pfetl validate-config
pfetl check-sources
pfetl preview-mapping <dataset>
pfetl preview-identity <dataset>
pfetl preview-plan
pfetl dry-run-admission [dataset/all]
```

Exact command naming should follow current CLI conventions.

Outputs are human-readable and optionally structured only if existing CLI already supports it.

`dry-run-admission` executes discovery/provider read/source validation/normalization/identity/Bronze validation without publishing financial Silver/Gold and without mutating production warehouse state. Use transaction rollback/temp context where needed.

## 6. Detailed implementation sequence

### Step 1 - Define application diagnostic facade and CLI tri-config support
Expose cohesive methods returning typed results. CLI should not orchestrate Pandera/Polars/Control Plane internals.
Add full support for tri-configuration CLI arguments across launcher and diagnostic subcommands:
- `--config <path>`: Execution and storage settings (default `config.toml`);
- `--rules <path>`: Financial policies and tax rules (default `rules.toml`);
- `--sources <path>`: Evidence source topology, selectors, and mappings (default `sources.toml`).

### Step 2 - `validate-config` & Capability-Scoped Financial Rules Validation
Validate the full tri-configuration triumvirate (`settings.toml`, `sources.toml`, `financial_rules.toml`) without source I/O:
1. **Settings & Plan Validation:** Validate `Settings` (paths, database names, retention) and resolve active `CapabilityId` set from `settings.capabilities`.
2. **Sources Validation:** Validate `SourceConfiguration` schemas, dataset bindings, field types, and normalizations against active capabilities.
3. **Capability-Scoped Financial Rules Contracts & Semantic Validation:**
   - Partition `FinancialRules` parameters along the Capability Graph (`HOUSEHOLD_CORE`, `WEALTH`, `INVESTMENT_ACCOUNTING`, `BENCHMARK_ENRICHMENT`, `FOREIGN_ASSET_ENRICHMENT`, `TAX`, `FIRE`).
   - **Logical TOML Heading Restructuring by Capability:**
     Restructure `financial_rules.toml` so top-level headings map cleanly to capability namespaces (`[household]`, `[wealth]`, `[investments]`, `[benchmark]`, `[tax]`, `[fire]`), replacing disparate legacy root keys (`[income]`, `[expense]`, `[assets]`, `[assumptions]`) with an intuitive, unified heading hierarchy that aligns the configuration file directly with the capability model contracts.
   - **Plan-Driven Scoped Validation:**
     - If a capability is disabled (e.g. `TAX` or `FIRE` inactive in a household-only plan), its financial rules section is completely optional or omitted; a minimal 25-line rules file validates cleanly without errors.
     - If a capability is enabled, its corresponding financial rules contract is strictly validated.
   - **Concrete Mathematical & Probability Invariants:**
     - Probabilities strictly bounded: $0.0 \le p \le 1.0$ (Merton jump probability, human capital shock probability).
     - Stochastic matrix normalization: Markov transition matrix rows must each sum strictly to $1.0$.
     - Numerical constraints: Monte Carlo iterations $\ge 100$, annual volatility $> 0.0$, SWR multiplier $> 0.0$, positive maximum months horizon.
     - Tax schedule monotonicity: Tax slabs, indexation dates, and capital gains holding period thresholds must be strictly positive and monotonic.
     - Disjoint classification invariant: Enforce zero overlap between contradictory category/subcategory classifications (e.g. an account UID cannot be configured as both a liquid cash pool and an illiquid asset; an expense cannot be both core essential and discretionary luxury).

### Step 3 - source reachability/selector checks
Verify configured file/DB/provider reachability and table/sheet selectors. Do not mutate registry merely to check.

### Step 4 - mapping preview
Show source fields -> canonical fields and ordered normalization operations for selected DatasetId. No sensitive row dump by default.

### Step 5 - identity preview
Show strategy, identity fields, bounded sample IDs and collision diagnostics. Clearly distinguish trusted source identity vs derived identity.

### Step 6 - capability/contract preview
Show requested/resolved capabilities, required source/Bronze datasets and active Silver/Gold outputs.

### Step 7 - admission dry run
Use a rollback-only or isolated execution context. Run through Bronze validation but do not commit production Pre-Bronze/Bronze/Silver/Gold. Provider network behavior should respect existing cache/policy and require explicit confirmation only if current CLI convention demands it.

### Step 8 - Error UX
Render typed remediation from existing validation/planner errors. Do not catch everything into generic "invalid config."

### Step 9 - Architecture guard
CLI/presentation cannot import Pandera or implement mapping/identity algorithms.

### Step 10 - Documentation/help text
Command `--help` states side effects precisely, especially dry run.

### Step 11 - Diagnostic Telemetry & Developer Debug Logging Alignment
Ensure diagnostic commands produce rich, structured observability for both human operators and forensic tooling:
- Surface actionable remediation hints, field mapping diffs, and identity strategies cleanly in CLI narrative tables without cryptic stack traces.
- Expose verbose developer debug logging (`outputs/logs/`) capturing source schema inference, Pandera constraint evaluations, selector path resolution, and artifact hashes.
- Standardize dry-run admission telemetry so UI progress sinks display live per-file admission checks with progress percentages.

## 7. Files and symbols in scope

Modify:
- CLI/presentation command modules;
- application diagnostic facade/service;
- bootstrap wiring;
- tests/help snapshots if used.

Reuse existing core services. Do not create companion app code.

## 8. Cross-cutting impacts

**Persistence:** validation/preview commands no mutation. Dry-run admission must rollback/isolate all warehouse/Control Plane changes or use explicit non-mutating planner/provider paths.

**Identity:** preview does not persist generated IDs.

**Observability:** diagnostics may emit command-level events if current CLI does; dry run clearly tagged so it cannot be confused with committed financial run.

**Performance:** previews bounded; no full-history print.

**Security/privacy:** do not print raw sensitive rows/absolute secrets by default.

## 9. Tests and verification

Required:
- valid/invalid config CLI tests;
- unreachable source;
- invalid Excel sheet/SQLite table;
- mapping preview exactness;
- identity preview stable sample + collision case;
- plan preview active contract set;
- dry run leaves production DB/Control Plane unchanged;
- dry run catches source and Bronze validation failures;
- CLI imports no Pandera/financial implementation internals;
- full normal pipeline unaffected.

## 10. Explicit non-goals

Do not:
- build Config Studio;
- add interactive GUI/wizard;
- edit configuration automatically;
- duplicate validators in CLI;
- publish financial outputs during dry run.

## 11. Completion checklist

- [ ] Config validation command works.
- [ ] Source/selector diagnostics work.
- [ ] Mapping preview works.
- [ ] Identity preview works.
- [ ] Plan/contract preview works.
- [ ] Admission dry run is non-mutating.
- [ ] Errors are actionable.
- [ ] Diagnostic telemetry and developer forensic logging verified.
- [ ] CLI reuses application services.
- [ ] No companion application scope leaked in.

## 12. Commit boundary

```text
feat(cli): add configuration diagnostics
```

## 13. Handoff to Phase 046

Phase 046 may assume a new user can diagnose configuration and admission from PFETL itself. The final batch uses those exact interfaces to certify multiple external household/investment topologies, performance, public configuration stability and a clean-install end-to-end acceptance journey.

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
