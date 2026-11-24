# PFETL Core UI Closure Patch --- Authoritative Implementation Plan

## Status and authority

This document is the implementation authority for the final PFETL Core
UI closure patch against the v12.0.0 baseline.

The objective is deliberately narrow:

> Close the remaining desktop responsiveness, dependency-direction,
> forensic-log usability, and operator-UX gaps without expanding PFETL
> Core product scope.

At completion:

``` text
application.operator
    → fully architecture-clean

all potentially blocking UI I/O
    → background execution

forensic JSONL
    → cached + asynchronous + debounced + lightweight

application status
    → truthful

configuration editors
    → safe and polished

PFETL Core UI
    → FROZEN
```

Financial calculations, warehouse architecture, observability
architecture, pipeline behavior, new analytics, and new product surfaces
are out of scope.

------------------------------------------------------------------------

## 1. Finish `OperatorService` decoupling

### Current issue

`application/operator.py` correctly accepts `OperatorInspector`, but
still imports and falls back to `LocalOperatorInspector`.

That leaves this dependency possible:

``` text
application → infrastructure
```

### Correct implementation

Make `OperatorService` require an `OperatorInspector`.

Conceptually:

``` python
class OperatorService:
    def __init__(
        self,
        inspector: OperatorInspector,
        ...
    ) -> None:
        self._inspector = inspector
```

Remove the direct infrastructure import and the fallback construction of
`LocalOperatorInspector`.

### CLI composition

Do not construct `OperatorService(config_path=...)` directly from the
CLI.

Route CLI construction through the bootstrap/composition root so that:

``` text
LocalOperatorInspector
        ↓
OperatorService
```

is assembled outside the application layer.

Desktop and CLI must therefore use the same composition rules.

### Verification

Assert:

``` text
application/
    imports contracts
    does NOT import infrastructure
```

Then verify that:

``` text
pfetl status
pfetl info
pfetl doctor
```

remain behaviorally equivalent.

------------------------------------------------------------------------

## 2. Add one reusable Tk background-task runner

Do this before fixing Doctor, System refresh, Snapshot, Restore, or
forensic loading.

The application must not grow several slightly different threading
patterns.

### New file

``` text
presentation/desktop/background_tasks.py
```

### Responsibilities

The helper should:

-   execute a callable on a bounded background worker;
-   marshal success callbacks onto the Tk thread;
-   marshal error callbacks onto the Tk thread;
-   optionally invoke a completion/finally callback;
-   prevent worker code from touching Tk widgets;
-   tolerate widget/application destruction before completion;
-   support a task token/generation where stale results matter.

Conceptually:

``` python
runner.submit(
    work=...,
    on_success=...,
    on_error=...,
    on_finally=...,
)
```

All UI callbacks must return through `widget.after(0, ...)`.

A small bounded `ThreadPoolExecutor` or equivalent daemon-thread helper
is sufficient.

Do not introduce asyncio, a general job framework, or another process
architecture.

------------------------------------------------------------------------

## 3. Extend `AppState` with global operation state

Use the existing centralized presentation state rather than letting each
tab invent its own busy flags.

Add a small enum such as:

``` text
READY
PIPELINE_RUNNING
CHECKING
SNAPSHOTTING
RESTORING
ATTENTION
RECOVERY_REQUIRED
FAILED
```

`AppState` should own the current operation, last relevant operation
result, and recovery state needed by presentation.

This is presentation state only. Do not create a domain/application
state-machine framework.

------------------------------------------------------------------------

## 4. Make the top status badge truthful

Replace the static:

``` text
● Engine Ready
```

with state derived from `AppState`.

Recommended presentation:

  State           Label
  --------------- -----------------------
  ready           `● Ready`
  pipeline        `● Running`
  doctor/system   `● Checking`
  snapshot        `● Snapshotting`
  restore         `● Restoring`
  recovery        `● Recovery Required`
  warning         `● Attention`
  failed          `● Failed`

Use the existing theme status colors.

### Priority

Transient operations should take precedence over historical state:

``` text
RESTORING
>
SNAPSHOTTING
>
PIPELINE_RUNNING
>
CHECKING
>
RECOVERY_REQUIRED
>
FAILED / ATTENTION
>
READY
```

Tabs update `AppState`; the application header subscribes to it.

Do not allow individual tabs to manipulate the header widget directly.

------------------------------------------------------------------------

## 5. Add global operation interlocking

Run, Snapshot, and Restore must understand each other's state.

For example, while the pipeline is running, incompatible
Snapshot/Restore actions should be disabled.

While restoring, Run, Snapshot, and additional Restore operations must
be unavailable.

Centralize this decision from `AppState` rather than scattering
button-state rules across tabs.

The objective is simple:

