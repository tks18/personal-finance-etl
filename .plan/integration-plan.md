# PFETL Core × Analytics Studio — Integration Implementation Plan

## Purpose

Integrate the released **PFETL Analytics Studio 1.1.0** cleanly into the existing PFETL Core CustomTkinter operator application.

This is a **single bounded integration phase**.

The integration must not move Studio analytics into Core and must not embed NiceGUI inside Tkinter.

The target experience is:

```text
PFETL Core Desktop
        ↓
Analytics Studio control card
        ↓
Start Studio
        ↓
Core launches Studio server child process
        ↓
passes active Settings + FinancialRules
        ↓
waits for Studio /healthz
        ↓
Open Studio in browser
```

Core may also:

```text
Stop Studio
Restart Studio
Open Studio
show Studio status
show Studio process logs
```

Studio remains an independently releasable application.

---

# 1. Integration boundary

Preserve the existing architectural boundary.

PFETL Core communicates with Studio only through:

```text
process launch
Settings TOML path
FinancialRules TOML path
loopback host/port
Studio runtime metadata
GET /healthz
stdout/stderr
process termination
```

Do not import Studio analytics, pages, data gateways, report code, or NiceGUI application internals into PFETL Core.

The integration is **process orchestration**, not application merging.

---

# 2. Runtime architecture

Use this model:

```text
PFETL Core CustomTkinter
        │
        ├── StudioProcessService
        │       │
        │       ├── launch
        │       ├── health
        │       ├── open browser
        │       ├── restart
        │       └── stop
        │
        └───────────────┐
                        ↓
             Analytics Studio server
             separate child process
                        ↓
               127.0.0.1:<port>
                        ↓
                    browser
```

Never run NiceGUI's event loop inside Tkinter's process or a Tk worker thread.

The child-process boundary protects:

- Tk responsiveness;
- NiceGUI lifecycle;
- server shutdown;
- dependency isolation;
- future Studio upgrades.

---

# 3. Add a Core-side Studio process contract

Add a small application-facing contract representing Studio lifecycle operations.

Suggested concepts:

```python
StudioStatus
StudioRuntime
StudioLaunchRequest
StudioProcessController
```

Example status values:

```text
STOPPED
STARTING
READY
STOPPING
FAILED
```

`StudioRuntime` should contain only operational information such as:

```text
pid
host
port
health_url
version
started_at
```

Do not store financial values.

Do not duplicate Studio's runtime JSON model unnecessarily; Core may parse the documented runtime contract into its own typed model.

---

# 4. Implement the concrete process supervisor

Place the concrete subprocess/file/network implementation in the appropriate Core infrastructure/operator area.

Suggested responsibility:

```text
StudioProcessService
```

or equivalent.

It owns:

- locating the Studio executable/command;
- launching the child;
- creating a Core-owned runtime-file path;
- capturing stdout/stderr;
- polling `/healthz`;
- reading Studio runtime metadata;
- opening the browser;
- graceful stop;
- forced termination fallback;
- restart;
- stale runtime cleanup;
- status inspection.

Keep UI widgets out of this service.

---

# 5. Launch command

Core must launch Studio's **server mode**, not the Studio tray.

For an installed/PyPI development environment, conceptually:

```bash
pfetl-studio-server \
  --host 127.0.0.1 \
  --port 0 \
  --auto-port \
  --no-browser \
  --runtime-file <core-runtime-path> \
  --settings <active-settings.toml> \
  --rules <active-financial-rules.toml>
```

For a packaged PFETL distribution, resolve the bundled Studio server executable or the packaged Studio executable's server/CLI mode according to the final packaging layout.

Core must not depend on the user's PATH when Studio is bundled with Core.

---

# 6. Pass the active PFETL profile explicitly

The Core desktop already knows the active:

```text
Settings TOML
FinancialRules TOML
```

Use those exact active paths when launching Studio.

Before launch:

- confirm both files exist;
- confirm neither is mid-save;
- use the same active profile visible in Core;
- do not copy the files;
- do not translate configuration into another format.

Studio performs its normal profile validation after launch.

If Core later changes active profile while Studio is already running, do **not** silently mutate Studio's profile.

Recommended initial behavior:

```text
active Core profile changes
        ↓
Studio status becomes "Restart required"
```

The user can then restart Studio, which relaunches it with the new pair.

This is simpler and safer than introducing cross-process profile synchronization.

---

# 7. Health and readiness

After spawning Studio:

```text
STARTING
    ↓
wait for runtime metadata
    ↓
poll health_url
    ↓
verify:
    status == ready
    app == pfetl-analytics-studio
    ↓
READY
```

Use bounded polling with a startup timeout.

Do not mark Studio Ready merely because:

- the PID exists;
- the port is open;
- the runtime file exists.

