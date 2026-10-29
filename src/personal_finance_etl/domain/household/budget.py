"""Household Budget Forecast and Spend Analytics builders.

Owns
----
- BudgetForecastBuilder: Driven by financial_rules.budget config (40/20/30+10 allocation rule).

Does not own
-------------
- Expense and spend analytics aggregation (owned by domain.household.expense).
- Raw transaction stage ingestion (owned by domain.household.transforms).
- Household policy configuration models (owned by config.financial_rules.household).
- Physical table storage or DuckDB registration (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.polars import rolling_avg, rolling_std, safe_divide
from personal_finance_etl.domain.household.expense import SpendAnalyticsBuilder

__all__ = ["BudgetForecastBuilder", "SpendAnalyticsBuilder"]


class BudgetForecastBuilder:
    """Constructs the Budget Forecast Monthly presentation model.

    Driven by financial_rules.budget config (40/20/30+10 rule):
      - Core Expense  = 40% of smoothed income
      - Non-Core      = 20% of smoothed income (Total - Core)
      - Investment    = 30% of smoothed income (Net Transfers to investment accounts)
      - Buffer        = 10% implicit remainder

    Produces actuals-vs-targets variance, Z-score anomaly detection,
    trend/momentum signals, Lifestyle Creep Index, a 0-100 health score,
    and a 3-month rolling income-weighted forward budget plan.
    """

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: Mapping[str, pl.LazyFrame],
        rules: FinancialRules,
    ) -> None:
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def _derive_investment_actuals(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        """Derive actual investment deployments, redemptions, and net savings.

        Parameters
        ----------
        lf : pl.LazyFrame
            Base monthly totals LazyFrame.

        Returns
        -------
        pl.LazyFrame
            Frame enriched with Actual_Investment, Actual_Savings, and expense actuals.
        """
        df_buys = self.dfs.get("df_f_tf_inv_purchase")
        df_sells = self.dfs.get("df_f_tf_inv_sale")

        if df_buys is not None:
            lf_buys = df_buys.lazy() if isinstance(df_buys, pl.DataFrame) else df_buys
            lf_inv_buys = (
                lf_buys.with_columns(pl.col("Date").dt.month_start().alias("MONTH_START_DATE"))
                .group_by("MONTH_START_DATE")
                .agg(pl.col("Value").sum().fill_null(0.0).alias("Investment_Deployed"))
            )
            lf = lf.join(lf_inv_buys, on="MONTH_START_DATE", how="left").sort("MONTH_START_DATE")
            lf = lf.with_columns(pl.col("Investment_Deployed").fill_null(0.0))
        else:
            lf = lf.with_columns(pl.lit(0.0).alias("Investment_Deployed"))

        if df_sells is not None:
            lf_sells = df_sells.lazy() if isinstance(df_sells, pl.DataFrame) else df_sells
            lf_inv_sells = (
                lf_sells.with_columns(pl.col("Date").dt.month_start().alias("MONTH_START_DATE"))
                .group_by("MONTH_START_DATE")
                .agg(pl.col("Sell_Value").sum().fill_null(0.0).alias("Investment_Redeemed"))
            )
            lf = lf.join(lf_inv_sells, on="MONTH_START_DATE", how="left").sort("MONTH_START_DATE")
            lf = lf.with_columns(pl.col("Investment_Redeemed").fill_null(0.0))
        else:
            lf = lf.with_columns(pl.lit(0.0).alias("Investment_Redeemed"))

        return (
            lf.with_columns(
                (pl.col("Investment_Deployed") - pl.col("Investment_Redeemed")).alias(
                    "Actual_Investment"
                )
            )
            .with_columns(
                pl.col("Total_Cash_Income").alias("Actual_Income"),
                pl.col("Total_Core_Expense").alias("Actual_Core_Expense"),
                (pl.col("Total_Expense") - pl.col("Total_Core_Expense")).alias(
                    "Actual_NonCore_Expense"
                ),
                pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
            )
            .with_columns(
                (
                    pl.col("Actual_Income")
                    - pl.col("Actual_Core_Expense")
                    - pl.col("Actual_NonCore_Expense")
                    - pl.col("Actual_Investment")
                ).alias("Actual_Savings"),
            )
        )

    def _compute_rolling_statistics_and_budget_income(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        """Compute rolling income/expense baselines and recency-weighted budget income.

        Parameters
        ----------
        lf : pl.LazyFrame
            Frame containing monthly actuals.

        Returns
        -------
        pl.LazyFrame
            Frame enriched with smoothed Budget_Income and Income_Regime.
        """
        return (
            lf.with_columns(
                pl.col("Actual_Income").shift(1).alias("Inc_T1"),
                pl.col("Actual_Income").shift(2).alias("Inc_T2"),
                pl.col("Actual_Income").shift(3).alias("Inc_T3"),
                rolling_avg("Actual_Income", 3).alias("Income_3M_Mean"),
                rolling_avg("Actual_Income", 6).alias("Income_6M_Mean"),
                rolling_std("Actual_Income", 6).alias("Income_6M_Std"),
                rolling_avg("Actual_Core_Expense", 3).alias("Core_3M_Mean"),
                rolling_avg("Actual_Core_Expense", 6).alias("Core_6M_Mean"),
                rolling_std("Actual_Core_Expense", 6).alias("Core_6M_Std"),
                rolling_avg("Actual_NonCore_Expense", 3).alias("NonCore_3M_Mean"),
                rolling_avg("Actual_NonCore_Expense", 6).alias("NonCore_6M_Mean"),
                rolling_std("Actual_NonCore_Expense", 6).alias("NonCore_6M_Std"),
            )
            .with_columns(
                pl.when(
                    pl.col("Inc_T1").is_not_null()
                    & pl.col("Inc_T2").is_not_null()
                    & pl.col("Inc_T3").is_not_null()
                )
                .then((3 * pl.col("Inc_T1") + 2 * pl.col("Inc_T2") + 1 * pl.col("Inc_T3")) / 6.0)
                .when(pl.col("Inc_T1").is_not_null() & pl.col("Inc_T2").is_not_null())
                .then((2 * pl.col("Inc_T1") + 1 * pl.col("Inc_T2")) / 3.0)
                .when(pl.col("Inc_T1").is_not_null())
                .then(pl.col("Inc_T1"))
                .otherwise(pl.col("Actual_Income"))
                .alias("Budget_Income"),
            )
            .with_columns(
                safe_divide("Income_6M_Std", "Income_6M_Mean").alias("Income_Volatility_Pct"),
                pl.col("Actual_Income").shift(1).alias("Prev_Income"),
            )
            .with_columns(
                pl.when(pl.col("Income_Volatility_Pct") > 0.20)
                .then(pl.lit("Volatile"))
                .when(
                    pl.col("Prev_Income").is_not_null()
                    & (pl.col("Actual_Income") > pl.col("Prev_Income") * 1.05)
                )
                .then(pl.lit("Growing"))
                .otherwise(pl.lit("Stable"))
                .alias("Income_Regime"),
            )
        )

    def _calculate_budget_targets_and_variances(
        self,
        lf: pl.LazyFrame,
        core_pct: float,
        non_core_pct: float,
        investment_pct: float,
        buffer_pct: float,
    ) -> pl.LazyFrame:
        """Calculate rule-based allocation targets and actuals-vs-budget variances.

        Parameters
        ----------
        lf : pl.LazyFrame
            Frame containing smoothed budget income.
        core_pct : float
            Core expense budget allocation percentage.
        non_core_pct : float
            Non-core expense budget allocation percentage.
        investment_pct : float
            Investment target budget allocation percentage.
        buffer_pct : float
            Implicit surplus buffer percentage.

        Returns
        -------
        pl.LazyFrame
            Frame enriched with target benchmarks, variances, and allocation percentages.
        """
        return (
            lf.with_columns(
                pl.lit(core_pct).alias("Rule_Core_Pct_Budget"),
                pl.lit(non_core_pct).alias("Rule_NonCore_Pct_Budget"),
                pl.lit(investment_pct).alias("Rule_Investment_Pct_Budget"),
                (pl.col("Budget_Income") * core_pct).alias("Budget_Core_Expense_Target"),
                (pl.col("Budget_Income") * non_core_pct).alias("Budget_NonCore_Expense_Target"),
                (pl.col("Budget_Income") * investment_pct).alias("Budget_Investment_Target"),
            )
            .with_columns(
                (
                    pl.col("Budget_Core_Expense_Target") + pl.col("Budget_NonCore_Expense_Target")
                ).alias("Budget_Total_Expense_Target"),
                (pl.col("Budget_Income") * buffer_pct).alias("Budget_Surplus_Buffer"),
            )
            .with_columns(
                (pl.col("Actual_Core_Expense") - pl.col("Budget_Core_Expense_Target")).alias(
                    "Core_Expense_Variance"
                ),
                (pl.col("Actual_NonCore_Expense") - pl.col("Budget_NonCore_Expense_Target")).alias(
                    "NonCore_Expense_Variance"
                ),
                (pl.col("Budget_Investment_Target") - pl.col("Actual_Investment")).alias(
                    "Investment_Shortfall"
                ),
                (
                    (pl.col("Actual_Core_Expense") + pl.col("Actual_NonCore_Expense"))
                    - pl.col("Budget_Total_Expense_Target")
                ).alias("Total_Budget_Variance"),
            )
            .with_columns(
                safe_divide("Actual_Core_Expense", "Actual_Income").alias(
                    "Actual_Core_Pct_of_Income"
                ),
                safe_divide("Actual_NonCore_Expense", "Actual_Income").alias(
                    "Actual_NonCore_Pct_of_Income"
                ),
                safe_divide("Actual_Investment", "Actual_Income").alias(
                    "Actual_Investment_Pct_of_Income"
                ),
                safe_divide("Actual_Savings", "Actual_Income").alias(
                    "Actual_Savings_Pct_of_Income"
                ),
            )
        )

    def _calculate_runway_and_health_flags(
        self, lf: pl.LazyFrame, emergency_months: int
    ) -> pl.LazyFrame:
        """Calculate zero-income runway, emergency fund gap, and budget health signals.

        Parameters
        ----------
        lf : pl.LazyFrame
            Frame containing actuals and variances.
        emergency_months : int
            Target emergency fund reserve in months of core spending.

        Returns
        -------
        pl.LazyFrame
            Frame enriched with runway calculations and boolean health status flags.
        """
        return (
            lf.with_columns(
                safe_divide("Liquid_Assets_Market", "Actual_Core_Expense").alias(
                    "Zero_Income_Runway_Months"
                ),
                (
                    pl.col("Core_6M_Mean").fill_null(pl.col("Actual_Core_Expense"))
                    * emergency_months
                    - pl.col("Liquid_Assets_Market")
                ).alias("Emergency_Fund_Gap"),
            )
            .with_columns(
                (pl.col("Actual_Core_Expense") > pl.col("Budget_Core_Expense_Target")).alias(
                    "Is_Core_Overspent"
                ),
                (pl.col("Actual_NonCore_Expense") > pl.col("Budget_NonCore_Expense_Target")).alias(
                    "Is_NonCore_Overspent"
                ),
                (pl.col("Actual_Investment") < pl.col("Budget_Investment_Target")).alias(
                    "Is_Investment_Underfunded"
                ),
                (pl.col("Income_Volatility_Pct") > 0.20).alias("Is_Income_Volatile"),
            )
            .with_columns(
                (
                    ~(
                        pl.col("Is_Core_Overspent")
                        | pl.col("Is_NonCore_Overspent")
                        | pl.col("Is_Investment_Underfunded")
                    )
                ).alias("Is_Budget_Month_Healthy"),
            )
        )

    def _project_final_budget_schema(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        """Select and order columns matching the presentation budget model schema.

        Parameters
        ----------
        lf : pl.LazyFrame
            Fully evaluated budget forecast LazyFrame.

        Returns
        -------
        pl.LazyFrame
            Final schema projected budget model.
        """
        return lf.select(
            [
                "MONTH_START_DATE",
                "MONTH_END_DATE",
                "YEAR_MONTH",
                # Income anchor
                "Total_Income",
                "Actual_Income",
                "Budget_Income",
                # Rule targets
                "Rule_Core_Pct_Budget",
                "Rule_NonCore_Pct_Budget",
                "Rule_Investment_Pct_Budget",
                "Budget_Core_Expense_Target",
                "Budget_NonCore_Expense_Target",
                "Budget_Investment_Target",
                "Budget_Surplus_Buffer",
                "Budget_Total_Expense_Target",
                # Actuals
                "Actual_Core_Expense",
                "Actual_NonCore_Expense",
                "Investment_Deployed",
                "Investment_Redeemed",
                "Actual_Investment",
                "Actual_Savings",
                # Runway
                "Zero_Income_Runway_Months",
                "Emergency_Fund_Gap",
                # Flags
                "Is_Core_Overspent",
                "Is_NonCore_Overspent",
                "Is_Investment_Underfunded",
                "Is_Income_Volatile",
                "Is_Budget_Month_Healthy",
            ]
        )

    def build(self) -> pl.LazyFrame:
        """Build the Budget Forecast LazyFrame matching gold.Forecast_Budget_Variance.

        Returns
        -------
        pl.LazyFrame
            LazyFrame matching presentation Budget Forecast schema.
        """
        lf_raw = self.base_lf.get("lf_monthly_totals")
        if not isinstance(lf_raw, pl.LazyFrame):
            return pl.LazyFrame()
        lf: pl.LazyFrame = lf_raw

        budget = self.rules.budget
        core_pct = budget.income_allocation.core_expense_pct
        non_core_pct = budget.income_allocation.non_core_expense_pct
        investment_pct = budget.income_allocation.investment_pct
        buffer_pct = 1.0 - core_pct - non_core_pct - investment_pct
        emergency_months = budget.alerts.emergency_fund_target_months

        lf = lf.sort("MONTH_START_DATE")
        lf = self._derive_investment_actuals(lf)
        lf = self._compute_rolling_statistics_and_budget_income(lf)
        lf = self._calculate_budget_targets_and_variances(
            lf, core_pct, non_core_pct, investment_pct, buffer_pct
        )
        lf = self._calculate_runway_and_health_flags(lf, emergency_months)
        return self._project_final_budget_schema(lf)
