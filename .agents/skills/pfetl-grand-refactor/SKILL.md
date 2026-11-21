---
name: pfetl-grand-refactor
description: >-
  Use this skill when planning, implementing, reviewing, verifying, or preparing commits for any PFETL Grand Refactor phase (001-060), especially work involving SourceBindingId, Pre-Bronze, semantic interpretation, canonical production, satisfiability planning, Bronze/Silver/Gold contracts, capability composition, replay/recovery, external topology certification, or final contract freeze.
---

# PFETL Grand Refactor Execution Governance

Use this Skill to execute the Grand Refactor as one continuous phase-to-phase migration. The phase file is the implementation authority; this Skill supplies the operating discipline and permanent invariants.

## 1. Load Authorities in Order

Before changing code for a phase, read:

1. `planning/grand-refactor/phases/<active-phase>-*.md`
2. `planning/grand-refactor/ARCHITECTURE.md`
3. `planning/grand-refactor/README.md`
4. root `AGENTS.md` and any nested `AGENTS.md` for touched workspaces

Treat the previous completed phase handoff as inherited-state authority. v9.5.3 remains the historical financial/regression oracle; Phase 045 / v10.3.0 is the implementation baseline inherited by the post-045 canonicalization program.

If implementation evidence contradicts the phase, stop and amend the owning phase/architecture before silently redesigning the system.

## 2. Execute One Atomic Phase

For the active phase:

1. Inspect the exact current symbols/files named by the phase.
2. Confirm the inherited handoff actually exists.
3. Implement only the phase-owned architectural outcome.
4. Add/update focused tests and architecture guards as the phase requires.
5. Run the phase-specific verification matrix.
6. Run repository quality gates required by the phase/release boundary.
7. Verify every unique completion-checklist assertion.
8. Use `pfetl-conventional-commits` to preview semantically coherent commit groups/messages.
9. Record the phase completion evidence only after the repository is green.
10. Stop. Do not pull the next phase forward.

A phase may exceed the nominal 3-4 hour sprint if cutting it would leave an unsafe half-state.

## 3. Permanent Financial Invariant

For unchanged methodology:

```text
same evidence
+ same FinancialRules
+ same enabled capabilities
+ same market evidence
= same financial truth
```

Protected deterministic identity families include:

- PURCHASE
- SALE
- LOT
- REALIZED
- RECON_LOT_GROUP
- RECON_GROUP
- RECON_EVENT
- TAX

Any unexplained protected-ID or paise-level financial drift stops the phase unless the phase explicitly owns an intentional representation-only change.

Never change FIFO, reconciliation, Tax, XIRR, Wealth, FIRE or other financial methodology merely to simplify schema/architecture work.

## 4. Source and Canonical Identity Rules

Keep these concepts separate:

```text
SourceId
  physical evidence container/provider configuration

SourceBindingId
  configured physical tabular stream

CanonicalRouteId
  route from one binding into one canonical DatasetId

DatasetId
  PFETL canonical financial evidence/state identity
```

After the owning cutovers:

- Pre-Bronze is keyed by `SourceBindingId`, not canonical `DatasetId`.
- One binding may emit zero-to-many canonical routes/fragments.
- One canonical DatasetId may consume zero-to-many routes/providers/registered recipes.
- Multi-source composition is explicit; declaration/filesystem order never selects financial truth.
- Source-row identity and canonical Bronze identity are separate.

Do not reintroduce `SourceDatasetConfig.dataset_id` coupling once Phase 055 removes the compatibility path.

## 5. Layer Ownership

```text
Raw / Control Plane
  exact evidence + operational provenance

Pre-Bronze
  source-shaped tabular evidence, binding-keyed

Semantic interpretation
  bounded row-local source encoding -> canonical evidence meaning

Bronze
  PFETL canonical financial evidence

Silver
  PFETL reconstructed financial state / methodology

Gold
  PFETL analytical and decision surfaces
```

Silver/domain logic must not interpret source deletion flags, numeric source transaction/category codes, broker action strings, placeholder rows or provider topology after their canonical cutover.

## 6. Bounded Semantic Interpretation

Configuration may express deterministic bounded semantics such as:

- existing normalization rules;
- `MapValues`;
- `Constant`;
- `IncludeWhen`;
- `ExcludeWhen`;
- equality/membership/null/empty predicates.

