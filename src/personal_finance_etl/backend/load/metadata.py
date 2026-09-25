import os

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.config.settings import Settings
from personal_finance_etl.backend.load.control_plane.orchestrator import ControlPlane
from personal_finance_etl.backend.load.control_plane.utils import (
    FILE_TYPE_MAP,
    compute_file_hash,
    generate_file_id,
)
from personal_finance_etl.backend.load.registry import DATA_CONTRACT_REGISTRY
from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.utils.logger import logger


class MetaLayer:
    """
    Manages all DuckDB analytical telemetry schemas.
    Maintains a strictly lean, "current-state" snapshot of the Lakehouse.
    Run tracking and historical lineages are deferred to the SQLite ControlPlane.
    """

    def __init__(self, db_manager: DuckDBManager, cfg: Settings, rules: FinancialRules | None):
        self.db_manager = db_manager
        self.cfg = cfg
        self.rules = rules
        self.conn = self.db_manager.conn

    def heal_duckdb_registry(self, cp: "ControlPlane") -> None:
        """Self-heals DuckDB file registry if items in SQLite control plane are missing."""
        duckdb_rows = self.conn.execute("SELECT relative_path FROM meta.m_File_Registry").fetchall()
        duckdb_paths = {str(r[0]) for r in duckdb_rows}
        raw_all: dict[str, list[str]] = cp.artifacts.get_all_paths_by_category()

        missing_count = 0
        for _cat, paths in raw_all.items():
            for path in paths:
                if path not in duckdb_paths:
                    cp.artifacts.db.conn.execute(
                        "UPDATE cp_file_registry SET sync_status = 'PENDING_BRONZE' WHERE relative_path = ?",
                        [path],
                    )
                    missing_count += 1

        if missing_count > 0:
            logger.info(
                f"Self-Healing: {missing_count} file(s) in Raw Store missing from DuckDB. Re-queued for Bronze."
            )

    def register_file(
        self, filepath: str, category: str, row_count: int, cp: "ControlPlane"
    ) -> None:
        """Upserts a record into meta.m_File_Registry after successful Bronze ingestion."""
        unique_path = filepath.replace("\\", "/")
        file_name = os.path.basename(filepath)

        if filepath.startswith("virtual://"):
            file_type = "parquet"
            # Retrieve metadata from Raw Store registry directly
            reg = cp.artifacts.get_registry()
            file_hash: str = str(reg.get(unique_path, ""))
            file_size = 0
        else:
            file_type = FILE_TYPE_MAP.get(category, "csv")
            file_hash = compute_file_hash(filepath)
            try:
                file_size = os.path.getsize(filepath)
            except OSError:
                file_size = 0

        file_id = generate_file_id(filepath)

        # Check if exists
        exists = self.conn.execute(
            "SELECT 1 FROM meta.m_File_Registry WHERE relative_path = ?", [unique_path]
        ).fetchone()

        if exists:
            self.conn.execute(
                """
                UPDATE meta.m_File_Registry 
                SET last_ingested = CURRENT_TIMESTAMP, 
                    file_hash = ?, file_size_bytes = ?, row_count = ?
                WHERE relative_path = ?
                """,
                [file_hash, file_size, row_count, unique_path],
            )
        else:
            self.conn.execute(
                """
                INSERT INTO meta.m_File_Registry 
                (file_id, file_name, relative_path, file_category, file_type, 
                 first_ingested, last_ingested, file_hash, file_size_bytes, row_count)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, ?)
                """,
                [
                    file_id,
                    file_name,
                    unique_path,
                    category,
                    file_type,
                    file_hash,
                    file_size,
                    row_count,
                ],
            )

    def load(self, dfs: dict[str, pl.DataFrame]) -> None:
        """Truncates and records the latest table sizes and financial rules into the meta schema."""
        logger.info("Recording current table metrics and configurations to Meta Layer...")

        self.conn.execute("DELETE FROM meta.m_Table_Row_Counts")
        self.conn.execute("DELETE FROM meta.m_Financial_Rules")
        self.conn.execute("DELETE FROM meta.m_Settings")

        contract_by_id = {c.contract_id: c for c in DATA_CONTRACT_REGISTRY}

        for contract_id, df in dfs.items():
            contract = contract_by_id.get(contract_id)

            if contract is None:
                continue

            try:
                count = df.height
            except Exception:
                count = 0

            physical_table = contract.physical_table.split(".", maxsplit=1)[-1]

            self.conn.execute(
                """
                INSERT INTO meta.m_Table_Row_Counts
                (schema_name, table_name, row_count, generated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [
                    contract.layer,
                    physical_table,
                    count,
                ],
            )

        if self.rules is not None:
            rule_records = self.rules.export_to_db_records()
            for record in rule_records:
                self.conn.execute(
                    """
                    INSERT INTO meta.m_Financial_Rules 
                    (Rule_Domain, Rule_Type, Target_Level, Target_ID) 
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        record["Rule_Domain"],
                        record["Rule_Type"],
                        record["Target_Level"],
                        record["Target_ID"],
                    ],
                )

        setting_records = self.cfg.export_to_db_records()
        for record in setting_records:
            self.conn.execute(
                """
                INSERT INTO meta.m_Settings 
                (Setting_Group, Setting_Key, Setting_Value) 
                VALUES (?, ?, ?)
                """,
                [
                    record["Setting_Group"],
                    record["Setting_Key"],
                    record["Setting_Value"],
                ],
            )

        logger.info("Meta layer load complete. DuckDB snapshot represents the latest active state.")
