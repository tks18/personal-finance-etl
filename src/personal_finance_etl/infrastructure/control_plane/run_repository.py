"""Run lifecycle, execution status, and failure persistence in the control plane.

Owns
----
- Pipeline run lifecycle management (start_run, finish_run, update_status).
- Commit state transitions (NOT_STARTED -> STARTED -> COMMITTING -> COMMITTED / ROLLED_BACK).
- Run failure audit logging and failure domain classification.
- Crash recovery and convergence marking for interrupted runs.
- External provider request audit logging and file-sync summary metrics.
- Simulation run reproducibility tracking and fingerprint persistence.

Does not own
-------------
- Source file artifact tracking and binary payload vaulting (owned by artifact_repository).
- SQLite connection and low-level transaction primitives (owned by connection).
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import logging
import math
import sqlite3
import uuid
from datetime import date, datetime
from typing import Any, cast

from personal_finance_etl.contracts.lifecycle import (
    CommitState,
    FailureDomain,
    classify_failure_domain,
)
from personal_finance_etl.infrastructure.control_plane.connection import SQLiteManager

logger = logging.getLogger("personal_finance_etl.control_plane.run_repo")


class RunRepository:
    """Persistence and audit transitions for pipeline execution runs and lifecycle events.

    Parameters
    ----------
    db : SQLiteManager
        Active control plane SQLite connection manager.
    """

    def __init__(self, db: SQLiteManager) -> None:
        self.db = db

    @staticmethod
    def _canonical_json(value: str) -> str:
        """Parse and re-serialize JSON with sorted keys and minimal whitespace."""
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _application_version() -> str:
        """Retrieve installed application version string."""
        try:
            return f"v{importlib.metadata.version('personal-finance-etl')}"
        except importlib.metadata.PackageNotFoundError:
            return "v-unknown"

    def start_run(self, cfg_json: str | None = None, rules_json: str | None = None) -> str:
        """Initialize a new pipeline execution run record and snapshot configs.

        Parameters
        ----------
        cfg_json : str, optional
            Serialized settings snapshot payload.
        rules_json : str, optional
            Serialized financial rules snapshot payload.

        Returns
        -------
        str
            Unique run ID UUID.
        """
        run_id = str(uuid.uuid4())
        now = datetime.now().isoformat(timespec="seconds")
        settings_id: str | None = None
        rules_id: str | None = None
        with self.db.atomic():
            for payload, prefix, table in (
                (cfg_json, "snap_set_", "cp_settings_snapshots"),
                (rules_json, "snap_rule_", "cp_rules_snapshots"),
            ):
                if not payload:
                    continue
                canonical = self._canonical_json(payload)
                digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                snapshot_id = f"{prefix}{digest}"
                self.db.conn.execute(
                    f"INSERT OR IGNORE INTO {table} (snapshot_id, content_hash, canonical_payload, created_at) VALUES (?, ?, ?, ?)",
                    (snapshot_id, digest, canonical, now),
                )
                if table == "cp_settings_snapshots":
                    settings_id = snapshot_id
                else:
                    rules_id = snapshot_id
            self.db.conn.execute(
                """INSERT INTO cp_runs
                   (run_id, started_at, status, commit_state, application_version, schema_version,
                    settings_snapshot_id, rules_snapshot_id)
                   VALUES (?, ?, 'STARTED', 'STARTED', ?, ?, ?, ?)""",
                (
                    run_id,
                    now,
                    self._application_version(),
                    f"v{self.db.SCHEMA_VERSION}",
                    settings_id,
                    rules_id,
                ),
            )
        return run_id

    def get_run_metadata(self, run_id: str) -> dict[str, str | None]:
        """Fetch snapshot IDs associated with a run."""
        row = self.db.conn.execute(
            "SELECT settings_snapshot_id, rules_snapshot_id FROM cp_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row:
            return {"settings_snapshot_id": row[0], "rules_snapshot_id": row[1]}
        return {}

    def update_run_status(self, run_id: str, status: str) -> None:
        """Update the overall status of a pipeline run.

        Parameters
        ----------
        run_id : str
            Target run ID.
        status : str
            New status string (e.g., 'RUNNING', 'SUCCESS', 'FAILED').

        Raises
        ----------
        ValueError
            If status is empty.
        KeyError
            If run_id does not exist.
        """
        normalized_status = status.strip().upper()
        if not normalized_status:
            raise ValueError("Run status must be a non-empty string.")
        with self.db.atomic():
            cursor = self.db.conn.execute(
                "UPDATE cp_runs SET status = ? WHERE run_id = ?", (normalized_status, run_id)
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Cannot update unknown run ID: {run_id}")

    def update_commit_state(self, run_id: str, commit_state: str | CommitState) -> None:
        """Update the two-phase commit state of a run."""
        val = (
            commit_state.value
            if isinstance(commit_state, CommitState)
            else str(commit_state).strip().upper()
        )
        with self.db.atomic():
            cursor = self.db.conn.execute(
                "UPDATE cp_runs SET commit_state = ? WHERE run_id = ?", (val, run_id)
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Cannot update commit state for unknown run ID: {run_id}")

    def save_execution_log(self, run_id: str, log_data: bytes) -> None:
        """Save raw execution log bytes to the run record."""
        with self.db.atomic():
            cursor = self.db.conn.execute(
                "UPDATE cp_runs SET execution_log = ? WHERE run_id = ?", (log_data, run_id)
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Cannot save execution log for unknown run ID: {run_id}")

    def finish_run(
        self, run_id: str, status: str, commit_state: str | CommitState | None = None
    ) -> None:
        """Finalize a pipeline run with termination timestamp and state."""
        normalized_status = status.strip().upper()
        if not normalized_status:
            raise ValueError("Run status must be a non-empty string.")
        now = datetime.now().isoformat(timespec="seconds")
        with self.db.atomic():
            if commit_state is not None:
                val = (
                    commit_state.value
                    if isinstance(commit_state, CommitState)
                    else str(commit_state).strip().upper()
                )
                cursor = self.db.conn.execute(
                    "UPDATE cp_runs SET status = ?, commit_state = ?, finished_at = ? WHERE run_id = ?",
                    (normalized_status, val, now, run_id),
                )
            else:
                cursor = self.db.conn.execute(
                    "UPDATE cp_runs SET status = ?, finished_at = ? WHERE run_id = ?",
                    (normalized_status, now, run_id),
                )
            if cursor.rowcount != 1:
                raise KeyError(f"Cannot finish unknown run ID: {run_id}")

    @staticmethod
    def _json_safe(value: object) -> object:
        """Recursively serialize objects to JSON-compatible data structures."""
        if isinstance(value, dict):
            mapping = cast(dict[object, object], value)
            return {str(key): RunRepository._json_safe(item) for key, item in mapping.items()}
        if isinstance(value, (list, tuple)):
            items = cast(list[object] | tuple[object, ...], value)
            return [RunRepository._json_safe(item) for item in items]
        if isinstance(value, float) and not math.isfinite(value):
            return str(value)
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @classmethod
    def _fingerprint_dataframe(cls, input_df: Any | None) -> str:
        """Compute deterministic SHA-256 fingerprint of a tabular DataFrame."""
        if input_df is None:
            return "no-input"
        if not hasattr(input_df, "to_dicts") or not hasattr(input_df, "columns"):
            raise TypeError(
                "Simulation input must expose Polars-compatible columns and to_dicts()."
            )
        columns: list[str] = [str(column) for column in input_df.columns]
        rows = cast(list[dict[str, object]], input_df.to_dicts())
        digest = hashlib.sha256()
        header = json.dumps(columns, ensure_ascii=False, separators=(",", ":"))
        digest.update(header.encode("utf-8"))
        digest.update(b"\n")
        for row in rows:
            safe_row = cls._json_safe(row)
            encoded = json.dumps(
                safe_row, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
            )
            digest.update(encoded.encode("utf-8"))
            digest.update(b"\n")
        return digest.hexdigest()

    def log_simulation_run(
        self,
        run_id: str,
        root_seed: str,
        rules: Any,
        input_df: Any | None = None,
        result_df: Any | None = None,
        input_as_of_date: date | str | None = None,
        result_fingerprint: str | None = None,
        settings_snapshot_id: str | None = None,
        rules_snapshot_id: str | None = None,
    ) -> None:
        """Record a reproducible Monte Carlo simulation run in cp_simulation_runs."""
        sim_id = f"sim_{run_id}"
        now = datetime.now().isoformat(timespec="seconds")
        combined_rules = {
            "monte_carlo": rules.assumptions.monte_carlo.model_dump(),
            "fire": rules.assumptions.fire.model_dump(),
            "cma": rules.assumptions.cma.model_dump(),
        }
        model_fingerprint = hashlib.sha256(
            json.dumps(
                self._json_safe(combined_rules),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        input_fingerprint = self._fingerprint_dataframe(input_df)
        if result_fingerprint is None and result_df is not None:
            result_fingerprint = self._fingerprint_dataframe(result_df)

        if input_as_of_date is None and input_df is not None:
            candidate_cols = [
                "MONTH_START_DATE",
                "MONTH_END_DATE",
                "Date",
                "DATE",
                "as_of_date",
                "Closing_Date",
            ]
            for col in candidate_cols:
                if hasattr(input_df, "columns") and col in input_df.columns:
                    try:
                        if hasattr(input_df, "height") and input_df.height > 0:
                            max_val = input_df[col].max()
                            if max_val is not None:
                                if isinstance(max_val, datetime):
                                    input_as_of_date = max_val.date().isoformat()
                                elif isinstance(max_val, date):
                                    input_as_of_date = max_val.isoformat()
                                else:
                                    input_as_of_date = str(max_val).split("T")[0].split(" ")[0]
                                break
                    except (KeyError, TypeError, ValueError, AttributeError):
                        pass
        elif isinstance(input_as_of_date, (date, datetime)):
            input_as_of_date = (
                input_as_of_date.date().isoformat()
                if isinstance(input_as_of_date, datetime)
                else input_as_of_date.isoformat()
            )

        iterations = rules.assumptions.monte_carlo.iterations
        horizon = rules.assumptions.monte_carlo.max_months

        with self.db.atomic():
            self.db.conn.execute(
                """INSERT INTO cp_simulation_runs (
                       simulation_id, run_id, created_at, root_seed, iterations, horizon,
                       input_as_of_date, settings_snapshot_id, rules_snapshot_id,
                       model_implementation_version, input_fingerprint, model_fingerprint,
                       result_fingerprint, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUCCESS')
                   ON CONFLICT(simulation_id) DO UPDATE SET
                       created_at = excluded.created_at,
                       root_seed = excluded.root_seed,
                       iterations = excluded.iterations,
                       horizon = excluded.horizon,
                       input_as_of_date = excluded.input_as_of_date,
                       settings_snapshot_id = excluded.settings_snapshot_id,
                       rules_snapshot_id = excluded.rules_snapshot_id,
                       model_implementation_version = excluded.model_implementation_version,
                       input_fingerprint = excluded.input_fingerprint,
                       model_fingerprint = excluded.model_fingerprint,
                       result_fingerprint = excluded.result_fingerprint,
                       status = excluded.status""",
                (
                    sim_id,
                    run_id,
                    now,
                    str(root_seed),
                    iterations,
                    horizon,
                    str(input_as_of_date) if input_as_of_date is not None else None,
                    settings_snapshot_id,
                    rules_snapshot_id,
                    "v1.0-gbm-fire",
                    input_fingerprint,
                    model_fingerprint,
                    result_fingerprint,
                ),
            )

    def log_run_failure(
        self,
        run_id: str,
        failed_isin: str | None,
        stage: str,
        error_type: str,
        error_message: str,
        traceback_log: str | None = None,
        failure_domain: FailureDomain | str | None = None,
    ) -> None:
        """Persist a failure audit record with domain classification."""
        now = datetime.now().isoformat(timespec="seconds")
        if failure_domain is None:
            resolved_domain = classify_failure_domain(stage, error_type or error_message).value
        elif isinstance(failure_domain, FailureDomain):
            resolved_domain = failure_domain.value
        else:
            resolved_domain = str(failure_domain).upper()

        self.db.conn.execute(
            """INSERT INTO cp_run_failures
               (run_id, failed_isin, stage, error_type, error_message, traceback_log, failure_domain, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                failed_isin,
                stage,
                error_type,
                error_message,
                traceback_log,
                resolved_domain,
                now,
            ),
        )

    def get_recovery_required_runs(self) -> list[str]:
        """Return all run IDs currently marked RECOVERY_REQUIRED."""
        cursor = self.db.conn.execute(
            "SELECT run_id FROM cp_runs WHERE UPPER(status) = 'RECOVERY_REQUIRED' ORDER BY started_at"
        )
        return [str(row[0]) for row in cursor.fetchall()]

    def mark_recovery_required(
        self,
        run_id: str,
        error_message: str,
        stage: str = "COMMIT",
        traceback_log: str | None = None,
    ) -> None:
        """Atomically persist RECOVERY_REQUIRED status and CROSS_STORE_DIVERGENCE event."""
        now = datetime.now().isoformat(timespec="seconds")
        try:
            with self.db.atomic():
                self.db.conn.execute(
                    "UPDATE cp_runs SET status = 'RECOVERY_REQUIRED', commit_state = ?, finished_at = ? WHERE run_id = ?",
                    (CommitState.RECOVERY_REQUIRED.value, now, run_id),
                )
                self.log_run_failure(
                    run_id=run_id,
                    failed_isin=None,
                    stage=stage,
                    error_type="CROSS_STORE_DIVERGENCE",
                    error_message=error_message,
                    traceback_log=traceback_log,
                    failure_domain=FailureDomain.RECOVERY,
                )
        except Exception:
            conn = sqlite3.connect(self.db.db_path, timeout=30.0)
            try:
                conn.execute(
                    "UPDATE cp_runs SET status = 'RECOVERY_REQUIRED', commit_state = ?, finished_at = ? WHERE run_id = ?",
                    (CommitState.RECOVERY_REQUIRED.value, now, run_id),
                )
                conn.execute(
                    """INSERT INTO cp_run_failures
                       (run_id, failed_isin, stage, error_type, error_message, traceback_log, failure_domain, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        run_id,
                        None,
                        stage,
                        "CROSS_STORE_DIVERGENCE",
                        error_message,
                        traceback_log,
                        FailureDomain.RECOVERY.value,
                        now,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def mark_recovery_converged(self, recovered_run_id: str, reconciling_run_id: str) -> None:
        """Mark a prior RECOVERY_REQUIRED run as CONVERGED after successful reconciliation."""
        now = datetime.now().isoformat(timespec="seconds")
        with self.db.atomic():
            self.db.conn.execute(
                "UPDATE cp_runs SET status = 'CONVERGED', commit_state = ? WHERE run_id = ? AND UPPER(status) = 'RECOVERY_REQUIRED'",
                (CommitState.CONVERGED.value, recovered_run_id),
            )
            self.log_run_failure(
                run_id=recovered_run_id,
                failed_isin=None,
                stage="RECOVERY_CONVERGENCE",
                error_type="CONVERGED",
                error_message=f"Cross-store divergence resolved and converged by run {reconciling_run_id} at {now}.",
                failure_domain=FailureDomain.RECOVERY,
            )

    def recover_stale_runs(self) -> None:
        """Atomically recover interrupted runs; safe to repeat after a crash."""
        now = datetime.now().isoformat(timespec="seconds")
        recovered = 0
        with self.db.atomic():
            stale_runs = self.db.conn.execute(
                "SELECT run_id, status FROM cp_runs WHERE UPPER(status) IN ('STARTED', 'RUNNING', 'COMMITTING')"
            ).fetchall()
            for run_id, status in stale_runs:
                is_committing = str(status).upper() == "COMMITTING"
                new_status = "RECOVERY_REQUIRED" if is_committing else "FAILED"
                new_commit_state = (
                    CommitState.RECOVERY_REQUIRED.value
                    if is_committing
                    else CommitState.ROLLED_BACK.value
                )
                error_type = "CROSS_STORE_DIVERGENCE" if is_committing else "InterruptedRunError"
                error_message = (
                    "Run crashed while COMMITTING; cross-store commit state uncertain, recovery required."
                    if is_committing
                    else f"Run was left in {status} state and recovered as FAILED on startup."
                )

                cursor = self.db.conn.execute(
                    "UPDATE cp_runs SET status = ?, commit_state = ?, finished_at = ? "
                    "WHERE run_id = ? AND UPPER(status) IN ('STARTED', 'RUNNING', 'COMMITTING')",
                    (new_status, new_commit_state, now, run_id),
                )
                if cursor.rowcount != 1:
                    continue
                self.log_run_failure(
                    run_id=run_id,
                    failed_isin=None,
                    stage="RECOVERY",
                    error_type=error_type,
                    error_message=error_message,
                    failure_domain=FailureDomain.RECOVERY,
                )
                recovered += 1
        if recovered:
            logger.warning("[CONTROL_PLANE] Recovered %d interrupted run(s).", recovered)

    def log_provider_requests(self, run_id: str, records: list[dict[str, Any]]) -> None:
        """Persist batch of external provider requests with retry/status provenance."""
        if not records:
            return
        now = datetime.now().isoformat(timespec="seconds")
        params: list[
            tuple[
                str,
                str,
                str,
                str,
                str | None,
                str | None,
                int,
                str,
                str | None,
                str | None,
                str,
            ]
        ] = []
        for rec in records:
            req_id = rec.get("request_id") or str(uuid.uuid4())
            provider = str(rec.get("provider", "UNKNOWN"))
            entity = str(rec.get("entity", "UNKNOWN"))
            req_start = rec.get("requested_start")
            if isinstance(req_start, (date, datetime)):
                req_start = req_start.isoformat()
            elif req_start is not None:
                req_start = str(req_start)
            req_end = rec.get("requested_end")
            if isinstance(req_end, (date, datetime)):
                req_end = req_end.isoformat()
            elif req_end is not None:
                req_end = str(req_end)
            attempt_count = int(rec.get("attempt_count", 1))
            status = str(rec.get("status", "SUCCESS")).upper()
            failure_class = rec.get("failure_class")
            if failure_class is not None:
                failure_class = str(failure_class)
            final_error = rec.get("final_error")
            if final_error is not None:
                final_error = str(final_error)
            created_at = rec.get("created_at") or now
            if isinstance(created_at, (date, datetime)):
                created_at = created_at.isoformat()
            params.append(
                (
                    req_id,
                    run_id,
                    provider,
                    entity,
                    req_start,
                    req_end,
                    attempt_count,
                    status,
                    failure_class,
                    final_error,
                    str(created_at),
                )
            )
        with self.db.atomic():
            self.db.conn.executemany(
                """INSERT INTO cp_external_provider_requests
                   (request_id, run_id, provider, entity, requested_start, requested_end,
                    attempt_count, status, failure_class, final_error, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                params,
            )

    def log_sync_summary(self, run_id: str, summary: dict[str, Any]) -> None:
        """Persist authoritative file-sync summary metrics for a pipeline run."""
        now = datetime.now().isoformat(timespec="seconds")
        actionable_count = int(summary.get("actionable_count", 0))
        synced_count = int(summary.get("synced_count", 0))
        healed_count = int(summary.get("healed_count", 0))
        failed_count = int(summary.get("failed_count", 0))
        deferred_count = int(summary.get("deferred_count", 0))
        sync_status = str(summary.get("sync_status", "COMPLETE")).upper()
        with self.db.atomic():
            self.db.conn.execute(
                """INSERT INTO cp_run_sync_summaries
                   (run_id, actionable_count, synced_count, healed_count, failed_count, deferred_count, sync_status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(run_id) DO UPDATE SET
                       actionable_count = excluded.actionable_count,
                       synced_count = excluded.synced_count,
                       healed_count = excluded.healed_count,
                       failed_count = excluded.failed_count,
                       deferred_count = excluded.deferred_count,
                       sync_status = excluded.sync_status,
                       created_at = excluded.created_at""",
                (
                    run_id,
                    actionable_count,
                    synced_count,
                    healed_count,
                    failed_count,
                    deferred_count,
                    sync_status,
                    now,
                ),
            )

    def get_sync_summary(self, run_id: str) -> dict[str, Any] | None:
        """Retrieve file-sync summary metrics for a pipeline run."""
        row = self.db.conn.execute(
            """SELECT run_id, actionable_count, synced_count, healed_count, failed_count, deferred_count, sync_status, created_at
               FROM cp_run_sync_summaries WHERE run_id = ?""",
            (run_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "run_id": row[0],
            "actionable_count": row[1],
            "synced_count": row[2],
            "healed_count": row[3],
            "failed_count": row[4],
            "deferred_count": row[5],
            "sync_status": row[6],
            "created_at": row[7],
        }

