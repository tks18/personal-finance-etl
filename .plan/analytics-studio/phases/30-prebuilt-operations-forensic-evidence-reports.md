# Phase 30 — Prebuilt Operations, Forensic and Evidence Reports

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 29.

## Phase outcome
Implement Data Health & PFETL Operations, Run Forensic, and Source Evidence & Change reports from Control Plane/Meta/JSONL evidence.

## Inherited state
- Operations/forensics complete and twelve built-ins certified.

## Files in scope
- `reports/templates/operations.py`
- `reports/templates/forensic.py`
- `reports/templates/evidence.py`
- registry/tests

## Grounded PFETL / Studio inputs
- OperationsAnalytics run/sync/source/provider/failure/snapshot services.
- Forensic event summary/lineage.
- Artifact registry/events/payload availability.
- Meta contracts/row counts.

## Required contracts at phase exit
- Stable IDs: `data_health_operations`, `run_forensic`, `source_evidence_change`.

## Data and query semantics
- Data Health default last 10 runs/custom window.
- Run Forensic requires selected run and optional stage/component/severity filters.
- Evidence report supports run/date/source/event filters; report indicates payload availability but does not embed arbitrary source binary blobs by default.

## UI / interaction specification
- Operations reports use local operational evidence and provenance; no finance methodology.

## Implementation sequence
1. Define blocks for health/freshness/sync/providers/failures/row counts.
2. Define forensic event timeline/slow operations/failures/lineage.
3. Define source change history/hash/replay/convergence/payload availability.
4. Test filters and exports on fixture Control Plane.

## Focused verification
- All ten Control Plane tables have at least one report/page consumer.
- Forensic report order follows event sequence.

## Edge cases and failure behaviour
- Large event logs summarized in PDF with bounded appendix; XLSX may contain larger table within safe limits.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not auto-attach source payloads to reports.

## Exit criteria
- [ ] All 15 built-in reports are certified and exportable.

## Exact report composition
### Data Health & PFETL Operations
- **Default window:** latest 10 runs; custom run/date window supported.
- **Blocks:** run success/commit/duration trend; sync actionable/synced/healed/failed/deferred; source freshness; provider request attempts/failures; failure-domain summary; warehouse contract/row-count health; Settings/Rules change markers; simulation status.
- **Acceptance:** operational metrics come directly from Control Plane/Meta services and do not infer financial health from row counts alone.

### Run Forensic Report
- **Required input:** one selected run.
- **Blocks:** run provenance; Settings/Rules snapshot IDs; event counts by severity/code/outcome; stage/component timeline; slow emitted operations by `duration_ms`; rows/retries/cache hits/providers/workers; failures/remediation; parent-child operation lineage; bounded event appendix.
- **Filters:** stage, component, severity, event code, outcome, provider, worker, failure domain.
- **Acceptance:** event ordering follows `sequence` then timestamp and missing durations are not synthesized.

### Source Evidence & Change Report
- **Default window:** custom run/date window.
- **Blocks:** source registry/freshness; artifact added/changed/renamed/replayed/converged events; hashes/sizes/status transitions; affected warehouse tables; provider/source context; retained-payload availability list.
- **Acceptance:** binary payload bytes are not embedded automatically; report only records availability/identity unless explicitly exported separately by the user.

## Handoff to next phase
Phase 31 builds custom report authoring on the stable registry.
