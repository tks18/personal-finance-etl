from collections.abc import Mapping
from typing import Any

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules


class TaxLiabilityForecastBuilder:
    """
    Constructs AE9 (FY Tax Liability & Alpha Tracker).
    """

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: dict[str, Any],
        rules: FinancialRules,
    ):
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build(self) -> pl.LazyFrame:
        f_market_data = self.dfs.get("df_f_tf_investment_analytics_lot")
        if f_market_data is None:
            return pl.LazyFrame()

        lf_market_data = (
            f_market_data.lazy() if isinstance(f_market_data, pl.DataFrame) else f_market_data
        )

        lf_market_data = lf_market_data.with_columns(
            pl.col("Closing_Date").dt.month_start().alias("MONTH_START_DATE")
        )

        # Use .over() to get latest closing date per month — avoids double group-by pattern
        df_monthly_tax = lf_market_data.filter(
            pl.col("Closing_Date") == pl.col("Closing_Date").max().over("MONTH_START_DATE")
        )

        tax_rates = self.rules.assumptions.tax.rates if self.rules else None
        eq_ltcg = tax_rates.equity_ltcg if tax_rates else 0.125
        eq_stcg = tax_rates.equity_stcg if tax_rates else 0.20
        ltcg_exemption = (
            self.rules.assumptions.tax.fallback_equity_ltcg_exemption if self.rules else 125000.0
        )
        # Fallback dividend rate from TOML — live value joined from macro table below
        fallback_div_rate = self.rules.assumptions.macro.fallback_dividend_income_rate if self.rules else 0.30

        # Join Dividend_Income_Tax_Rate from d_macro_parameters using the same asof pattern
        df_macro = self.dfs.get("df_d_macro_parameters")
        if df_macro is not None:
            lf_macro = (
                df_macro.lazy() if isinstance(df_macro, pl.DataFrame) else df_macro
            ).select(
                pl.col("FY_Start_Date").cast(pl.Date),
                pl.col("Dividend_Income_Tax_Rate").cast(pl.Float64),
            )
            df_monthly_tax = (
                df_monthly_tax.sort("Closing_Date")
                .join_asof(
                    lf_macro.sort("FY_Start_Date"),
                    left_on="Closing_Date",
                    right_on="FY_Start_Date",
                    strategy="backward",
                )
                .with_columns(
                    pl.col("Dividend_Income_Tax_Rate").fill_null(fallback_div_rate)
                )
            )
        else:
            df_monthly_tax = df_monthly_tax.with_columns(
                pl.lit(fallback_div_rate).alias("Dividend_Income_Tax_Rate")
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
            df_monthly_tax.sort("Closing_Date")
            .group_by(["MONTH_START_DATE", "FY"])
            .agg(
                pl.col("FY_Realized_STCG").last().alias("Realized_STCG"),
                pl.col("FY_Realized_LTCG").last().alias("Realized_LTCG"),
                pl.col("FY_Realized_Gain").last().alias("Realized_Gain"),
                pl.col("FY_Realized_STCL").last().alias("Realized_STCL"),
                pl.col("FY_Realized_LTCL").last().alias("Realized_LTCL"),
                pl.col("FY_Realized_Loss").last().alias("Realized_Loss"),
                pl.col("FY_Realized_Net_PnL").last().alias("Realized_Net_PnL"),
                pl.col("FY_LTCG_Remaining_Exemption").last().alias("LTCG_Exemption_Remaining"),
                pl.col("Close_Value").sum().alias("Total_Portfolio_Value"),
                pl.when(pl.col("P/L") < 0)
                .then(pl.col("P/L"))
                .otherwise(0.0)
                .sum()
                .alias("Unrealized_Losses"),
                # Carry forward the FY-specific dividend tax rate (last observation in month)
                pl.col("Dividend_Income_Tax_Rate").last().alias("Dividend_Income_Tax_Rate"),
            )
            .join(df_inc_tax, on="MONTH_START_DATE", how="left")
            .with_columns(
                pl.col("Taxable_Dividends").fill_null(0.0),
                pl.col("Taxable_Interest").fill_null(0.0),
                # Fix: clip to 0+ so this never goes negative due to carry data anomalies
                (pl.lit(ltcg_exemption) - pl.col("LTCG_Exemption_Remaining"))
                .clip(lower_bound=0.0)
                .alias("LTCG_Exemption_Used"),
            )
            .with_columns(
                (
                    (pl.col("Realized_STCG").clip(lower_bound=0.0) * eq_stcg)
                    + (
                        (pl.col("Realized_LTCG") - pl.col("LTCG_Exemption_Used")).clip(
                            lower_bound=0.0
                        )
                        * eq_ltcg
                    )
                    # Dividend rate sourced from macro table (individual marginal slab)
                    + (pl.col("Taxable_Dividends").clip(lower_bound=0.0) * pl.col("Dividend_Income_Tax_Rate"))
                ).alias("Projected_Tax_Bill"),
                (pl.col("Unrealized_Losses").abs()).alias("Harvesting_Offset_Remaining"),
            )
            .with_columns(
                pl.when(pl.col("Total_Portfolio_Value") > 0)
                .then((pl.col("Projected_Tax_Bill") / pl.col("Total_Portfolio_Value")) * 100.0)
                .otherwise(0.0)
                .alias("Tax_Drag_Pct"),
                # Tax Harvesting Capacity = amount of unrealized losses usable against this FY's gains
                pl.min_horizontal(
                    pl.col("Harvesting_Offset_Remaining"),
                    (pl.col("Realized_STCG") + pl.col("Realized_LTCG")).clip(lower_bound=0.0),
                ).alias("Tax_Harvesting_Capacity"),
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
                .alias("Tax_Alpha_Pct"),
                # Tax Efficiency Ratio = fraction of realized gains kept after tax
                pl.when(pl.col("Realized_Gain") > 0)
                .then(
                    (pl.col("Realized_Gain") - pl.col("Projected_Tax_Bill"))
                    / pl.col("Realized_Gain")
                )
                .otherwise(pl.lit(None))
                .alias("Tax_Efficiency_Ratio"),
            )
            .select(
                [
                    "MONTH_START_DATE",
                    pl.col("FY").alias("Financial_Year"),
                    "Realized_STCG",
                    "Realized_LTCG",
                    "Realized_Gain",
                    "Realized_STCL",
                    "Realized_LTCL",
                    "Realized_Loss",
                    "Realized_Net_PnL",
                    "Taxable_Dividends",
                    "Taxable_Interest",
                    "LTCG_Exemption_Used",
                    "LTCG_Exemption_Remaining",
                    "Projected_Tax_Bill",
                    "Harvesting_Offset_Remaining",
                    "Tax_Drag_Pct",
                    "Tax_Alpha_Pct",
                    "Tax_Harvesting_Capacity",
                    "Tax_Efficiency_Ratio",
                ]
            )
            .sort("MONTH_START_DATE")
        )
