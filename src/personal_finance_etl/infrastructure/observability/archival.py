"""Execution trace and log archival engine.

Owns
----
- Resilient compression and storage of execution traces and log files into Control Plane.
- Benchmarked zlib compression policy balancing compression ratio and throughput.
- Non-fatal degradation guarantees ensuring archival failure never interrupts successful runs.
- Round-trip trace decompression and retrieval for forensic audits.

Does not own
-------------
- Control Plane schema definitions or SQLite connection lifecycle (owned by control_plane).
- Active forensic JSONL stream emission (owned by infrastructure.observability.forensic_sink).
"""

from __future__ import annotations

import json
import logging
import sqlite3
import zlib
from pathlib import Path
from typing import cast

from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane

logger = logging.getLogger("personal_finance_etl.observability.archival")

__all__ = [
    "DEFAULT_COMPRESSION_LEVEL",
    "archive_run_trace",
    "compress_bytes",
    "decompress_bytes",
    "retrieve_run_trace",
    "retrieve_run_trace_events",
    "retrieve_run_trace_text",
]

DEFAULT_COMPRESSION_LEVEL = 6


def compress_bytes(data: bytes, level: int = DEFAULT_COMPRESSION_LEVEL) -> bytes:
    """Compress raw payload bytes using zlib.

    Parameters
    ----------
    data : bytes
        Raw uncompressed byte string.
    level : int, default=6
        Zlib compression level (0–9). Level 6 offers optimal ~90% compression ratio.

    Returns
    -------
    bytes
        Zlib-compressed byte payload.
    """
    return zlib.compress(data, level=level)


def decompress_bytes(data: bytes) -> bytes:
    """Decompress a zlib-compressed payload.

    Parameters
    ----------
    data : bytes
        Compressed byte string.

    Returns
    -------
    bytes
        Decompressed raw byte payload.
    """
    return zlib.decompress(data)


def archive_run_trace(
    cp: ControlPlane,
    run_id: str,
    trace_file_path: str | Path,
    compression_level: int = DEFAULT_COMPRESSION_LEVEL,
) -> bool:
    """Safely compress and persist execution log or JSONL trace into Control Plane.

    Guarantees non-fatal degradation: if disk read, compression, or SQLite persistence
    fails, a warning is logged but no exception is raised, ensuring financial run outcomes
    are never compromised by telemetry archival issues.

    Parameters
    ----------
    cp : ControlPlane
        Active Control Plane facade instance.
    run_id : str
        Target execution run identifier.
    trace_file_path : str | Path
        File system path to log or JSONL trace.
    compression_level : int, default=6
        Compression level to apply (0-9).

    Returns
    -------
    bool
        True if trace was successfully archived, False on non-fatal failure or missing file.
    """
    path = Path(trace_file_path)
    if not path.exists():
        logger.debug(
            "Trace Archival: Trace file not found at %s. Skipping archival for run %s.",
            path,
            run_id,
        )
        return False

    try:
        log_bytes = path.read_bytes()
        compressed_log = compress_bytes(log_bytes, level=compression_level)
        cp.runs.save_execution_log(run_id, compressed_log)
        logger.debug(
            "Trace Archival: Successfully archived compressed trace for run %s (%d -> %d bytes).",
            run_id,
            len(log_bytes),
            len(compressed_log),
        )
        return True
    except (sqlite3.Error, OSError, zlib.error, UnicodeDecodeError, KeyError, RuntimeError) as err:
        logger.warning(
            "Trace Archival: Non-fatal degradation saving execution trace to Control Plane for run %s: %s",
            run_id,
            err,
        )
        return False


def retrieve_run_trace(
    cp: ControlPlane,
    run_id: str,
    decompress: bool = True,
) -> bytes | None:
    """Fetch archived execution log or trace payload from Control Plane for a run.

    Parameters
    ----------
    cp : ControlPlane
        Active Control Plane facade instance.
    run_id : str
        Target execution run identifier.
    decompress : bool, default=True
        Whether to decompress the stored zlib payload.

    Returns
    -------
    bytes | None
        Decompressed (or raw) trace bytes if present, else None.
    """
    try:
        raw = cp.runs.get_execution_log(run_id)
    except (sqlite3.Error, RuntimeError, KeyError) as err:
        logger.warning(
            "Trace Archival: Failed to retrieve stored trace from Control Plane for run %s: %s",
            run_id,
            err,
        )
        return None
    if raw is None:
        return None

    if not decompress:
        return raw

    try:
        return decompress_bytes(raw)
    except zlib.error as err:
        logger.warning(
            "Trace Archival: Failed to decompress stored trace for run %s: %s",
            run_id,
            err,
        )
        return raw


def retrieve_run_trace_text(
    cp: ControlPlane,
    run_id: str,
    encoding: str = "utf-8",
) -> str | None:
    """Fetch and decode archived execution log or trace payload as a string.

    Parameters
    ----------
    cp : ControlPlane
        Active Control Plane facade instance.
    run_id : str
        Target execution run identifier.
    encoding : str, default="utf-8"
        String encoding format for decoding decompressed trace bytes.

    Returns
    -------
    str | None
        Decoded trace string if present, else None.
    """
    raw_bytes = retrieve_run_trace(cp, run_id, decompress=True)
    if raw_bytes is None:
        return None
    return raw_bytes.decode(encoding=encoding, errors="replace")


def retrieve_run_trace_events(
    cp: ControlPlane,
    run_id: str,
) -> list[dict[str, object]] | None:
    """Fetch, decompress, and parse archived JSONL forensic events from Control Plane.

    Parameters
    ----------
    cp : ControlPlane
        Active Control Plane facade instance.
    run_id : str
        Target execution run identifier.

    Returns
    -------
    list[dict[str, object]] | None
        List of parsed JSON event dictionaries if present, else None.
    """
    text = retrieve_run_trace_text(cp, run_id)
    if text is None:
        return None
    records: list[dict[str, object]] = []
    for line in text.splitlines():
        line_str = line.strip()
        if not line_str:
            continue
        try:
            records.append(cast(dict[str, object], json.loads(line_str)))
        except json.JSONDecodeError:
            continue
    return records
