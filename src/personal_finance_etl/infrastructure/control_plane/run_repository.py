"""Run lifecycle, execution status, and failure persistence in the control plane.

Owns
----
- Pipeline run lifecycle management (start_run, finish_run, update_status).
- Commit state transitions (NOT_STARTED -> STARTED -> COMMITTING -> COMMITTED / ROLLED_BACK).
- Run failure audit logging and failure domain classification.
- Crash recovery and convergence marking for interrupted runs.
- External provider request audit logging and file-sync summary metrics.
- Simulation run reproducibility tracking and fingerprint persistence delegating to simulation_fingerprint.

Does not own
-------------
- Source file artifact tracking and binary payload vaulting (owned by artifact_repository).
- SQLite connection and low-level transaction primitives (owned by connection).
- Simulation mathematical fingerprint calculation (owned by simulation_fingerprint).
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import sqlite3
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.contracts.extraction import ExtractionProviderRequest
from personal_finance_etl.contracts.lifecycle import (
    CommitState,
    FailureDomain,
    SyncSummaryRecord,
    classify_failure_domain,
)
from personal_finance_etl.infrastructure.control_plane.connection import SQLiteManager
from personal_finance_etl.infrastructure.control_plane.simulation_fingerprint import (
    compute_model_fingerprint,
    fingerprint_dataframe,
    json_safe,
    resolve_input_as_of_date,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)

__all__ = ["RunRepository", "SimulationRunParams"]

diagnostics = get_observability_diagnostics("personal_finance_etl.control_plane.run_repo")

# Static SQL query constants
SQL_INSERT_SETTINGS_SNAPSHOT = (
    "INSERT OR IGNORE INTO cp_settings_snapshots "
    "(snapshot_id, content_hash, canonical_payload, created_at) VALUES (?, ?, ?, ?)"
)

SQL_INSERT_RULES_SNAPSHOT = (
    "INSERT OR IGNORE INTO cp_rules_snapshots "
    "(snapshot_id, content_hash, canonical_payload, created_at) VALUES (?, ?, ?, ?)"
)

SQL_INSERT_RUN = """
INSERT INTO cp_runs (
    run_id, started_at, status, commit_state, application_version, schema_version,
    settings_snapshot_id, rules_snapshot_id
) VALUES (?, ?, 'STARTED', 'STARTED', ?, ?, ?, ?)
"""

SQL_SELECT_RUN_METADATA = (
    "SELECT settings_snapshot_id, rules_snapshot_id FROM cp_runs WHERE run_id = ?"
)

SQL_UPDATE_RUN_STATUS = "UPDATE cp_runs SET status = ? WHERE run_id = ?"

SQL_UPDATE_COMMIT_STATE = "UPDATE cp_runs SET commit_state = ? WHERE run_id = ?"

SQL_UPDATE_EXECUTION_LOG = "UPDATE cp_runs SET execution_log = ? WHERE run_id = ?"

SQL_SELECT_EXECUTION_LOG = "SELECT execution_log FROM cp_runs WHERE run_id = ?"

SQL_SELECT_RUN_STATUS = """
SELECT run_id, started_at, finished_at, status, commit_state,
       application_version, schema_version, settings_snapshot_id,
       rules_snapshot_id, (execution_log IS NOT NULL) AS has_execution_log
