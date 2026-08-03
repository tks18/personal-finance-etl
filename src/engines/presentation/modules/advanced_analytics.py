from collections.abc import Mapping
from typing import Any

import polars as pl


class AdvancedAnalyticsBuilder:
    """
    Constructs AE4, AE5, AE6, and AE7 advanced presentation models.
    """

    def __init__(
        self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], base_lf: dict[str, Any], rules=None
    ):
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build_risk_dashboard(self) -> pl.LazyFrame:
        """AE7: Rolling Risk & Drawdown Dashboard."""
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

        return (
            lf_monthly.join(lf_inv_monthly, on="MONTH_START_DATE", how="left")
            .with_columns(pl.col("Total_Investment_Value").fill_null(0.0))
            .sort("MONTH_START_DATE")
            .with_columns(
                pl.col("Total_Investment_Value").cum_max().alias("All_Time_High_Inv"),
                pl.col("Total_Net_Worth").cum_max().alias("All_Time_High_NW"),
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
                pl.when(
                    (pl.col("Total_Net_Worth").shift(1) + (pl.col("Net_Cashflow_Month") * 0.5)) > 0
                )
                .then(
                    (
                        pl.col("Total_Net_Worth")
                        - pl.col("Total_Net_Worth").shift(1)
                        - pl.col("Net_Cashflow_Month")
                    )
                    / (pl.col("Total_Net_Worth").shift(1) + (pl.col("Net_Cashflow_Month") * 0.5))
                )
                .otherwise(0.0)
                .alias("NW_Monthly_Return"),
                pl.when(pl.col("All_Time_High_NW") > 0)
                .then(
                    (pl.col("Total_Net_Worth") - pl.col("All_Time_High_NW"))
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
                pl.when(pl.col("Drawdown_Pct") < 0)
                .then(
                    1.0
                    - (
                        pl.col("Drawdown_Pct")
                        / pl.col("Drawdown_Pct")
                        .cum_min()
                        .over("All_Time_High_Inv", order_by="MONTH_START_DATE")
                    )
                )
                .otherwise(1.0)
                .alias("Recovery_From_Drawdown_%"),
                pl.when(pl.col("Total_Investment_Value").shift(12) > 0)
                .then(
                    (pl.col("Total_Investment_Value") - pl.col("Total_Investment_Value").shift(12))
                    / pl.col("Total_Investment_Value").shift(12)
                )
                .otherwise(0.0)
                .alias("Rolling_12M_Return"),
            )
            .with_columns(
                # 12M Rolling Volatility
                (pl.col("Monthly_Return").rolling_std(window_size=12) * (12**0.5)).alias(
                    "Annualized_Volatility_12M"
                ),
                (pl.col("NW_Monthly_Return").rolling_std(window_size=12) * (12**0.5)).alias(
                    "NW_Volatility_12M"
                ),
                pl.col("Monthly_Return")
                .rolling_quantile(0.05, interpolation="nearest", window_size=36)
                .alias("VaR_95_Monthly"),
            )
            .with_columns(
                pl.col("Drawdown_Pct").rolling_min(window_size=12).alias("Max_Drawdown_12M")
            )
            .with_columns(
                pl.when(pl.col("Max_Drawdown_12M") < 0)
                .then(pl.col("Rolling_12M_Return") / pl.col("Max_Drawdown_12M").abs())
                .otherwise(None)
                .alias("Calmar_Ratio"),
                pl.when(pl.col("Annualized_Volatility_12M") > 0)
                .then((pl.col("Rolling_12M_Return") - pl.col("Risk_Free_Rate")) / pl.col("Annualized_Volatility_12M"))
                .otherwise(0.0)
                .alias("Sharpe_Ratio_Monthly"),
            )
            .select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "Total_Net_Worth",
                    "All_Time_High_NW",
                    "Drawdown_Pct",
                    "NW_Drawdown_Pct",
                    "Real_Drawdown_Pct",
                    "Monthly_Return",
                    "Recovery_From_Drawdown_%",
                    "Rolling_12M_Return",
                    "Annualized_Volatility_12M",
                    "NW_Volatility_12M",
                    "VaR_95_Monthly",
                    "Max_Drawdown_12M",
                    "Calmar_Ratio",
                    "Sharpe_Ratio_Monthly",
                ]
            )
        )

    def build_sector_allocation(self) -> pl.LazyFrame:
        """AE3: Sector Rotation Analytics (Using Instrument Class and Subtype as a Proxy)."""
        f_market_data = self.dfs.get("df_f_tf_investment_analytics_lot")
        d_inv_master = self.dfs.get("df_d_tf_investment_master")
        if f_market_data is None or d_inv_master is None:
            return pl.LazyFrame()

        lf_market_data = (
            f_market_data.lazy() if isinstance(f_market_data, pl.DataFrame) else f_market_data
        )
        lf_inv_master = (
            d_inv_master.lazy() if isinstance(d_inv_master, pl.DataFrame) else d_inv_master
        )

        # Get latest closing date per month
        lf_market_data = lf_market_data.with_columns(
            pl.col("Closing_Date").dt.month_start().alias("MONTH_START_DATE")
        )

        latest_month_dates = lf_market_data.group_by("MONTH_START_DATE").agg(
            pl.col("Closing_Date").max().alias("Max_Closing_Date")
        )

        # Filter for only those max dates and join attributes
        df_monthly_base = (
            lf_market_data.join(latest_month_dates, on="MONTH_START_DATE")
            .filter(pl.col("Closing_Date") == pl.col("Max_Closing_Date"))
            .join(
                lf_inv_master.select(["ISIN", "INSTRUMENT_CLASS", "INSTRUMENT_SUBTYPE"]),
                on="ISIN",
                how="left",
            )
        )

        # Aggregate by both Class and Subtype
        df_monthly_sector = df_monthly_base.group_by(
            ["MONTH_START_DATE", "Max_Closing_Date", "INSTRUMENT_CLASS", "INSTRUMENT_SUBTYPE"]
        ).agg(pl.col("Close_Value").sum().fill_null(0.0).alias("Subtype_Total_Value"))

        df_concentration = (
            df_monthly_sector.sort("MONTH_START_DATE")
            .with_columns(
                pl.col("Subtype_Total_Value")
                .sum()
                .over(["MONTH_START_DATE", "INSTRUMENT_CLASS"])
                .alias("Class_Total_Value"),
                pl.col("Subtype_Total_Value")
                .sum()
                .over("MONTH_START_DATE")
                .alias("Total_Portfolio_Value"),
            )
            .with_columns(
                pl.when(pl.col("Total_Portfolio_Value") > 0)
                .then(pl.col("Subtype_Total_Value") / pl.col("Total_Portfolio_Value"))
                .otherwise(0.0)
                .alias("Subtype_Weight"),
                pl.when(pl.col("Total_Portfolio_Value") > 0)
                .then(pl.col("Class_Total_Value") / pl.col("Total_Portfolio_Value"))
                .otherwise(0.0)
                .alias("Class_Weight"),
            )
            .with_columns(pl.col("Subtype_Weight").pow(2).alias("Squared_Subtype_Weight"))
            .with_columns(
                pl.col("Squared_Subtype_Weight")
                .sum()
                .over("MONTH_START_DATE")
                .alias("Subtype_HHI_Concentration_Index"),
                (
                    pl.col("Subtype_Weight")
                    - pl.col("Subtype_Weight").shift(1).over("INSTRUMENT_SUBTYPE")
                ).alias("Weight_Change_MoM"),
            )
            .with_columns(
                (1.0 / pl.col("Subtype_HHI_Concentration_Index")).alias(
                    "Effective_Diversification"
                ),
                pl.col("INSTRUMENT_SUBTYPE").count().over("MONTH_START_DATE").alias("Num_Subtypes"),
            )
        )

        if self.rules and getattr(self.rules.assumptions, "target_allocations", None):
            alloc_data = [
                {"INSTRUMENT_CLASS": str(k), "Target_Weight": float(v)}
                for k, v in self.rules.assumptions.target_allocations.items()
            ]
            lf_target_allocs = pl.LazyFrame(alloc_data)
            df_concentration = df_concentration.join(
                lf_target_allocs, on="INSTRUMENT_CLASS", how="left"
            ).with_columns(pl.col("Target_Weight").fill_null(0.0))
            df_concentration = df_concentration.with_columns(
                (pl.col("Class_Weight") > pl.col("Target_Weight")).alias("Is_Overweight"),
                (pl.col("Class_Weight") - pl.col("Target_Weight")).alias("Benchmark_Deviation"),
            ).drop("Target_Weight")
        else:
            df_concentration = df_concentration.with_columns(
                pl.lit(False).alias("Is_Overweight"),
                pl.lit(0.0).alias("Benchmark_Deviation"),
            )

        # Calculate Class HHI independently to avoid duplicating class weights for each subtype
        class_hhi_lf = (
            df_concentration.select(["MONTH_START_DATE", "INSTRUMENT_CLASS", "Class_Weight"])
            .unique()
            .with_columns(pl.col("Class_Weight").pow(2).alias("Squared_Class_Weight"))
            .with_columns(
                pl.col("Squared_Class_Weight")
                .sum()
                .over("MONTH_START_DATE")
                .alias("Class_HHI_Concentration_Index")
            )
            .select(["MONTH_START_DATE", "INSTRUMENT_CLASS", "Class_HHI_Concentration_Index"])
            .unique()
        )

        df_concentration = df_concentration.join(
            class_hhi_lf, on=["MONTH_START_DATE", "INSTRUMENT_CLASS"], how="left"
        )

        f_class_data = self.dfs.get("df_f_tf_investment_analytics_class")
        if f_class_data is not None:
            lf_class = (
                f_class_data.lazy() if isinstance(f_class_data, pl.DataFrame) else f_class_data
            )
            lf_class = lf_class.with_columns(
                pl.col("Closing_Date").dt.month_start().alias("MONTH_START_DATE")
            )
            lf_class_agg = lf_class.group_by(["MONTH_START_DATE", "INSTRUMENT_CLASS"]).agg(
                pl.col("XIRR").last().alias("Class_CAGR")
            )
            df_concentration = df_concentration.join(
                lf_class_agg, on=["MONTH_START_DATE", "INSTRUMENT_CLASS"], how="left"
            )
        else:
            df_concentration = df_concentration.with_columns(pl.lit(0.0).alias("Class_CAGR"))

        return df_concentration.select(
            [
                "MONTH_START_DATE",
                pl.col("Max_Closing_Date").alias("As_Of_Date"),
                "INSTRUMENT_CLASS",
                "INSTRUMENT_SUBTYPE",
                "Class_Total_Value",
                "Subtype_Total_Value",
                "Total_Portfolio_Value",
                "Class_Weight",
                "Subtype_Weight",
                "Weight_Change_MoM",
                "Class_HHI_Concentration_Index",
                "Subtype_HHI_Concentration_Index",
                "Effective_Diversification",
                "Is_Overweight",
                "Class_CAGR",
                "Benchmark_Deviation",
            ]
        ).sort(
            ["MONTH_START_DATE", "Class_Weight", "Subtype_Weight"],
            descending=[False, True, True],
        )

    def build_tax_harvesting(self) -> pl.LazyFrame:
        """AE6: Tax Harvesting Optimizer."""
        f_market = self.dfs.get("df_f_tf_investment_analytics_lot")
        d_inv_master = self.dfs.get("df_d_tf_investment_master")
        if f_market is None or d_inv_master is None:
            return pl.LazyFrame()

        lf_market = f_market.lazy() if isinstance(f_market, pl.DataFrame) else f_market
        lf_inv_master = (
            d_inv_master.lazy() if isinstance(d_inv_master, pl.DataFrame) else d_inv_master
        )

        tax_rates = self.rules.assumptions.tax.rates if self.rules else None
        eq_ltcg = tax_rates.equity_ltcg if tax_rates else 0.125
        eq_stcg = tax_rates.equity_stcg if tax_rates else 0.20
        debt_ltcg = tax_rates.debt_ltcg if tax_rates else 0.20
        debt_stcg = tax_rates.debt_stcg if tax_rates else 0.30
        gold_ltcg = tax_rates.gold_ltcg if tax_rates else 0.20
        gold_stcg = tax_rates.gold_stcg if tax_rates else 0.30

        return (
            lf_market.filter(pl.col("Closing_Date") == pl.col("Closing_Date").max())
            .filter(pl.col("P/L") < 0)  # Only look at lots with unrealized losses
            .join(
                lf_inv_master.select(
                    ["ISIN", "TAX_TYPE", pl.col("INSTRUMENT_NAME").alias("Instrument Name")]
                ),
                on="ISIN",
                how="left",
            )
            .group_by(["ISIN", "Instrument Name", "Holding_Type"])
            .agg(
                [
                    pl.col("Quantity").sum().alias("Harvestable_Quantity"),
                    pl.col("Buy_Value").sum().alias("Total_Invested"),
                    pl.col("Close_Value").sum().alias("Current_Value"),
                    pl.col("P/L").sum().alias("Harvestable_Loss"),
                    (pl.col("Closing_Date").max() - pl.col("Buy_Date").min())
                    .dt.total_days()
                    .alias("Max_Days_Held"),
                    pl.col("TAX_TYPE").first().alias("TAX_TYPE"),
                    pl.col("FY_LTCG_Remaining_Exemption").first().alias("LTCG_Exemption_Remaining"),
                ]
            )
            .with_columns(
                pl.when(
                    (pl.col("Holding_Type") == "LTCG")
                    & (pl.col("TAX_TYPE").str.to_lowercase() == "equity")
                )
                .then(eq_ltcg)
                .when(
                    (pl.col("Holding_Type") == "STCG")
                    & (pl.col("TAX_TYPE").str.to_lowercase() == "equity")
                )
                .then(eq_stcg)
                .when(
                    (pl.col("Holding_Type") == "LTCG")
                    & (pl.col("TAX_TYPE").str.to_lowercase() == "debt")
                )
                .then(debt_ltcg)
                .when(
                    (pl.col("Holding_Type") == "STCG")
                    & (pl.col("TAX_TYPE").str.to_lowercase() == "debt")
                )
                .then(debt_stcg)
                .when(
                    (pl.col("Holding_Type") == "LTCG")
                    & (pl.col("TAX_TYPE").str.to_lowercase() == "gold")
                )
                .then(gold_ltcg)
                .when(
                    (pl.col("Holding_Type") == "STCG")
                    & (pl.col("TAX_TYPE").str.to_lowercase() == "gold")
                )
                .then(gold_stcg)
                .otherwise(0.30)
                .alias("applicable_tax_rate")
            )
            .with_columns(
                (pl.col("Harvestable_Loss") / pl.col("Total_Invested")).alias("Loss_Percentage"),
                pl.when(
                    (pl.col("Holding_Type") == "LTCG")
                    & (pl.col("TAX_TYPE").str.to_lowercase() == "equity")
                    & (pl.col("LTCG_Exemption_Remaining") > 0)
                )
                .then(0.0)
                .otherwise(pl.col("Harvestable_Loss").abs() * pl.col("applicable_tax_rate"))
                .alias("Tax_Savings_If_Harvested"),
            )
            .with_columns(
                pl.col("Harvestable_Loss").alias("Offset_Potential"),
                pl.col("Tax_Savings_If_Harvested").alias("Net_Tax_Benefit"),
            )
            .drop("applicable_tax_rate", "TAX_TYPE")
            .with_columns(
                (pl.col("Net_Tax_Benefit") * (1.0 + pl.col("Loss_Percentage").abs())).alias(
                    "Priority_Score"
                )
            )
            .sort("Harvestable_Loss")  # Most negative first
        )
