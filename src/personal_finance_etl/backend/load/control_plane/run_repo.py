import hashlib
import importlib.metadata
import uuid
from datetime import datetime

from personal_finance_etl.backend.load.control_plane.connection import SQLiteManager


class RunRepository:
    def __init__(self, db: SQLiteManager):
        self.db = db

    def start_run(self, cfg_json: str | None = None, rules_json: str | None = None) -> str:
        run_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        settings_id, rules_id = None, None

        if cfg_json:
            cfg_hash = hashlib.sha256(cfg_json.encode("utf-8")).hexdigest()
            settings_id = f"snap_set_{cfg_hash[:12]}"
            self.db.conn.execute(
                "INSERT OR IGNORE INTO cp_settings_snapshots (snapshot_id, content_hash, canonical_payload, created_at) VALUES (?, ?, ?, ?)",
                (settings_id, cfg_hash, cfg_json, now),
            )

        if rules_json:
            rules_hash = hashlib.sha256(rules_json.encode("utf-8")).hexdigest()
            rules_id = f"snap_rule_{rules_hash[:12]}"
            self.db.conn.execute(
                "INSERT OR IGNORE INTO cp_rules_snapshots (snapshot_id, content_hash, canonical_payload, created_at) VALUES (?, ?, ?, ?)",
                (rules_id, rules_hash, rules_json, now),
            )

        try:
            app_version = f"v{importlib.metadata.version('personal-finance-etl')}"
        except importlib.metadata.PackageNotFoundError:
            app_version = "v-unknown"

        self.db.conn.execute(
            """
            INSERT INTO cp_runs (run_id, started_at, status, application_version, schema_version, settings_snapshot_id, rules_snapshot_id)
            VALUES (?, ?, 'STARTED', ?, 'v1', ?, ?)
            """,
            (run_id, now, app_version, settings_id, rules_id),
        )
        return run_id

    def update_run_status(self, run_id: str, status: str) -> None:
        self.db.conn.execute("UPDATE cp_runs SET status = ? WHERE run_id = ?", (status, run_id))

    def save_execution_log(self, run_id: str, log_data: bytes) -> None:
        self.db.conn.execute(
            "UPDATE cp_runs SET execution_log = ? WHERE run_id = ?", (log_data, run_id)
        )

    def finish_run(self, run_id: str, status: str) -> None:
        now = datetime.now().isoformat()
        self.db.conn.execute(
            "UPDATE cp_runs SET status = ?, finished_at = ? WHERE run_id = ?",
            (status.upper(), now, run_id),
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
        now = datetime.now().isoformat()
        self.db.conn.execute(
            "INSERT INTO cp_run_failures (run_id, failed_isin, stage, error_type, error_message, traceback_log, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_id, failed_isin, stage, error_type, error_message, traceback_log, now),
        )

    def recover_stale_runs(self) -> None:
        """
        Transitions any run in an unfinished state (STARTED, RUNNING, COMMITTING)
        to FAILED, indicating the previous process was interrupted.
        """
        now = datetime.now().isoformat()

        # Log failure for all stale runs
        cursor = self.db.conn.execute(
            "SELECT run_id, status FROM cp_runs WHERE status IN ('STARTED', 'RUNNING', 'COMMITTING')"
        )
        stale_runs = cursor.fetchall()

        for row in stale_runs:
            run_id = row[0]
            status = row[1]
            self.log_run_failure(
                run_id=run_id,
                failed_isin=None,
                stage="RECOVERY",
                error_type="InterruptedRunError",
                error_message=f"Run was left in {status} state and recovered as FAILED on startup.",
            )

            self.db.conn.execute(
                "UPDATE cp_runs SET status = 'FAILED', finished_at = ? WHERE run_id = ?",
                (now, run_id),
            )
        self.db.commit()
