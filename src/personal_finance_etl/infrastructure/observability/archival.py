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

import logging
import os
import sqlite3
import zlib

from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane

logger = logging.getLogger("personal_finance_etl.observability.archival")

__all__ = [
    "DEFAULT_COMPRESSION_LEVEL",
    "archive_run_trace",
    "compress_bytes",
    "decompress_bytes",
    "retrieve_run_trace",
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
    trace_file_path: str,
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
    trace_file_path : str
        File system path to log or JSONL trace.
    compression_level : int, default=6
        Compression level to apply (0-9).

    Returns
    -------
    bool
        True if trace was successfully archived, False on non-fatal failure or missing file.
    """
    if not os.path.exists(trace_file_path):
        logger.debug(
            "Trace Archival: Trace file not found at %s. Skipping archival for run %s.",
            trace_file_path,
            run_id,
        )
        return False

    try:
        with open(trace_file_path, "rb") as f:
            log_bytes = f.read()

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
