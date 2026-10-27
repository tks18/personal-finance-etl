"""Observability trace file retention and automatic disk cleanup manager.

Owns
----
- Enforcing bounded retention policies across local forensic JSONL and log trace directories.
- Pruning expired or excessive runs beyond configured run counts (retain_last_n_runs).
- Age-based trace eviction (max_age_days).
- Non-fatal file unlink operations guarded against locked file descriptors.

Does not own
-------------
- Control Plane database record purging (owned by infrastructure.control_plane).
- Active forensic sink file writing (owned by infrastructure.observability.forensic_sink).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)

diagnostics = get_observability_diagnostics("personal_finance_etl.observability.retention")

__all__ = ["LogRetentionManager"]


class LogRetentionManager:
    """Manages disk lifecycle and retention policies for local forensic log files.

    Parameters
    ----------
    logs_dir : Path | str
        Directory containing execution traces (*.jsonl, *.log).
    retain_last_n_runs : int, default=12
        Maximum number of recent execution runs to retain on disk.
    max_age_days : int | None, default=30
        Maximum age threshold in days before traces are eligible for pruning.
    """

    def __init__(
        self,
        logs_dir: Path | str,
        retain_last_n_runs: int = 12,
        max_age_days: int | None = 30,
    ) -> None:
        self.logs_dir = Path(logs_dir)
        self.retain_last_n_runs = max(1, retain_last_n_runs)
        self.max_age_days = max_age_days

    def discover_trace_files(self) -> list[Path]:
        """Find all trace and log files in the managed logs directory sorted newest first.

        Returns
        -------
        list[Path]
            Trace file paths ordered from most recently modified to oldest.
        """
        if not self.logs_dir.exists() or not self.logs_dir.is_dir():
            return []

        trace_extensions = {".jsonl", ".log"}
        candidates: list[Path] = [
            p
            for p in self.logs_dir.iterdir()
            if p.is_file() and p.suffix.lower() in trace_extensions
        ]

        # Sort newest first based on mtime
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates

    def prune_expired_traces(self, dry_run: bool = False) -> list[Path]:
        """Prune trace files exceeding retention count or age boundaries.

        Parameters
        ----------
        dry_run : bool, default=False
            If True, identifies candidate files without unlinking them from disk.

        Returns
        -------
        list[Path]
            List of pruned (or candidate) file paths.
        """
        files = self.discover_trace_files()
        if not files:
            return []

        now = time.time()
        to_prune: list[Path] = []

        # 1. Enforce run count bound
        if len(files) > self.retain_last_n_runs:
            to_prune.extend(files[self.retain_last_n_runs :])

        # 2. Enforce age bound if specified
        if self.max_age_days is not None and self.max_age_days > 0:
            max_age_seconds = self.max_age_days * 86400.0
            for f in files[: self.retain_last_n_runs]:
                try:
                    file_age = now - f.stat().st_mtime
                    if file_age > max_age_seconds and f not in to_prune:
                        to_prune.append(f)
                except OSError:
                    continue

        if not to_prune:
            diagnostics.debug(
                "Log Retention: All %d trace file(s) in %s are within retention bounds.",
                len(files),
                self.logs_dir,
            )
            return []

        pruned_successfully: list[Path] = []
        for file_path in to_prune:
            if dry_run:
                pruned_successfully.append(file_path)
                continue

            try:
                os.unlink(file_path)
                pruned_successfully.append(file_path)
                diagnostics.debug("Log Retention: Pruned expired trace file %s.", file_path.name)
            except (OSError, PermissionError) as err:
                diagnostics.warning(
                    "Log Retention: Non-fatal failure pruning trace file %s: %s",
                    file_path.name,
                    err,
                )

        if pruned_successfully and not dry_run:
            diagnostics.info(
                "Log Retention: Pruned %d expired trace file(s) from %s.",
                len(pruned_successfully),
                self.logs_dir,
            )

        return pruned_successfully
