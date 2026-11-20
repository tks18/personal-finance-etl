"""Full-replace analytical layer loading and table management in the warehouse Silver layer.

Owns
----
- Full-replace publishing of transformed DataFrames into silver.* DuckDB tables.
- Topological schema recreation and foreign key ordering.
- Dimension string normalization (converting empty strings to nulls).
- Critical data quality gatekeeping for d_Investment_Master (ISIN, TAX_TYPE null checks).

Does not own
-------------
- Upstream financial transformations (owned by domain services).
- Gold presentation layer publishing (owned by infrastructure.warehouse.gold).
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
from personal_finance_etl.infrastructure.warehouse.schema.silver import (
    generate_silver_ddl,
)

diagnostics = get_observability_diagnostics("personal_finance_etl.warehouse.silver")

SILVER_DIMENSION_TABLES: frozenset[str] = frozenset(
    {
        "silver.common_calendar",
        "silver.wealth_income_category",
        "silver.wealth_income_subcategory",
        "silver.wealth_expense_category",
        "silver.wealth_expense_subcategory",
        "silver.wealth_asset_category",
        "silver.wealth_asset_subcategory",
        "silver.common_currency",
        "silver.investment_benchmark_master_dim",
        "silver.investment_master",
        "silver.investment_macro_parameters_dim",
    }
)


class SilverLayer:
    """Full-replace layer for engine-computed analytics and reference data.

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

    @staticmethod
    def _sanitize_dimension_strings(df: pl.DataFrame) -> pl.DataFrame:
        """Convert empty strings to null values across string columns in dimension tables.

        Parameters
        ----------
        df : pl.DataFrame
            Input dimension DataFrame.

        Returns
        -------
        pl.DataFrame
            Sanitized DataFrame with empty strings replaced by nulls.
        """
        string_cols = [
            c
            for c, d in zip(df.columns, df.dtypes, strict=True)
            if d in (getattr(pl, "Utf8", None), getattr(pl, "String", None))
        ]
        if string_cols:
            return df.with_columns(
                [
                    pl.when(pl.col(c) == "").then(None).otherwise(pl.col(c)).alias(c)
                    for c in string_cols
                ]
            )
        return df

    @staticmethod
    def _validate_investment_master(df: pl.DataFrame) -> None:
        """Enforce non-null constraints on critical columns in silver.investment_master.

        Parameters
        ----------
        df : pl.DataFrame
            Investment master DataFrame.

        Raises
        ------
        ValueError
            If rows with missing ISIN or TAX_TYPE are present.
        """
        critical_errors: list[str] = []
        for col_name in ("ISIN", "TAX_TYPE"):
            if col_name in df.columns:
                missing = df.filter(pl.col(col_name).is_null())
                if missing.height > 0:
                    diagnostics.error(
                        "CRITICAL: Found %d rows with missing %s in silver.investment_master.",
                        missing.height,
                        col_name,
                    )
                    diagnostics.error(
                        "Please add the %s for the following instruments to your tracker:", col_name
                    )
                    for row in missing.to_dicts():
                        diagnostics.error("-> %s", row)
                    critical_errors.append(col_name)

        if critical_errors:
            raise ValueError(
                f"Critical data-quality violation in silver.investment_master: Missing {', '.join(critical_errors)}"
            )

    def _write(self, df: pl.DataFrame | pl.LazyFrame, table_name: str) -> int:
        """Write DataFrame or LazyFrame into a Silver table with quality checks.

        Parameters
        ----------
        df : pl.DataFrame | pl.LazyFrame
            Data to publish.
        table_name : str
            Physical Silver table name.

        Returns
        -------
        int
            Number of rows inserted.
        """
        if isinstance(df, pl.LazyFrame):
            # Materialization Boundary: PUBLICATION_BOUNDARY
            # Terminal execution of lazy transformation graph for DuckDB Silver table insertion
            df = df.collect()

        if df.height == 0:
            return 0

        if table_name in SILVER_DIMENSION_TABLES:
            df = self._sanitize_dimension_strings(df)

        if table_name == "silver.investment_master":
            self._validate_investment_master(df)

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
        """Re-create plan-aware silver tables and insert transformed DataFrames.

        Parameters
        ----------
        dfs : dict[str, pl.DataFrame]
            Transformed DataFrames keyed by contract_id.
        plan : ExecutionPlan, optional
            Active execution plan. If None, full silver schema is initialized.
        """
        diagnostics.info("Loading transformed datasets into Silver layer...")

        managed_silver_tables = [
            c.physical_table
            for c in sorted(
                (c for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"),
                key=lambda c: c.publication_order,
                reverse=True,
            )
        ]
        self.db_manager.conn.execute("CREATE SCHEMA IF NOT EXISTS silver")
        for tbl in managed_silver_tables:
            self.db_manager.conn.execute(f"DROP TABLE IF EXISTS {tbl}")  # nosec B608

        self.db_manager.conn.execute(generate_silver_ddl(plan))

        active_contracts = [
            c
            for c in DATA_CONTRACT_REGISTRY
            if c.layer == "silver" and (plan is None or c.dataset_id in plan.active_silver_datasets)
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
                    event_code=EventCode.SILVER_REPLACE,
                    message=f"Silver layer synchronized {contract.physical_table} ({rows:,} rows)",
                    severity=DiagnosticSeverity.DEBUG,
                    presentation_kind=PresentationKind.INTERNAL,
                    stage=EngineStage.PUBLISHING,
                    entity_type="Table",
                    entity_id=contract.physical_table,
                    rows=rows,
                )

        diagnostics.info(
            "Rebuilt %d analytical tables (%s total rows).",
            tables_built,
            f"{total_rows:,}",
        )
