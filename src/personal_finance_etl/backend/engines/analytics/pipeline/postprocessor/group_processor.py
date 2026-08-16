from datetime import date
from typing import Any

import polars as pl

from personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.analytics import AdvancedAnalyticsCalculator
from personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.xirr import PortfolioXIRRCalculator

PORTFOLIO_COL_RENAMES = {
    "Portfolio_XIRR": "XIRR",
    "Portfolio_After_Tax_XIRR": "After_Tax_XIRR",
    "Portfolio_BM_XIRR": "BM_XIRR",
    "Portfolio_Active_Return": "Active_Return",
    # Risk-adjusted (portfolio)
    "Portfolio_Sharpe_Ratio": "Sharpe_Ratio",
    "Portfolio_Sortino_Ratio": "Sortino_Ratio",
    "Portfolio_Calmar_Ratio": "Calmar_Ratio",
    "Portfolio_Max_Drawdown": "Max_Drawdown",
    # Benchmark equivalents
    "Portfolio_BM_Sharpe_Ratio": "BM_Sharpe_Ratio",
    "Portfolio_BM_Sortino_Ratio": "BM_Sortino_Ratio",
    "Portfolio_BM_Calmar_Ratio": "BM_Calmar_Ratio",
    "Portfolio_BM_Max_Drawdown": "BM_Max_Drawdown",
    # Comparison alphas
    "Portfolio_Sharpe_Alpha": "Sharpe_Alpha",
    "Portfolio_Sortino_Alpha": "Sortino_Alpha",
    "Portfolio_Calmar_Alpha": "Calmar_Alpha",
}


class GroupProcessor:
    """
    Computes XIRR, Sharpe, and other metrics at arbitrary group levels (Class, Subtype).
    """

    def __init__(self, analytics_calc: AdvancedAnalyticsCalculator):
        self.xirr_calc = PortfolioXIRRCalculator()
        self.analytics_calc = analytics_calc

    def run(
        self,
        unique_dates: list[date],
        group_cashflows: dict[str, list[dict[str, Any]]],
        group_terminals: dict[str, dict[date, dict[str, Any]]],
        level_name: str,
        extra_key_col: str | None = None,
    ) -> pl.DataFrame:
        """
        Runs the exact same portfolio-level metric calculations, but partitioned by a group key.
        """
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
                        pl.lit(parts[0]).alias(level_name), pl.lit(parts[1]).alias(extra_key_col)
                    )
                else:
                    df_group = df_group.with_columns(
                        pl.lit(key).alias(level_name), pl.lit("Unknown").alias(extra_key_col)
                    )
            else:
                df_group = df_group.with_columns(pl.lit(key).alias(level_name))

            all_group_dfs.append(df_group)

        if not all_group_dfs:
            return pl.DataFrame()

        return pl.concat(all_group_dfs)
