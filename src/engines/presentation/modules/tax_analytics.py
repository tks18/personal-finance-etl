from collections.abc import Mapping
from typing import Any

import polars as pl


class TaxAnalyticsBuilder:
    """
    Constructs AE6 (Tax Harvesting) and AE9 (FY Tax Liability & Alpha Tracker).
    """

    def __init__(
        self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], base_lf: dict[str, Any], rules=None
    ):
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build_tax_harvesting(self) -> pl.LazyFrame:
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
                    [
                        "ISIN",
                        "TAX_TYPE",
                        "INSTRUMENT_TYPE",
                        "INSTRUMENT_SUBTYPE",
                        pl.col("INSTRUMENT_NAME").alias("Instrument Name"),
                    ]
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
                    pl.col("INSTRUMENT_TYPE").first().alias("INSTRUMENT_TYPE"),
                    pl.col("INSTRUMENT_SUBTYPE").first().alias("INSTRUMENT_SUBTYPE"),
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
                (pl.col("Harvestable_Loss").abs() / pl.col("Total_Invested")).alias(
                    "Loss_Percentage"
                ),
                (pl.col("Harvestable_Loss").abs() * pl.col("applicable_tax_rate")).alias(
                    "Tax_Savings_If_Harvested"
                ),
            )
            .with_columns(
                pl.when(
                    (pl.col("Holding_Type") == "LTCG")
                    & (pl.col("TAX_TYPE").str.to_lowercase() == "equity")
                    & (pl.col("LTCG_Exemption_Remaining") > 0)
                )
                .then(
                    pl.col("Tax_Savings_If_Harvested")
                    - (pl.col("LTCG_Exemption_Remaining") * eq_ltcg)
                )
                .otherwise(pl.col("Tax_Savings_If_Harvested"))
                .alias("Net_Tax_Benefit")
            )
            .with_columns(
                pl.when(pl.col("Net_Tax_Benefit") < 0)
                .then(0.0)
                .otherwise(pl.col("Net_Tax_Benefit"))
                .alias("Net_Tax_Benefit")
            )
            .with_columns(
                (pl.col("Net_Tax_Benefit") / pl.col("Harvestable_Loss").abs()).alias(
                    "Offset_Potential"
                )
            )
            .with_columns(
                pl.when(
                    pl.col("INSTRUMENT_SUBTYPE")
                    .cast(pl.String)
                    .str.to_lowercase()
                    .is_in(["index fund", "etf", "index", "liquid"])
                )
                .then(True)
                .when(
                    pl.col("INSTRUMENT_TYPE")
                    .cast(pl.String)
                    .str.to_lowercase()
                    .is_in(["etf", "mutual fund", "index"])
                )
                .then(True)
                .otherwise(False)
                .alias("Substitute_Asset_Available")
            )
            .with_columns(
                (
                    (pl.col("Loss_Percentage") * 0.4)
                    + (pl.col("Offset_Potential") * 0.4)
                    + (pl.when(pl.col("Holding_Type") == "STCG").then(0.1).otherwise(0.0))
                    + (pl.when(pl.col("Substitute_Asset_Available")).then(0.2).otherwise(0.0))
                ).alias("Priority_Score")
            )
            .select(
                [
                    "ISIN",
                    "Instrument Name",
                    "Holding_Type",
                    "Max_Days_Held",
                    "Harvestable_Quantity",
                    "Total_Invested",
                    "Current_Value",
                    "Harvestable_Loss",
                    "Loss_Percentage",
                    "LTCG_Exemption_Remaining",
                    "Tax_Savings_If_Harvested",
                    "Net_Tax_Benefit",
                    "Offset_Potential",
                    "Substitute_Asset_Available",
                    "Priority_Score",
                ]
            )
            .sort("Priority_Score", descending=True)
        )

    def build_tax_liability_forecast(self) -> pl.LazyFrame:
        f_market_data = self.dfs.get("df_f_tf_investment_analytics_lot")
        if f_market_data is None:
            return pl.LazyFrame()

        lf_market_data = (
            f_market_data.lazy() if isinstance(f_market_data, pl.DataFrame) else f_market_data
        )

        lf_market_data = lf_market_data.with_columns(
            pl.col("Closing_Date").dt.month_start().alias("MONTH_START_DATE")
        )

        latest_month_dates = lf_market_data.group_by("MONTH_START_DATE").agg(
            pl.col("Closing_Date").max().alias("Max_Closing_Date")
        )

        df_monthly_tax = lf_market_data.join(latest_month_dates, on="MONTH_START_DATE").filter(
            pl.col("Closing_Date") == pl.col("Max_Closing_Date")
        )

        tax_rates = self.rules.assumptions.tax.rates if self.rules else None
        eq_ltcg = tax_rates.equity_ltcg if tax_rates else 0.125
        eq_stcg = tax_rates.equity_stcg if tax_rates else 0.20
        ltcg_exemption = (
            self.rules.assumptions.tax.fallback_equity_ltcg_exemption if self.rules else 125000.0
        )

        lf_inc_agg = self.base_lf.get("lf_inc_agg")
        if lf_inc_agg is not None:
            df_inc_tax = (
                lf_inc_agg.with_columns(pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"))
                .group_by("MONTH_START_DATE")
                .agg(
                    pl.when(pl.col("Is_Dividend_Income"))
                    .then(pl.col("INCOME"))
                    .otherwise(0.0)
                    .sum()
                    .alias("Taxable_Dividends"),
                    pl.when(pl.col("Is_Interest_Income"))
                    .then(pl.col("INCOME"))
                    .otherwise(0.0)
                    .sum()
                    .alias("Taxable_Interest"),
                )
            )
        else:
            df_inc_tax = pl.LazyFrame(
                schema={
                    "MONTH_START_DATE": pl.Date,
                    "Taxable_Dividends": pl.Float64,
                    "Taxable_Interest": pl.Float64,
                }
            )

        return (
            df_monthly_tax.group_by(["MONTH_START_DATE", "FY"])
            .agg(
                pl.col("FY_Realized_STCG").last().alias("Realized_STCG"),
                pl.col("FY_Realized_LTCG").last().alias("Realized_LTCG"),
                pl.col("FY_LTCG_Remaining_Exemption").last().alias("LTCG_Exemption_Remaining"),
                pl.col("Close_Value").sum().alias("Total_Portfolio_Value"),
                pl.when(pl.col("P/L") < 0)
                .then(pl.col("P/L"))
                .otherwise(0.0)
                .sum()
                .alias("Unrealized_Losses"),
            )
            .join(df_inc_tax, on="MONTH_START_DATE", how="left")
            .with_columns(
                pl.col("Taxable_Dividends").fill_null(0.0),
                pl.col("Taxable_Interest").fill_null(0.0),
                (pl.lit(ltcg_exemption) - pl.col("LTCG_Exemption_Remaining")).alias(
                    "LTCG_Exemption_Used"
                ),
            )
            .with_columns(
                (
                    (pl.col("Realized_STCG") * eq_stcg)
                    + ((pl.col("Realized_LTCG") - pl.col("LTCG_Exemption_Used")) * eq_ltcg)
                    + (pl.col("Taxable_Dividends") * 0.30)
                ).alias("Projected_Tax_Bill"),
                (pl.col("Unrealized_Losses").abs()).alias("Harvesting_Offset_Remaining"),
            )
            .with_columns(
                pl.when(pl.col("Total_Portfolio_Value") > 0)
                .then((pl.col("Projected_Tax_Bill") / pl.col("Total_Portfolio_Value")) * 100.0)
                .otherwise(0.0)
                .alias("Tax_Drag_Pct")
            )
            .with_columns(
                pl.when(pl.col("Total_Portfolio_Value") > 0)
                .then(
                    (
                        pl.when(pl.col("Realized_STCG") < 0)
                        .then(pl.col("Realized_STCG").abs() * eq_stcg)
                        .otherwise(0.0)
                        / pl.col("Total_Portfolio_Value")
                    )
                    * 100.0
                )
                .otherwise(0.0)
                .alias("Tax_Alpha_Pct")
            )
            .select(
                [
                    "MONTH_START_DATE",
                    pl.col("FY").alias("Financial_Year"),
                    "Realized_STCG",
                    "Realized_LTCG",
                    "Taxable_Dividends",
                    "Taxable_Interest",
                    "LTCG_Exemption_Used",
                    "LTCG_Exemption_Remaining",
                    "Projected_Tax_Bill",
                    "Harvesting_Offset_Remaining",
                    "Tax_Drag_Pct",
                    "Tax_Alpha_Pct",
                ]
            )
            .sort("MONTH_START_DATE")
        )