`/healthz` is the readiness authority.

On timeout:

```text
FAILED
```

and expose a useful diagnostic message.

---

# 8. Studio logs in the CustomTkinter UI

## Yes — this is supported cleanly

Launch Studio with:

```python
subprocess.Popen(
    ...,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    ...
)
```

Read both streams from background reader threads or a bounded process-log reader.

Never call blocking `readline()` on Tk's main thread.

The flow should be:

```text
Studio stdout/stderr
        ↓
background reader
        ↓
Core-side queue
        ↓
existing Tk batched event drain
        ↓
Core narrative / Studio log view
```

Reuse the batching discipline already implemented in PFETL Core.

Do not create one Tk `.after()` callback per log line.

---

# 9. Do not merge observability architectures

Studio process output shown in Core is **operator process logging**, not canonical PFETL observability.

Keep these concepts separate:

```text
PFETL observability
→ canonical Core structured events / JSONL / Control Plane

Studio server stdout/stderr
→ child-process operational logs surfaced by Core
```

Do not inject arbitrary Studio stdout lines into PFETL's forensic JSONL as if they were Core financial-pipeline events.

If useful, Core may wrap process lines in a lightweight presentation event:

```text
source = analytics_studio
stream = stdout | stderr
message = ...
timestamp = ...
```

for the Tk UI only.

This avoids contaminating Core's observability contract.

---

# 10. UI placement

Do not add a new analytical tab to PFETL Core.

Studio integration belongs in the **operator/control surface**.

Recommended location:

```text
System & Health
```

or a compact persistent card in the Run/System area.

Suggested card:

```text
┌──────────────────────────────────────────────┐
│ Analytics Studio                            │
│ ● Ready · 127.0.0.1:xxxxx                  │
│                                              │
│ [ Open Studio ] [ Restart ] [ Stop ]        │
│                                              │
│ Profile: current Settings + FinancialRules   │
│ Version: 1.1.0                               │
└──────────────────────────────────────────────┘
```

When stopped:

```text
● Stopped

[ Start Studio ]
```

When starting:

```text
● Starting...

[ Cancel / Stop ]
```

When failed:

```text
● Failed

[ Retry ] [ Show Logs ]
```

Keep the card operational, not analytical.

---

# 11. Optional Studio process-log panel

The Core UI may expose Studio process logs in either:

1. the existing Logs area with a clear `Analytics Studio` source selector; or
2. a small expandable log area/dialog from the Studio control card.

Preferred if easy:

```text
Logs
├── PFETL Live Narrative
├── PFETL Forensic JSONL
└── Analytics Studio Process
```

The Studio process view should:

- show recent stdout/stderr;
- be bounded;
- batch updates;
- distinguish stderr;
- support Clear;
- optionally Copy;
- not pretend to be Studio's analytical/forensic log viewer.

Studio's full operational analysis remains inside Analytics Studio.

---

# 12. Start behavior

On **Start Studio**:

1. validate active Settings + FinancialRules;
2. check whether an owned/live Studio process already exists;
3. resolve the bundled/installed Studio server command;
4. create/clean the runtime metadata target;
5. spawn the child;
6. begin stdout/stderr readers;
7. set state to `STARTING`;
8. poll `/healthz`;
9. set `READY`;
10. optionally open the browser.

Recommended UX:

- Start Studio may automatically open the browser once ready;
- Open Studio remains available afterward.

---

# 13. Open behavior

On **Open Studio**:

- require `READY`;
- use the host/port from validated runtime metadata;
- open the default browser using Python's `webbrowser` module;
- do not hardcode port 8080.

If status is stale, revalidate `/healthz` first.

---

# 14. Stop behavior

On **Stop Studio**:

```text
READY
↓
STOPPING
↓
graceful child termination
↓
bounded wait
↓
force terminate only if necessary
↓
STOPPED
```

Only terminate the process Core owns or a Studio process that has been strongly validated through runtime metadata + health identity.

Never kill an arbitrary process because it owns the same port.

Clean the Core-owned runtime file after shutdown.

---

# 15. Restart behavior

Restart is:

```text
Stop
↓
wait for STOPPED
↓
Start with current active profile
↓
wait for READY
```

This is also the correct way to apply a changed Core profile.

Do not attempt hot cross-process reconfiguration.

---

# 16. Core application shutdown

When PFETL Core closes:

- if Core launched the Studio process, stop it cleanly;
- do not leave an orphan child process by default.

If future UX deliberately supports “keep Studio running after Core exits,” that can be added later as an explicit preference.

For the initial integration, lifecycle ownership should be deterministic.

---

# 17. Core pipeline interaction

Studio is read-only, but Core already protects its warehouse during pipeline activity using `pipeline.lock`.

Recommended behavior:

### If Studio is stopped

Allow normal pipeline operation.

