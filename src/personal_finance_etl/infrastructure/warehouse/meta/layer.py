"""Metadata projection and data quality tracking in the warehouse Meta layer.

Owns
----
- DuckDB analytical telemetry schemas and current-state snapshots.
- Self-healing DuckDB file registry against SQLite Control Plane records (heal_duckdb_registry).
- Ingested file registration in meta.m_File_Registry (register_file).
- Recording table row metrics, financial rules, settings, data contracts, and simulation run provenance.
- Dropping uncontracted orphaned physical tables in pre_bronze/bronze/silver/gold schemas.

Does not own
-------------
- Durable multi-run audit history or raw binary payload vaulting (owned by control plane).
- DuckDB connection lifecycle (owned by infrastructure.warehouse.connection).
"""

from __future__ import annotations

import os
import sqlite3

import duckdb
import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.config.sources.change_detection import SyncStrategy
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.control_plane.hashing import (
    FILE_TYPE_MAP,
    compute_file_hash,
    generate_file_id,
    normalize_path,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    PERSISTED_DATA_SCHEMAS,
    PRE_BRONZE_CONTRACT_REGISTRY,
    WarehouseLayer,
)
from personal_finance_etl.infrastructure.warehouse.fingerprints import (
    generate_contract_registry_fingerprint,
)
from personal_finance_etl.infrastructure.warehouse.meta.healing import DuckDBRegistryHealer
from personal_finance_etl.infrastructure.warehouse.registry import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
)

diagnostics = get_observability_diagnostics("personal_finance_etl.warehouse.meta")


