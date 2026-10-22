"""Listener-owned append-only JSONL forensic observability sink.

Owns
----
- JsonlForensicSink: Append-only JSONL file sink for high-resolution diagnostic traces.
- Direct disk file writing owned exclusively by the background listener thread.
- Thread-safe file handle management and structured event serialization.

Does not own
-------------
- Queue listener lifecycle and multi-process IPC (owned by infrastructure.observability.queue).
- Presentation narrative formatting or terminal rendering (owned by presentation).
- Event creation and contextual span tracking (owned by application.observability).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import TextIO, cast

from personal_finance_etl.contracts.observability import (
    ObservabilityEvent,
    ObservabilitySink,
)
from personal_finance_etl.infrastructure.observability.redaction import (
    redact_dict,
    redact_text,
)

__all__ = ["JsonlForensicSink"]


class JsonlForensicSink(ObservabilitySink):
    """Append-only JSONL forensic sink owned exclusively by the background listener.

    Guarantees no producer performs synchronous file I/O on critical execution paths.
    All disk writes are serialized and formatted as single-line JSON records.
    """

    def __init__(self, log_path: str | Path, buffer_size: int = 1) -> None:
        self.log_path = Path(log_path)
        self.buffer_size = buffer_size
        self._lock = threading.Lock()
        self._file: TextIO | None = None
        self._pending_writes: int = 0

        # Ensure parent directory exists immediately
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _ensure_file_open(self) -> TextIO:
        """Lazily open the target log file handle in append mode."""
        if self._file is None or self._file.closed:
            self._file = open(  # pylint: disable=consider-using-with
                self.log_path, mode="a", encoding="utf-8", buffering=8192
            )
        return self._file

    def emit(self, event: ObservabilityEvent) -> None:
        """Append a single structured ObservabilityEvent line in JSON format.

        Parameters
        ----------
        event : ObservabilityEvent
            The canonical structured event to append to the trace file.
        """
        payload = event.to_dict()
        if "message" in payload and isinstance(payload["message"], str):
            payload["message"] = redact_text(payload["message"])
        if "error" in payload and isinstance(payload["error"], dict):
            payload["error"] = redact_dict(cast(dict[str, object], payload["error"]))

        line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"
        with self._lock:
            f = self._ensure_file_open()
            f.write(line)
            self._pending_writes += 1
            if self._pending_writes >= self.buffer_size:
                f.flush()
                self._pending_writes = 0

    def flush(self) -> None:
        """Flush buffered writes to physical disk storage."""
        with self._lock:
            if self._file is not None and not self._file.closed:
                self._file.flush()
                self._pending_writes = 0

    def close(self) -> None:
        """Flush remaining buffered writes and close the underlying file handle."""
        with self._lock:
            if self._file is not None and not self._file.closed:
                try:
                    self._file.flush()
                finally:
                    self._file.close()
                    self._file = None
                    self._pending_writes = 0
