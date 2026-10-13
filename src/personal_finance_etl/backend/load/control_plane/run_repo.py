from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import uuid
from datetime import date, datetime
from typing import Any, cast

from personal_finance_etl.backend.load.control_plane.connection import SQLiteManager


class RunRepository:
    def __init__(self, db: SQLiteManager):
        self.db = db

    @staticmethod
    def _canonical_json(value: str) -> str:
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @staticmethod
    def _application_version() -> str:
        try:
            return f"v{importlib.metadata.version('personal-finance-etl')}"
        except importlib.metadata.PackageNotFoundError:
            return "v-unknown"

    def start_run(self, cfg_json: str | None = None, rules_json: str | None = None) -> str:
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
                   (run_id, started_at, status, application_version, schema_version,
                    settings_snapshot_id, rules_snapshot_id)
                   VALUES (?, ?, 'STARTED', ?, ?, ?, ?)""",
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
        row = self.db.conn.execute(
            "SELECT settings_snapshot_id, rules_snapshot_id FROM cp_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row:
            return {"settings_snapshot_id": row[0], "rules_snapshot_id": row[1]}
        return {}

    def update_run_status(self, run_id: str, status: str) -> None:
        normalized_status = status.strip().upper()
        if not normalized_status:
            raise ValueError("Run status must be a non-empty string.")
        with self.db.atomic():
            cursor = self.db.conn.execute(
                "UPDATE cp_runs SET status = ? WHERE run_id = ?", (normalized_status, run_id)
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Cannot update unknown run ID: {run_id}")

    def save_execution_log(self, run_id: str, log_data: bytes) -> None:
        with self.db.atomic():
            cursor = self.db.conn.execute(
                "UPDATE cp_runs SET execution_log = ? WHERE run_id = ?", (log_data, run_id)
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Cannot save execution log for unknown run ID: {run_id}")

    def finish_run(self, run_id: str, status: str) -> None:
        normalized_status = status.strip().upper()
        if not normalized_status:
            raise ValueError("Run status must be a non-empty string.")
        now = datetime.now().isoformat(timespec="seconds")
        with self.db.atomic():
            cursor = self.db.conn.execute(
                "UPDATE cp_runs SET status = ?, finished_at = ? WHERE run_id = ?",
                (normalized_status, now, run_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(f"Cannot finish unknown run ID: {run_id}")

    @staticmethod
    def _json_safe(value: object) -> object:
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
                        # EXPECTED_FALLBACK: Column does not contain parseable date format or is non-tabular
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
    ) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        self.db.conn.execute(
            """INSERT INTO cp_run_failures
               (run_id, failed_isin, stage, error_type, error_message, traceback_log, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (run_id, failed_isin, stage, error_type, error_message, traceback_log, now),
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
                    "UPDATE cp_runs SET status = 'RECOVERY_REQUIRED', finished_at = ? WHERE run_id = ?",
                    (now, run_id),
                )
                self.log_run_failure(
                    run_id=run_id,
                    failed_isin=None,
                    stage=stage,
                    error_type="CROSS_STORE_DIVERGENCE",
                    error_message=error_message,
                    traceback_log=traceback_log,
                )
        except Exception:
            # Fallback to direct connection if main connection or savepoint failed
            import sqlite3

            conn = sqlite3.connect(self.db.db_path, timeout=30.0)
            try:
                conn.execute(
                    "UPDATE cp_runs SET status = 'RECOVERY_REQUIRED', finished_at = ? WHERE run_id = ?",
                    (now, run_id),
                )
                conn.execute(
                    """INSERT INTO cp_run_failures
                       (run_id, failed_isin, stage, error_type, error_message, traceback_log, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (run_id, None, stage, "CROSS_STORE_DIVERGENCE", error_message, traceback_log, now),
                )
                conn.commit()
            finally:
                conn.close()

    def mark_recovery_converged(self, recovered_run_id: str, reconciling_run_id: str) -> None:
        """Mark a prior RECOVERY_REQUIRED run as CONVERGED after successful reconciliation."""
        now = datetime.now().isoformat(timespec="seconds")
        with self.db.atomic():
            self.db.conn.execute(
                "UPDATE cp_runs SET status = 'CONVERGED' WHERE run_id = ? AND UPPER(status) = 'RECOVERY_REQUIRED'",
                (recovered_run_id,),
            )
            self.log_run_failure(
                run_id=recovered_run_id,
                failed_isin=None,
                stage="RECOVERY_CONVERGENCE",
                error_type="CONVERGED",
                error_message=f"Cross-store divergence resolved and converged by run {reconciling_run_id} at {now}.",
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
                error_type = "CROSS_STORE_DIVERGENCE" if is_committing else "InterruptedRunError"
                error_message = (
                    "Run crashed while COMMITTING; cross-store commit state uncertain, recovery required."
                    if is_committing
                    else f"Run was left in {status} state and recovered as FAILED on startup."
                )

                cursor = self.db.conn.execute(
                    "UPDATE cp_runs SET status = ?, finished_at = ? "
                    "WHERE run_id = ? AND UPPER(status) IN ('STARTED', 'RUNNING', 'COMMITTING')",
                    (new_status, now, run_id),
                )
                if cursor.rowcount != 1:
                    continue
                self.log_run_failure(
                    run_id=run_id,
                    failed_isin=None,
                    stage="RECOVERY",
                    error_type=error_type,
                    error_message=error_message,
                )
                recovered += 1
        if recovered:
            from personal_finance_etl.backend.utils.logger import logger

            logger.warning("[CONTROL_PLANE] Recovered %d interrupted run(s).", recovered)
