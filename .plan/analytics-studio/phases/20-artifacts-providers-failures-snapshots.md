# Phase 20 — Artifact, Provider, Failure and Snapshot Intelligence

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 19.

## Phase outcome
Use the remaining non-log Control Plane history to explain source freshness/change, provider behavior, failures and exact run assumptions.

## Inherited state
- Operations Runs tab and run selection exist.

## Files in scope
- `analytics/operations.py`
- `pages/operations.py`
- `tests/test_operations_forensics.py`

## Grounded PFETL / Studio inputs
- `cp_file_registry`, `cp_artifact_run_events`, `cp_external_provider_requests`, `cp_run_failures`, `cp_settings_snapshots`, `cp_rules_snapshots`.
- `meta.m_File_Registry`, `meta.m_Settings`, `meta.m_Financial_Rules` for current warehouse snapshot context.

## Required contracts at phase exit
- `source_registry(filters)` returns lifecycle/freshness fields.
- `artifact_events(run/file filters)` returns change timeline.
- `provider_requests(run/provider/status filters)` returns attempts/window/failures.
- `run_failures(run filters)` returns domain/stage/type/message/traceback metadata.
- `snapshot_diff(run_a,run_b,kind)` performs JSON structural diff of canonical snapshot payloads only.

## Data and query semantics
- Source freshness uses `last_seen_at`, `last_changed_at`, `last_synced_at` independently.
- Artifact event types/reason/convergence are displayed verbatim; Studio does not infer change semantics.
- Provider attempt_count/status/failure_class are operational evidence.
- Snapshot diffs compare stored canonical payloads, not current TOMLs.

## UI / interaction specification
- Sources & Artifacts: registry table, freshness badges, event timeline/detail.
- Providers & Failures: request table + attempts/failure chart; failure table/detail with traceback collapsed by default.
- Run detail includes Settings/Rules snapshot viewer and diff-to-previous successful run.

## Implementation sequence
1. Implement source/artifact/provider/failure queries.
2. Implement snapshot payload parse/diff.
3. Render filters and detail drawers.
4. Test freshness fields, provider attempts, failure fields and deterministic snapshot diff.

## Focused verification
- Fixture artifact lifecycle fields, provider attempts, failure domain/stage and snapshot diffs match source rows exactly.
- Snapshot diff ordering is deterministic and profile/run scoped.

## Edge cases and failure behaviour
- No source files: registry empty state.
- Malformed snapshot payload: raw text available with parse warning.
- Traceback may contain paths; display only locally and never include in telemetry.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not add source mutation/retry buttons.

## Exit criteria
- [ ] All non-log Control Plane tables except payload/simulation are consumed in operations views.

## Handoff to next phase
Phase 21 adds archived JSONL analytics and retained payload access.
