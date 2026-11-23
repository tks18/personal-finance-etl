# Phase 07 — Forensic Logs and System UI

**Sprint:** 2–3 hours  
**Goal:** turn the desktop app into a useful PFETL control center by exposing the existing forensic JSONL truth and Phase-13 operator services, without duplicating backend systems.

## Final top-level UI

```text
Run | Configuration | Logs | System
```

`Configuration` contains the Phase-5 Settings and Phase-6 Financial Rules editors.

## A. Run tab

Move the current `UnifiedETLTab` run controls into `run_tab.py` with minimal behavior change:

- selected config/rules paths;
- Run;
- Snapshot;
- Restore;
- progress bar;
- current human-facing observability narrative.

Preserve `BaseEngineTab.handle_status()` semantics and event suppression.

Consider moving snapshot/restore execution to a background thread only if current synchronous restore causes visible UI blocking during real use. Do not redesign recovery in this phase.

## B. Logs tab: narrative + forensic

Create `logs_tab.py` with two sub-tabs:

```text
Live Narrative | Forensic JSONL
```

### JSONL source

Resolve log directory from the **currently selected Settings file** using `Settings.resolve_logs_dir()` through a façade/read helper. Discover `.jsonl` files sorted newest first. Do not read archived Control Plane BLOBs in v1 unless the active file is missing and the existing archive API already makes this trivial.

### Run/file selector

Show:

- filename;
- modified time;
- size;
- detected run ID after parsing first event where possible.

Provide Refresh and Open Folder actions.

### Parsing

Parse one line at a time with `json.loads`. Invalid/truncated lines should produce a visible warning row rather than crash the page.

For normal run sizes, in-memory parse is acceptable. If a trace is very large, cap initial display and provide incremental Load More; do not create an index database.

### Table/filter fields

Use existing `ObservabilityEvent.to_dict()` shape:

```text
timestamp
severity
event_code
outcome
presentation_kind
message
context.run_id
context.stage
context.component
context.operation
context.entity_type
context.entity_id
context.duration_ms
context.rows
context.attempt
context.provider
context.cache_hit
context.worker_id
context.batch_id
```

Filters:

- severity;
- stage;
- component;
- event code;
- free-text search across message/entity/operation;
- failures only toggle.

### Detail pane

On row selection display all structured data:

- operation/parent IDs and lineage context;
- settings/rules fingerprints;
- commit state;
- full error block;
- traceback summary in monospace text;
- remediation hint;
- retryable flag;
- context variables.

This viewer is read-only.

## C. System tab

Create `system_tab.py`. Use only façade methods backed by the decoupled Phase-1 operator service:

```text
engine.get_system_status(config_path)
engine.get_system_info(config_path)
engine.run_doctor(config_path, rules_path)
```

### Status cards

Display:

- pipeline lock state;
- DuckDB and Raw Store present/missing + sizes;
- latest run status and timestamps;
- latest sync counts/status;
- stale runs;
- recovery-required count.

### Info section

Display:

- PFETL version;
- Python/platform;
- active config/rules paths;
- DB paths;
- statements/household source paths;
- Bronze/Silver/Gold counts;
- available warehouse schemas.

### Doctor section

Button: **Run Doctor**.

Render every `DoctorCheckResult` with PASS/WARN/FAIL, message and remediation. Do not hide WARN/FAIL behind a dialog only.

Actions allowed:

- Refresh;
- Run Doctor;
- Open Logs Folder;
- Open Database Folder.

No direct SQL browser, data editor or financial dashboard.

## D. App/root refactor

After tabs exist, reduce `app.py` to:

- window title/geometry/theme/icon;
- create one shared `PersonalFinanceEngine`;
- shared selected config/rules variables or a tiny presentation state object;
- construct tab view;
- wire selection changes across Run/Configuration/Logs/System.

Do not duplicate one engine per tab if a shared façade suffices.

## Tests

Keep tests lightweight:

- JSONL parser handles valid/error/truncated rows;
- filter function returns expected events;
- selected Settings path resolves expected log directory;
- System view adapter accepts SystemStatus/SystemInfo/DoctorReport models;
- no direct `sqlite3`/`duckdb` imports under `presentation/desktop`.

Manual smoke test is required for actual widget layout and threading.

## Exit criteria

The desktop UI is materially useful beyond Run: it configures PFETL, shows live logs, inspects forensic JSONL, exposes system/doctor state, and still delegates all backend truth to existing services.
