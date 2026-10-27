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

from personal_finance_etl.application.observability import ObservabilityEmitter, get_global_emitter
from personal_finance_etl.application.observability.diagnostics import get_observability_diagnostics
from personal_finance_etl.contracts.application import EngineStage
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    PresentationKind,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.registry import DATA_CONTRACT_REGISTRY
from personal_finance_etl.infrastructure.warehouse.schema.silver import SILVER_DDL

diagnostics = get_observability_diagnostics("personal_finance_etl.warehouse.silver")


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
        """Enforce non-null constraints on critical columns in d_Investment_Master.

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
                        "CRITICAL: Found %d rows with missing %s in d_Investment_Master.",
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
                f"Critical data-quality violation in d_Investment_Master: Missing {', '.join(critical_errors)}"
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

        if "d_" in table_name:
            df = self._sanitize_dimension_strings(df)

        if table_name == "silver.d_Investment_Master":
            self._validate_investment_master(df)

        self.db_manager.conn.register("temp_df", df)
        self.db_manager.conn.execute(
            f"INSERT INTO {table_name} BY NAME SELECT * FROM temp_df"  # nosec B608
        )
        self.db_manager.conn.unregister("temp_df")
        return df.height

    def load(self, dfs: dict[str, pl.DataFrame]) -> None:
        """Truncate all silver.* tables and re-insert transformed DataFrames.

        Parameters
        ----------
        dfs : dict[str, pl.DataFrame]
            Transformed DataFrames keyed by contract_id.
        """
        diagnostics.info("Loading transformed datasets into Silver layer...")

        contracts = sorted(
            (c for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"),
            key=lambda c: c.publication_order,
        )
        self.db_manager.conn.execute("DROP SCHEMA IF EXISTS silver CASCADE")
        self.db_manager.conn.execute("CREATE SCHEMA silver")
        self.db_manager.conn.execute(SILVER_DDL)

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
