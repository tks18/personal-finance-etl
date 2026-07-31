from collections.abc import Mapping

import polars as pl


class AdvancedAnalyticsBuilder:
    """
    Constructs AE4, AE5, AE6, and AE7 advanced presentation models.
    """

    def __init__(
        self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], base_lf: dict[str, pl.LazyFrame]
    ):
        self.dfs = dfs
        self.base_lf = base_lf

    def build_risk_dashboard(self) -> pl.LazyFrame:
        """AE7: Rolling Risk & Drawdown Dashboard."""
        lf_monthly = self.base_lf.get("lf_monthly_totals")
        if lf_monthly is None:
            return pl.LazyFrame()

        return (
            lf_monthly.sort("MONTH_START_DATE")
            .with_columns(pl.col("Total_Net_Worth").cum_max().alias("All_Time_High_NW"))
            .with_columns(
                pl.when(pl.col("All_Time_High_NW") > 0)
                .then(
                    (pl.col("Total_Net_Worth") - pl.col("All_Time_High_NW"))
                    / pl.col("All_Time_High_NW")
                )
                .otherwise(0.0)
                .alias("Drawdown_Pct")
            )
            .with_columns(
                # Calculate Monthly Return
                pl.when(pl.col("Total_Net_Worth").shift(1) > 0)
                .then(
                    (pl.col("Total_Net_Worth") - pl.col("Total_Net_Worth").shift(1))
                    / pl.col("Total_Net_Worth").shift(1)
                )
                .otherwise(0.0)
                .alias("Monthly_Return")
            )
            .with_columns(
                # 12M Rolling Volatility
                (pl.col("Monthly_Return").rolling_std(window_size=12) * (12**0.5)).alias(
                    "Annualized_Volatility_12M"
                )
            )
            .select(
                [
                    "MONTH_START_DATE",
                    "MONTH_END_DATE",
                    "Total_Net_Worth",
                    "All_Time_High_NW",
                    "Drawdown_Pct",
                    "Monthly_Return",
                    "Annualized_Volatility_12M",
                ]
            )
        )

    def build_sector_allocation(self) -> pl.LazyFrame:
        """AE3: Sector Rotation Analytics (Using Instrument Class and Subtype as a Proxy)."""
        f_market_data = self.dfs.get("df_f_investment_market_data")
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
            pl.col("Closing_Date")
            .cast(pl.String)
            .str.slice(0, 7)
            .str.strptime(pl.Date, "%Y-%m", strict=False)
            .alias("MONTH_START_DATE")
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
            df_monthly_sector.with_columns(
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
            .with_columns((pl.col("Subtype_Weight") * 100).pow(2).alias("Squared_Subtype_Weight"))
            .with_columns(
                pl.col("Squared_Subtype_Weight")
                .sum()
                .over("MONTH_START_DATE")
                .alias("Subtype_HHI_Concentration_Index")
            )
        )

        # Calculate Class HHI independently to avoid duplicating class weights for each subtype
        class_hhi_lf = (
            df_concentration.select(["MONTH_START_DATE", "INSTRUMENT_CLASS", "Class_Weight"])
            .unique()
            .with_columns((pl.col("Class_Weight") * 100).pow(2).alias("Squared_Class_Weight"))
            .with_columns(
                pl.col("Squared_Class_Weight")
                .sum()
                .over("MONTH_START_DATE")
                .alias("Class_HHI_Concentration_Index")
            )
            .select(["MONTH_START_DATE", "INSTRUMENT_CLASS", "Class_HHI_Concentration_Index"])
            .unique()
        )

        df_final = (
            df_concentration.join(
                class_hhi_lf, on=["MONTH_START_DATE", "INSTRUMENT_CLASS"], how="left"
            )
            .select(
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
                    "Class_HHI_Concentration_Index",
                    "Subtype_HHI_Concentration_Index",
                ]
            )
            .sort(
                ["MONTH_START_DATE", "Class_Weight", "Subtype_Weight"],
                descending=[False, True, True],
            )
        )
        return df_final

    def build_tax_harvesting(self) -> pl.LazyFrame:
        """AE6: Tax Harvesting Optimizer."""
        f_market = self.dfs.get("df_f_investment_market_data")
        d_inv_master = self.dfs.get("df_d_tf_investment_master")
        if f_market is None or d_inv_master is None:
            return pl.LazyFrame()

        lf_market = f_market.lazy() if isinstance(f_market, pl.DataFrame) else f_market
        lf_inv_master = (
            d_inv_master.lazy() if isinstance(d_inv_master, pl.DataFrame) else d_inv_master
        )

        return (
            lf_market.filter(pl.col("Closing_Date") == pl.col("Closing_Date").max())
            .filter(pl.col("P/L") < 0)  # Only look at lots with unrealized losses
            .join(
                lf_inv_master.select(["ISIN", pl.col("INSTRUMENT_NAME").alias("Instrument Name")]),
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
                ]
            )
            .with_columns(
                (pl.col("Harvestable_Loss") / pl.col("Total_Invested")).alias("Loss_Percentage")
            )
            .sort("Harvestable_Loss")  # Most negative first
        )
