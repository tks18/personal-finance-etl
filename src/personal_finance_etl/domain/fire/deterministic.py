"""Deterministic and stochastic Financial Independence (FIRE) analytics builder.

Owns
----
- WealthRiskAnalyticsBuilder: Calculates Target FI, Coast FI, Lean FI, savings runway, withdrawal rates, and Monte Carlo forecasts.
- Constructs df_p_tf_wealth_risk_analytics_inputs and df_p_tf_wealth_risk_analytics.

Does not own
-------------
- Monte Carlo numerical kernel execution (owned by domain.fire.simulation).
- Inflation time-series generation (owned by domain.fire.inflation).
- Presentation DAG scheduling (owned by application.wealth.wealth_service).
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.polars import rolling_avg, rolling_sum, safe_divide
from personal_finance_etl.domain.fire.reproducibility import build_monthly_seed_expr
from personal_finance_etl.domain.fire.simulation import get_monte_carlo_fire_batch

__all__ = ["WealthRiskAnalyticsBuilder"]


class WealthRiskAnalyticsBuilder:
    """Constructs the Wealth Risk & FIRE Forecasting analytical models."""

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: Mapping[str, pl.LazyFrame],
        rules: FinancialRules,
        root_seed: str = "default_seed",
    ) -> None:
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules
        self.root_seed = root_seed
        # Cache DOB parts once to avoid repeated string splits in LazyFrame expressions
        dob_parts = rules.assumptions.monte_carlo.date_of_birth.split("-")
        self._dob_year = int(dob_parts[0])
        self._dob_month = int(dob_parts[1])
        self._tax_rate = rules.assumptions.tax.rates.equity_ltcg

    def _prepare_base_inputs(self, lf_monthly_totals: pl.LazyFrame) -> pl.LazyFrame:
        """Prepare base FIRE inputs, monthly net savings, and after-tax net worth.

        Parameters
        ----------
        lf_monthly_totals : pl.LazyFrame
            Base monthly totals LazyFrame.

        Returns
        -------
        pl.LazyFrame
            Base LazyFrame enriched with after-tax net worth and savings metrics.
        """
        lf_fire_base = (
            lf_monthly_totals.select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "Total_Net_Worth",
                    "Total_Net_Worth_Market",
                    "Total_Income",
                    "Total_Cash_Income",
                    "Total_Core_Expense",
                    "Total_Expense",
                    "INFLATION_YOY_PCT",
                    "CPI_INDEX",
                    "Liquid_Assets_Market",
                ]
            )
            .with_columns(
                pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
                (pl.col("Total_Cash_Income") - pl.col("Total_Core_Expense")).alias("Net_Savings"),
                (pl.col("Total_Cash_Income") - pl.col("Total_Expense")).alias("Net_Savings_Total"),
            )
            .sort("MONTH_START_DATE")
        )

        df_inv_port = self.dfs.get("df_f_investment_analytics_portfolio")
        if df_inv_port is not None:
            lf_inv_port = (
                df_inv_port.lazy() if isinstance(df_inv_port, pl.DataFrame) else df_inv_port
            )
            lf_inv_port_mapped = lf_inv_port.with_columns(
                pl.col("Closing_Date").dt.month_end().alias("MONTH_END_DATE")
            )
            lf_inv_port_agg = lf_inv_port_mapped.filter(
                pl.col("Closing_Date") == pl.col("Closing_Date").max().over("MONTH_END_DATE")
            ).select(
                [
                    "MONTH_END_DATE",
                    pl.col("Total_Current_Value").alias("Port_Market_Value"),
                    pl.col("Total_Invested_Value").alias("Port_Book_Value"),
                ]
            )

            lf_fire_base = (
                lf_fire_base.join(
                    lf_inv_port_agg,
                    on="MONTH_END_DATE",
                    how="left",
                )
                .with_columns(
                    pl.col("Port_Market_Value").fill_null(0.0),
                    pl.col("Port_Book_Value").fill_null(0.0),
                )
                .with_columns(
                    pl.when(pl.col("Port_Market_Value") > pl.col("Port_Book_Value"))
                    .then(
                        pl.col("Total_Net_Worth_Market")
                        - (
                            (pl.col("Port_Market_Value") - pl.col("Port_Book_Value"))
                            * self._tax_rate
                        )
                    )
                    .otherwise(pl.col("Total_Net_Worth_Market"))
                    .alias("Total_Net_Worth_Market_Af_Tax")
                )
                .drop(["Port_Market_Value", "Port_Book_Value"])
            )
        else:
            lf_fire_base = lf_fire_base.with_columns(
                pl.col("Total_Net_Worth_Market").alias("Total_Net_Worth_Market_Af_Tax")
            )
        return lf_fire_base

    def _compute_rolling_projections(
        self, lf_fire_base: pl.LazyFrame
    ) -> tuple[pl.LazyFrame, pl.LazyFrame]:
        """Compute rolling expenditure, savings averages, and deterministic FI targets.

        Parameters
        ----------
        lf_fire_base : pl.LazyFrame
            Base monthly totals with after-tax valuation.

        Returns
        -------
        tuple[pl.LazyFrame, pl.LazyFrame]
            Tuple containing:
            - lf_fire_forecast: Rolling forecast table with deterministic FI targets.
            - lf_fire_inputs: Feature vector driving the Monte Carlo simulation engine.
        """
        swr = self.rules.assumptions.fire.swr_multiplier
        lf_fire_forecast = (
            lf_fire_base.sort("MONTH_START_DATE")
            .with_columns(
                rolling_avg("Total_Core_Expense", 3).alias("Trailing_3M_Avg_Spend"),
                rolling_avg("Total_Core_Expense", 6).alias("Trailing_6M_Avg_Spend"),
                rolling_avg("Total_Core_Expense", 12).alias("Trailing_12M_Avg_Spend"),
                rolling_sum("Total_Core_Expense", 12).alias("Trailing_12M_Spend"),
                rolling_avg("Net_Savings", 6).alias("Trailing_6M_Avg_Savings"),
                rolling_avg("Net_Savings", 12).alias("Trailing_12M_Avg_Savings"),
                rolling_sum("Net_Savings", 12).alias("Trailing_12M_Savings"),
                rolling_avg("Total_Expense", 3).alias("Trailing_3M_Avg_Total_Spend"),
                rolling_avg("Total_Expense", 6).alias("Trailing_6M_Avg_Total_Spend"),
                rolling_avg("Total_Expense", 12).alias("Trailing_12M_Avg_Total_Spend"),
                rolling_sum("Total_Expense", 12).alias("Trailing_12M_Total_Spend"),
                rolling_avg("Net_Savings_Total", 6).alias("Trailing_6M_Avg_Total_Savings"),
                rolling_avg("Net_Savings_Total", 12).alias("Trailing_12M_Avg_Total_Savings"),
                rolling_sum("Net_Savings_Total", 12).alias("Trailing_12M_Total_Savings"),
            )
            .with_columns(
                (pl.col("Trailing_12M_Spend") * swr).alias("Target_FI_Today"),
                (pl.col("Trailing_12M_Total_Spend") * swr).alias("Target_FI_Today_Total"),
            )
            .with_columns(
                safe_divide("Total_Net_Worth_Market_Af_Tax", "Target_FI_Today").alias(
                    "Current_FI_Coverage_Pct"
                ),
                safe_divide("Total_Net_Worth_Market_Af_Tax", "Trailing_3M_Avg_Spend").alias(
                    "Runway_Months_Linear"
                ),
                safe_divide("Total_Net_Worth_Market_Af_Tax", "Target_FI_Today_Total").alias(
                    "Current_FI_Coverage_Pct_Total"
                ),
                safe_divide("Total_Net_Worth_Market_Af_Tax", "Trailing_3M_Avg_Total_Spend").alias(
                    "Runway_Months_Total_Linear"
                ),
            )
        )

        lf_fire_inputs = lf_fire_forecast.select(
            [
                "MONTH_START_DATE",
                "Total_Net_Worth_Market_Af_Tax",
                "Trailing_12M_Avg_Savings",
                "Trailing_12M_Avg_Spend",
                "Trailing_12M_Avg_Total_Spend",
                "Target_FI_Today",
                "Trailing_12M_Avg_Total_Savings",
                "Target_FI_Today_Total",
                "INFLATION_YOY_PCT",
            ]
        )
        return lf_fire_forecast, lf_fire_inputs

    def _execute_monte_carlo_simulations(
        self, lf_fire_forecast: pl.LazyFrame, cma_real_return: float, cma_fat_tail: float
    ) -> pl.LazyFrame:
        """Run batch Monte Carlo stochastic simulations across monthly historical snapshots.

        Parameters
        ----------
        lf_fire_forecast : pl.LazyFrame
            Forecast table containing rolling inputs and targets.
        cma_real_return : float
            Capital Market Assumptions expected real return rate.
        cma_fat_tail : float
            Fat-tail distribution multiplier for extreme downside market shocks.

        Returns
        -------
        pl.LazyFrame
            Forecast table unnested with Monte Carlo percentiles and runway forecasts.
        """
        return (
            lf_fire_forecast.with_columns(
                pl.col("MONTH_START_DATE").dt.year().alias("_temp_year"),
                pl.col("MONTH_START_DATE").dt.month().alias("_temp_month"),
            )
            .with_columns(
                (
                    (pl.col("_temp_year") - self._dob_year) * 12
                    + (pl.col("_temp_month") - self._dob_month)
                )
                .cast(pl.Int32)
                .alias("Age_Months"),
                build_monthly_seed_expr(
                    self.root_seed, year_col="_temp_year", month_col="_temp_month"
                ),
            )
            .with_columns(
                pl.struct(
                    [
                        "Total_Net_Worth_Market_Af_Tax",
                        "Trailing_12M_Avg_Savings",
                        "Trailing_12M_Avg_Spend",
                        "Trailing_12M_Avg_Total_Spend",
                        "Target_FI_Today",
                        "Trailing_12M_Avg_Total_Savings",
                        "Target_FI_Today_Total",
                        "INFLATION_YOY_PCT",
                        "Age_Months",
                        "Seed_Int",
                    ]
                )
                .map_batches(
                    get_monte_carlo_fire_batch(self.rules, cma_real_return, cma_fat_tail),
                    return_dtype=pl.Struct(
                        [
                            pl.Field("Months_To_FI_Conservative_P90", pl.Float64),
                            pl.Field("Months_To_FI_Base_P50", pl.Float64),
                            pl.Field("Months_To_FI_Aggressive_P10", pl.Float64),
                            pl.Field("Probability_Of_Success_Pct", pl.Float64),
                            pl.Field("Target_FI_Future_Nominal_P50", pl.Float64),
                            pl.Field("Runway_Months_Stressed_P10", pl.Float64),
                            pl.Field("Runway_Months_Base_P50", pl.Float64),
                            pl.Field("Terminal_Wealth_Nominal_P50", pl.Float64),
                        ]
                    ),
                )
                .alias("mc_results")
            )
            .unnest("mc_results")
            .drop(["_temp_year", "_temp_month", "Age_Months", "Seed_Int"])
        )

    def _compute_milestones_and_trends(
        self, lf_fire_forecast: pl.LazyFrame, cma_real_return: float
    ) -> pl.LazyFrame:
        """Compute Lean FI, Coast FI, withdrawal rates, velocities, and wealth trends.

        Parameters
        ----------
        lf_fire_forecast : pl.LazyFrame
            Forecast table with unnested Monte Carlo outcomes.
        cma_real_return : float
            Assumed real investment return rate.

        Returns
        -------
        pl.LazyFrame
            Enriched forecast table with complete FI milestone and trend analytics.
        """
        coast_real_return = self.rules.assumptions.fire.coast_fi_real_return
        coast_years = self.rules.assumptions.fire.coast_fi_years
        lean_ratio = self.rules.assumptions.fire.lean_fi_ratio

        return (
            lf_fire_forecast.with_columns(
                safe_divide(
                    pl.max_horizontal(
                        0.0, pl.col("Target_FI_Today") - pl.col("Total_Net_Worth_Market_Af_Tax")
                    ),
                    "Trailing_12M_Avg_Savings",
                ).alias("Estimated_Months_To_FI_Linear"),
                safe_divide(
                    pl.max_horizontal(
                        0.0,
                        pl.col("Target_FI_Today_Total") - pl.col("Total_Net_Worth_Market_Af_Tax"),
                    ),
                    "Trailing_12M_Avg_Total_Savings",
                ).alias("Estimated_Months_To_FI_Total_Linear"),
                pl.lit(cma_real_return).alias("Real_Return_Assumed_Pct"),
                pl.max_horizontal(
                    0.0, pl.col("Target_FI_Today") - pl.col("Total_Net_Worth_Market_Af_Tax")
                ).alias("FI_Gap"),
                pl.max_horizontal(
                    0.0, pl.col("Target_FI_Today_Total") - pl.col("Total_Net_Worth_Market_Af_Tax")
                ).alias("FI_Gap_Total"),
                (pl.col("Target_FI_Today") / ((1.0 + coast_real_return) ** coast_years)).alias(
                    "Coast_FI_Today"
                ),
                (
                    pl.col("Target_FI_Today_Total") / ((1.0 + coast_real_return) ** coast_years)
                ).alias("Coast_FI_Today_Total"),
                (pl.col("Target_FI_Today") * lean_ratio).alias("Lean_FI_Today"),
                (pl.col("Target_FI_Today_Total") * lean_ratio).alias("Lean_FI_Today_Total"),
                safe_divide("Trailing_12M_Spend", "Total_Net_Worth_Market_Af_Tax").alias(
                    "Withdrawal_Rate_If_Retired_Now"
                ),
                safe_divide("Trailing_12M_Total_Spend", "Total_Net_Worth_Market_Af_Tax").alias(
                    "Withdrawal_Rate_If_Retired_Now_Total"
                ),
            )
            .with_columns(
                (pl.col("FI_Gap") - pl.col("FI_Gap").shift(1)).alias("FI_Gap_Monthly_Trend"),
                (pl.col("FI_Gap_Total") - pl.col("FI_Gap_Total").shift(1)).alias(
                    "FI_Gap_Total_Monthly_Trend"
                ),
                safe_divide(
                    safe_divide("FI_Gap", "Months_To_FI_Base_P50"), "Total_Cash_Income"
                ).alias("Savings_Rate_Required"),
                safe_divide(
                    safe_divide("FI_Gap_Total", "Months_To_FI_Base_P50"), "Total_Cash_Income"
                ).alias("Savings_Rate_Required_Total"),
                (pl.col("Months_To_FI_Base_P50") / 12.0).alias("Years_To_FI_P50"),
                pl.col("Target_FI_Future_Nominal_P50")
                .fill_null(pl.col("Target_FI_Today"))
                .alias("Target_FI_Future_Nominal"),
                pl.col("Target_FI_Future_Nominal_P50")
                .fill_null(pl.col("Target_FI_Today_Total"))
                .alias("Target_FI_Total_Future_Nominal"),
                pl.when(
                    pl.col("Months_To_FI_Base_P50").is_not_nan()
                    & pl.col("Months_To_FI_Base_P50").is_not_null()
                )
                .then(
                    pl.col("MONTH_START_DATE").dt.offset_by(
                        pl.format(
                            "{}mo",
                            pl.col("Months_To_FI_Base_P50")
                            .fill_nan(0.0)
                            .fill_null(0.0)
                            .clip(0.0, 1200.0)
                            .cast(pl.Int64),
                        )
                    )
                )
                .otherwise(pl.lit(None).cast(pl.Date))
                .alias("Projected_FI_Date_P50"),
            )
            .sort("MONTH_START_DATE")
            .with_columns(
                (
                    pl.col("Total_Net_Worth_Market_Af_Tax")
                    - pl.col("Total_Net_Worth_Market_Af_Tax").shift(1)
                ).alias("Wealth_Velocity"),
            )
            .with_columns(
                (pl.col("Wealth_Velocity") - pl.col("Wealth_Velocity").shift(1)).alias(
                    "Wealth_Acceleration"
                ),
            )
            .with_columns(
                safe_divide("Net_Savings", "Total_Cash_Income").alias("Savings_Rate_Actual"),
                safe_divide("Net_Savings_Total", "Total_Cash_Income").alias(
                    "Savings_Rate_Actual_Total"
                ),
                (
                    pl.col("Current_FI_Coverage_Pct") - pl.col("Current_FI_Coverage_Pct").shift(1)
                ).alias("FI_Velocity"),
                (
                    pl.col("Current_FI_Coverage_Pct_Total")
                    - pl.col("Current_FI_Coverage_Pct_Total").shift(1)
                ).alias("FI_Velocity_Total"),
                pl.when(pl.col("Total_Net_Worth_Market_Af_Tax").shift(36) > 0)
                .then(
                    (
                        (pl.col("Total_Net_Worth_Market_Af_Tax") / pl.col("CPI_INDEX"))
                        / (
                            pl.col("Total_Net_Worth_Market_Af_Tax").shift(36)
                            / pl.col("CPI_INDEX").shift(36)
                        )
                    ).pow(1.0 / 3.0)
                    - 1.0
                )
                .otherwise(pl.lit(None))
                .alias("Real_NW_CAGR_3Y"),
            )
        )

    def _assemble_final_projection(self, lf_fire_forecast: pl.LazyFrame) -> pl.LazyFrame:
        """Select and alias presentation-tier columns in canonical schema order.

        Parameters
        ----------
        lf_fire_forecast : pl.LazyFrame
            Fully enriched analytical forecast table.

        Returns
        -------
        pl.LazyFrame
            Final schema projected table ready for publication in gold.
        """
        return lf_fire_forecast.select(
            [
                "MONTH_START_DATE",
                "MONTH_END_DATE",
                "YEAR_MONTH",
                "Total_Income",
                "Total_Cash_Income",
                pl.col("Trailing_6M_Avg_Total_Spend").alias("Trailing_6M_Avg_Spend"),
                pl.col("Trailing_12M_Avg_Total_Spend").alias("Trailing_12M_Avg_Spend"),
                pl.col("Trailing_6M_Avg_Total_Savings").alias("Trailing_6M_Avg_Savings"),
                pl.col("Trailing_12M_Avg_Total_Savings").alias("Trailing_12M_Avg_Savings"),
                "Real_Return_Assumed_Pct",
                pl.col("Target_FI_Today_Total").alias("Target_FI_Today"),
                pl.col("Coast_FI_Today_Total").alias("Coast_FI_Today"),
                pl.col("Lean_FI_Today_Total").alias("Lean_FI_Today"),
                "Target_FI_Total_Future_Nominal",
                pl.col("Current_FI_Coverage_Pct_Total").alias("Current_FI_Coverage_Pct"),
                pl.col("FI_Gap_Total").alias("FI_Gap"),
                pl.col("FI_Gap_Total_Monthly_Trend").alias("FI_Gap_Monthly_Trend"),
                pl.col("Estimated_Months_To_FI_Total_Linear").alias(
                    "Estimated_Months_To_FI_Linear"
                ),
                "Months_To_FI_Conservative_P90",
                "Months_To_FI_Base_P50",
                "Months_To_FI_Aggressive_P10",
                "Probability_Of_Success_Pct",
                "Years_To_FI_P50",
                "Projected_FI_Date_P50",
                pl.col("Runway_Months_Total_Linear").alias("Runway_Months_Linear"),
                "Runway_Months_Stressed_P10",
                "Runway_Months_Base_P50",
                pl.col("Withdrawal_Rate_If_Retired_Now_Total").alias(
                    "Withdrawal_Rate_If_Retired_Now"
                ),
                pl.col("Savings_Rate_Required_Total").alias("Savings_Rate_Required"),
                pl.col("Savings_Rate_Actual_Total").alias("Savings_Rate_Actual"),
                pl.col("FI_Velocity_Total").alias("FI_Velocity"),
                "Wealth_Velocity",
                "Wealth_Acceleration",
                "Real_NW_CAGR_3Y",
                "Terminal_Wealth_Nominal_P50",
            ]
        )

    def build(self) -> dict[str, pl.LazyFrame]:
        """Build FIRE analytics and simulation inputs LazyFrames.

        Returns
        -------
        dict[str, pl.LazyFrame]
            Dictionary containing:
            - df_p_tf_wealth_risk_analytics_inputs: Feature vector driving the Monte Carlo engine.
            - df_p_tf_wealth_risk_analytics: Unified table of deterministic FI metrics and Monte Carlo percentiles.
        """
        cma_real_return = self.rules.assumptions.cma.expected_real_return
        cma_fat_tail = self.rules.assumptions.cma.fat_tail_multiplier

        lf_monthly_totals = self.base_lf["lf_monthly_totals"]
        lf_fire_base = self._prepare_base_inputs(lf_monthly_totals)
        lf_fire_forecast, lf_fire_inputs = self._compute_rolling_projections(lf_fire_base)
        lf_fire_mc = self._execute_monte_carlo_simulations(
            lf_fire_forecast, cma_real_return, cma_fat_tail
        )
        lf_fire_analyzed = self._compute_milestones_and_trends(lf_fire_mc, cma_real_return)
        lf_final = self._assemble_final_projection(lf_fire_analyzed)

        return {
            "df_p_tf_wealth_risk_analytics_inputs": lf_fire_inputs,
            "df_p_tf_wealth_risk_analytics": lf_final,
        }
