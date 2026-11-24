"""High-performance forensic event data model, inverted indexing, and LRU trace cache.

Owns
----
- ForensicEvent: Immutable, typed dataclass representing a single forensic telemetry event.
- ParsedTrace: Indexed collection of events with inverted indices (severity, stage, failures).
- TraceCache: Size-bounded LRU cache of ParsedTrace instances keyed by (path, size, mtime_ns).
- parse_trace_file: Resilient JSONL parser extracting structured events and building indices.

Does not own
-------------
- JSONL file writing or live event sink emission (owned by infrastructure.observability).
- CustomTkinter UI widgets or rendering (owned by presentation.desktop.logs_tab).
"""

from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

__all__ = [
    "ForensicEvent",
    "ParsedTrace",
    "TraceCache",
    "format_display_timestamp",
    "format_full_local_timestamp",
    "get_trace_cache",
    "parse_trace_file",
]


def format_display_timestamp(iso_str: str) -> str:
    """Convert an ISO-8601 UTC timestamp to local system time (HH:MM:SS)."""
    if not iso_str:
        return "-"
    try:
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone().strftime("%H:%M:%S")
    except Exception:  # pylint: disable=broad-exception-caught
        return iso_str[11:19] if len(iso_str) >= 19 else iso_str


def format_full_local_timestamp(iso_str: str) -> str:
    """Format full local timestamp with timezone name and UTC reference."""
    if not iso_str or iso_str == "-":
        return "-"
    try:
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        local_dt = dt.astimezone()
        tz_name = local_dt.tzname() or "Local"
        local_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")
        return f"{local_str} {tz_name} (UTC: {iso_str})"
    except Exception:  # pylint: disable=broad-exception-caught
        return iso_str


@dataclass(slots=True)
class ForensicEvent:  # pylint: disable=too-many-instance-attributes
    """Immutable, typed representation of a single forensic log event."""

    raw_index: int
    timestamp_iso: str
    timestamp_display: str
    event_code: str
    severity: str
    presentation_kind: str
    outcome: str
    message: str
    normalized_search_text: str

    # Context fields
    run_id: str = ""
    stage: str = ""
    component: str = ""
    operation: str = ""
    operation_id: str = ""
    parent_operation_id: str = ""
    entity_type: str = ""
    entity_id: str = ""
    duration_ms: float | None = None
    rows: int | None = None
    attempt: int | None = None
    provider: str = ""
    worker_id: str = ""
    batch_id: str = ""
    commit_state: str = ""
    settings_hash: str = ""
    rules_hash: str = ""

    # Error fields
    error_type: str = ""
    error_message: str = ""
    error_details: str = ""

    # Complete raw event dictionary
    raw_data: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, item: str) -> Any:
        """Allow dictionary-style key access for backwards compatibility."""
        if item in self.raw_data:
            return self.raw_data[item]
        return getattr(self, item, None)

    def get(self, item: str, default: Any = None) -> Any:
        """Allow dictionary-style get for backwards compatibility."""
        if item in self.raw_data:
            return self.raw_data[item]
        val = getattr(self, item, None)
        return val if val is not None else default

    @classmethod
    def from_dict(cls, data: dict[str, Any], raw_index: int) -> ForensicEvent:
        """Construct ForensicEvent from raw dictionary, precomputing normalized search text."""
        iso_ts = str(data.get("timestamp") or "")
        display_ts = format_display_timestamp(iso_ts)
        code = str(data.get("event_code") or "GENERIC_DIAGNOSTIC")
        sev = str(data.get("severity") or "INFO").upper()
        p_kind = str(data.get("presentation_kind") or "LOG")
        out = str(data.get("outcome") or "COMPLETED").upper()
        msg = str(data.get("message") or "")

        raw_ctx = data.get("context")
        ctx: dict[str, Any] = raw_ctx if isinstance(raw_ctx, dict) else {}
        raw_err = data.get("error")
        err: dict[str, Any] = raw_err if isinstance(raw_err, dict) else {}

        run_id = str(ctx.get("run_id") or "")
        stage = str(ctx.get("stage") or "").upper()
        comp = str(ctx.get("component") or "")
        op = str(ctx.get("operation") or "")
        op_id = str(ctx.get("operation_id") or "")
        parent_op_id = str(ctx.get("parent_operation_id") or "")
        entity_type = str(ctx.get("entity_type") or "")
        entity_id = str(ctx.get("entity_id") or "")

        dur = ctx.get("duration_ms")
        duration_ms = float(dur) if isinstance(dur, (int, float)) else None

        r = ctx.get("rows")
        rows = int(r) if isinstance(r, int) else None

        att = ctx.get("attempt")
        attempt = int(att) if isinstance(att, int) else None

        provider = str(ctx.get("provider") or "")
        worker_id = str(ctx.get("worker_id") or "")
        batch_id = str(ctx.get("batch_id") or "")
        commit_state = str(ctx.get("commit_state") or "")
        settings_hash = str(ctx.get("settings_hash") or "")
        rules_hash = str(ctx.get("rules_hash") or "")

        err_type = str(err.get("error_type") or err.get("exception_type") or "")
        err_msg = str(err.get("message") or err.get("exception_message") or "")
        err_det = str(err.get("details") or err.get("traceback_summary") or "")

        # Item 11: Single precomputed lowercase normalized search text
        tokens = [
            iso_ts,
            display_ts,
            code,
            sev,
            p_kind,
            out,
            msg,
            run_id,
            stage,
            comp,
            op,
            op_id,
            entity_type,
            entity_id,
            provider,
            worker_id,
            batch_id,
            err_type,
            err_msg,
            err_det,
        ]
        normalized_search = " ".join(t.lower() for t in tokens if t)

        return cls(
            raw_index=raw_index,
            timestamp_iso=iso_ts,
            timestamp_display=display_ts,
            event_code=code,
            severity=sev,
            presentation_kind=p_kind,
            outcome=out,
            message=msg,
            normalized_search_text=normalized_search,
            run_id=run_id,
            stage=stage,
            component=comp,
            operation=op,
            operation_id=op_id,
            parent_operation_id=parent_op_id,
            entity_type=entity_type,
            entity_id=entity_id,
            duration_ms=duration_ms,
            rows=rows,
            attempt=attempt,
            provider=provider,
            worker_id=worker_id,
            batch_id=batch_id,
            commit_state=commit_state,
            settings_hash=settings_hash,
            rules_hash=rules_hash,
            error_type=err_type,
            error_message=err_msg,
            error_details=err_det,
            raw_data=data,
        )


