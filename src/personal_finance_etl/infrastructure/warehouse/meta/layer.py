"""Metadata projection and data quality tracking in the warehouse Meta layer.

Owns
----
- DuckDB analytical telemetry schemas and current-state snapshots.
- Self-healing DuckDB file registry against SQLite Control Plane records (heal_duckdb_registry).
- Ingested file registration in meta.m_File_Registry (register_file).
- Recording table row metrics, financial rules, settings, data contracts, and simulation run provenance.
- Dropping uncontracted orphaned physical tables in bronze/silver/gold schemas.

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
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.control_plane.hashing import (
    FILE_TYPE_MAP,
    compute_file_hash,
    generate_file_id,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
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

        ext = os.path.splitext(file_path)[1].lower()
        file_type = FILE_TYPE_MAP.get(ext, "UNKNOWN")

        file_id = generate_file_id(file_path)
        policy_attr = ext.lstrip(".").lower()
        should_hash = getattr(self.cfg.FILE_HASH_POLICY, policy_attr, False)

        if should_hash and os.path.exists(file_path):
            file_hash = compute_file_hash(file_path)
        else:
            file_hash = ""

        existing = self.conn.execute(
            "SELECT row_count FROM meta.m_File_Registry WHERE relative_path = ?",
            [unique_path],
        ).fetchone()

        if existing:
            self.conn.execute(
                """
                UPDATE meta.m_File_Registry 
                SET file_hash = ?, file_size_bytes = ?, row_count = ?, last_ingested = CURRENT_TIMESTAMP
                WHERE relative_path = ?
                """,
                [file_hash, file_size, row_count, unique_path],
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
        """Record row counts for all built Silver and Gold analytical tables.

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

    def _record_data_contracts(self) -> None:
        """Publish registered Bronze, Silver, and Gold data contracts into DuckDB."""
        self.conn.execute("DELETE FROM meta.m_Data_Contracts")

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
                    True,
                    contract.publication_order,
                ],
            )

    def _cleanup_orphaned_tables(self) -> None:
        """Drop any physical tables in bronze/silver/gold schemas not declared in contract registries."""
        existing_tables = self.conn.execute(
            "SELECT lower(table_schema), lower(table_name) FROM information_schema.tables WHERE lower(table_schema) IN ('bronze', 'silver', 'gold')"
        ).fetchall()

        valid_physical_tables = {c.physical_table.lower() for c in BRONZE_CONTRACT_REGISTRY}
        valid_physical_tables.update({c.physical_table.lower() for c in DATA_CONTRACT_REGISTRY})

        for schema_name, table_name in existing_tables:
            full_table_name = f"{schema_name}.{table_name}"
            if full_table_name not in valid_physical_tables:
                diagnostics.warning(
                    "MetaLayer: Dropping orphaned physical table %s", full_table_name
                )
                self.conn.execute(f"DROP TABLE IF EXISTS {full_table_name} CASCADE")  # nosec B608

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

    def load(self, dfs: dict[str, pl.DataFrame], cp: ControlPlane | None = None) -> None:
        """Truncate and record latest table row counts, configurations, and simulation provenance.

        Parameters
        ----------
        dfs : dict[str, pl.DataFrame]
            Transformed DataFrames keyed by contract_id.
        cp : ControlPlane, optional
            Active control plane facade for mirroring simulation provenance.
        """
        diagnostics.info("Recording current table metrics and configurations to Meta Layer...")

        self._record_table_metrics(dfs)
        self._record_rules_and_settings()
        self._record_data_contracts()
        self._cleanup_orphaned_tables()

        tables_metadata = [
            {
                "table_name": c.physical_table,
                "grain": c.grain,
                "producer": c.producer,
            }
            for c in DATA_CONTRACT_REGISTRY
        ]
        contract_registry_fingerprint = generate_contract_registry_fingerprint(tables_metadata)

        if cp is not None:
            self._mirror_latest_simulation(cp, contract_registry_fingerprint)

        diagnostics.info(
            "Meta layer load complete. DuckDB snapshot represents the latest active state."
        )
