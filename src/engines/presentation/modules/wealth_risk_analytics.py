from collections.abc import Mapping
from typing import Any

import polars as pl

from src.config.financial_rules import FinancialRules
from src.engines.presentation.helpers.fire_mc_sim import get_monte_carlo_fire_batch
from src.utils.polars_expressions import rolling_avg, rolling_sum, safe_divide


class WealthRiskAnalyticsBuilder:
    """
    Constructs the Wealth Risk & FIRE Forecasting presentation model.
    """

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: dict[str, Any],
        lf_risk: pl.LazyFrame,
        rules: FinancialRules,
    ) -> None:
        self.dfs = dfs
        self.base_lf = base_lf
        self.lf_risk = lf_risk
        self.rules = rules
        # Cache DOB parts once to avoid repeated string splits in LazyFrame expressions
        dob_parts = rules.assumptions.monte_carlo.date_of_birth.split("-")
        self._dob_year = int(dob_parts[0])
        self._dob_month = int(dob_parts[1])
        self._tax_rate = rules.assumptions.tax.rates.equity_ltcg

    def build(self) -> pl.LazyFrame:
        lf_monthly_totals = self.base_lf["lf_monthly_totals"]

        lf_fire_base = (
            lf_monthly_totals.select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "Total_Net_Worth",
                    "Total_Net_Worth_Market",
                    "Total_Income",
                    "Total_Core_Expense",
                    "Total_Expense",
                    "INFLATION_YOY_PCT",
                    "CPI_INDEX",
                    "Liquid_Assets_Market",
                ]
            )
            .with_columns(
                pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
                (pl.col("Total_Income") - pl.col("Total_Core_Expense")).alias("Net_Savings"),
                (pl.col("Total_Income") - pl.col("Total_Expense")).alias("Net_Savings_Total"),
            )
            .sort("MONTH_START_DATE")
        )

        df_inv_port = self.dfs.get("df_f_tf_investment_analytics_portfolio")

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
                        - ((pl.col("Port_Market_Value") - pl.col("Port_Book_Value")) * self._tax_rate)
                    )
                    .otherwise(pl.col("Total_Net_Worth_Market"))
                    .alias("Total_Net_Worth_Market_Af_Tax")
                )
                .drop(["Port_Market_Value", "Port_Book_Value"])
            )

        swr = self.rules.assumptions.fire.swr_multiplier
        coast_real_return = self.rules.assumptions.fire.coast_fi_real_return
        coast_years = self.rules.assumptions.fire.coast_fi_years
        lean_ratio = self.rules.assumptions.fire.lean_fi_ratio

        cma_real_return = self.rules.assumptions.cma.expected_real_return
        cma_fat_tail = self.rules.assumptions.cma.fat_tail_multiplier
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
        lf_fire_forecast = (
            lf_fire_forecast.with_columns(
                pl.col("MONTH_START_DATE").dt.year().alias("_temp_year"),
                pl.col("MONTH_START_DATE").dt.month().alias("_temp_month"),
            )
            .with_columns(
                (
                    (
                        pl.col("_temp_year") - self._dob_year
                    )
                    * 12
                    + (
                        pl.col("_temp_month") - self._dob_month
                    )
                )
                .cast(pl.Int32)
                .alias("Age_Months"),
                # Month-year derived seed: same month always produces identical MC paths,
                # large integer gap between adjacent months prevents RNG correlation.
                # e.g. Jan 2025 = 2025*12+1 = 24301, Feb 2025 = 24302
                (pl.col("_temp_year") * 12 + pl.col("_temp_month")).cast(pl.Int32).alias("Seed_Int"),
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
                            pl.Field("Months_To_FI_Total_Conservative_P90", pl.Float64),
                            pl.Field("Months_To_FI_Total_Base_P50", pl.Float64),
                            pl.Field("Months_To_FI_Total_Aggressive_P10", pl.Float64),
                            pl.Field("Probability_Of_Success_Pct", pl.Float64),
                            pl.Field("Probability_Of_Success_Total_Pct", pl.Float64),
                            pl.Field("Target_FI_Future_Nominal_P50", pl.Float64),
                            pl.Field("Target_FI_Total_Future_Nominal_P50", pl.Float64),
                            pl.Field("Runway_Months_Stressed_P10", pl.Float64),
                            pl.Field("Runway_Months_Base_P50", pl.Float64),
                            pl.Field("Runway_Months_Total_Stressed_P10", pl.Float64),
                            pl.Field("Runway_Months_Total_Base_P50", pl.Float64),
                            pl.Field("Terminal_Wealth_P50", pl.Float64),
                            pl.Field("Terminal_Wealth_P10", pl.Float64),
                            pl.Field("Max_Drawdown_Pct_P50", pl.Float64),
                            pl.Field("Compounded_Lost_Savings_EV", pl.Float64),
                            pl.Field("Peak_Inflation_Experienced_Pct", pl.Float64),
                            pl.Field("Decumulation_First_5Y_CAGR_P10", pl.Float64),
                            pl.Field("Average_Realized_Withdrawal_Rate_P50", pl.Float64),
                            pl.Field("Terminal_Wealth_Nominal_P50", pl.Float64),
                            pl.Field("Terminal_Wealth_Total_Nominal_P50", pl.Float64),
                        ]
                    ),
                )
                .alias("mc_results")
            )
            .unnest("mc_results")
            .drop(["_temp_year", "_temp_month", "Age_Months", "Seed_Int"])
            .with_columns(
                # Legacy linear for reference
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
                safe_divide(safe_divide("FI_Gap", "Months_To_FI_Base_P50"), "Total_Income").alias(
                    "Savings_Rate_Required"
                ),
                safe_divide(
                    safe_divide("FI_Gap_Total", "Months_To_FI_Total_Base_P50"), "Total_Income"
                ).alias("Savings_Rate_Required_Total"),
                (pl.col("Months_To_FI_Base_P50") / 12.0).alias("Years_To_FI_P50"),
                (pl.col("Months_To_FI_Total_Base_P50") / 12.0).alias("Years_To_FI_Total_P50"),
                pl.col("Target_FI_Future_Nominal_P50")
                .fill_null(pl.col("Target_FI_Today"))
                .alias("Target_FI_Future_Nominal"),
                pl.col("Target_FI_Total_Future_Nominal_P50")
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
                pl.when(
                    pl.col("Months_To_FI_Total_Base_P50").is_not_nan()
                    & pl.col("Months_To_FI_Total_Base_P50").is_not_null()
                )
                .then(
                    pl.col("MONTH_START_DATE").dt.offset_by(
                        pl.format(
                            "{}mo",
                            pl.col("Months_To_FI_Total_Base_P50")
                            .fill_nan(0.0)
                            .fill_null(0.0)
                            .clip(0.0, 1200.0)
                            .cast(pl.Int64),
                        )
                    )
                )
                .otherwise(pl.lit(None).cast(pl.Date))
                .alias("Projected_FI_Date_Total_P50"),
                pl.col("Current_FI_Coverage_Pct").alias("NW_Percentile_of_FI"),
                pl.col("Current_FI_Coverage_Pct_Total").alias("NW_Percentile_of_FI_Total"),
            )
            .join(
                self.lf_risk.select(
                    [
                        "MONTH_START_DATE",
                        "Drawdown_Pct",
                        "Monthly_Return",
                        "Rolling_12M_Return",
                        "All_Time_High_NW",
                        "NW_Drawdown_Pct",
                        "Real_Drawdown_Pct",
                        "Recovery_From_Drawdown_%",
                        "Max_Drawdown_12M",
                        "Annualized_Volatility_12M",
                        "NW_Volatility_12M",
                        "Sharpe_Ratio_12M",
                        "Sortino_Ratio_12M",
                        "Calmar_Ratio_12M",
                    ]
                ),
                on="MONTH_START_DATE",
                how="left",
            )
            .sort("MONTH_START_DATE")
            .with_columns(
                (
                    pl.col("Total_Net_Worth_Market_Af_Tax")
                    - pl.col("Total_Net_Worth_Market_Af_Tax").shift(1)
                ).alias("Wealth_Velocity"),
                pl.col("Drawdown_Pct").fill_null(0.0),
            )
            .with_columns(
                (pl.col("Wealth_Velocity") - pl.col("Wealth_Velocity").shift(1)).alias(
                    "Wealth_Acceleration"
                ),
                pl.when(pl.col("Drawdown_Pct") < -0.20)
                .then(self.rules.assumptions.fire.cape_swr_floor)
                .when(pl.col("Drawdown_Pct") < -0.10)
                .then(self.rules.assumptions.fire.cape_swr_ceiling)
                .otherwise(self.rules.assumptions.fire.cape_swr_base)
                .alias("CAPE_Adjusted_SWR"),
            )
            .with_columns(
                # Actual monthly savings rate as a percentage of income
                safe_divide("Net_Savings", "Total_Income").alias("Savings_Rate_Actual"),
                safe_divide("Net_Savings_Total", "Total_Income").alias("Savings_Rate_Actual_Total"),
                # FI Velocity: MoM change in FI coverage — positive = approaching FI
                (pl.col("Current_FI_Coverage_Pct") - pl.col("Current_FI_Coverage_Pct").shift(1))
                .alias("FI_Velocity"),
                (pl.col("Current_FI_Coverage_Pct_Total") - pl.col("Current_FI_Coverage_Pct_Total").shift(1))
                .alias("FI_Velocity_Total"),
                # Real Net Worth CAGR over 3 years (36 months), inflation-adjusted
                pl.when(pl.col("Total_Net_Worth_Market_Af_Tax").shift(36) > 0)
                .then(
                    (
                        (pl.col("Total_Net_Worth_Market_Af_Tax") / pl.col("CPI_INDEX"))
                        / (pl.col("Total_Net_Worth_Market_Af_Tax").shift(36) / pl.col("CPI_INDEX").shift(36))
                    )
                    .pow(1.0 / 3.0)
                    - 1.0
                )
                .otherwise(pl.lit(None))
                .alias("Real_NW_CAGR_3Y"),
            )
        )

        # Risk Metrics are already natively merged

        lf_fire_forecast = lf_fire_forecast.select(
            [
                "MONTH_START_DATE",
                "MONTH_END_DATE",
                "YEAR_MONTH",
                "Total_Income",
                "Total_Core_Expense",
                "Total_Expense",
                "Net_Savings",
                "Net_Savings_Total",
                "Total_Net_Worth",
                "Total_Net_Worth_Market",
                "Total_Net_Worth_Market_Af_Tax",
                "Trailing_6M_Avg_Spend",
                "Trailing_6M_Avg_Savings",
                "Trailing_12M_Avg_Spend",
                "Trailing_12M_Avg_Savings",
                "INFLATION_YOY_PCT",
                "Real_Return_Assumed_Pct",
                "Target_FI_Today",
                "Coast_FI_Today",
                "Lean_FI_Today",
                "Target_FI_Future_Nominal",
                "Current_FI_Coverage_Pct",
                "NW_Percentile_of_FI",
                "FI_Gap",
                "FI_Gap_Monthly_Trend",
                "Estimated_Months_To_FI_Linear",
                "Months_To_FI_Conservative_P90",
                "Months_To_FI_Base_P50",
                "Months_To_FI_Aggressive_P10",
                "Probability_Of_Success_Pct",
                "Years_To_FI_P50",
                "Projected_FI_Date_P50",
                "Runway_Months_Linear",
                "Runway_Months_Stressed_P10",
                "Runway_Months_Base_P50",
                "Withdrawal_Rate_If_Retired_Now",
                "Savings_Rate_Required",
                "Trailing_6M_Avg_Total_Spend",
                "Trailing_6M_Avg_Total_Savings",
                "Trailing_12M_Avg_Total_Spend",
                "Trailing_12M_Avg_Total_Savings",
                "Target_FI_Today_Total",
                "Coast_FI_Today_Total",
                "Lean_FI_Today_Total",
                "Target_FI_Total_Future_Nominal",
                "Current_FI_Coverage_Pct_Total",
                "NW_Percentile_of_FI_Total",
                "FI_Gap_Total",
                "FI_Gap_Total_Monthly_Trend",
                "Estimated_Months_To_FI_Total_Linear",
                "Months_To_FI_Total_Conservative_P90",
                "Months_To_FI_Total_Base_P50",
                "Months_To_FI_Total_Aggressive_P10",
                "Probability_Of_Success_Total_Pct",
                "Years_To_FI_Total_P50",
                "Projected_FI_Date_Total_P50",
                "Runway_Months_Total_Linear",
                "Runway_Months_Total_Stressed_P10",
                "Runway_Months_Total_Base_P50",
                "Withdrawal_Rate_If_Retired_Now_Total",
                "Savings_Rate_Required_Total",
                "Wealth_Velocity",
                "Wealth_Acceleration",
                "CAPE_Adjusted_SWR",
                "Savings_Rate_Actual",
                "Savings_Rate_Actual_Total",
                "FI_Velocity",
                "FI_Velocity_Total",
                "Real_NW_CAGR_3Y",
                "Terminal_Wealth_P50",
                "Terminal_Wealth_P10",
                "Max_Drawdown_Pct_P50",
                "Compounded_Lost_Savings_EV",
                "Peak_Inflation_Experienced_Pct",
                "Decumulation_First_5Y_CAGR_P10",
                "Average_Realized_Withdrawal_Rate_P50",
                "Terminal_Wealth_Nominal_P50",
                "Terminal_Wealth_Total_Nominal_P50",
                # Risk Metrics natively merged
                "Monthly_Return",
                "Rolling_12M_Return",
                "All_Time_High_NW",
                "NW_Drawdown_Pct",
                "Real_Drawdown_Pct",
                "Drawdown_Pct",
                "Recovery_From_Drawdown_%",
                "Max_Drawdown_12M",
                "Annualized_Volatility_12M",
                "NW_Volatility_12M",
                "Sharpe_Ratio_12M",
                "Sortino_Ratio_12M",
                "Calmar_Ratio_12M",
            ]
        )
        return lf_fire_forecast
