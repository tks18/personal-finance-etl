"""Infrastructure observability, event emission, forensic sinks, and listener orchestration.

Owns
----
- ObservabilityEmitter: Central event emitter managing multi-sink fan-out.
- SpanContext: Scoped execution span coordinator measuring durations and state transitions.
- CorrelationScope: Lightweight ambient context manager for operation correlation.
- ObservabilityDiagnostics: Canonical diagnostic facade for component-scoped logging.
- JsonlForensicSink: Append-only JSONL file sink for high-resolution diagnostic traces.
- AsyncObservabilityListener: Dedicated daemon thread owning file I/O operations.
- ObservabilityQueueSink: Non-blocking queue sink routing events across processes.
- BufferedEventQueue: Read/write queue used by the asynchronous listener.
- RedactionPolicy: Sensitive field redaction (PAN, passwords, credentials).
- LogRetentionManager: Diagnostic log cleanup and size management.

Does not own
-------------
- Canonical event schema and error models (owned by contracts.observability).
- Presentation narrative rendering (owned by presentation).
- Domain calculation mathematics (owned by domain).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.observability.archival import (
    DEFAULT_COMPRESSION_LEVEL,
    archive_run_trace,
    compress_bytes,
    decompress_bytes,
    retrieve_run_trace,
    retrieve_run_trace_events,
    retrieve_run_trace_text,
)
from personal_finance_etl.infrastructure.observability.context import (
    get_current_context,
    reset_current_context,
    set_current_context,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    ObservabilityDiagnostics,
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.observability.emitter import (
    CorrelationScope,
    ObservabilityEmitter,
    SpanContext,
    get_global_emitter,
    set_global_emitter,
)
from personal_finance_etl.infrastructure.observability.forensic_sink import (
    JsonlForensicSink,
)
from personal_finance_etl.infrastructure.observability.queue import (
    AsyncObservabilityListener,
    BufferedEventQueue,
    ObservabilityQueueSink,
    create_forensic_pipeline,
)
from personal_finance_etl.infrastructure.observability.redaction import (
    SENSITIVE_KEY_SUBSTRINGS,
    ConfigFingerprintDict,
    RedactionPolicy,
    RulesFingerprintDict,
    fingerprint_config,
    fingerprint_rules,
    hash_identifier,
    redact_dict,
    redact_text,
)
from personal_finance_etl.infrastructure.observability.retention import (
    LogRetentionManager,
)

__all__ = [
    "AsyncObservabilityListener",
    "BufferedEventQueue",
    "ConfigFingerprintDict",
    "CorrelationScope",
    "DEFAULT_COMPRESSION_LEVEL",
    "JsonlForensicSink",
    "LogRetentionManager",
    "ObservabilityDiagnostics",
    "ObservabilityEmitter",
    "ObservabilityQueueSink",
    "RedactionPolicy",
    "RulesFingerprintDict",
    "SENSITIVE_KEY_SUBSTRINGS",
    "SpanContext",
    "archive_run_trace",
    "compress_bytes",
    "create_forensic_pipeline",
    "decompress_bytes",
    "fingerprint_config",
    "fingerprint_rules",
    "get_current_context",
    "get_global_emitter",
    "get_observability_diagnostics",
    "hash_identifier",
    "redact_dict",
    "redact_text",
    "reset_current_context",
    "retrieve_run_trace",
    "retrieve_run_trace_events",
    "retrieve_run_trace_text",
    "set_current_context",
    "set_global_emitter",
]