@dataclass
class ParsedTrace:
    """Collection of parsed events with precomputed inverted indices and dynamic filters."""

    path: Path
    file_size: int
    mtime_ns: int
    events: list[ForensicEvent] = field(default_factory=list[ForensicEvent])

    # Item 12: Inverted indexes
    severity_index: dict[str, set[int]] = field(default_factory=dict[str, set[int]])
    stage_index: dict[str, set[int]] = field(default_factory=dict[str, set[int]])
    failures_indices: set[int] = field(default_factory=set[int])

    # Item 15: Dynamically discovered options
    available_stages: list[str] = field(default_factory=list[str])
    available_severities: list[str] = field(default_factory=list[str])

    @property
    def total_events(self) -> int:
        """Total number of parsed events in trace."""
        return len(self.events)

    @property
    def filepath(self) -> str:
        """String representation of trace path."""
        return str(self.path)

    @property
    def all_stages(self) -> list[str]:
        """Backward-compatible alias for available stages."""
        return self.available_stages

    @property
    def all_severities(self) -> list[str]:
        """Backward-compatible alias for available severities."""
        return self.available_severities

    @property
    def failed_indices(self) -> set[int]:
        """Backward-compatible alias for failures indices."""
        return self.failures_indices

    def __len__(self) -> int:
        """Return the count of events in trace."""
        return len(self.events)

    def filter_events(
        self,
        severity: str = "ALL",
        stage: str = "ALL",
        failures_only: bool = False,
        query: str = "",
    ) -> list[int]:
        """Filter event indices using inverted set intersections and debounced text search."""
        candidate_sets: list[set[int]] = []

        # 1. Failures constraint
        if failures_only:
            candidate_sets.append(self.failures_indices)

        # 2. Severity constraint
        sev_clean = severity.strip().upper()
        if sev_clean and sev_clean not in ("ALL", "ALL SEVERITIES"):
            matching_sev = self.severity_index.get(sev_clean, set())
            candidate_sets.append(matching_sev)

        # 3. Stage constraint
        stg_clean = stage.strip().upper()
        if stg_clean and stg_clean not in ("ALL", "ALL STAGES"):
            matching_stg = self.stage_index.get(stg_clean, set())
            candidate_sets.append(matching_stg)

        # Intersect candidate sets
        if candidate_sets:
            # Sort sets by length to minimize intersection cost
            candidate_sets.sort(key=len)
            surviving: set[int] = set(candidate_sets[0])
            for s in candidate_sets[1:]:
                surviving &= s
            filtered_indices = sorted(surviving)
        else:
            filtered_indices = list(range(len(self.events)))

        # 4. Normalized substring query
        q_clean = query.strip().lower()
        if q_clean:
            filtered_indices = [
                idx
                for idx in filtered_indices
                if q_clean in self.events[idx].normalized_search_text
            ]

        return filtered_indices