### If Studio is running and PFETL pipeline starts

Do not necessarily stop Studio.

Studio already detects the PFETL lock and avoids unsafe analytical reads.

The Core Studio card may display:

```text
Studio Ready · PFETL pipeline running
```

or:

```text
Studio Ready · Analytics temporarily locked
```

Do not add complex coordination unless real usage proves it necessary.

---

# 18. Packaging integration

When Core is packaged, include Studio as a bundled sibling application/server artifact.

Recommended conceptual layout:

```text
PFETL/
├── pfetl.exe
├── studio/
│   └── PFETL Analytics Studio.exe
└── _internal/
```

The exact PyInstaller output layout may differ.

The important rule:

> Core resolves Studio from a package-owned path, not PATH and not a development repository.

Create one resolver such as:

```python
resolve_studio_executable()
```

supporting:

```text
development environment
installed package/tool
packaged PFETL distribution
```

For packaged Core, the bundled path wins.

---

# 19. Version compatibility

Do not tightly couple exact patch versions.

Core should require a minimum compatible Studio contract version or simply validate the runtime API it needs.

For the initial integration, the required contract is:

```text
server launch arguments
runtime metadata
/healthz
loopback serving
clean termination
```

If `/healthz` identifies the expected application and the server starts successfully, Core can operate it.

Show Studio version in the UI for diagnostics.

Do not make Core fail merely because Studio moved from `1.1.0` to `1.1.1`.

---

# 20. Failure handling

Handle explicitly:

### Executable missing

```text
Analytics Studio is not installed/bundled.
```

### Invalid active profile

```text
Studio could not start because the active Settings/FinancialRules profile is invalid.
```

### Startup timeout

Show:

- status Failed;
- last process output;
- runtime metadata if available.

### Port/startup failure

Studio's auto-port mode should normally avoid this.

Surface the server error rather than silently retrying forever.

### Unexpected process exit

Monitor the child process.

If it exits while Core believes it is Ready:

```text
READY → FAILED
```

and surface the exit code plus recent stderr.

---

# 21. Tests

Add focused integration tests rather than a large new suite.

## Process service

Test:

- launch command construction;
- active profile paths passed correctly;
- runtime metadata parsing;
- health polling;
- startup timeout;
- missing executable;
- stop;
- restart;
- unexpected child exit.

## Logging

Test:

- stdout captured;
- stderr captured;
- lines enter the Core queue;
- UI batching remains bounded;
- log reader threads terminate with the process.

## UI state

Test:

```text
STOPPED
STARTING
READY
STOPPING
FAILED
```

button availability and status labels.

## Profile change

Test:

```text
Studio running with profile A
Core switches to profile B
→ restart required
```

and restart launches B.

## Packaging resolver

Test development and packaged-path resolution independently.

---

# 22. Explicit non-goals

Do not add:

```text
Studio charts inside CustomTkinter
Studio reports inside CustomTkinter
embedded browser/webview
NiceGUI thread inside Core
shared Python objects between apps
shared SQLite connection
shared DuckDB connection
financial IPC
automatic Studio updates
Studio tray when launched by Core
```

When Core launches Studio, it launches **server mode only**.

The Studio standalone tray remains for standalone use.

---

# 23. Expected Core files

Exact names should follow the current PFETL structure, but changes should be limited to areas equivalent to:

```text
contracts/
    studio lifecycle contract

application/operator or application services/
    Studio lifecycle orchestration

infrastructure/
    subprocess + health + executable resolver

presentation/desktop/
    Studio control card
    Studio process-log projection

bootstrap/
    dependency composition

packaging/
    include Studio executable

tests/
    focused Studio integration tests
```

Do not modify financial domain modules.

---

# 24. Acceptance checklist

The integration is complete when:

- Core starts normally without Studio running;
- Studio card shows `Stopped`;
- Start launches Studio server mode;
- active Settings + FinancialRules are passed correctly;
- Core remains responsive during startup;
- Studio stdout/stderr appear in the Tk UI without blocking it;
- `/healthz` determines Ready;
- Open Studio opens the resolved URL;
- Stop terminates the owned Studio process;
- Restart works;
- profile changes require/recommend restart rather than hot mutation;
- unexpected Studio exit becomes `Failed`;
- Core shutdown cleans up the owned Studio child;
- pipeline lock behavior remains safe;
- packaged Core finds the bundled Studio executable without PATH;
- no Studio analytical code is imported into Core;
- existing PFETL financial/golden tests remain unchanged and green.

---

# 25. Closure rule

After this integration is green:

> **Do not expand the PFETL Core UI with Analytics Studio functionality.**

Core remains:

```text
configure
run
observe
diagnose
recover
launch Studio
```

Studio remains:

```text
explore
analyze
visualize
report
```

That is the final product boundary.
