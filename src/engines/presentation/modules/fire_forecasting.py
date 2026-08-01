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
                    "INFLATION_YOY_PCT",
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

        rng = np.random.default_rng(42)

        # Probabilistic Monte Carlo Simulation for FIRE using map_batches
        def monte_carlo_fire_batch(s: pl.Series) -> pl.Series:
            df = s.struct.unnest()
            pv = df["Total_Net_Worth"].to_numpy().astype(float)
            pmt = df["Trailing_6M_Avg_Savings"].to_numpy().astype(float)
            fv = df["Target_FI_Number"].to_numpy().astype(float)
            infl = df["INFLATION_YOY_PCT"].to_numpy().astype(float)

            n_rows = len(pv)
            out_p90 = np.zeros(n_rows)
            out_p50 = np.zeros(n_rows)
            out_p10 = np.zeros(n_rows)

            iterations = 1000
            max_months = 480  # Max 40 years forecast
            vol_r = 0.15 / np.sqrt(12)  # 15% annual volatility

            # We process sequentially in the batch to avoid creating a massive 3D matrix (n_rows x iterations x max_months)
            for i in range(n_rows):
                # Calculate real return dynamically: Assumes 12% nominal return - trailing inflation
                mean_r = (0.12 - (infl[i] / 100.0)) / 12.0
                if mean_r < 0.01 / 12.0:
                    mean_r = 0.01 / 12.0  # Floor at 1% real return
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
                (pl.lit(12.0) - pl.col("INFLATION_YOY_PCT")).alias("Real_Return_Assumed_Pct"),
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
                    "INFLATION_YOY_PCT",
                    "Real_Return_Assumed_Pct",
                ]
            )
        )
        return lf_fire_forecast
