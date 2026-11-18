"""Self-healing synchronization between SQLite Control Plane and DuckDB file registries.

Owns
----
- DuckDBRegistryHealer: Enforces 1:1 bi-directional consistency between SQLite and DuckDB file registries.
- Pruning dangling DuckDB registry entries and table rows for deleted files.
- Re-queuing missing or dropped bronze tables/files back to PENDING_BRONZE in SQLite.

Does not own
-------------
- DuckDB connection lifecycle (owned by infrastructure.warehouse.connection).
- Durable multi-run audit history (owned by control plane).
- Warehouse telemetry recording (owned by infrastructure.warehouse.meta).
"""

from __future__ import annotations

import os

import duckdb

from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.warehouse.contracts import (
    PRE_BRONZE_ARTIFACT_ID,
    PRE_BRONZE_CONTRACT_REGISTRY,
    PreBronzeDataContract,
)
from personal_finance_etl.infrastructure.warehouse.registry import (
    BRONZE_CONTRACT_REGISTRY,
    BronzeDataContract,
    get_bronze_contract_by_dataset_id,
)

diagnostics = get_observability_diagnostics("personal_finance_etl.warehouse.meta.healing")

__all__ = ["DuckDBRegistryHealer"]


class DuckDBRegistryHealer:
    """Enforces bi-directional consistency between SQLite Control Plane and DuckDB file registries.

    Parameters
    ----------
    conn : duckdb.DuckDBPyConnection
        Active DuckDB connection.
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection) -> None:
        self.conn = conn

    def _inspect_bronze_table_files(self) -> tuple[dict[str, bool], dict[str, set[str]]]:
        """Check presence of physical Pre-Bronze and Bronze tables and scan distinct loaded filenames.

        Returns
        -------
        tuple[dict[str, bool], dict[str, set[str]]]
            (tables_exist, table_files).
        """
        existing_tables = {
            f"{r[0]}.{r[1]}".lower()
            for r in self.conn.execute(
                "SELECT lower(table_schema), lower(table_name) "
                "FROM information_schema.tables WHERE lower(table_schema) IN ('bronze', 'pre_bronze')"
            ).fetchall()
        }
        tables_exist: dict[str, bool] = {}
        table_files: dict[str, set[str]] = {}
        for contract in BRONZE_CONTRACT_REGISTRY:
            table = contract.physical_table
            is_present = table.lower() in existing_tables
            tables_exist[table] = is_present
            if is_present and not contract.is_full_replace:
                try:
                    rows = self.conn.execute(
                        f"SELECT DISTINCT __file_name__ FROM {table}"  # nosec B608
                    ).fetchall()
                    table_files[table] = {str(r[0]) for r in rows}
                except duckdb.CatalogException:
                    table_files[table] = set()
            else:
                table_files[table] = set()

        for pb_contract in PRE_BRONZE_CONTRACT_REGISTRY:
            pb_table = pb_contract.physical_table
            tables_exist[pb_table] = pb_table.lower() in existing_tables

        return tables_exist, table_files

    @staticmethod
    def _is_sync_record_missing(
        path: str,
        status: str | None,
        duckdb_paths: set[str],
        tables_exist: dict[str, bool],
        bronze_contracts: list[BronzeDataContract],
        pb_contracts: list[PreBronzeDataContract],
        row_count: int,
        table_files: dict[str, set[str]],
    ) -> bool:
        """Determine if an individual synced file is absent or dropped from DuckDB.

        Parameters
        ----------
        path : str
            Relative file path.
        status : str | None
            Sync status string from control plane registry.
        duckdb_paths : set[str]
            Set of paths present in DuckDB m_File_Registry.
        tables_exist : dict[str, bool]
            Map of physical table name to existence in DuckDB.
        bronze_contracts : list[BronzeDataContract]
            Matching bronze contracts for this category.
        pb_contracts : list[PreBronzeDataContract]
            Matching Pre-Bronze contracts for this category.
        row_count : int
            DuckDB row count for this file.
        table_files : dict[str, set[str]]
            Distinct filenames loaded per table.

        Returns
        -------
        bool
            True if file needs healing back to PENDING_BRONZE.
        """
        if status != "SYNCED":
            return False
        if path not in duckdb_paths:
            return True

        for pb in pb_contracts:
            if not tables_exist.get(pb.physical_table, False):
                return True

        for b_contract in bronze_contracts:
            target_table = b_contract.physical_table
            if not tables_exist.get(target_table, False):
                return True
            if (
                not b_contract.is_full_replace
                and row_count > 0
                and os.path.basename(path) not in table_files.get(target_table, set())
            ):
                return True

        return False

    def _heal_missing_sync_records(
        self,
        cp: ControlPlane,
        duckdb_paths: set[str],
        duckdb_row_counts: dict[str, int],
        synced_registry: dict[str, str],
        cat_to_bronze_contracts: dict[str, list[BronzeDataContract]],
        cat_to_pb_contracts: dict[str, list[PreBronzeDataContract]],
        tables_exist: dict[str, bool],
        table_files: dict[str, set[str]],
    ) -> int:
        """Find registered SQLite files absent or dropped in DuckDB and re-mark as PENDING_BRONZE.

        Parameters
        ----------
        cp : ControlPlane
            Control plane instance.
        duckdb_paths : set[str]
            Set of paths in DuckDB file registry.
        duckdb_row_counts : dict[str, int]
            Row counts per path in DuckDB.
        synced_registry : dict[str, str]
            Map of path to sync status in SQLite.
        cat_to_bronze_contracts : dict[str, list[BronzeDataContract]]
            Map of category to list of bronze contracts.
        cat_to_pb_contracts : dict[str, list[PreBronzeDataContract]]
            Map of category to list of pre-bronze contracts.
        tables_exist : dict[str, bool]
            Map of table name to existence flag.
        table_files : dict[str, set[str]]
            Map of table name to set of filenames present.

        Returns
        -------
        int
            Count of healed missing files.
        """
        missing_count = 0
        raw_all: dict[str, list[str]] = cp.artifacts.get_all_paths_by_category()

        for cat, paths in raw_all.items():
            b_contracts = cat_to_bronze_contracts.get(cat, [])
            pb_contracts = cat_to_pb_contracts.get(cat, [])

            for path in paths:
                status = synced_registry.get(path)
                row_count = duckdb_row_counts.get(path, 0)
                if self._is_sync_record_missing(
                    path,
                    status,
                    duckdb_paths,
                    tables_exist,
                    b_contracts,
                    pb_contracts,
                    row_count,
                    table_files,
                ):
                    cp.artifacts.db.conn.execute(
                        "UPDATE cp_file_registry SET sync_status = 'PENDING_BRONZE' WHERE relative_path = ?",
                        [path],
                    )
                    missing_count += 1
        return missing_count

    def _prune_dangling_duckdb_files(
        self,
        duckdb_paths: set[str],
        synced_registry: dict[str, str],
        cat_to_table: dict[str, str],
        tables_exist: dict[str, bool],
    ) -> int:
        """Remove DuckDB registry entries and table rows for files no longer in control plane.

        Parameters
        ----------
        duckdb_paths : set[str]
            Paths present in DuckDB.
        synced_registry : dict[str, str]
            Paths mapped in SQLite control plane.
        cat_to_table : dict[str, str]
            Map of category to table name.
        tables_exist : dict[str, bool]
            Map of table name to existence flag.

        Returns
        -------
        int
            Count of pruned files.
        """
        deleted_count = 0
        for duckdb_path in duckdb_paths:
            if duckdb_path not in synced_registry:
                row = self.conn.execute(
                    "SELECT file_name, file_category, file_id FROM meta.m_File_Registry WHERE relative_path = ?",
                    [duckdb_path],
                ).fetchone()

                if row:
                    fname, cat, file_id = row
                    del_table = cat_to_table.get(cat)
                    if del_table and tables_exist.get(del_table, False):
                        try:
                            self.conn.execute(
                                f"DELETE FROM {del_table} WHERE __file_name__ = ?",  # nosec B608
                                [fname],
                            )
                        except duckdb.CatalogException:
                            pass

                    # Prune associated rows in Pre-Bronze tables using explicit artifact provenance
                    if file_id:
                        for pb_contract in PRE_BRONZE_CONTRACT_REGISTRY:
                            try:
                                self.conn.execute(
                                    f"DELETE FROM {pb_contract.physical_table} WHERE {PRE_BRONZE_ARTIFACT_ID} = ?",  # nosec B608
                                    [file_id],
                                )
                            except duckdb.CatalogException:
                                pass

                self.conn.execute(
                    "DELETE FROM meta.m_File_Registry WHERE relative_path = ?",
                    [duckdb_path],
                )
                deleted_count += 1
        return deleted_count

    def heal_duckdb_registry(self, cp: ControlPlane) -> None:
        """Enforce 1:1 bi-directional consistency between SQLite and DuckDB file registries.

        Parameters
        ----------
        cp : ControlPlane
            Active control plane facade.
        """
        diagnostics.info(
            "Executing self-healing synchronization between SQLite and DuckDB registries..."
        )

        tables_exist, table_files = self._inspect_bronze_table_files()

        synced_registry: dict[str, str] = {
            r[0]: r[1]
            for r in cp.artifacts.db.conn.execute(
                "SELECT relative_path, sync_status FROM cp_file_registry"
            ).fetchall()
        }

        duckdb_rows = self.conn.execute(
            "SELECT relative_path, row_count FROM meta.m_File_Registry"
        ).fetchall()
        duckdb_paths = {r[0] for r in duckdb_rows}
        duckdb_row_counts = {r[0]: r[1] for r in duckdb_rows}

        cat_to_bronze_contracts: dict[str, list[BronzeDataContract]] = {}
        for c in BRONZE_CONTRACT_REGISTRY:
            cat_to_bronze_contracts.setdefault(c.sync_category, []).append(c)
            cat_to_bronze_contracts.setdefault(c.dataset_id.value, []).append(c)

        cat_to_pb_contracts: dict[str, list[PreBronzeDataContract]] = {}
        for pb in PRE_BRONZE_CONTRACT_REGISTRY:
            cat_to_pb_contracts.setdefault(pb.dataset_id.value, []).append(pb)
            b_match = get_bronze_contract_by_dataset_id(pb.dataset_id)
            if b_match is not None:
                cat_to_pb_contracts.setdefault(b_match.sync_category, []).append(pb)

        cat_to_table = {c.sync_category: c.physical_table for c in BRONZE_CONTRACT_REGISTRY}

        deleted_count = self._prune_dangling_duckdb_files(
            duckdb_paths, synced_registry, cat_to_table, tables_exist
        )
        missing_count = self._heal_missing_sync_records(
            cp,
            duckdb_paths,
            duckdb_row_counts,
            synced_registry,
            cat_to_bronze_contracts,
            cat_to_pb_contracts,
            tables_exist,
            table_files,
        )

        if deleted_count > 0 or missing_count > 0:
            diagnostics.warning(
                "MetaLayer Healing Report: Pruned %d orphaned records from DuckDB; "
                "Re-queued %d missing/dropped files into SQLite Control Plane.",
                deleted_count,
                missing_count,
            )
        else:
            diagnostics.info("MetaLayer: SQLite Control Plane and DuckDB are 100%% synchronized.")
