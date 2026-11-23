# Phase 21 — Forensic JSONL and Retained Source Evidence

## Sprint contract
- **Timebox:** 2–3 focused hours.
- **Authority:** program `README.md` + this phase file + current repository source only.
- **Definition of done:** implemented code, focused tests green, changed code passes Ruff/mypy, repository runnable, no PFETL mutation.
- **Scope discipline:** if the work cannot fit this boundary without redesigning ownership or methodology, stop at the smallest coherent implementation and surface the conflict. Do not turn the sprint into a hidden platform project.

## Depends on
Phase 20.

## Phase outcome
Turn archived canonical observability events and retained source payloads into a searchable forensic workbench without creating another logging backend.

## Inherited state
- Archived log decoder exists from Phase 04.
- Operations page/run selection and source registry exist.

## Files in scope
- `data/log_reader.py`
- `analytics/operations.py`
- `pages/operations.py`
- `tests/test_operations_forensics.py`

## Grounded PFETL / Studio inputs
- `cp_runs.execution_log` zlib-compressed JSONL preferred source.
- Filesystem JSONL under resolved logs directory is fallback/current convenience only.
- ObservabilityEvent serialized fields: schema_version,event_id,sequence,timestamp,event_code,severity,presentation_kind,outcome,message,progress,context,error.
- Context exact fields: run_id,stage,component,operation,operation_id,parent_operation_id,entity_type,entity_id,duration_ms,rows,attempt,provider,cache_hit,worker_id,batch_id,commit_state,settings_fingerprint,rules_fingerprint.
- Error fields: exception_type,exception_message,failure_domain,traceback_summary,retryable,context_variables,remediation_hint,failing_stage,failing_entity.
- `cp_file_payloads(file_id,file_bytes)` retained source evidence.

## Required contracts at phase exit
- `ForensicEvent` Studio model mirrors serialized fields without importing Core enums; unknown enum strings are accepted as strings for forward compatibility.
- `forensic_events(run_id, filter)` preserves event `sequence` ordering then timestamp.
- `operation_tree(run_id)` joins parent_operation_id → operation_id and retains orphan nodes.
- `forensic_summary(run_id)` computes only operational summaries: counts, provided duration_ms, rows, retries, cache-hit counts, provider/worker/batch distributions.
- `source_payload(file_id)` returns bytes only on explicit user action.

## Data and query semantics
- Do not synthesize missing duration by subtracting arbitrary events. Use `duration_ms` when Core emitted it.
- Malformed JSONL lines are counted/skipped with raw line diagnostic; valid events still load.
- Operation lineage uses explicit IDs only.
- Payload bytes are never preloaded into tables or cached persistently by Studio.

## UI / interaction specification
- Forensics & Evidence subview: event filters for severity/code/outcome/stage/component/operation/entity/provider/worker/batch/error domain plus text search.
- Timeline table + event detail drawer with raw JSON.
- Summary panels: slowest emitted durations, row processing, retries, cache hits, provider/worker activity, failure domains.
- Lineage tree for selected operation/run.
- Artifact detail shows “retained payload available” and explicit Download Evidence button.

## Implementation sequence
1. Normalize decoded JSON into Studio event model.
2. Implement filter/summary/lineage functions.
3. Implement payload availability/download with user-chosen destination; never auto-extract/execute content.
4. Render forensic UI.
5. Test ordering, malformed line handling, parent-child lineage, error fields and byte-identical payload download.

## Focused verification
- Event sequence/order preserved.
- Summary uses only fields actually present.
- Downloaded fixture payload hash equals stored bytes.

## Edge cases and failure behaviour
- No execution_log: use filesystem fallback if matching run log discoverable, otherwise show unavailable.
- Large logs: parse/filter server-side/in Python incrementally enough for local scale; cap UI rows and provide search.
- Unknown event schema_version: display raw-compatible fields and warning rather than crash.

## Explicit non-goals
- Do not import `personal_finance_etl` or copy PFETL financial algorithms into Studio.
- Do not write to PFETL DuckDB, Control Plane/Raw Store SQLite, Settings TOML or FinancialRules TOML.
- Do not create an API server, plugin system, cross-repo shared package or generic framework unless this phase explicitly requires it.
- Do not add documentation files outside the root `README.md`; implementation knowledge belongs in code/tests after the planning program is consumed.
- Do not send logs/payloads to external services.
- Do not implement log deletion/retention controls.

## Exit criteria
- [ ] All observability context/error fields are inspectable.
- [ ] Control Plane payload evidence can be explicitly downloaded.
- [ ] Operations area now consumes all ten Control Plane tables plus Meta context.

## Handoff to next phase
Phase 22 builds exhaustive Data Catalog/Guided Explorer over the established catalog/semantics.
