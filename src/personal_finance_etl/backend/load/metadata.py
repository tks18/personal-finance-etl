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
from personal_finance_etl.backend.load.database import DuckDBManager
from personal_finance_etl.backend.load.registry import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
)
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

        # We only care about checking files that CP thinks are SYNCED
        synced_registry = cp.artifacts.get_all_registry()

        cat_to_contract = {
            contract.sync_category: contract for contract in BRONZE_CONTRACT_REGISTRY
        }
        cat_to_table = {k: v.physical_table for k, v in cat_to_contract.items()}

        # Pre-check which tables actually exist in DuckDB and what files they own
        tables_exist: dict[str, bool] = {}
        table_files: dict[str, set[str]] = {}
        for contract in BRONZE_CONTRACT_REGISTRY:
            table = contract.physical_table
            try:
                self.conn.execute(f"SELECT 1 FROM {table} LIMIT 1")
                tables_exist[table] = True
                if not contract.is_full_replace:
                    rows = self.conn.execute(
                        f"SELECT DISTINCT __file_name__ FROM {table}"
                    ).fetchall()
                    table_files[table] = {str(r[0]) for r in rows}
            except Exception:
                tables_exist[table] = False
                table_files[table] = set()

        missing_count = 0
        raw_all: dict[str, list[str]] = cp.artifacts.get_all_paths_by_category()

        for cat, paths in raw_all.items():
            contract = cat_to_contract.get(cat)
            table = contract.physical_table if contract else None
            table_exists = tables_exist.get(table, False) if table else True
            files_in_table: set[str] = table_files.get(table, set()) if table else set()

            for path in paths:
                status = synced_registry.get(path)
                if status == "SYNCED":
                    # If it's missing from meta OR the physical bronze table is gone
                    if path not in duckdb_paths or not table_exists:
                        cp.artifacts.db.conn.execute(
                            "UPDATE cp_file_registry SET sync_status = 'PENDING_BRONZE' WHERE relative_path = ?",
                            [path],
                        )
                        missing_count += 1
                    # Or if it's an event source and its specific rows are missing
                    elif (
                        contract
                        and not contract.is_full_replace
                        and os.path.basename(path) not in files_in_table
                    ):
                        cp.artifacts.db.conn.execute(
                            "UPDATE cp_file_registry SET sync_status = 'PENDING_BRONZE' WHERE relative_path = ?",
                            [path],
                        )
                        missing_count += 1

        # Delete from DuckDB anything that no longer exists in CP
        deleted_count = 0
        for duckdb_path in duckdb_paths:
            if duckdb_path not in synced_registry:
                # Get the category from DuckDB to find the table
                row = self.conn.execute(
                    "SELECT file_name, file_category FROM meta.m_File_Registry WHERE relative_path = ?",
                    [duckdb_path],
                ).fetchone()

                if row:
                    fname, cat = row
                    table = cat_to_table.get(cat)
                    if table and tables_exist.get(table, False):
                        try:
                            self.conn.execute(
                                f"DELETE FROM {table} WHERE __file_name__ = ?", [fname]
                            )
                        except Exception as e:
                            logger.debug(f"[Bronze] Could not delete {fname} from {table}: {e}")

                    self.conn.execute(
                        "DELETE FROM meta.m_File_Registry WHERE relative_path = ?", [duckdb_path]
                    )
                    deleted_count += 1

        if missing_count > 0 or deleted_count > 0:
            logger.info(
                f"Self-Healing: Re-queued {missing_count} missing file(s). Purged {deleted_count} deleted file(s)."
            )

    def migrate_identity(self, renames: list[tuple[str, str, str]]) -> None:
        """Migrates relative paths in DuckDB meta.m_File_Registry."""
        if not renames:
            return

        for old_path, new_path, _ in renames:
            new_rel_path = new_path.replace("\\", "/")
            old_rel_path = old_path.replace("\\", "/")
            new_name = os.path.basename(new_path)
            new_file_id = generate_file_id(new_rel_path)

            self.conn.execute(
                """
                UPDATE meta.m_File_Registry
                SET relative_path = ?, file_name = ?, file_id = ?
                WHERE relative_path = ?
                """,
                [new_rel_path, new_name, new_file_id, old_rel_path],
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
            file_data = reg.get(unique_path)
            file_hash: str = str(file_data[0]) if file_data else ""
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

        self.conn.execute("DELETE FROM meta.m_Data_Contracts")
        from personal_finance_etl.backend.load.registry import BRONZE_CONTRACT_REGISTRY

        for b_contract in BRONZE_CONTRACT_REGISTRY:
            self.conn.execute(
                """
                INSERT INTO meta.m_Data_Contracts 
                (contract_id, layer, physical_table, domain, grain, producer, is_full_replace, publication_order) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    b_contract.extraction_attribute,
                    "bronze",
                    b_contract.physical_table,
                    "Raw",
                    "File",
                    "ControlPlane",
                    b_contract.is_full_replace,
                    0,
                ],
            )

        for contract in DATA_CONTRACT_REGISTRY:
            self.conn.execute(
                """
                INSERT INTO meta.m_Data_Contracts 
                (contract_id, layer, physical_table, domain, grain, producer, is_full_replace, publication_order) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    contract.contract_id,
                    contract.layer,
                    contract.physical_table,
                    contract.domain,
                    contract.grain,
                    contract.producer,
                    True,  # Silver and Gold are strictly full replace layers
                    contract.publication_order,
                ],
            )

        # Clean up any orphaned physical tables in DuckDB that aren't governed by a contract
        # (excluding meta tables since they govern the system itself)
        existing_tables = self.conn.execute(
            "SELECT lower(table_schema), lower(table_name) FROM information_schema.tables WHERE lower(table_schema) IN ('bronze', 'silver', 'gold')"
        ).fetchall()

        valid_physical_tables = {c.physical_table.lower() for c in BRONZE_CONTRACT_REGISTRY}
        valid_physical_tables.update({c.physical_table.lower() for c in DATA_CONTRACT_REGISTRY})

        for schema_name, table_name in existing_tables:
            full_table_name = f"{schema_name}.{table_name}"
            if full_table_name not in valid_physical_tables:
                logger.warning(f"MetaLayer: Dropping orphaned physical table {full_table_name}")
                self.conn.execute(f"DROP TABLE IF EXISTS {full_table_name} CASCADE")

        logger.info("Meta layer load complete. DuckDB snapshot represents the latest active state.")
