# Personal Finance ETL --- Observability Finalization & Legacy Eradication Plan

## Purpose

The structured observability architecture already exists. This plan
finishes the migration.

The objective is to remove every remaining legacy logging/status path,
make the structured event model the **only semantic observability
interface**, substantially improve forensic debugging and user-facing
run narratives, and certify that the result preserves application
performance.

This is an implementation plan, not a redesign of financial
architecture.

## Final-state constitution

``` text
Producer
   │
   ▼
ObservabilityEvent
   │
   ├──► User Narrative ─────► CLI / Desktop
   ├──► Forensic Trace ─────► async structured JSONL
   └──► Durable Evidence ────► Control Plane
```

> **One semantic event. Multiple intentional projections. No legacy
> logging semantics.**

The producer states what happened. Presentation decides how to show it.
Infrastructure decides how to persist diagnostics. The Control Plane
retains durable operational evidence.

------------------------------------------------------------------------

# Non-negotiable completion gates

The migration is complete only when all of these are true:

-   `ObservabilityEvent` is the sole machine-significant event contract.
-   `infer_log_level()` is deleted.
-   No message text, prefix, emoji, or substring determines severity or
    event semantics.
-   `EngineStatusMessage` is removed from logging/status
    responsibilities.
-   `QueueStream` is removed or reduced to an explicit raw stdout/stderr
    compatibility adapter emitting canonical events.
-   No production subsystem uses a parallel semantic logging vocabulary.
-   Main-process and worker forensic output use asynchronous
    queue/listener delivery.
-   The full serialized forensic payload is redacted, including context.
-   Configuration/rules fingerprint events contain real fingerprints.
-   No financial/data computation is performed solely for logging.
-   No default observability exists inside numerical/FIFO hot loops.
-   Real cached/cold performance certification passes.
-   Architecture tests prevent the legacy patterns from returning.

------------------------------------------------------------------------

# Phase 0 --- Freeze Evidence & Build the Demolition Ledger

## Implement

Re-run the current observability census and create a complete migration
ledger covering:

-   every `EngineStatusMessage(...)` construction;
-   every `logging.*` call;
-   every `infer_log_level` reference/export;
-   `QueueStream`;
-   legacy logger setup helpers;
-   direct forensic sink registrations;
-   stdout/stderr capture;
-   UI progress/data transport;
-   provider and worker logging;
-   lifecycle/recovery logging;
-   configuration/rules dumps.

Classify every item:

``` text
MIGRATE
KEEP_AS_ADAPTER
DELETE
SEPARATE_DATA_TRANSPORT
```

Capture current cached/cold runtime, trace size, event count and
compression time.

## Enterprise implementation

Do not remove compatibility code until every current consumer has an
explicit destination in the new model.

## Complete when

-   100% of legacy callsites are classified;
-   benchmark evidence is recorded;
-   no unknown logging/status path remains.

------------------------------------------------------------------------

# Phase 1 --- Close the Canonical Event Contract

## Implement

Review and finalize:

``` text
EventCode
DiagnosticSeverity
PresentationKind
EventOutcome
ObservabilityContext
ErrorDetails
ObservabilityEvent
```

Reuse existing:

``` text
EngineStage
FailureDomain
CommitState
run_id
```

Add/adjust event codes only where current migration reveals genuine
semantic gaps.

Define strict bounded context rules:

-   scalar values;
-   short strings;
-   small bounded collections only where justified;
-   no DataFrame/LazyFrame;
-   no arbitrary payload blobs;
-   no anonymous `Any` context.

## Enterprise implementation

Event codes are stable machine contracts. Messages remain human
descriptions and may evolve without changing behavior.

## Complete when

-   all remaining legacy events map cleanly to canonical event codes;
-   serialization/validation tests cover every event family;
-   no event requires parsing its message to understand what happened.

------------------------------------------------------------------------

# Phase 2 --- Make Forensic Delivery Truly Asynchronous

## Implement

Wire the existing queue/listener infrastructure into the **actual normal
pipeline**:

``` text
ObservabilityEmitter
        ↓
ObservabilityQueueSink
        ↓
AsyncObservabilityListener
        ↓
JsonlForensicSink
```

