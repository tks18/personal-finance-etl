"""Infrastructure observability, forensic sinks, and asynchronous listener orchestration.

Owns
----
- JsonlForensicSink: Append-only JSONL file sink for high-resolution diagnostic traces.
- AsyncObservabilityListener: Dedicated daemon thread owning file I/O operations.
- ObservabilityQueueSink: Non-blocking queue sink routing events across processes.
- EventQueue: Protocol unifying thread and multiprocessing event queues.
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
)
from personal_finance_etl.infrastructure.observability.forensic_sink import (
    JsonlForensicSink,
)
from personal_finance_etl.infrastructure.observability.queue import (
    AsyncObservabilityListener,
    EventQueue,
    ObservabilityQueueSink,
    create_forensic_pipeline,
)
from personal_finance_etl.infrastructure.observability.redaction import (
    SENSITIVE_KEY_SUBSTRINGS,
    ConfigFingerprintDict,
    RedactionPolicy,
    fingerprint_config,
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
    "EventQueue",
    "JsonlForensicSink",
    "LogRetentionManager",
    "ObservabilityQueueSink",
    "RedactionPolicy",
    "SENSITIVE_KEY_SUBSTRINGS",
    "archive_run_trace",
    "compress_bytes",
    "create_forensic_pipeline",
    "decompress_bytes",
    "fingerprint_config",
    "hash_identifier",
    "redact_dict",
    "redact_text",
    "retrieve_run_trace",
]