class MetaLayer:
    """Manages all DuckDB analytical telemetry schemas and current-state snapshots.

    Parameters
    ----------
    db_manager : DuckDBManager
        Active DuckDB connection manager.
    cfg : Settings
        Application configuration settings.
    rules : FinancialRules, optional
        Active authoritative financial rules.
    """

    def __init__(
        self,
        db_manager: DuckDBManager,
        cfg: Settings,
        rules: FinancialRules | None = None,
    ) -> None:
        self.db_manager = db_manager
        self.cfg = cfg
        self.rules = rules
        self.conn = self.db_manager.conn

    def heal_duckdb_registry(self, cp: ControlPlane) -> None:
        """Enforce 1:1 bi-directional consistency between SQLite and DuckDB file registries.

        Parameters
        ----------
        cp : ControlPlane
            Active control plane facade.
        """
        DuckDBRegistryHealer(self.conn).heal_duckdb_registry(cp)

    def migrate_identity(self, renames: list[tuple[str, str, str]]) -> None:
        """Migrate relative paths and identifiers in DuckDB meta.m_File_Registry.

        Parameters
        ----------
        renames : list[tuple[str, str, str]]
            Triplets of (old_path, new_path, category).
        """
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
            diagnostics.debug(
                "[METADATA:QUERY] Migrated DuckDB identity from '%s' to '%s'.",
                old_rel_path,
                new_rel_path,
            )

    def register_file(
        self,
        file_path: str,
        category: str,
        row_count: int,
        cp: ControlPlane,
    ) -> None:
        """Insert or update an ingested file's provenance in meta.m_File_Registry.

        Parameters
        ----------
        file_path : str
            Full path to the source file.
        category : str
            File category.
        row_count : int
            Row count inserted.
        cp : ControlPlane
            Control plane instance.
        """
        file_name = os.path.basename(file_path)
        unique_path = file_path
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        ext = os.path.splitext(file_name)[1].lower().lstrip(".")
        if ext == "parquet":
            file_type = "parquet"
        elif ext in ("xlsx", "xls"):
            file_type = "excel"
        elif ext in ("sqlite", "db"):
            file_type = "sqlite"
        elif ext == "csv":
            file_type = "csv"
        else:
            file_type = FILE_TYPE_MAP.get(category, "UNKNOWN")
        file_id = generate_file_id(file_path)
        norm_path = normalize_path(file_path)

        cursor = cp.artifacts.db.conn.execute(
            "SELECT file_hash, file_type, file_size_bytes FROM cp_file_registry WHERE relative_path = ?",
            [norm_path],
        )
        row = cursor.fetchone()
        if row:
            file_hash = row[0] or ""
            file_type = row[1] or file_type
            file_size = row[2] if row[2] is not None else file_size
        else:
            file_hash = compute_file_hash(file_path) if os.path.exists(file_path) else ""

        existing = self.conn.execute(
            "SELECT row_count FROM meta.m_File_Registry WHERE relative_path = ?",
            [unique_path],
        ).fetchone()

        if existing:
            self.conn.execute(
                """
                UPDATE meta.m_File_Registry 
                SET file_hash = ?, file_type = ?, file_size_bytes = ?, row_count = ?, last_ingested = CURRENT_TIMESTAMP
                WHERE relative_path = ?
                """,
                [file_hash, file_type, file_size, row_count, unique_path],
            )
        else:
            self.conn.execute(
                """
                INSERT INTO meta.m_File_Registry 
                (file_id, file_name, relative_path, file_category, file_type, file_hash, file_size_bytes, row_count, first_ingested, last_ingested)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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

    def _record_table_metrics(self, dfs: dict[str, pl.DataFrame]) -> None:
        """Record row counts for all built Pre-Bronze, Silver, and Gold analytical tables.

        Parameters
        ----------
        dfs : dict[str, pl.DataFrame]
            Transformed DataFrames keyed by contract_id.
        """
        self.conn.execute("DELETE FROM meta.m_Table_Row_Counts")
        contract_by_id = {c.contract_id: c for c in DATA_CONTRACT_REGISTRY}

        for contract_id, df in dfs.items():
            contract = contract_by_id.get(contract_id)
            if contract is None:
                continue

            count = df.height
            physical_table = contract.physical_table.split(".", maxsplit=1)[-1]
            self.conn.execute(
                """
                INSERT INTO meta.m_Table_Row_Counts
                (schema_name, table_name, row_count, generated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                [contract.layer, physical_table, count],
            )

        # Record Pre-Bronze table metrics if physical tables exist in DuckDB
        pre_bronze_tables = self.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'pre_bronze'"
        ).fetchall()
        for (tbl_name,) in pre_bronze_tables:
            try:
                row = self.conn.execute(
                    f"SELECT count(*) FROM pre_bronze.{tbl_name}"  # nosec B608
                ).fetchone()
                if row is not None:
                    count = int(row[0])
                    self.conn.execute(
                        """
                        INSERT INTO meta.m_Table_Row_Counts
                        (schema_name, table_name, row_count, generated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        ["pre_bronze", tbl_name, count],
                    )
            except duckdb.CatalogException:
                pass

    def _record_rules_and_settings(self) -> None:
        """Snapshot current financial rules and environment settings into meta tables."""
        self.conn.execute("DELETE FROM meta.m_Financial_Rules")
        self.conn.execute("DELETE FROM meta.m_Settings")

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

    def _record_data_contracts(self, plan: ExecutionPlan | None = None) -> None:
        """Publish registered Pre-Bronze, Bronze, Silver, and Gold data contracts into DuckDB.

        Parameters
        ----------
        plan : ExecutionPlan | None, optional
            Active execution plan. If None, all registered data contracts are recorded.
        """
        self.conn.execute("DELETE FROM meta.m_Data_Contracts")

        for pb_contract in PRE_BRONZE_CONTRACT_REGISTRY:
            if (
                plan is not None
                and pb_contract.dataset_id is not None
                and not plan.is_pre_bronze_dataset_active(pb_contract.dataset_id)
            ):
                continue
            contract_id = str(pb_contract.binding_id)
            self.conn.execute(
                """
                INSERT INTO meta.m_Data_Contracts 
                (contract_id, layer, physical_table, domain, grain, producer, is_full_replace, publication_order) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    contract_id,
                    WarehouseLayer.PRE_BRONZE.value,
                    pb_contract.physical_table,
                    "PreBronze",
                    "Source",
                    "Provider",
                    pb_contract.sync_strategy == SyncStrategy.FULL_REPLACE,
                    -1,
                ],
            )

        for b_contract in BRONZE_CONTRACT_REGISTRY:
            if plan is not None and not plan.is_bronze_dataset_active(b_contract.dataset_id):
                continue
            self.conn.execute(
                """
                INSERT INTO meta.m_Data_Contracts 
                (contract_id, layer, physical_table, domain, grain, producer, is_full_replace, publication_order) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    b_contract.dataset_id.value,
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
            if plan is not None:
                if contract.layer == "silver" and not plan.is_silver_dataset_active(
                    contract.dataset_id
                ):
                    continue
                if contract.layer == "gold" and not plan.is_gold_dataset_active(
                    contract.dataset_id
                ):
                    continue
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
                    True,
                    contract.publication_order,
                ],
            )

    def cleanup_orphaned_tables(self, plan: ExecutionPlan | None = None) -> None:
        """Drop any managed physical tables in pre_bronze/bronze/silver/gold schemas not active in plan.

        Parameters
        ----------
        plan : ExecutionPlan | None, optional
            Active execution plan. If None, all declared contracts are treated as active.

        Notes
        -----
        Unknown or user-defined tables not present in any contract registry are strictly preserved.
        """
        schema_placeholders = ", ".join(f"'{s}'" for s in PERSISTED_DATA_SCHEMAS)
        existing_tables = self.conn.execute(
            f"SELECT lower(table_schema), lower(table_name) "  # nosec B608
            f"FROM information_schema.tables WHERE lower(table_schema) IN ({schema_placeholders})"
        ).fetchall()

        all_managed_tables: set[str] = {
            c.physical_table.lower() for c in PRE_BRONZE_CONTRACT_REGISTRY
        }
        all_managed_tables.update(c.physical_table.lower() for c in BRONZE_CONTRACT_REGISTRY)
        all_managed_tables.update(c.physical_table.lower() for c in DATA_CONTRACT_REGISTRY)

        active_tables: set[str] = set()
        if plan is None:
            active_tables.update(all_managed_tables)
        else:
            active_tables.update(
                c.physical_table.lower()
                for c in PRE_BRONZE_CONTRACT_REGISTRY
                if c.dataset_id is None or plan.is_pre_bronze_dataset_active(c.dataset_id)
            )
            active_tables.update(
                c.physical_table.lower()
                for c in BRONZE_CONTRACT_REGISTRY
                if plan.is_bronze_dataset_active(c.dataset_id)
            )
            active_tables.update(
                c.physical_table.lower()
                for c in DATA_CONTRACT_REGISTRY
                if (
                    (c.layer == "silver" and plan.is_silver_dataset_active(c.dataset_id))
                    or (c.layer == "gold" and plan.is_gold_dataset_active(c.dataset_id))
                )
            )

        to_drop = [
            f"{schema_name}.{table_name}"
            for schema_name, table_name in existing_tables
            if f"{schema_name}.{table_name}" in all_managed_tables
            and f"{schema_name}.{table_name}" not in active_tables
        ]
        contract_order = {
            c.physical_table.lower(): c.publication_order for c in DATA_CONTRACT_REGISTRY
        }
        to_drop.sort(key=lambda t: contract_order.get(t.lower(), 0), reverse=True)

        for full_table_name in to_drop:
            diagnostics.warning(
                "MetaLayer: Dropping inactive managed physical table %s", full_table_name
            )
            self.conn.execute(f"DROP TABLE IF EXISTS {full_table_name}")  # nosec B608

        for schema_name, table_name in existing_tables:
            full_table_name = f"{schema_name}.{table_name}"
            if full_table_name not in all_managed_tables:
                diagnostics.debug(
                    "MetaLayer: Preserving unmanaged / user-defined table %s", full_table_name
                )

    def _cleanup_orphaned_tables(self, plan: ExecutionPlan | None = None) -> None:
        """Drop any managed physical tables not declared in active contracts (internal alias).

        Parameters
        ----------
        plan : ExecutionPlan | None, optional
            Active execution plan.
        """
        self.cleanup_orphaned_tables(plan)

    def _mirror_latest_simulation(
        self,
        cp: ControlPlane,
        contract_registry_fingerprint: str,
    ) -> None:
        """Mirror provenance from the latest successful Monte Carlo simulation into DuckDB meta.

        Parameters
        ----------
        cp : ControlPlane
            Active control plane facade.
        contract_registry_fingerprint : str
            Cryptographic fingerprint of data contracts.
        """
        try:
            sim_row = cp.db.conn.execute(
                """
                SELECT simulation_id, run_id, created_at, root_seed, iterations, horizon,
                       input_as_of_date, model_implementation_version, model_fingerprint,
                       input_fingerprint, result_fingerprint, settings_snapshot_id,
                       rules_snapshot_id, status
                FROM cp_simulation_runs
                WHERE status = 'SUCCESS'
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()

            if sim_row is not None:
                self.conn.execute("DELETE FROM meta.m_Latest_Simulation")
                self.conn.execute(
                    """
                    INSERT INTO meta.m_Latest_Simulation (
                        simulation_id, run_id, created_at, root_seed, iterations, horizon,
                        input_as_of_date, model_implementation_version, model_fingerprint,
                        input_fingerprint, result_fingerprint, contract_registry_fingerprint,
                        settings_snapshot_id, rules_snapshot_id, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    list(sim_row[:11]) + [contract_registry_fingerprint] + list(sim_row[11:]),
                )
                diagnostics.info(
                    "Mirrored latest simulation run '%s' into meta.m_Latest_Simulation "
                    "(contract_registry_fingerprint=%s...).",
                    sim_row[0],
                    contract_registry_fingerprint[:12],
                )
        except (sqlite3.Error, duckdb.Error) as mirror_err:
            diagnostics.warning(
                "Could not mirror simulation run into DuckDB meta: %s",
                mirror_err,
            )

    def load(
        self,
        dfs: dict[str, pl.DataFrame],
        cp: ControlPlane | None = None,
        plan: ExecutionPlan | None = None,
    ) -> None:
        """Truncate and record latest table row counts, configurations, and simulation provenance.

        Parameters
        ----------
        dfs : dict[str, pl.DataFrame]
            Transformed DataFrames keyed by contract_id.
        cp : ControlPlane, optional
            Active control plane facade for mirroring simulation provenance.
        plan : ExecutionPlan, optional
            Active execution plan specifying active datasets and pruned columns.
        """
        diagnostics.info("Recording current table metrics and configurations to Meta Layer...")

        self._record_table_metrics(dfs)
        self._record_rules_and_settings()
        self._record_data_contracts(plan)
        self.cleanup_orphaned_tables(plan)

        tables_metadata = [
            {
                "dataset_id": c.dataset_id.value,
                "table_name": c.physical_table,
                "grain": c.grain,
                "producer": c.producer,
            }
            for c in DATA_CONTRACT_REGISTRY
            if plan is None
            or (c.layer == "silver" and plan.is_silver_dataset_active(c.dataset_id))
            or (c.layer == "gold" and plan.is_gold_dataset_active(c.dataset_id))
        ]
        contract_registry_fingerprint = generate_contract_registry_fingerprint(tables_metadata)

        if cp is not None:
            self._mirror_latest_simulation(cp, contract_registry_fingerprint)

        diagnostics.info(
            "Meta layer load complete. DuckDB snapshot represents the latest active state."
        )
