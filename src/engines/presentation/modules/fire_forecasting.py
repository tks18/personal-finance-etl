import numpy as np
import polars as pl


class FireForecastingBuilder:
    """
    Constructs the FIRE & Wealth Forecasting presentation model.
    """

    def __init__(self, base_lf: dict[str, pl.LazyFrame]):
        self.base_lf = base_lf

    def build(self) -> pl.LazyFrame:
        lf_monthly_totals = self.base_lf["lf_monthly_totals"]

        lf_fire_base = (
            lf_monthly_totals.select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "Total_Net_Worth",
                    "Total_Income",
                    "Total_Expense",
                ]
            )
            .with_columns(
                pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
                (pl.col("Total_Income") - pl.col("Total_Expense")).alias("Net_Savings"),
            )
            .sort("MONTH_START_DATE")
        )

        lf_fire_forecast = (
            lf_fire_base.with_columns(
                pl.col("Total_Expense").rolling_mean(window_size=3).alias("Trailing_3M_Avg_Spend"),
                pl.col("Total_Expense").rolling_mean(window_size=6).alias("Trailing_6M_Avg_Spend"),
                pl.col("Total_Expense").rolling_sum(window_size=12).alias("Trailing_12M_Spend"),
                pl.col("Net_Savings").rolling_mean(window_size=6).alias("Trailing_6M_Avg_Savings"),
            )
            .with_columns((pl.col("Trailing_12M_Spend") * 25.0).alias("Target_FI_Number"))
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

        # Probabilistic Monte Carlo Simulation for FIRE
        def monte_carlo_fire(row: dict[str, float]) -> dict[str, float]:
            pv_val = row.get("Total_Net_Worth")
            pv = float(pv_val) if pv_val is not None else 0.0
            pmt_val = row.get("Trailing_6M_Avg_Savings")
            pmt = float(pmt_val) if pmt_val is not None else 0.0
            fv_val = row.get("Target_FI_Number")
            fv = float(fv_val) if fv_val is not None else 0.0

            if fv <= pv:
                return {"Months_To_FI_Conservative_P90": 0.0, "Months_To_FI_Base_P50": 0.0, "Months_To_FI_Aggressive_P10": 0.0}
            if pmt <= 0:
                return {"Months_To_FI_Conservative_P90": 999.0, "Months_To_FI_Base_P50": 999.0, "Months_To_FI_Aggressive_P10": 999.0}

            iterations = 1000
            max_months = 480  # Max 40 years forecast
            mean_r = 0.07 / 12  # 7% real return
            vol_r = 0.15 / np.sqrt(12)  # 15% annual volatility

            np.random.seed(42) # For deterministic dashboard results
            returns = np.random.normal(mean_r, vol_r, (iterations, max_months))
            multipliers = 1.0 + returns

            wealth = np.empty((iterations, max_months))
            wealth[:, 0] = pv
            for i in range(1, max_months):
                wealth[:, i] = wealth[:, i - 1] * multipliers[:, i] + pmt

            reached = wealth >= fv
            months_to_fire = np.argmax(reached, axis=1).astype(float)
            never_reached = ~np.any(reached, axis=1)
            months_to_fire[never_reached] = 999.0

            return {
                "Months_To_FI_Conservative_P90": float(np.percentile(months_to_fire, 90)),
                "Months_To_FI_Base_P50": float(np.percentile(months_to_fire, 50)),
                "Months_To_FI_Aggressive_P10": float(np.percentile(months_to_fire, 10)),
            }

        schema = pl.Struct([
            pl.Field("Months_To_FI_Conservative_P90", pl.Float64),
            pl.Field("Months_To_FI_Base_P50", pl.Float64),
            pl.Field("Months_To_FI_Aggressive_P10", pl.Float64),
        ])

        lf_fire_forecast = lf_fire_forecast.with_columns(
            pl.struct(["Total_Net_Worth", "Trailing_6M_Avg_Savings", "Target_FI_Number"])
            .map_elements(monte_carlo_fire, return_dtype=schema)
            .alias("mc_results")
        ).unnest("mc_results").with_columns(
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
        ).select(
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
            ]
        )
        return lf_fire_forecast
