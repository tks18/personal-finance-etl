"""Full-replace presentation layer loading and table management in the warehouse Gold layer.

Owns
----
- Full-replace publishing of presentation DataFrames into gold.* DuckDB tables.
- Presentation schema recreation and publication in forward topological order.
- LazyFrame execution plan logging and row insertion via DuckDB BY NAME.

Does not own
-------------
- Presentation engine calculations (owned by domain and application services).
- Silver analytical layer publishing (owned by infrastructure.warehouse.silver).
- DuckDB connection lifecycle (owned by infrastructure.warehouse.connection).
"""

from __future__ import annotations

import polars as pl

from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.execution_plan import ExecutionPlan
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    PresentationKind,
)
from personal_finance_etl.infrastructure.observability import (
    ObservabilityEmitter,
    get_global_emitter,
)
from personal_finance_etl.infrastructure.observability.diagnostics import (
    get_observability_diagnostics,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.registry import DATA_CONTRACT_REGISTRY
from personal_finance_etl.infrastructure.warehouse.schema.gold import (
    generate_gold_ddl,
)

diagnostics = get_observability_diagnostics("personal_finance_etl.warehouse.gold")


class GoldLayer:
    """Full-replace layer for BI-ready presentation tables.

    Parameters
    ----------
    db_manager : DuckDBManager
        Active DuckDB connection manager.
    """

    def __init__(
        self,
        db_manager: DuckDBManager,
        emitter: ObservabilityEmitter | None = None,
    ) -> None:
        self.db_manager = db_manager
        self.emitter = emitter or get_global_emitter()

    def _write(self, df: pl.DataFrame | pl.LazyFrame, table_name: str) -> int:
        """Write DataFrame or LazyFrame into a Gold presentation table.

        Parameters
        ----------
        df : pl.DataFrame | pl.LazyFrame
            Data to publish.
        table_name : str
            Physical Gold table name.

        Returns
        -------
        int
            Number of rows inserted.
        """
        if isinstance(df, pl.LazyFrame):
            compact_plan = df.explain().replace("\n", " | ")
            diagnostics.debug("Physical Plan for Gold '%s': %s", table_name, compact_plan)
            # Materialization Boundary: PUBLICATION_BOUNDARY
            # Terminal execution of lazy presentation graph for DuckDB Gold table insertion
            df = df.collect()

        if df.height == 0:
            return 0

        pragma_info = self.db_manager.conn.execute(
            f"PRAGMA table_info('{table_name}')"  # nosec B608
        ).fetchall()
        target_columns = {row[1] for row in pragma_info}
        if target_columns:
            selected_cols = [c for c in df.columns if c in target_columns]
            df = df.select(selected_cols)

        self.db_manager.conn.register("temp_df", df)
        self.db_manager.conn.execute(
            f"INSERT INTO {table_name} BY NAME SELECT * FROM temp_df"  # nosec B608
        )
        self.db_manager.conn.unregister("temp_df")
        return df.height

    def load(
        self,
        dfs: dict[str, pl.DataFrame],
        plan: ExecutionPlan | None = None,
    ) -> None:
        """Re-create plan-aware gold tables and insert presentation DataFrames.

        Parameters
        ----------
        dfs : dict[str, pl.DataFrame]
            Presentation DataFrames keyed by contract_id.
        plan : ExecutionPlan, optional
            Active execution plan. If None, full gold schema is initialized.
        """
        diagnostics.info("Loading presentation datasets into Gold layer...")

        managed_gold_tables = [
            c.physical_table
            for c in sorted(
                (c for c in DATA_CONTRACT_REGISTRY if c.layer == "gold"),
                key=lambda c: c.publication_order,
                reverse=True,
            )
        ]
        self.db_manager.conn.execute("CREATE SCHEMA IF NOT EXISTS gold")
        for tbl in managed_gold_tables:
            self.db_manager.conn.execute(f"DROP TABLE IF EXISTS {tbl}")  # nosec B608

        self.db_manager.conn.execute(generate_gold_ddl(plan))

        active_contracts = [
            c
            for c in DATA_CONTRACT_REGISTRY
            if c.layer == "gold" and (plan is None or c.dataset_id in plan.active_gold_datasets)
        ]
        contracts = sorted(active_contracts, key=lambda c: c.publication_order)

        total_rows = 0
        tables_built = 0

        for contract in contracts:
            if contract.contract_id in dfs:
                rows = self._write(
                    dfs[contract.contract_id],
                    contract.physical_table,
                )
                if rows > 0:
                    tables_built += 1
                    total_rows += rows
                self.emitter.emit_event(
                    event_code=EventCode.GOLD_REPLACE,
                    message=f"Gold layer synchronized {contract.physical_table} ({rows:,} rows)",
                    severity=DiagnosticSeverity.DEBUG,
                    presentation_kind=PresentationKind.INTERNAL,
                    stage=EngineStage.PUBLISHING,
                    entity_type="Table",
                    entity_id=contract.physical_table,
                    rows=rows,
                )

        diagnostics.info(
            "Rebuilt %d presentation tables (%s total rows).",
            tables_built,
            f"{total_rows:,}",
        )
