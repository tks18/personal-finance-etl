---
name: pfetl-pipeline-diagnostics
description: >-
  Use this skill when validating PFETL configuration, running or profiling the headless pipeline, troubleshooting SourceBinding/Pre-Bronze/canonical-production failures, inspecting DuckDB and SQLite state, investigating replay/recovery, verifying protected deterministic IDs, or diagnosing financial output differences.
---

# PFETL Pipeline Diagnostics & Headless Troubleshooting

Use the application diagnostics and current SourceConfiguration model first. Do not troubleshoot the post-Phase-055 architecture through retired Settings source paths, source-category assumptions or source-shaped Bronze tables.

## 1. Start With Non-Mutating Diagnostics

Prefer PFETL-native diagnostic services/CLI before running a full pipeline:

```text
validate-config
check-sources
preview-mapping
preview-identity
preview-plan
dry-run-admission
```

Exact command spelling is defined by the current CLI implementation. These diagnostics should explain configuration, source reachability, binding selectors, semantic mapping, identity and canonical satisfiability without writing production state.

When diagnosing post-Phase-051 plans, inspect both:

- `ExecutionPlan`: active financial capabilities and required canonical evidence;
- `CanonicalProductionPlan`: resolved producers/dependencies for canonical DatasetIds.

## 2. Configuration Mental Model

Keep these identities distinct:

```text
SourceId
  physical source/provider configuration

SourceBindingId
  physical tabular evidence stream

CanonicalRouteId
  bounded route into canonical evidence

DatasetId
  PFETL canonical financial dataset
```

Pre-Bronze is source-shaped and binding-keyed after the cutover. Bronze is canonical financial evidence.

Do not diagnose a missing canonical DatasetId by searching for a same-named source table/file. Ask which binding/route/provider/derived recipe is supposed to produce it.

## 3. Headless Execution

Use the repository fixture runner for isolated end-to-end runs:

```powershell
uv run python tests/fixtures/run_headless.py
```

Use static fixture SourceConfiguration/FinancialRules files under `tests/fixtures/` rather than obsolete source paths in runtime Settings.

For ad-hoc programmatic runs, prefer the application facade/composition root already used by tests instead of directly constructing deep infrastructure objects. Follow root/test `AGENTS.md` and current bootstrap APIs.

## 4. Diagnose the Data Spine in Order

When a run fails, locate the first broken boundary instead of inspecting Gold first.

```text
SourceConfiguration / capability selection
        -> SourceBindingPlan
        -> Raw / Control Plane sync
        -> Gate 1
        -> binding-keyed Pre-Bronze
        -> normalization / semantic interpretation
        -> CanonicalRoute / CanonicalFragment
        -> CanonicalProductionPlan
        -> canonical identity / duplicate / grain checks
        -> Gate 2
        -> CanonicalIntegrityValidator
        -> DatasetCollection
        -> Silver financial reconstruction
        -> Gold
```

### Source / Gate-1 failures

Check:

- source enabled state;
- `SourceBindingId` and selector;
- configured source schema/types;
- artifact/provider reachability;
- change-detection result;
- source-row identity/fingerprint where applicable.

### Semantic-route failures

Check:

- rule ordering;
- include/exclude predicates;
- unknown `MapValues` input;
- placeholder/deleted-row filtering;
- route target DatasetId;
- canonical projection completeness.

Unknown canonical-enum mappings should fail explicitly. Do not “fix” them by silently keeping arbitrary values.

### Canonical-production failures

Check:

- resolved producer kind (`SOURCE`, `PROVIDER`, `DERIVED`);
- explicit `DIRECT`/`UNION` inputs;
- aligned required/optional columns;
- canonical identity collisions;
- duplicate policy;
- grain/uniqueness;
- Gate-2 violations;
- canonical reference/integrity failures.

Do not use loose concatenation or keep-first/keep-last dedupe to mask evidence conflicts.

### Satisfiability failures

Classify separately from runtime data failures:

- missing required producer;
- ambiguous producers;
- invalid explicit producer selection;
- unsatisfied derived dependency;
- derived dependency cycle;
- optional evidence unavailable.

Stale Bronze from a prior run is not evidence that the current configuration is satisfiable.