> Two incompatible operations must never mutate or inspect derived
> storage concurrently merely because two buttons were clickable.

System inspection can remain available where it is safe.

------------------------------------------------------------------------

## 6. Run Doctor asynchronously

### Current issue

`SystemTab.run_doctor()` calls the operator/engine Doctor path
synchronously from Tk.

Doctor can involve filesystem, SQLite, DuckDB, and provider/network
inspection.

### Correct implementation

On click:

``` text
set CHECKING
disable Doctor action
show checking state
        ↓
BackgroundTaskRunner
        ↓
engine.run_doctor(...)
        ↓
Tk success/error callback
        ↓
render report
restore presentation state
```

Do not destroy the previous successful Doctor result while a refresh is
running.

If the new Doctor attempt fails, retain the previous result and display
the refresh error separately.

The market/provider probe must never freeze navigation or window
repainting.

------------------------------------------------------------------------

## 7. Run System refresh asynchronously

Apply the same mechanism to `get_system_status()` and
`get_system_info()`.

Immediately indicate that a refresh is occurring, but retain the
existing displayed values until the replacement result arrives.

Update the cards atomically when successful.

Do not blank and reconstruct the whole page before I/O completes.

------------------------------------------------------------------------

## 8. Run Snapshot asynchronously

Keep the existing backup/application service unchanged.

The UI flow should become:

``` text
Create Snapshot
        ↓
set SNAPSHOTTING
disable incompatible operations
        ↓
background runner
        ↓
engine.snapshot_database(...)
        ↓
success/error callback
        ↓
restore final AppState
```

Show the resulting snapshot path on success.

Archive/copy work must not execute on Tk's thread.

------------------------------------------------------------------------

## 9. Run Restore asynchronously

The file picker and restore confirmation remain on the Tk thread.

After confirmation:

``` text
set RESTORING
        ↓
background runner
        ↓
engine.restore_database(...)
        ↓
Tk completion
```

During Restore:

-   Run is disabled;
-   Snapshot is disabled;
-   additional Restore actions are disabled;
-   the window remains interactive and repaintable.

After a successful restore, refresh the relevant System/profile
presentation state.

------------------------------------------------------------------------

## 10. Extract forensic-log logic from `logs_tab.py`

### New file

``` text
presentation/desktop/forensic_model.py
```

`logs_tab.py` should own widgets and user interaction.

`forensic_model.py` should own:

-   JSONL parsing;
-   parsed trace models;
-   search normalization;
-   filter indexes;
-   filtering;
-   pagination;
-   cache management.

Suggested lightweight models:

``` text
ForensicEvent
ParsedTrace
TraceFilter
TracePage
TraceCache
```

Do not create a generic observability query engine.

This is presentation-only read logic for the existing forensic JSONL.

------------------------------------------------------------------------

## 11. Parse JSONL in the background

When a trace is selected:

``` text
select trace
↓
increment load generation
↓
show loading state
↓
background parse
↓
ParsedTrace
↓
cache
↓
Tk render
```

### Stale-load protection

If Trace A begins loading, the user selects Trace B, and A finishes
later, A must not overwrite B.

Maintain a monotonically increasing `load_generation` or request token.

Only the latest generation may update the forensic UI.

------------------------------------------------------------------------

## 12. Add a bounded forensic trace cache

Cache parsed traces by:

``` text
(path, file_size, mtime_ns)
```

The value is a `ParsedTrace`.

Use a small LRU cache of approximately 3--5 traces.

When an unchanged cached trace is reopened:

``` text
disk read = 0
JSON parsing = 0
```

Rendering should begin immediately.

Do not retain every historical trace indefinitely.

------------------------------------------------------------------------

## 13. Parse and normalize each event once

During initial parsing, precompute the fields needed for search and
display.

Build one normalized lowercase search string per event from at least:

``` text
message
event_code
stage
component
operation
entity_type
entity_id
provider
failure_domain
exception_type
exception_message
remediation_hint
```

Text search then operates against the precomputed field rather than
repeatedly traversing nested dictionaries.

Malformed JSONL lines should be handled without crashing the whole
trace. Preserve enough information to identify malformed entries where
useful.

------------------------------------------------------------------------

## 14. Build structured filter indexes

For frequently filtered fields, build indexes such as:

``` text
severity
stage
component
event_code
outcome
failure_domain
```

using:

``` text
value → set[event_index]
```

Structured filtering can then intersect matching index sets before
applying text search.

This keeps behavior predictable even if forensic traces grow beyond
their current size.

------------------------------------------------------------------------

## 15. Populate filter options from the active trace

Severity, stage, component, event code, outcome, failure-domain, and
similar dropdown values should come from the loaded `ParsedTrace`.

Do not depend on stale or hardcoded filter choices.