class TraceCache:
    """Size-bounded LRU cache for parsed JSONL traces with mtime invalidation."""

    def __init__(self, capacity: int = 4) -> None:
        self.capacity: int = max(1, capacity)
        self._cache: OrderedDict[tuple[str, int, int], ParsedTrace] = OrderedDict()

    def __len__(self) -> int:
        """Return the number of entries currently stored in cache."""
        return len(self._cache)

    def get(self, path: Path | str) -> ParsedTrace | None:
        """Retrieve cached trace if path exists and file size/mtime match."""
        try:
            file_path = Path(path)
            stat = file_path.stat()
            key = (str(file_path.resolve()), stat.st_size, stat.st_mtime_ns)
        except OSError:
            return None

        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def put(self, trace: ParsedTrace) -> None:
        """Store parsed trace into cache, evicting oldest item if capacity is reached."""
        key = (str(trace.path.resolve()), trace.file_size, trace.mtime_ns)
        if key in self._cache:
            self._cache.move_to_end(key)
        else:
            if len(self._cache) >= self.capacity:
                self._cache.popitem(last=False)
            self._cache[key] = trace

    def clear(self) -> None:
        """Evict all items from the cache."""
        self._cache.clear()


_GLOBAL_TRACE_CACHE = TraceCache(capacity=4)


def get_trace_cache() -> TraceCache:
    """Access the application-wide singleton TraceCache."""
    return _GLOBAL_TRACE_CACHE


def parse_trace_file(path: Path | str, max_lines: int | None = None) -> ParsedTrace:
    """Parse JSONL trace file into an indexed ParsedTrace instance."""
    file_path = Path(path)
    stat = file_path.stat()
    events: list[ForensicEvent] = []
    sev_index: dict[str, set[int]] = {}
    stg_index: dict[str, set[int]] = {}
    failures: set[int] = set()
    discovered_stages: set[str] = set()
    discovered_severities: set[str] = set()

    with open(file_path, encoding="utf-8", errors="replace") as f:
        for idx, line in enumerate(f):
            if max_lines is not None and idx >= max_lines:
                break
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                if not isinstance(data, dict):
                    continue
            except Exception:  # pylint: disable=broad-exception-caught
                continue

            event = ForensicEvent.from_dict(data, raw_index=idx)
            events.append(event)

            # Update indices
            cur_idx = len(events) - 1
            if event.severity:
                sev_index.setdefault(event.severity, set()).add(cur_idx)
                discovered_severities.add(event.severity)

            if event.stage:
                stg_index.setdefault(event.stage, set()).add(cur_idx)
                discovered_stages.add(event.stage)

            if event.severity in ("ERROR", "FATAL") or event.outcome == "FAILED":
                failures.add(cur_idx)

    parsed = ParsedTrace(
        path=file_path,
        file_size=stat.st_size,
        mtime_ns=stat.st_mtime_ns,
        events=events,
        severity_index=sev_index,
        stage_index=stg_index,
        failures_indices=failures,
        available_stages=sorted(discovered_stages),
        available_severities=sorted(discovered_severities),
    )

    get_trace_cache().put(parsed)
    return parsed
