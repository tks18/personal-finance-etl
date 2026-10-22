"""Infrastructure observability, forensic sinks, and asynchronous listener orchestration.

Owns
----
- JsonlForensicSink: Append-only JSONL file sink for high-resolution diagnostic traces.
- AsyncObservabilityListener: Dedicated daemon thread owning file I/O operations.
- ObservabilityQueueSink: Non-blocking queue sink routing events across processes.
- EventQueue: Protocol unifying thread and multiprocessing event queues.

Does not own
-------------
- Canonical event schema and error models (owned by contracts.observability).
- Application event dispatch and span context timing (owned by application.observability).
- Presentation narrative rendering (owned by presentation).
"""

from __future__ import annotations

from personal_finance_etl.infrastructure.observability.forensic_sink import (
    JsonlForensicSink,
)
from personal_finance_etl.infrastructure.observability.queue import (
    AsyncObservabilityListener,
    EventQueue,
    ObservabilityQueueSink,
)

__all__ = [
    "AsyncObservabilityListener",
    "EventQueue",
    "JsonlForensicSink",
    "ObservabilityQueueSink",
]