When a new trace loads:

1.  rebuild available filter values;
2.  preserve a current selection only if it remains valid;
3.  otherwise reset that filter to `All`.

This is required both for correctness and for fixing the current
unreliable filtering behavior.

------------------------------------------------------------------------

## 16. Debounce forensic text search

Do not invoke full filtering on every keystroke.

Use approximately 150--200 ms debounce:

``` text
keystroke
↓
cancel pending callback
↓
after(175 ms)
↓
apply filter
```

Dropdown/checkbox filters can apply immediately.

`Ctrl+F` should focus the forensic search field when Logs is active.

------------------------------------------------------------------------

## 17. Replace heavy forensic event-card rendering

The current rich-card-per-event design creates unnecessary CustomTkinter
widget churn.

Replace it with:

``` text
compact event list
        +
single detail pane
```

### Event list

Each visible row should contain only lightweight information such as:

``` text
timestamp
severity
stage/component
event code if useful
short message
```

### Detail pane

Render the selected event richly:

``` text
full message
run ID
stage
component
operation
operation ID
parent operation
entity type / ID
duration
rows
provider
attempt
cache hit
worker
batch
commit state

structured context

error
traceback
failure domain
retryable
remediation
```

Only one detailed event view should exist at a time.

This is the largest expected rendering-performance improvement.

------------------------------------------------------------------------

## 18. Use fixed forensic pagination

Replace accumulating `Load More` behavior with deterministic pagination:

``` text
Previous
Page X / Y
Next
```

Use approximately 100 events per page, reducing to 75 only if real UI
testing shows a benefit.

Display:

``` text
1,347 events
212 matching
Showing 101–200
```

Changing filters resets the current page to 1.

------------------------------------------------------------------------

## 19. Preserve forensic selection intelligently

If the currently selected event still matches after a filter change,
preserve it.

Otherwise select the first visible match.

If no events match:

``` text
No matching events
```

and clear the detail pane.

Filtering and pagination should therefore feel deterministic rather than
causing random selection jumps.

------------------------------------------------------------------------

## 20. Keep Live Log and Forensic JSONL separate

Do not merge the two logging experiences.

They serve different purposes:

``` text
Live Log
    → polished execution narrative

Forensic JSONL
    → structured diagnostic inspection
```

The existing batched live-event mechanism is already performant and
should remain intact.

The forensic rewrite must not disturb the live observability projection.

------------------------------------------------------------------------

## 21. Add Settings and FinancialRules dirty-state protection

Both editors should compare current UI state with the last successfully
loaded/saved baseline.

If dirty and the user attempts an action that would discard the current
document, such as:

-   selecting another profile;
-   reloading;
-   closing the application;
-   replacing the active document;

show:

``` text
Save
Discard
Cancel
```

Normal navigation between application tabs should not trigger warnings.

Successful Save/Save As resets the dirty baseline.

------------------------------------------------------------------------

## 22. Improve validation feedback

When Pydantic validation fails:

1.  preserve all current user-entered values;
2.  identify affected fields/sections;
3.  visually mark invalid controls;
4.  show a short inline message;
5.  scroll/focus the first invalid field where practical;
6.  retain a summary for multi-field or model-level validation errors.

Complex rules such as allocation totals, tax overlaps, matrices, or LTCG
ladders may require section-level validation messages rather than
falsely attributing the problem to one scalar input.

Do not weaken existing Pydantic validation to simplify the UI.

------------------------------------------------------------------------

## 23. Add only high-value keyboard shortcuts

Implement:

``` text
Ctrl+S
    Save active Settings/FinancialRules editor

Ctrl+Shift+S
    Save As

Ctrl+F
    Focus forensic search when Logs is active

Ctrl+R
    Refresh current System view or selected trace where safe

Esc
    Close transient dialogs where appropriate
```

Do not create a command palette or generalized shortcut framework.

------------------------------------------------------------------------

## 24. Persist harmless UI preferences

Use the existing preference infrastructure.

Persist only lightweight presentation preferences such as:

``` text
window geometry
last top-level tab
last Configuration subtab
last FinancialRules domain
last forensic filter values
```

Optionally retain the last selected log only if the file still exists.

Do not persist:

``` text
parsed trace objects
trace caches
unsaved TOML edits
operation state
background tasks
```

Invalid or stale preferences should fall back safely without blocking
startup.

------------------------------------------------------------------------

## 25. Focused tests

Update the existing compact UI/operational test suite rather than
creating a new phase-test family.

### Architecture

Assert that `application.operator` does not import
`infrastructure.operator`.

Assert that CLI operator commands are assembled through composition.

### Background runner

Test:

-   successful background completion;
-   error completion;
-   callbacks return through Tk;
-   destroyed/stale UI targets do not crash;
-   workers never directly mutate widgets.