Do not add arbitrary Python/eval, SQL, user-authored Polars expressions, joins, aggregation, windows or financial formulas to source configuration.

Unknown canonical-enum values fail by default. Source deletion/placeholder semantics are resolved before Bronze unless independently canonical.

## 7. Canonical Production Rules

Canonical production may:

- consume canonical fragments;
- execute `DIRECT` or explicit `UNION` source assembly;
- consume supported provider evidence;
- execute registered/versioned PFETL-owned canonical derivation recipes;
- establish canonical identity after assembly;
- enforce duplicate/grain rules;
- run Gate 2 on the final assembled dataset;
- run cross-dataset canonical integrity before Silver.

It must not perform downstream financial calculations.

Default duplicate behavior is fail. Do not add ordering-dependent keep-first/keep-last semantics to financial evidence.

## 8. Satisfiability Planning Rules

Keep capability planning and evidence producibility separate:

- `ExecutionPlan` says what capabilities/canonical evidence are required.
- `CanonicalSatisfiabilityPlanner` resolves how the current configuration can produce them.

The planner must deterministically reject:

- missing required producers;
- multiple unresolved producers;
- invalid explicit producer selections;
- derived dependency cycles.

Existing/stale Bronze cannot satisfy missing current configuration.

## 9. DatasetContract Freeze Rules

By Phase 059:

- every Bronze/Silver/Gold DatasetId has exactly one authoritative DatasetContract;
- Pre-Bronze remains dynamic/source-configured;
- base DatasetContracts own complete schema, logical types, nullability, grain, keys, references, capability ownership, schema version and fingerprint;
- active `ExecutionPlan` derives effective contracts without mutating base contracts;
- DuckDB DDL, Bronze Pandera Gate-2 schema, capability-column indexes and machine-readable exports are generated adapters, not independent schema authorities;
- extraction-ready contract modules remain free of Polars/Pandera/DuckDB/SQLite/provider behavior.

Do not extract `pfetl-contracts` during the Grand Refactor. Phase 059 prepares the boundary; ecosystem extraction happens only after Phase 060 acceptance/readiness archaeology.

## 10. Recovery, Replay and Observability

Preserve existing persistence truth:

1. DuckDB commits first.
2. SQLite Control Plane commits second.
3. Split failure yields `RECOVERY_REQUIRED`.

Replay becomes binding/canonical-production aware. A changed binding/route/semantic rule must invalidate its affected canonical DatasetIds and downstream dependency closure. Identity-strategy changes that would mix generations require explicit rebuild semantics.

Observability remains one emitter with existing downstream consumers. Add only bounded source-binding/canonical context. Preserve multiprocessing run/parent-operation lineage.

## 11. Phase Families 046-060

Use the phase files for exact work, but retain this program intent:

- **046-051:** build SourceBinding/semantic-route/canonical-production/satisfiability architecture while preserving financial behavior.
- **052-055:** migrate Shan household then investment/reference/provider evidence and delete the migration-only legacy architecture.
- **056-057:** certify truly different external topologies and retire unused columns through consumer archaeology. These phases certify; they do not invent a parallel architecture.
- **058:** profile and optimize the final architecture only.
- **059:** freeze the complete PFETL contract universe and eliminate duplicate schema authority.
- **060:** final clean-install + v10.3.0-upgrade + financial/recovery/observability/warehouse-parity acceptance.

Phase 055 must hand Phase 056 exactly one production architecture.

## 12. Testing Discipline

Use the active phase test matrix. Add architecture guards when ownership becomes permanent so later phases cannot regress it.

Typical local sequence:

```powershell
uv run poe audit:fast
uv run pytest tests/architecture/test_boundaries.py
uv run pytest <focused tests>
```

Run full quality/recovery/real-data/performance gates when the phase or release requires them. If the current environment cannot execute a mandatory runtime gate, record it as unverified rather than claiming success.

## 13. Commit Discipline

Do not hard-code file-per-commit or one-phase-one-commit rules in implementation plans. Use `pfetl-conventional-commits` to preview semantic grouping and Commitlint-compliant messages. Planning docs define coherent change boundaries; the commit Skill owns staging and message mechanics.
