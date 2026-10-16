"""Portfolio aggregation across asset classes, subtypes, geographies, and weights.

Owns
----
- GroupProcessor: Computes XIRR, MDD, and core performance metrics partitioned by group key
  (Asset Class, Subtype, Sector, Industry, Geography, Currency).
- PortfolioWeightsCalculator: Computes instrument-level and lot-level portfolio weight fractions.
- PORTFOLIO_COL_RENAMES: Standard column renames for group-level metrics.

Does not own
-------------
- Multiprocessing task orchestration (owned by application.investments).
- Presentation rendering (owned by presentation).
"""

from datetime import date

import polars as pl

from personal_finance_etl.domain.investments.contracts import (
    CashflowDict,
    TerminalValueDict,
)
from personal_finance_etl.domain.investments.performance.xirr import (
    PortfolioXIRRCalculator,
)
from personal_finance_etl.domain.investments.portfolio.analytics import (
    AdvancedAnalyticsCalculator,
)

PORTFOLIO_COL_RENAMES: dict[str, str] = {
    "Portfolio_XIRR": "XIRR",
    "Portfolio_After_Tax_XIRR": "After_Tax_XIRR",
    "Portfolio_BM_XIRR": "BM_XIRR",
    "Portfolio_Active_Return": "Active_Return",
    "Portfolio_Max_Drawdown": "Max_Drawdown",
}


class GroupProcessor:
    """Computes XIRR, MDD, and other core metrics at arbitrary group levels (Class, Subtype)."""

    def __init__(self, analytics_calc: AdvancedAnalyticsCalculator):
        self.xirr_calc = PortfolioXIRRCalculator()
        self.analytics_calc = analytics_calc

    def run(
        self,
        unique_dates: list[date],
        group_cashflows: dict[str, list[CashflowDict]],
        group_terminals: (
            dict[str, dict[date, TerminalValueDict]] | dict[str, dict[date, dict[str, float]]]
        ),
        level_name: str,
        extra_key_col: str | None = None,
    ) -> pl.DataFrame:
        """Runs the exact same portfolio-level metric calculations, but partitioned by a group key."""
        all_group_dfs: list[pl.DataFrame] = []

        for key, cashflows in group_cashflows.items():
            terminals = group_terminals.get(key, {})

            # Use the exact same PyXIRR calculator as the portfolio uses!
            df_group = self.xirr_calc.calculate(unique_dates, cashflows, terminals)
            df_group = self.analytics_calc.calculate(df_group, unique_dates, terminals, cashflows)

            df_group = df_group.rename(PORTFOLIO_COL_RENAMES)

            if extra_key_col:
                parts = key.split("___")
                if len(parts) == 2:
                    df_group = df_group.with_columns(
                        pl.lit(parts[0]).alias(level_name),
                        pl.lit(parts[1]).alias(extra_key_col),
                    )
                else:
                    df_group = df_group.with_columns(
                        pl.lit(key).alias(level_name),
                        pl.lit("Unknown").alias(extra_key_col),
                    )
            else:
                df_group = df_group.with_columns(pl.lit(key).alias(level_name))

            all_group_dfs.append(df_group)

        if not all_group_dfs:
            return pl.DataFrame()

        return pl.concat(all_group_dfs)


class PortfolioWeightsCalculator:
    """Calculates Portfolio Weights."""

    @staticmethod
    def calculate(lazy_df: pl.LazyFrame) -> pl.LazyFrame:
        instr_val = lazy_df.group_by(["Closing_Date", "ISIN"]).agg(
            pl.col("Close_Value").sum().alias("Instrument_Close_Value")
        )
        port_tot = instr_val.group_by("Closing_Date").agg(
            pl.col("Instrument_Close_Value").sum().alias("Total_Portfolio_Value")
        )
        instr_val = instr_val.join(port_tot, on="Closing_Date", how="left").with_columns(
            (pl.col("Instrument_Close_Value") / pl.col("Total_Portfolio_Value"))
            .round(8)
            .alias("Portfolio_Weight")
        )
        lazy_df = lazy_df.join(
            instr_val.select(
                [
                    "Closing_Date",
                    "ISIN",
                    "Instrument_Close_Value",
                    "Portfolio_Weight",
                ]
            ),
            on=["Closing_Date", "ISIN"],
            how="left",
        )
        lazy_df = (
            lazy_df.join(
                port_tot,
                on="Closing_Date",
                how="left",
            )
            .with_columns(
                (pl.col("Close_Value") / pl.col("Total_Portfolio_Value"))
                .round(8)
                .alias("Lot_Weight")
            )
            .drop("Total_Portfolio_Value", "Instrument_Close_Value")
        )
        return lazy_df


__all__ = [
    "GroupProcessor",
    "PORTFOLIO_COL_RENAMES",
    "PortfolioWeightsCalculator",
]