### Operation interlock

Verify incompatible controls are disabled during pipeline, snapshot, and
restore operations.

### Doctor and System

Use deliberately slow fake inspectors/services and verify Tk regains
control immediately while the work proceeds.

### Snapshot and Restore

Use slow fakes and verify busy/interlock/status behavior without
blocking UI processing.

### Forensic model

Test:

-   valid JSONL;
-   malformed lines;
-   normalized search;
-   structured indexes;
-   combined filters;
-   filter-option discovery;
-   cache hit;
-   cache invalidation after file size/mtime change;
-   LRU eviction;
-   pagination;
-   selection preservation;
-   stale load-generation rejection.

### Search debounce

Multiple rapid search changes should produce one effective filtering
execution after the debounce interval.

### Editors

Test:

-   dirty detection;
-   Save/Discard/Cancel;
-   successful save resets dirty state;
-   invalid controls are identified;
-   Save As preserves expected behavior.

### Header status

Verify presentation for all supported `AppState` operation states.

------------------------------------------------------------------------

## 26. Performance acceptance

Use practical UX acceptance rather than building a benchmark laboratory.

  Behavior                   Acceptance
  -------------------------- -----------------------------
  Pipeline execution         no Tk blocking
  Live event rendering       batched; no visible backlog
  Doctor                     UI remains interactive
  System refresh             UI remains interactive
  Snapshot                   UI remains interactive
  Restore                    UI remains interactive
  JSONL first load           background; no freeze
  Cached trace reopen        effectively immediate
  Search typing              no visible lag
  Structured filter change   immediate after processing
  Page change                no perceptible freeze
  Settings/Rules save        validated and atomic
  Top-level navigation       responsive

Manual smoke testing plus focused automated tests is sufficient.

------------------------------------------------------------------------

## 27. Expected files in scope

Primarily:

``` text
application/operator.py
bootstrap/container.py
presentation/cli.py

presentation/desktop/app.py
presentation/desktop/state.py
presentation/desktop/run_tab.py
presentation/desktop/system_tab.py
presentation/desktop/logs_tab.py
presentation/desktop/settings_tab.py
presentation/desktop/financial_rules_tab.py
presentation/desktop/config_editor.py

presentation/desktop/background_tasks.py     NEW
presentation/desktop/forensic_model.py       NEW

tests/test_system_and_logs.py
tests/test_settings_editor.py
tests/test_rules_editor.py
tests/test_operational_integrity.py
```

Additional facade/bootstrap edits are acceptable only where required to
route CLI/operator construction through the composition root.

No finance/domain/warehouse changes should be necessary.

------------------------------------------------------------------------

## 28. Explicit non-goals

Do not add:

``` text
new financial metrics
financial charts
dashboard KPIs
SQL explorer
DuckDB browser
Control Plane browser
new top-level tabs
PySide6
asyncio
new observability architecture
new persistence layer
new Settings/FinancialRules parameters
Analytics Studio functionality
```

If implementation begins requiring any of those, stop and reassess.

This patch closes existing Core UI behavior. It does not expand the
product.

------------------------------------------------------------------------

## 29. Final acceptance checklist

Before declaring PFETL Core UI closed:

-   `pfetl` launches normally;
-   recent Settings and FinancialRules profiles still work;
-   Settings/Rules editing, validation, Save, and Save As work;
-   unsaved edits cannot be discarded accidentally;
-   pipeline execution remains unchanged;
-   live narrative remains smooth;
-   header reflects actual application operation state;
-   Doctor never freezes the UI;
-   System refresh never freezes the UI;
-   Snapshot never freezes the UI;
-   Restore never freezes the UI;
-   incompatible operations cannot execute simultaneously;
-   large forensic traces load without freezing;
-   forensic search typing has no visible lag;
-   every structured forensic filter works alone and in combination;
-   filter choices reflect the active trace;
-   switching traces cannot display stale parse results;
-   cached trace reopening is effectively immediate;
-   pagination and event-detail inspection work correctly;
-   no forensic diagnostic information is lost;
-   CLI `status`, `info`, and `doctor` remain functional;
-   `application` has no operator infrastructure dependency;
-   existing financial golden tests remain unchanged and green.

------------------------------------------------------------------------

# Closure rule

Once this patch is green:

> **PFETL Core UI is frozen.**

Future requests primarily involving financial exploration, visual
analytics, custom reports, dashboards, analytical drill-down, or rich
decision surfaces belong in **PFETL Analytics Studio**, not in the Core
desktop application.

PFETL Core should remain the reactor downstairs:

``` text
configure
run
observe
diagnose
recover
```

Analytics Studio owns everything upstairs that turns the resulting
financial truth into exploration and reporting.