FROM cp_runs WHERE run_id = ?
"""

SQL_FINISH_RUN_WITH_COMMIT = (
    "UPDATE cp_runs SET status = ?, commit_state = ?, finished_at = ? WHERE run_id = ?"
)

SQL_FINISH_RUN = "UPDATE cp_runs SET status = ?, finished_at = ? WHERE run_id = ?"

SQL_UPSERT_SIMULATION_RUN = """
INSERT INTO cp_simulation_runs (
    simulation_id, run_id, created_at, root_seed, iterations, horizon,
    input_as_of_date, settings_snapshot_id, rules_snapshot_id,
    model_implementation_version, input_fingerprint, model_fingerprint,
    result_fingerprint, status
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SUCCESS')
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
    status = excluded.status
"""

SQL_INSERT_RUN_FAILURE = """
INSERT INTO cp_run_failures (
    run_id, failed_isin, stage, error_type, error_message, traceback_log, failure_domain, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

SQL_SELECT_RECOVERY_REQUIRED_RUNS = (
    "SELECT run_id FROM cp_runs WHERE UPPER(status) = 'RECOVERY_REQUIRED' ORDER BY started_at"
)

SQL_UPDATE_RECOVERY_REQUIRED = "UPDATE cp_runs SET status = 'RECOVERY_REQUIRED', commit_state = ?, finished_at = ? WHERE run_id = ?"

SQL_UPDATE_RECOVERY_CONVERGED = (
    "UPDATE cp_runs SET status = 'CONVERGED', commit_state = ? "
    "WHERE run_id = ? AND UPPER(status) = 'RECOVERY_REQUIRED'"
)

SQL_SELECT_STALE_RUNS = (
    "SELECT run_id, status FROM cp_runs WHERE UPPER(status) IN ('STARTED', 'RUNNING', 'COMMITTING')"
)

SQL_UPDATE_STALE_RUN = (
    "UPDATE cp_runs SET status = ?, commit_state = ?, finished_at = ? "
    "WHERE run_id = ? AND UPPER(status) IN ('STARTED', 'RUNNING', 'COMMITTING')"
)

SQL_INSERT_PROVIDER_REQUEST = """
INSERT INTO cp_external_provider_requests (
    request_id, run_id, provider, entity, requested_start, requested_end,
    attempt_count, status, failure_class, final_error, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SQL_UPSERT_SYNC_SUMMARY = """
INSERT INTO cp_run_sync_summaries (
    run_id, actionable_count, synced_count, healed_count, failed_count, deferred_count, sync_status, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(run_id) DO UPDATE SET
    actionable_count = excluded.actionable_count,
    synced_count = excluded.synced_count,
    healed_count = excluded.healed_count,
    failed_count = excluded.failed_count,
    deferred_count = excluded.deferred_count,
    sync_status = excluded.sync_status,
    created_at = excluded.created_at
"""

SQL_SELECT_SYNC_SUMMARY = """
SELECT run_id, actionable_count, synced_count, healed_count, failed_count, deferred_count, sync_status, created_at
FROM cp_run_sync_summaries WHERE run_id = ?
"""

SQL_SELECT_LATEST_SUCCESSFUL_SIMULATION = """
SELECT simulation_id, run_id, created_at, root_seed, iterations, horizon,
       input_as_of_date, model_implementation_version, model_fingerprint,
       input_fingerprint, result_fingerprint, settings_snapshot_id,
       rules_snapshot_id, status
FROM cp_simulation_runs
WHERE status = 'SUCCESS'
ORDER BY created_at DESC
LIMIT 1
"""


@dataclass
class SimulationRunParams:
    """Parameters for recording a Monte Carlo simulation execution."""

    run_id: str
    root_seed: str
    rules: FinancialRules
    input_df: pl.DataFrame | pl.LazyFrame | None = None
    result_df: pl.DataFrame | pl.LazyFrame | None = None
    input_as_of_date: date | str | None = None
    result_fingerprint: str | None = None
    settings_snapshot_id: str | None = None
    rules_snapshot_id: str | None = None


class RunRepository:
    """Persistence and audit transitions for pipeline execution runs and lifecycle events.

    Parameters
    ----------
    db : SQLiteManager
        Active control plane SQLite connection manager.
    """

    def __init__(self, db: SQLiteManager) -> None:
        self.db = db

    # Backward-compatible static references to fingerprint helpers
    _json_safe = staticmethod(json_safe)
    _fingerprint_dataframe = staticmethod(fingerprint_dataframe)
    _compute_model_fingerprint = staticmethod(compute_model_fingerprint)
    _resolve_input_as_of_date = staticmethod(resolve_input_as_of_date)

    @staticmethod
    def _canonical_json(value: str) -> str:
        """Parse and re-serialize JSON with sorted keys and minimal whitespace.

        Parameters
        ----------
        value : str
            Input JSON string.

        Returns
        -------
        str
            Canonical formatted JSON string.
        """
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _application_version() -> str:
        """Retrieve installed application version string.

        Returns
        -------
        str
            Application version prefixed with 'v'.
        """
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
            if cfg_json:
                canonical_cfg = self._canonical_json(cfg_json)
                digest_cfg = hashlib.sha256(canonical_cfg.encode("utf-8")).hexdigest()
                settings_id = f"snap_set_{digest_cfg}"
                self.db.conn.execute(
                    SQL_INSERT_SETTINGS_SNAPSHOT,
                    (settings_id, digest_cfg, canonical_cfg, now),
                )
            if rules_json:
                canonical_rules = self._canonical_json(rules_json)
                digest_rules = hashlib.sha256(canonical_rules.encode("utf-8")).hexdigest()
                rules_id = f"snap_rule_{digest_rules}"
                self.db.conn.execute(
                    SQL_INSERT_RULES_SNAPSHOT,
                    (rules_id, digest_rules, canonical_rules, now),
                )
            self.db.conn.execute(
                SQL_INSERT_RUN,
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
        """Fetch snapshot IDs associated with a run.

        Parameters
        ----------
        run_id : str
            Target run ID.

        Returns
        -------
        dict[str, str | None]
            Map containing settings_snapshot_id and rules_snapshot_id.
        """
        row = self.db.conn.execute(
            SQL_SELECT_RUN_METADATA,
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
        ------
        ValueError
            If status is empty.
        KeyError
            If run_id does not exist.
        """
        normalized_status = status.strip().upper()
        if not normalized_status:
            raise ValueError("Run status must be a non-empty string.")
        with self.db.atomic():
            cursor = self.db.conn.execute(SQL_UPDATE_RUN_STATUS, (normalized_status, run_id))
            if cursor.rowcount != 1:
                raise KeyError(f"Cannot update unknown run ID: {run_id}")

    def update_commit_state(self, run_id: str, commit_state: str | CommitState) -> None:
        """Update the two-phase commit state of a run.

        Parameters
        ----------
        run_id : str
            Target run ID.
        commit_state : str | CommitState
            New commit state enum or string.

        Raises
        ------
        KeyError
            If run_id does not exist.
        """
        val = (
            commit_state.value
            if isinstance(commit_state, CommitState)
            else str(commit_state).strip().upper()
        )
        with self.db.atomic():
            cursor = self.db.conn.execute(SQL_UPDATE_COMMIT_STATE, (val, run_id))
            if cursor.rowcount != 1:
                raise KeyError(f"Cannot update commit state for unknown run ID: {run_id}")

    def save_execution_log(self, run_id: str, log_data: bytes) -> None:
        """Save raw execution log bytes to the run record.

        Parameters
        ----------
        run_id : str
            Target run ID.
        log_data : bytes
            Raw log bytes payload.

        Raises
        ------
        KeyError
            If run_id does not exist.
        """
        with self.db.atomic():
            cursor = self.db.conn.execute(SQL_UPDATE_EXECUTION_LOG, (log_data, run_id))
            if cursor.rowcount != 1:
                raise KeyError(f"Cannot save execution log for unknown run ID: {run_id}")

    def get_execution_log(self, run_id: str) -> bytes | None:
        """Fetch raw execution log bytes for a specific run ID.

        Parameters
        ----------
        run_id : str
            Target run identifier.

        Returns
        -------
        bytes | None
            Archived log payload bytes if found, else None.
        """
        row = self.db.conn.execute(
            SQL_SELECT_EXECUTION_LOG,
            (run_id,),
        ).fetchone()
        if row and row[0] is not None:
            return bytes(row[0])
        return None

    def get_run_status(self, run_id: str) -> dict[str, object] | None:
        """Fetch full lifecycle milestone status and commit state for a run.

        Parameters
        ----------
        run_id : str
            Target run identifier.

        Returns
        -------
        dict[str, object] | None
            Dictionary of run milestone attributes if found, else None.
        """
        row = self.db.conn.execute(
            SQL_SELECT_RUN_STATUS,
            (run_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "run_id": row[0],
            "started_at": row[1],
            "finished_at": row[2],
            "status": row[3],
            "commit_state": row[4],
            "application_version": row[5],
            "schema_version": row[6],
            "settings_snapshot_id": row[7],
            "rules_snapshot_id": row[8],
            "has_execution_log": bool(row[9]),
        }

    def finish_run(
        self, run_id: str, status: str, commit_state: str | CommitState | None = None
    ) -> None:
        """Finalize a pipeline run with termination timestamp and state.

        Parameters
        ----------
        run_id : str
            Target run ID.
        status : str
            Terminal status string.
        commit_state : str | CommitState | None, default=None
            Final commit state if explicitly assigned.

        Raises
        ------
        ValueError
            If status is empty.
        KeyError
            If run_id does not exist.
        """
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
                    SQL_FINISH_RUN_WITH_COMMIT,
                    (normalized_status, val, now, run_id),
                )
            else:
                cursor = self.db.conn.execute(
                    SQL_FINISH_RUN,
                    (normalized_status, now, run_id),
                )
            if cursor.rowcount != 1:
                raise KeyError(f"Cannot finish unknown run ID: {run_id}")

    def log_simulation_run(
        self,
        params: SimulationRunParams,
    ) -> None:
        """Record a reproducible Monte Carlo simulation run in cp_simulation_runs.

        Parameters
        ----------
        params : SimulationRunParams
            Structured simulation run parameters.
        """
        p = params
        sim_id = f"sim_{p.run_id}"
        now = datetime.now().isoformat(timespec="seconds")
        model_fp = compute_model_fingerprint(p.rules)
        input_fp = fingerprint_dataframe(p.input_df)

        result_fp = p.result_fingerprint
        if result_fp is None and p.result_df is not None:
            result_fp = fingerprint_dataframe(p.result_df)

        resolved_as_of_date = resolve_input_as_of_date(p.input_df, p.input_as_of_date)
        iterations = p.rules.assumptions.monte_carlo.iterations
        horizon = p.rules.assumptions.monte_carlo.max_months

        with self.db.atomic():
            self.db.conn.execute(
                SQL_UPSERT_SIMULATION_RUN,
                (
                    sim_id,
                    p.run_id,
                    now,
                    str(p.root_seed),
                    iterations,
                    horizon,
                    resolved_as_of_date,
                    p.settings_snapshot_id,
                    p.rules_snapshot_id,
                    "v1.0-gbm-fire",
                    input_fp,
                    model_fp,
                    result_fp,
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
        """Persist a failure audit record with domain classification.

        Parameters
        ----------
        run_id : str
            Active run identifier.
        failed_isin : str | None
            Associated ISIN if failure was instrument-specific.
        stage : str
            Pipeline execution stage.
        error_type : str
            Error classification or exception name.
        error_message : str
            Descriptive error narrative.
        traceback_log : str | None, default=None
            Full exception traceback string.
        failure_domain : FailureDomain | str | None, default=None
            Categorized failure domain.
        """
        now = datetime.now().isoformat(timespec="seconds")
        if failure_domain is None:
            resolved_domain = classify_failure_domain(stage, error_type or error_message).value
        elif isinstance(failure_domain, FailureDomain):
            resolved_domain = failure_domain.value
        else:
            resolved_domain = str(failure_domain).upper()

        self.db.conn.execute(
            SQL_INSERT_RUN_FAILURE,
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
        """Return all run IDs currently marked RECOVERY_REQUIRED.

        Returns
        -------
        list[str]
            List of run identifiers awaiting crash recovery.
        """
        cursor = self.db.conn.execute(SQL_SELECT_RECOVERY_REQUIRED_RUNS)
        return [str(row[0]) for row in cursor.fetchall()]

    def mark_recovery_required(
        self,
        run_id: str,
        error_message: str,
        stage: str = "COMMIT",
        traceback_log: str | None = None,
    ) -> None:
        """Atomically persist RECOVERY_REQUIRED status and CROSS_STORE_DIVERGENCE event.

        Parameters
        ----------
        run_id : str
            Run ID encountering divergence.
        error_message : str
            Explanation of divergence condition.
        stage : str, default='COMMIT'
            Stage where divergence occurred.
        traceback_log : str | None, default=None
            Optional traceback details.
        """
        now = datetime.now().isoformat(timespec="seconds")
        try:
            with self.db.atomic():
                self.db.conn.execute(
                    SQL_UPDATE_RECOVERY_REQUIRED,
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
                    SQL_UPDATE_RECOVERY_REQUIRED,
                    (CommitState.RECOVERY_REQUIRED.value, now, run_id),
                )
                conn.execute(
                    SQL_INSERT_RUN_FAILURE,
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
        """Mark a prior RECOVERY_REQUIRED run as CONVERGED after successful reconciliation.

        Parameters
        ----------
        recovered_run_id : str
            Prior run ID that was previously in divergence.
        reconciling_run_id : str
            Current run ID performing the successful reconciliation.
        """
        now = datetime.now().isoformat(timespec="seconds")
        with self.db.atomic():
            self.db.conn.execute(
                SQL_UPDATE_RECOVERY_CONVERGED,
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
            stale_runs = self.db.conn.execute(SQL_SELECT_STALE_RUNS).fetchall()
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
                    SQL_UPDATE_STALE_RUN,
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
            diagnostics.warning("ControlPlane: Recovered %d interrupted run(s).", recovered)

    @staticmethod
    def _normalize_provider_record(
        rec: ExtractionProviderRequest | Mapping[str, object],
        run_id: str,
        now: str,
    ) -> tuple[str, str, str, str, str | None, str | None, int, str, str | None, str | None, str]:
        """Normalize a provider request record into a SQL insert parameter tuple.

        Parameters
        ----------
        rec : ExtractionProviderRequest | Mapping[str, object]
            Input request record.
        run_id : str
            Active pipeline execution ID.
        now : str
            ISO-formatted timestamp fallback.

        Returns
        -------
        tuple[str, str, str, str, str | None, str | None, int, str, str | None, str | None, str]
            Normalized values for cp_external_provider_requests table columns.
        """
        req_id = str(rec.get("request_id") or uuid.uuid4())
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

        raw_attempts = rec.get("attempt_count", 1)
        if isinstance(raw_attempts, (int, str, float)):
            try:
                attempt_count = int(raw_attempts)
            except (TypeError, ValueError):
                attempt_count = 1
        else:
            attempt_count = 1

        status = str(rec.get("status", "SUCCESS")).upper()
        failure_class = rec.get("failure_class")
        failure_class_str = str(failure_class) if failure_class is not None else None
        final_error = rec.get("final_error")
        final_error_str = str(final_error) if final_error is not None else None

        created_at = rec.get("created_at") or now
        if isinstance(created_at, (date, datetime)):
            created_at = created_at.isoformat()

        return (
            req_id,
            run_id,
            provider,
            entity,
            req_start,
            req_end,
            attempt_count,
            status,
            failure_class_str,
            final_error_str,
            str(created_at),
        )

    def log_provider_requests(
        self,
        run_id: str,
        records: Sequence[ExtractionProviderRequest] | Sequence[Mapping[str, object]],
    ) -> None:
        """Persist batch of external provider requests with retry/status provenance.

        Parameters
        ----------
        run_id : str
            Pipeline execution identifier.
        records : Sequence[ExtractionProviderRequest] | Sequence[Mapping[str, object]]
            Collection of provider request log items.
        """
        if not records:
            return
        now = datetime.now().isoformat(timespec="seconds")
        params = [self._normalize_provider_record(rec, run_id, now) for rec in records]
        with self.db.atomic():
            self.db.conn.executemany(SQL_INSERT_PROVIDER_REQUEST, params)

    def log_sync_summary(
        self, run_id: str, summary: SyncSummaryRecord | Mapping[str, object]
    ) -> None:
        """Persist authoritative file-sync summary metrics for a pipeline run.

        Parameters
        ----------
        run_id : str
            Active pipeline execution ID.
        summary : SyncSummaryRecord | Mapping[str, object]
            Aggregated artifact sync counts and final status.
        """
        now = datetime.now().isoformat(timespec="seconds")
        raw_actionable = summary.get("actionable_count", 0)
        actionable_count = (
            int(raw_actionable) if isinstance(raw_actionable, (int, float, str)) else 0
        )
        raw_synced = summary.get("synced_count", 0)
        synced_count = int(raw_synced) if isinstance(raw_synced, (int, float, str)) else 0
        raw_healed = summary.get("healed_count", 0)
        healed_count = int(raw_healed) if isinstance(raw_healed, (int, float, str)) else 0
        raw_failed = summary.get("failed_count", 0)
        failed_count = int(raw_failed) if isinstance(raw_failed, (int, float, str)) else 0
        raw_deferred = summary.get("deferred_count", 0)
        deferred_count = int(raw_deferred) if isinstance(raw_deferred, (int, float, str)) else 0
        sync_status = str(summary.get("sync_status", "COMPLETE")).upper()
        with self.db.atomic():
            self.db.conn.execute(
                SQL_UPSERT_SYNC_SUMMARY,
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

    def get_sync_summary(self, run_id: str) -> SyncSummaryRecord | None:
        """Retrieve file-sync summary metrics for a pipeline run.

        Parameters
        ----------
        run_id : str
            Target run ID.

        Returns
        -------
        SyncSummaryRecord | None
            Summary record dictionary if found, else None.
        """
        row = self.db.conn.execute(SQL_SELECT_SYNC_SUMMARY, (run_id,)).fetchone()
        if not row:
            return None
        return {
            "run_id": str(row[0]),
            "actionable_count": int(row[1]),
            "synced_count": int(row[2]),
            "healed_count": int(row[3]),
            "failed_count": int(row[4]),
            "deferred_count": int(row[5]),
            "sync_status": str(row[6]),
            "created_at": str(row[7]),
        }

    def get_latest_successful_simulation(self) -> dict[str, object] | None:
        """Retrieve the most recent successful simulation run record.

        Returns
        -------
        dict[str, object] | None
            Simulation attribute dictionary if found, else None.
        """
        row = self.db.conn.execute(SQL_SELECT_LATEST_SUCCESSFUL_SIMULATION).fetchone()
        if not row:
            return None
        return {
            "simulation_id": row[0],
            "run_id": row[1],
            "created_at": row[2],
            "root_seed": row[3],
            "iterations": row[4],
            "horizon": row[5],
            "input_as_of_date": row[6],
            "model_implementation_version": row[7],
            "model_fingerprint": row[8],
            "input_fingerprint": row[9],
            "result_fingerprint": row[10],
            "settings_snapshot_id": row[11],
            "rules_snapshot_id": row[12],
            "status": row[13],
        }