The listener owns:

-   JSON serialization;
-   redaction;
-   file writes;
-   buffering/flushing;
-   orderly shutdown.

Use the same architecture for main-process and worker events.

Tune buffering so normal events do not trigger a disk flush per
emission.

Guarantee final drain/flush during teardown.

## Enterprise implementation

Application threads/processes enqueue diagnostics; they do not
synchronously perform forensic file I/O.

Backpressure/failure behavior must be explicit and must never silently
corrupt financial execution.

## Complete when

-   direct synchronous forensic sink registration is gone;
-   producers never write forensic files;
-   worker and main events share one listener-owned trace;
-   shutdown tests prove queued events are drained;
-   sink failure cannot falsely fail a financially successful run.

------------------------------------------------------------------------

# Phase 3 --- Full-Payload Redaction & Privacy Hardening

## Implement

Move redaction to the complete serialized event payload.

Protect:

``` text
message
error details
context
entity identifiers
provider metadata
configuration summaries
```

Apply central policies:

``` text
SAFE
HASH
REDACT
OMIT
```

Add adversarial tests for:

-   PAN/account-like identifiers;
-   API keys/tokens;
-   credentials;
-   secrets nested inside context;
-   bearer tokens;
-   sensitive paths/payload fragments.

## Enterprise implementation

Redaction happens once at the forensic boundary, not through developer
memory at individual callsites.

## Complete when

-   full-payload redaction tests pass;
-   no known sensitive class can bypass context serialization;
-   UI narrative exposes only intentionally safe metadata.

------------------------------------------------------------------------

# Phase 4 --- Configuration & Rules Provenance

## Implement

Wire the existing configuration/rules fingerprinting into real
observability events.

`SYSTEM_CONFIG_FINGERPRINT` must carry actual safe fingerprint context:

``` text
settings_fingerprint
financial_rules_fingerprint
```

Remove legacy full JSON configuration/rules dumps from normal logger
paths.

If forensic snapshots remain useful, emit a deliberately redacted
structured summary rather than unrestricted model dumps.

## Enterprise implementation

Use fingerprints for reproducibility and Control Plane correlation; do
not duplicate entire policy objects into logs.

## Complete when

-   fingerprint helper is used in production;
-   fingerprint event contains real values;
-   unrestricted config/rules debug dumps are gone;
-   replay/debug workflows can correlate a run with its policy
    fingerprints.

------------------------------------------------------------------------

# Phase 5 --- Separate Status from Data Transport

## Implement

Audit every remaining use of:

``` python
EngineStatusMessage.data
```

Create a dedicated typed transport/result contract for UI-bound tabular
data if the capability is still required.

The observability channel must carry:

``` text
state
progress
diagnostic context
presentation intent
```

not arbitrary DataFrames.

Migrate progress/status producers to `ObservabilityEvent`.

## Enterprise implementation

Observability and application-result transport are separate
responsibilities even when both ultimately reach the UI.

## Complete when

-   no DataFrame travels inside an observability/status event;
-   data/result callbacks have an explicit typed contract;
-   `EngineStatusMessage.data` is deleted.

------------------------------------------------------------------------

# Phase 6 --- Retire `EngineStatusMessage`

## Implement

Migrate all remaining direct `EngineStatusMessage(...)` constructions to
canonical observability events or the new result/data transport
contract.

Update:

-   CLI consumers;
-   Desktop consumers;
-   worker callbacks;
-   progress handling;
-   optional-operation status;
-   error presentation.

Remove dual-type consumer APIs such as:

``` text
EngineStatusMessage | ObservabilityEvent
```

## Enterprise implementation

There must be one semantic status/event language across presentation
surfaces.

## Complete when

-   production search returns zero `EngineStatusMessage` constructions;
-   CLI/Desktop consume canonical events only;
-   compatibility unions are gone;
-   UI behavior/regression tests pass.

------------------------------------------------------------------------

# Phase 7 --- Retire String/Stdout Legacy Semantics

## Implement

Delete `infer_log_level()` and remove its exports/tests.

Rework `QueueStream`.

Preferred final state:

