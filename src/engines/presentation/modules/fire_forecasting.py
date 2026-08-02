from typing import Any

import numpy as np
import polars as pl


class FireForecastingBuilder:
    """
    Constructs the FIRE & Wealth Forecasting presentation model.
    """

    def __init__(self, base_lf: dict[str, Any], lf_risk: pl.LazyFrame, rules=None):
        self.base_lf = base_lf
        self.lf_risk = lf_risk
        self.rules = rules

    def build(self) -> pl.LazyFrame:
        lf_monthly_totals = self.base_lf["lf_monthly_totals"]

        lf_fire_base = (
            lf_monthly_totals.select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "Total_Net_Worth",
                    "Total_Income",
                    "Total_Core_Expense",
                    "INFLATION_YOY_PCT",
                    "CPI_INDEX",
                ]
            )
            .with_columns(
                pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
                (pl.col("Total_Income") - pl.col("Total_Core_Expense")).alias("Net_Savings"),
            )
            .sort("MONTH_START_DATE")
        )

        fallback_return = 0.12
        if self.rules and self.rules.assumptions:
            fallback_return = self.rules.assumptions.fire.fallback_trailing_return

        lf_fire_base = lf_fire_base.join(
            self.lf_risk.select(
                ["MONTH_START_DATE", pl.col("Rolling_12M_Return").alias("Trailing_12M_Return")]
            ),
            on="MONTH_START_DATE",
            how="left",
        ).with_columns(pl.col("Trailing_12M_Return").fill_null(fallback_return))

        swr = 25.0
        coast_real_return = 0.05
        coast_years = 10
        lean_ratio = 0.7
        mc_iterations = 1000
        mc_max_months = 480
        mc_volatility = 0.15
        mc_floor = 0.01
        cpi_base = self.base_lf.get("cpi_base", 151.4)

        if self.rules and self.rules.assumptions:
            swr = self.rules.assumptions.fire.swr_multiplier
            coast_real_return = self.rules.assumptions.fire.coast_fi_real_return
            coast_years = self.rules.assumptions.fire.coast_fi_years
            lean_ratio = self.rules.assumptions.fire.lean_fi_ratio
            mc_iterations = self.rules.assumptions.monte_carlo.iterations
            mc_max_months = self.rules.assumptions.monte_carlo.max_months
            mc_volatility = self.rules.assumptions.monte_carlo.annual_volatility
            mc_floor = self.rules.assumptions.monte_carlo.real_return_floor
            cpi_base = self.rules.assumptions.macro.cpi_base_index

        lf_fire_forecast = (
            lf_fire_base.with_columns(
                pl.col("Total_Core_Expense")
                .rolling_mean(window_size=3)
                .alias("Trailing_3M_Avg_Spend"),
                pl.col("Total_Core_Expense")
                .rolling_mean(window_size=6)
                .alias("Trailing_6M_Avg_Spend"),
                pl.col("Total_Core_Expense")
                .rolling_sum(window_size=12)
                .alias("Trailing_12M_Spend"),
                pl.col("Net_Savings").rolling_mean(window_size=6).alias("Trailing_6M_Avg_Savings"),
                pl.col("Net_Savings").rolling_sum(window_size=12).alias("Trailing_12M_Savings"),
            )
            .with_columns((pl.col("Trailing_12M_Spend") * swr).alias("Target_FI_Number"))
            .with_columns(
                pl.when(pl.col("Target_FI_Number") > 0)
                .then(pl.col("Total_Net_Worth") / pl.col("Target_FI_Number"))
                .otherwise(0.0)
                .alias("Current_FI_Coverage_Pct"),
                pl.when(pl.col("Trailing_3M_Avg_Spend") > 0)
                .then(pl.col("Total_Net_Worth") / pl.col("Trailing_3M_Avg_Spend"))
                .otherwise(0.0)
                .alias("Runway_Months"),
            )
        )

        rng = np.random.default_rng(42)

        # Probabilistic Monte Carlo Simulation for FIRE using map_batches
        def monte_carlo_fire_batch(s: pl.Series) -> pl.Series:
            df = s.struct.unnest()
            pv = df["Total_Net_Worth"].to_numpy().astype(float)
            pmt = df["Trailing_6M_Avg_Savings"].to_numpy().astype(float)
            fv = df["Target_FI_Number"].to_numpy().astype(float)
            infl = df["INFLATION_YOY_PCT"].to_numpy().astype(float)
            ret_12m = df["Trailing_12M_Return"].to_numpy().astype(float)

            n_rows = len(pv)
            out_p90 = np.zeros(n_rows)
            out_p50 = np.zeros(n_rows)
            out_p10 = np.zeros(n_rows)

            iterations = mc_iterations
            max_months = mc_max_months  # Max 40 years forecast
            vol_r = mc_volatility / np.sqrt(12)  # monthly volatility

            # We process sequentially in the batch to avoid creating a massive 3D matrix (n_rows x iterations x max_months)
            for i in range(n_rows):
                # Calculate real return dynamically: Assumes Trailing 12M nominal return - trailing inflation
                mean_r = (ret_12m[i] - (infl[i] / 100.0)) / 12.0
                if mean_r < mc_floor / 12.0:
                    mean_r = mc_floor / 12.0  # Floor at X% real return
                if fv[i] <= pv[i]:
                    out_p90[i], out_p50[i], out_p10[i] = 0.0, 0.0, 0.0
                    continue
                if pmt[i] <= 0:
                    out_p90[i], out_p50[i], out_p10[i] = 999.0, 999.0, 999.0
                    continue

                returns = rng.normal(mean_r, vol_r, (iterations, max_months))
                multipliers = 1.0 + returns

                wealth = np.empty((iterations, max_months))
                wealth[:, 0] = pv[i]
                for m in range(1, max_months):
                    wealth[:, m] = wealth[:, m - 1] * multipliers[:, m] + pmt[i]

                reached = wealth >= fv[i]
                months_to_fire = np.argmax(reached, axis=1).astype(float)
                never_reached = ~np.any(reached, axis=1)
                months_to_fire[never_reached] = 999.0

                out_p90[i] = float(np.percentile(months_to_fire, 90))
                out_p50[i] = float(np.percentile(months_to_fire, 50))
                out_p10[i] = float(np.percentile(months_to_fire, 10))

            return pl.Series(
                [
                    {
                        "Months_To_FI_Conservative_P90": p90,
                        "Months_To_FI_Base_P50": p50,
                        "Months_To_FI_Aggressive_P10": p10,
                    }
                    for p90, p50, p10 in zip(out_p90, out_p50, out_p10, strict=True)
                ]
            )

        lf_fire_forecast = (
            lf_fire_forecast.with_columns(
                pl.struct(
                    [
                        "Total_Net_Worth",
                        "Trailing_6M_Avg_Savings",
                        "Target_FI_Number",
                        "INFLATION_YOY_PCT",
                        "Trailing_12M_Return",
                    ]
                )
                .map_batches(
                    monte_carlo_fire_batch,
                    return_dtype=pl.Struct(
                        [
                            pl.Field("Months_To_FI_Conservative_P90", pl.Float64),
                            pl.Field("Months_To_FI_Base_P50", pl.Float64),
                            pl.Field("Months_To_FI_Aggressive_P10", pl.Float64),
                        ]
                    ),
                )
                .alias("mc_results")
            )
            .unnest("mc_results")
            .with_columns(
                # Legacy linear for reference
                pl.when(
                    (pl.col("Trailing_6M_Avg_Savings") > 0)
                    & (pl.col("Target_FI_Number") > pl.col("Total_Net_Worth"))
                )
                .then(
                    (pl.col("Target_FI_Number") - pl.col("Total_Net_Worth"))
                    / pl.col("Trailing_6M_Avg_Savings")
                )
                .otherwise(0.0)
                .alias("Estimated_Months_To_FI_Linear"),
                ((pl.col("Trailing_12M_Return") * 100.0) - pl.col("INFLATION_YOY_PCT")).alias(
                    "Real_Return_Assumed_Pct"
                ),
                pl.max_horizontal(
                    0.0, pl.col("Target_FI_Number") - pl.col("Total_Net_Worth")
                ).alias("FI_Gap"),
                (pl.col("Target_FI_Number") / (pl.col("CPI_INDEX") / pl.lit(cpi_base))).alias(
                    "FI_Number_Real"
                ),
                (pl.col("Target_FI_Number") / ((1.0 + coast_real_return) ** coast_years)).alias(
                    "Coast_FI_Number"
                ),
                (pl.col("Target_FI_Number") * lean_ratio).alias("Lean_FI_Number"),
                pl.when(pl.col("Total_Net_Worth") > 0)
                .then(pl.col("Trailing_12M_Spend") / pl.col("Total_Net_Worth"))
                .otherwise(0.0)
                .alias("Withdrawal_Rate_If_Retired_Now"),
            )
            .with_columns(
                (pl.col("FI_Gap") - pl.col("FI_Gap").shift(1)).alias("FI_Gap_Monthly_Trend"),
                pl.when(
                    (pl.col("Months_To_FI_Base_P50") > 0)
                    & (pl.col("Months_To_FI_Base_P50") < 999)
                    & (pl.col("Total_Income") > 0)
                )
                .then((pl.col("FI_Gap") / pl.col("Months_To_FI_Base_P50")) / pl.col("Total_Income"))
                .otherwise(0.0)
                .alias("Savings_Rate_Required"),
                (pl.col("Months_To_FI_Base_P50") / 12.0).alias("Years_To_FI_P50"),
                pl.when(pl.col("Months_To_FI_Base_P50") < 999)
                .then(
                    pl.col("MONTH_START_DATE").dt.offset_by(
                        pl.format("{}mo", pl.col("Months_To_FI_Base_P50").cast(pl.Int64))
                    )
                )
                .otherwise(pl.lit(None).cast(pl.Date))
                .alias("Projected_FI_Date_P50"),
                pl.col("Current_FI_Coverage_Pct").alias("NW_Percentile_of_FI"),
            )
            .select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "YEAR_MONTH",
                    "Total_Net_Worth",
                    "Trailing_6M_Avg_Spend",
                    "Trailing_6M_Avg_Savings",
                    "Target_FI_Number",
                    "Current_FI_Coverage_Pct",
                    "Estimated_Months_To_FI_Linear",
                    "Months_To_FI_Conservative_P90",
                    "Months_To_FI_Base_P50",
                    "Months_To_FI_Aggressive_P10",
                    "Runway_Months",
                    "Years_To_FI_P50",
                    "Projected_FI_Date_P50",
                    "NW_Percentile_of_FI",
                    "INFLATION_YOY_PCT",
                    "Real_Return_Assumed_Pct",
                    "FI_Number_Real",
                    "Coast_FI_Number",
                    "Lean_FI_Number",
                    "Savings_Rate_Required",
                    "FI_Gap",
                    "FI_Gap_Monthly_Trend",
                    "Withdrawal_Rate_If_Retired_Now",
                ]
            )
        )
        return lf_fire_forecast
