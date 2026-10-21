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

import logging
import os

import duckdb

from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.warehouse.registry import (
    BRONZE_CONTRACT_REGISTRY,
    BronzeDataContract,
)

logger = logging.getLogger("personal_finance_etl.warehouse.meta.healing")

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
        """Check presence of physical bronze tables and scan distinct loaded filenames.

        Returns
        -------
        tuple[dict[str, bool], dict[str, set[str]]]
            (tables_exist, table_files).
        """
        existing_tables = {
            f"{r[0]}.{r[1]}".lower()
            for r in self.conn.execute(
                "SELECT lower(table_schema), lower(table_name) "
                "FROM information_schema.tables WHERE lower(table_schema) = 'bronze'"
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
        return tables_exist, table_files

    @staticmethod
    def _is_sync_record_missing(
        path: str,
        status: str | None,
        duckdb_paths: set[str],
        table_exists: bool,
        b_contract: BronzeDataContract | None,
        row_count: int,
        files_in_table: set[str],
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
        table_exists : bool
            Whether target bronze table exists.
        b_contract : BronzeDataContract | None
            Matching bronze contract if found.
        row_count : int
            DuckDB row count for this file.
        files_in_table : set[str]
            Distinct filenames loaded in table.

        Returns
        -------
        bool
            True if file needs healing back to PENDING_BRONZE.
        """
        if status != "SYNCED":
            return False
        if path not in duckdb_paths or not table_exists:
            return True
        return (
            b_contract is not None
            and not b_contract.is_full_replace
            and row_count > 0
            and os.path.basename(path) not in files_in_table
        )

    def _heal_missing_sync_records(
        self,
        cp: ControlPlane,
        duckdb_paths: set[str],
        duckdb_row_counts: dict[str, int],
        synced_registry: dict[str, str],
        cat_to_contract: dict[str, BronzeDataContract],
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
        cat_to_contract : dict[str, BronzeDataContract]
            Map of category to bronze contract.
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
            b_contract = cat_to_contract.get(cat)
            target_table = b_contract.physical_table if b_contract else None
            table_exists = tables_exist.get(target_table, False) if target_table else True
            files_in_table: set[str] = (
                table_files.get(target_table, set()) if target_table else set()
            )

            for path in paths:
                status = synced_registry.get(path)
                row_count = duckdb_row_counts.get(path, 0)
                if self._is_sync_record_missing(
                    path, status, duckdb_paths, table_exists, b_contract, row_count, files_in_table
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
                    "SELECT file_name, file_category FROM meta.m_File_Registry WHERE relative_path = ?",
                    [duckdb_path],
                ).fetchone()

                if row:
                    fname, cat = row
                    del_table = cat_to_table.get(cat)
                    if del_table and tables_exist.get(del_table, False):
                        try:
                            self.conn.execute(
                                f"DELETE FROM {del_table} WHERE __file_name__ = ?",  # nosec B608
                                [fname],
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
        logger.info(
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

        cat_to_contract = {c.sync_category: c for c in BRONZE_CONTRACT_REGISTRY}
        cat_to_table = {c.sync_category: c.physical_table for c in BRONZE_CONTRACT_REGISTRY}

        deleted_count = self._prune_dangling_duckdb_files(
            duckdb_paths, synced_registry, cat_to_table, tables_exist
        )
        missing_count = self._heal_missing_sync_records(
            cp,
            duckdb_paths,
            duckdb_row_counts,
            synced_registry,
            cat_to_contract,
            tables_exist,
            table_files,
        )

        if deleted_count > 0 or missing_count > 0:
            logger.warning(
                "MetaLayer Healing Report: Pruned %d orphaned records from DuckDB; "
                "Re-queued %d missing/dropped files into SQLite Control Plane.",
                deleted_count,
                missing_count,
            )
        else:
            logger.info("MetaLayer: SQLite Control Plane and DuckDB are 100%% synchronized.")