``` text
stdout → RAW_STDOUT event
stderr → RAW_STDERR event
```

only where third-party or transitional capture is genuinely required.

Do not infer:

``` text
SUCCESS
STEP
WARNING
ERROR
```

from words, prefixes or emojis.

If no production dependency requires stdout/stderr interception after
migration, remove `QueueStream` entirely.

## Enterprise implementation

Raw process text is compatibility telemetry, never semantic application
state.

## Complete when

-   `infer_log_level` does not exist;
-   constitutional tests explicitly prohibit it;
-   no severity/event classification parses prose;
-   `QueueStream` is either canonicalized or removed.

------------------------------------------------------------------------

# Phase 8 --- Normalize Python Logger Infrastructure

## Implement

Classify every helper in the old `infrastructure/logging` package:

``` text
KEEP
MOVE
DELETE
```

Prefer module loggers rooted under:

``` text
personal_finance_etl.*
```

over imported global logger objects.

Retain Python `logging` only where it still provides value for:

-   third-party/library integration;
-   compatibility capture;
-   low-level infrastructure diagnostics not represented as application
    events.

Do not allow Python logging to become a second application-event system.

Remove unused helpers such as file/queue setup functions that no longer
have production consumers.

## Enterprise implementation

Python logging becomes an infrastructure compatibility mechanism beneath
observability, not a peer architecture.

## Complete when

-   every legacy helper has an explicit reason to exist;
-   dead helpers/exports are deleted;
-   logger hierarchy/configuration is centralized;
-   no domain/application behavior depends on Python-log message text.

------------------------------------------------------------------------

# Phase 9 --- Dramatically Improve Forensic Debuggability

## Implement

Review every major subsystem and ensure the forensic trace can
reconstruct its execution:

### Run lifecycle

-   start/end;
-   stage transitions;
-   commit state;
-   rollback;
-   recovery;
-   failure domain.

### Ingestion/providers

-   source/provider;
-   entity;
-   interval;
-   attempt/retry;
-   cache state;
-   completeness outcome.

### Transformations/warehouse

-   contract/table;
-   operation;
-   known row counts;
-   duration;
-   publication outcome.

### Investments

-   batch/ISIN correlation;
-   worker identity;
-   major FIFO/reconciliation/valuation boundaries;
-   no row-level hot-loop noise.

### Tax/FIRE

-   major workflow boundaries;
-   event/simulation counts already known;
-   policy fingerprints;
-   stochastic run correlation.

### Recovery

-   validation;
-   stage/install;
-   rollback;
-   final certainty state.

Add context only when it answers a realistic debugging question.

## Enterprise implementation

A forensic trace should let a maintainer answer:

``` text
what was happening?
where?
for which entity?
under which run/operation?
with what inputs/policy identity?
what happened next?
why did it fail?
```

without reconstructing meaning from neighboring prose.

## Complete when

-   each major subsystem has a defined diagnostic story;
-   exception context is captured once at the owning boundary;
-   duplicate exception echo is eliminated;
-   trace remains bounded and queryable.

------------------------------------------------------------------------

# Phase 10 --- Dramatically Improve the User Run Narrative

## Implement

Refine the CLI/Desktop narrative around meaningful lifecycle milestones.

Target normal successful run:

``` text
20–40 rendered events
```

Show:

-   stage;
-   meaningful operation;
-   duration;
-   known row/entity counts;
-   cache state;
-   progress;
-   concise recovery state;
-   actionable failure summary;
-   run/debug identifier when needed.

Suppress:

-   implementation chatter;
-   stack traces;
-   worker internals;
-   repetitive per-entity success events;
-   forensic-only context.

Keep presentation semantics sink-owned.

## Enterprise implementation

The UI tells the story of the financial run, not the story of the Python
implementation.

## Complete when

-   CLI and Desktop project the same semantic events consistently;
-   successful runs are visually clean and scannable;
-   failures are actionable without being noisy;
-   no UI renderer infers semantics from prose.

------------------------------------------------------------------------

# Phase 11 --- Control Plane & Trace Lifecycle Finalization

## Implement

Keep Control Plane persistence selective.

Retain:

