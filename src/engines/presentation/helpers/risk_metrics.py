from collections.abc import Mapping
from typing import Any

import polars as pl


class RiskMetricsBuilder:
    """
    Constructs AE7: Rolling Risk & Drawdown Dashboard.
    """

    def __init__(
        self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], base_lf: dict[str, Any], rules
    ):
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build(self) -> pl.LazyFrame:
        lf_monthly = self.base_lf.get("lf_monthly_totals")
        f_market_data = self.dfs.get("df_f_tf_investment_analytics_lot")

        if lf_monthly is None or f_market_data is None:
            return pl.LazyFrame()

        lf_market = (
            f_market_data.lazy() if isinstance(f_market_data, pl.DataFrame) else f_market_data
        )

        # Get latest closing date per month and total value
        lf_inv_monthly = lf_market.with_columns(
            pl.col("Closing_Date").dt.month_start().alias("MONTH_START_DATE")
        )

        lf_inv_monthly = (
            lf_inv_monthly.group_by("MONTH_START_DATE")
            .agg(pl.col("Closing_Date").max().alias("Max_Closing_Date"))
            .join(lf_inv_monthly, on="MONTH_START_DATE")
            .filter(pl.col("Closing_Date") == pl.col("Max_Closing_Date"))
            .group_by("MONTH_START_DATE")
            .agg(
                pl.col("Close_Value").sum().alias("Total_Investment_Value"),
                pl.col("Buy_Value").sum().alias("Total_Invested_Value"),
            )
        )

        fallback_rfr = self.rules.assumptions.macro.fallback_risk_free_rate if self.rules else 0.05
        df_macro = self.dfs.get("df_d_macro_parameters")
        if df_macro is not None:
            lf_macro = df_macro.lazy() if isinstance(df_macro, pl.DataFrame) else df_macro
            lf_monthly = (
                lf_monthly.sort("MONTH_START_DATE")
                .join_asof(
                    lf_macro.sort("FY_Start_Date"),
                    left_on="MONTH_START_DATE",
                    right_on="FY_Start_Date",
                    strategy="backward",
                )
                .with_columns(pl.col("Risk_Free_Rate").fill_null(fallback_rfr))
            )
        else:
            lf_monthly = lf_monthly.with_columns(pl.lit(fallback_rfr).alias("Risk_Free_Rate"))

        lf_base = (
            lf_monthly.join(lf_inv_monthly, on="MONTH_START_DATE", how="left")
            .with_columns(pl.col("Total_Investment_Value").fill_null(0.0))
            .sort("MONTH_START_DATE")
            .with_columns(
                pl.col("Total_Investment_Value").cum_max().alias("All_Time_High_Inv"),
                pl.col("Total_Net_Worth_Market").cum_max().alias("All_Time_High_NW"),
                pl.col("Total_Net_Worth_Real").cum_max().alias("All_Time_High_Real_NW"),
                (pl.col("Total_Invested_Value") - pl.col("Total_Invested_Value").shift(1))
                .fill_null(0.0)
                .alias("Inv_Cashflow"),
            )
            .with_columns(
                pl.when(pl.col("All_Time_High_Inv") > 0)
                .then(
                    (pl.col("Total_Investment_Value") - pl.col("All_Time_High_Inv"))
                    / pl.col("All_Time_High_Inv")
                )
                .otherwise(0.0)
                .alias("Drawdown_Pct")
            )
            .with_columns(
                # Calculate Monthly Return on Investments using Modified Dietz (Investment specific cash flows)
                pl.when(
                    (pl.col("Total_Investment_Value").shift(1) + (pl.col("Inv_Cashflow") * 0.5)) > 0
                )
                .then(
                    (
                        pl.col("Total_Investment_Value")
                        - pl.col("Total_Investment_Value").shift(1)
                        - pl.col("Inv_Cashflow")
                    )
                    / (pl.col("Total_Investment_Value").shift(1) + (pl.col("Inv_Cashflow") * 0.5))
                )
                .otherwise(0.0)
                .alias("Monthly_Return"),
                pl.when((pl.col("Total_Net_Worth_Market").shift(1)) > 0)
                .then(
                    (
                        pl.col("Total_Net_Worth_Market")
                        - pl.col("Total_Net_Worth_Market").shift(1)
                        - pl.col("Net_Cashflow_Month")
                    )
                    / (
                        pl.col("Total_Net_Worth_Market").shift(1)
                        + (pl.col("Net_Cashflow_Month") * 0.5)
                    )
                )
                .otherwise(0.0)
                .alias("NW_Monthly_Return"),
                pl.when(pl.col("All_Time_High_NW") > 0)
                .then(
                    (pl.col("Total_Net_Worth_Market") - pl.col("All_Time_High_NW"))
                    / pl.col("All_Time_High_NW")
                )
                .otherwise(0.0)
                .alias("NW_Drawdown_Pct"),
                pl.when(pl.col("All_Time_High_Real_NW") > 0)
                .then(
                    (pl.col("Total_Net_Worth_Real") - pl.col("All_Time_High_Real_NW"))
                    / pl.col("All_Time_High_Real_NW")
                )
                .otherwise(0.0)
                .alias("Real_Drawdown_Pct"),
                pl.when(pl.col("Total_Investment_Value").shift(12) > 0)
                .then(
                    (pl.col("Total_Investment_Value") - pl.col("Total_Investment_Value").shift(12))
                    / pl.col("Total_Investment_Value").shift(12)
                )
                .otherwise(0.0)
                .alias("Rolling_12M_Return"),
            )
            .with_columns(
                (1.0 + pl.col("Drawdown_Pct")).alias("Recovery_From_Drawdown_%"),
                pl.col("Drawdown_Pct").rolling_min(window_size=12).alias("Max_Drawdown_12M"),
                # Calculate Volatility on the Investment Return
                (pl.col("Monthly_Return").rolling_std(window_size=12) * (12**0.5))
                .fill_null(0.0)
                .alias("Annualized_Volatility_12M"),
                (pl.col("NW_Monthly_Return").rolling_std(window_size=12) * (12**0.5))
                .fill_null(0.0)
                .alias("NW_Volatility_12M"),
            )
        )

        return lf_base.select(
            [
                "MONTH_START_DATE",
                pl.col("MONTH_START_DATE").dt.month_end().cast(pl.Date).alias("MONTH_END_DATE"),
                pl.col("Total_Net_Worth").fill_null(0.0),
                pl.col("Total_Net_Worth_Market").fill_null(0.0),
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
            ]
        )