## 5. Inspect DuckDB by Layer

The configured DuckDB warehouse contains:

- Pre-Bronze: source-shaped binding evidence;
- Bronze: canonical financial evidence;
- Silver: reconstructed financial state;
- Gold: analytical/decision surfaces;
- Meta: active contract/plan/catalog metadata.

Use read-only inspection for troubleshooting. Do not assume fixed Shan-specific physical table names; resolve active datasets/contracts from Meta/current plans where available.

Example generic inspection:

```powershell
uv run python -c "
import duckdb
from pathlib import Path

path = Path('outputs') / 'Shan_Finance.duckdb'
con = duckdb.connect(str(path), read_only=True)
for schema in ('pre_bronze', 'bronze', 'silver', 'gold', 'meta'):
    rows = con.execute(
        'SELECT table_name FROM information_schema.tables '
        'WHERE table_schema = ? ORDER BY table_name',
        [schema],
    ).fetchall()
    print(schema, rows)
con.close()
"
```

Use the actual configured warehouse path/name when different.

## 6. Inspect SQLite Control Plane / Raw Store

Use the Control Plane to answer operational questions:

- which run/artifact changed;
- hash/change-detection outcome;
- source/binding/configuration fingerprint;
- replay/rebuild requirement;
- commit/recovery state;
- retained provenance.

Do not infer canonical financial meaning from Control Plane source category/path metadata.

Prefer repository/application inspection APIs where available. Direct SQL is acceptable for read-only diagnosis only after confirming the current schema; do not rely on stale table/column names from this runbook.

## 7. Replay and Recovery

Commit order is invariant:

1. DuckDB first.
2. SQLite Control Plane second.
3. Failure between them -> `RECOVERY_REQUIRED`.

When configuration changes, distinguish:

- source/binding removed or disabled;
- binding re-enabled;
- mapping/semantic-route change;
- normalization change;
- selector metadata change;
- change-detection change;
- canonical identity strategy change.

A binding/semantic change should rebuild affected canonical DatasetIds plus downstream dependency closure. Identity-semantic changes may require a full identity rebuild rather than ordinary replay.

For recovery, use the current application recovery/backup services exposed by the composition root; do not hand-edit DuckDB/SQLite into agreement.

## 8. Protected Identity Verification

For migration or regression diagnosis, compare stable downstream identity families across equivalent runs:

- PURCHASE
- SALE
- LOT
- REALIZED
- RECON_LOT_GROUP
- RECON_GROUP
- RECON_EVENT
- TAX

Compare sorted identifiers and financially meaningful values, not row order.

If an upstream canonicalization change alters these identities unexpectedly, stop and trace the earliest difference through canonical evidence before modifying FIFO/Tax/reconciliation logic.

## 9. Financial Difference Triage

Use this order:

1. Confirm same evidence/artifact set.
2. Confirm same `FinancialRules` fingerprint.
3. Confirm same capability plan.
4. Confirm same market/provider evidence.
5. Compare canonical Bronze evidence.
6. Compare Silver inputs to the first differing financial engine.
7. Compare protected identities/values.
8. Only then inspect the financial kernel itself.

Do not compensate for source/canonical mismatches by changing financial formulas.

## 10. Observability / JSONL

Use the existing one-emitter observability lineage. Correlate by run and parent operation, then inspect source/binding/canonical context such as:

- `source_id`;
- `source_binding_id`;
- canonical route / DatasetId;
- producer kind;
- plan/contract fingerprint;
- stage/status;
- worker/process context.

Semantic diagnostics should emit bounded counts/context, not sensitive financial rows.

For multiprocessing regressions, verify child events retain the run and parent-operation lineage expected by the existing observability certification tests.

## 11. Performance Profiling

Profile the final path by boundary rather than timing only total runtime:

- source planning;
- provider extraction;
- Gate 1;
- Pre-Bronze persistence;
- normalization;
- semantic interpretation;
- fragment creation/UNION;
- canonical identity;
- Gate 2;
- canonical integrity;
- satisfiability planning;
- Silver/Gold execution;
- observability overhead.

Optimize measured bottlenecks only. Do not weaken validation, recovery or observability to recover runtime.