-   run lifecycle;
-   failure telemetry;
-   provider outcomes;
-   sync summaries;
-   simulation records;
-   compressed forensic trace.

Do not add per-debug-event SQLite writes.

Benchmark trace archival:

``` text
read
compress
persist
retrieve
decompress
```

Validate compression level and retention policy against realistic
enlarged traces.

Ensure trace archival remains non-fatal.

## Enterprise implementation

Control Plane proves the run. JSONL reconstructs the run. They correlate
by `run_id` without duplicating responsibilities.

## Complete when

-   durable evidence is selective;
-   trace retrieval works for success/failure runs;
-   archival overhead is bounded;
-   archival failure cannot corrupt financial lifecycle truth.

------------------------------------------------------------------------

# Phase 12 --- Constitutional Legacy-Eradication Tests

## Implement

Strengthen architecture tests so the repository itself rejects
regression.

Explicitly prohibit:

``` text
infer_log_level
EngineStatusMessage
message-prefix machine semantics
severity inference from strings/emojis
direct application forensic file writes
unredacted structured payloads
logging-triggered Polars materialization
default hot-loop observability
parallel semantic logging contracts
```

Add positive architecture assertions:

-   canonical event contract exists;
-   CLI/Desktop consume it;
-   forensic pipeline uses async listener;
-   context is bounded/typed;
-   Control Plane trace correlation exists.

## Enterprise implementation

The final architecture should be enforceable, not merely documented.

## Complete when

-   tests fail if any legacy mechanism is reintroduced;
-   test names accurately match what they certify;
-   the observability constitution is executable.

------------------------------------------------------------------------

# Phase 13 --- Real Performance Certification

## Benchmark matrix

Run repeated representative benchmarks:

``` text
cached NORMAL
cached DEBUG
cold NORMAL
cold DEBUG
```

Use at least 5 runs per mode; 10 is preferred.

Capture:

``` text
median
p25
p75
min/max
event count
trace size
compression time
CPU impact where useful
```

Compare against the pre-modernization baseline around:

``` text
cached ~28 s
cold   ~48 s
```

## Gates

  Criterion                            Acceptance
  -------------------------------- --------------
  Cached NORMAL regression           ≤0.5% median
  Cold NORMAL regression             ≤0.5% median
  DEBUG regression                   ≤1.5% median
  Logging-only Polars collects                  0
  Default hot-loop observability                0
  Sensitive payload leaks                       0
  Legacy semantic interfaces                    0
  Uncorrelated critical events                  0

If performance exceeds the budget, optimize observability before
release.

## Complete when

-   real pipeline evidence is retained;
-   performance gates pass;
-   normal UI remains responsive;
-   debug trace remains diagnostically rich;
-   no waiver is required.

------------------------------------------------------------------------

# Phase 14 --- Canonical Documentation & Freeze

## Implement

Update only permanent documentation affected by the final architecture:

-   reliability/observability architecture;
-   developer engineering standards;
-   testing/validation;
-   debugging/tooling workflow;
-   CLI/Desktop operating guidance;
-   root README only at SHOW depth.

Remove release-number language from canonical docs.

Document the final invariant:

> **User logs explain the run. Debug traces reconstruct the run. Control
> Plane proves the run happened.**

Archive/delete temporary migration plans once the implementation is
certified.

## Complete when

-   code, tests and docs describe one observability architecture;
-   legacy logging interfaces are zero;
-   performance certification is recorded;
-   the observability architecture is frozen.

------------------------------------------------------------------------

# Final Acceptance State

``` text
Application code
      │
      ▼
ObservabilityEvent
      │
      ├──► Beautiful user narrative
      │
      ├──► Rich asynchronous forensic trace
      │
      └──► Selective durable operational evidence
```

There is no second semantic logger.

There is no severity inference from prose.

There is no DataFrame hidden inside a status message.

There is no synchronous forensic disk write in the execution hot path.

There is no unredacted context payload.

There is no logging-driven financial computation.

There is no legacy observability compatibility layer left merely because
deleting it felt impolite.

## Release definition

The observability finalization release is complete only when:

> **the new observability pattern is not merely the preferred path; it
> is the only supported application observability architecture.**
