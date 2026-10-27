"""Infrastructure observability, forensic sinks, and asynchronous listener orchestration.

Owns
----
- JsonlForensicSink: Append-only JSONL file sink for high-resolution diagnostic traces.
- AsyncObservabilityListener: Dedicated daemon thread owning file I/O operations.
- ObservabilityQueueSink: Non-blocking queue sink routing events across processes.
- BufferedEventQueue: Read/write queue used by the asynchronous listener.
- create_forensic_pipeline: Assembles asynchronous queue, listener, and JSONL forensic sink.

Does not own
-------------
- Canonical event schema and error models (owned by contracts.observability).
- Application event dispatch and span context timing (owned by application.observability).
- Presentation narrative rendering (owned by presentation).
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
    "ConfigFingerprintDict",
    "DEFAULT_COMPRESSION_LEVEL",
    "AsyncObservabilityListener",
    "BufferedEventQueue",
    "JsonlForensicSink",
    "LogRetentionManager",
    "ObservabilityQueueSink",
    "RedactionPolicy",
    "RulesFingerprintDict",
    "SENSITIVE_KEY_SUBSTRINGS",
    "archive_run_trace",
    "compress_bytes",
    "create_forensic_pipeline",
    "decompress_bytes",
    "fingerprint_config",
    "fingerprint_rules",
    "hash_identifier",
    "redact_dict",
    "redact_text",
    "retrieve_run_trace",
    "retrieve_run_trace_events",
    "retrieve_run_trace_text",
]
