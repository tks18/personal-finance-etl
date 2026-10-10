from collections.abc import Mapping
from typing import Any

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules


class TaxLiabilityForecastBuilder:
    """
    Constructs AE9 (FY Tax Liability & Alpha Tracker).
    Evaluated lazily as part of the Presentation DAG.
    """

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: dict[str, Any],
        rules: FinancialRules | None,
    ):
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build(self) -> pl.LazyFrame:
        f_market_data = self.dfs.get("df_f_investment_analytics_lot")
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
        fallback_div_rate = (
            self.rules.assumptions.macro.fallback_ordinary_income_rate if self.rules else 0.30
        )

        # Derive blended CG rates from all configured groups.
        # Falls back to equity-only rates when capital_gains_groups is not configured.
        cg_groups = self.rules.assumptions.tax.capital_gains_groups if self.rules else {}
        if cg_groups:
            _st_rates: list[float] = []
            _lt_rates: list[float] = []
            for key, grp in cg_groups.items():
                k = key.lower()
                if grp.gain_type == "ST":
                    if "equity" in k and "foreign" not in k:
                        _st_rates.append(tax_rates.equity_stcg if tax_rates else 0.20)
                    elif "foreign" in k or "default" in k:
                        _st_rates.append(tax_rates.foreign_equity_stcg if tax_rates else 0.30)
                    elif "debt" in k:
                        _st_rates.append(tax_rates.debt_stcg if tax_rates else 0.30)
                    elif "gold" in k or "other_assets" in k or "reit" in k or "sgb" in k:
                        _st_rates.append(tax_rates.gold_stcg if tax_rates else 0.30)
                    else:
                        _st_rates.append(eq_stcg)
                else:  # LT
                    if "equity" in k and "foreign" not in k:
                        _lt_rates.append(tax_rates.equity_ltcg if tax_rates else 0.125)
                    elif "foreign" in k or "default" in k:
                        _lt_rates.append(tax_rates.foreign_equity_ltcg if tax_rates else 0.125)
                    elif "debt" in k:
                        _lt_rates.append(tax_rates.debt_ltcg if tax_rates else 0.20)
                    elif "gold" in k or "other_assets" in k or "reit" in k or "sgb" in k:
                        _lt_rates.append(tax_rates.gold_ltcg if tax_rates else 0.20)
                    else:
                        _lt_rates.append(eq_ltcg)
            blended_stcg_rate = sum(_st_rates) / len(_st_rates) if _st_rates else eq_stcg
            blended_ltcg_rate = sum(_lt_rates) / len(_lt_rates) if _lt_rates else eq_ltcg
        else:
            blended_stcg_rate = eq_stcg
            blended_ltcg_rate = eq_ltcg

        # Join Ordinary Income Tax Rate from d_macro_parameters using the same asof pattern
        df_macro = self.dfs.get("df_d_macro_parameters")
        if df_macro is not None:
            lf_macro = (df_macro.lazy() if isinstance(df_macro, pl.DataFrame) else df_macro).select(
                pl.col("FY_Start_Date").cast(pl.Date),
                pl.col("Estimated_Ordinary_Income_Tax_Rate").cast(pl.Float64),
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
                    pl.col("Estimated_Ordinary_Income_Tax_Rate").fill_null(fallback_div_rate)
                )
            )
        else:
            df_monthly_tax = df_monthly_tax.with_columns(
                pl.lit(fallback_div_rate).alias("Estimated_Ordinary_Income_Tax_Rate")
            )

        lf_inc_agg = self.base_lf.get("lf_inc_agg")

        if lf_inc_agg is not None:
            df_inc_tax = (
                lf_inc_agg
                .drop("MONTH_START_DATE") if "MONTH_START_DATE" in lf_inc_agg.collect_schema().names() else lf_inc_agg
            )
            df_inc_tax = (
                df_inc_tax.with_columns(
                    pl.col("DATE").cast(pl.Date).dt.month_start().alias("MONTH_START_DATE")
                )
                .group_by("MONTH_START_DATE")
                .agg(
                    pl.when(pl.col("Is_Dividend_Income"))
                    .then(pl.col("BASE_AMOUNT"))
                    .otherwise(0.0)
                    .sum()
                    .alias("Taxable_Dividends"),
                    pl.when(pl.col("Is_Interest_Income"))
                    .then(pl.col("BASE_AMOUNT"))
                    .otherwise(0.0)
                    .sum()
                    .alias("Taxable_Interest"),
                )
            )
        else:
            df_inc_tax = (
                lf_market_data.select(
                    pl.col("Closing_Date").dt.month_start().alias("MONTH_START_DATE")
                )
                .unique()
                .with_columns(
                    pl.lit(0.0).alias("Taxable_Dividends"),
                    pl.lit(0.0).alias("Taxable_Interest"),
                )
            )

        df_inc_tax = df_inc_tax.with_columns(pl.col("MONTH_START_DATE").cast(pl.Date))
        df_monthly_tax = (
            df_monthly_tax.sort("Closing_Date")
            .with_columns(pl.col("MONTH_START_DATE").cast(pl.Date))
            .group_by(["MONTH_START_DATE", "FY"])
            .agg(
                pl.col("FY_Realized_STCG").last().alias("Realized_STCG"),
                pl.col("FY_Realized_LTCG").last().alias("Realized_LTCG"),
                pl.col("FY_Realized_Gain").last().alias("Realized_Gain"),
                pl.col("FY_Realized_STCL").last().alias("Realized_STCL"),
                pl.col("FY_Realized_LTCL").last().alias("Realized_LTCL"),
                pl.col("FY_Realized_Loss").last().alias("Realized_Loss"),
                pl.col("FY_Realized_Net_PnL").last().alias("Realized_Net_PnL"),
                pl.col("Equity_LTCG_Exemption").last().alias("LTCG_Exemption_Remaining"),
                pl.col("Close_Value").sum().alias("Total_Portfolio_Value"),
                pl.when(pl.col("P/L") < 0)
                .then(pl.col("P/L"))
                .otherwise(0.0)
                .sum()
                .alias("Unrealized_Losses"),
                # Carry forward the FY-specific ordinary tax rate (last observation in month)
                pl.col("Estimated_Ordinary_Income_Tax_Rate")
                .last()
                .alias("Estimated_Ordinary_Income_Tax_Rate"),
                # Extract CHECK_REQUIRED metrics from the monthly slice
                pl.when(pl.col("Lot_Source_Type") == "RECONCILIATION")
                .then(1)
                .otherwise(0)
                .sum()
                .alias("Check_Required_Lot_Count"),
                pl.when(pl.col("Lot_Source_Type") == "RECONCILIATION")
                .then(pl.col("Close_Value"))
                .otherwise(0.0)
                .sum()
                .alias("Check_Required_Market_Value"),
                pl.when(pl.col("Lot_Source_Type") == "RECONCILIATION")
                .then(pl.col("P/L"))
                .otherwise(0.0)
                .sum()
                .alias("Check_Required_Unrealized_PL"),
            )
            .join(df_inc_tax, on="MONTH_START_DATE", how="left")
            .with_columns(
                pl.col("Taxable_Dividends").fill_null(0.0),
                pl.col("Taxable_Interest").fill_null(0.0),
            )
            .with_columns(
                # Step 1: STCL vs STCG
                pl.max_horizontal(
                    pl.col("Realized_STCG").clip(lower_bound=0.0) - pl.col("Realized_STCL").abs(),
                    pl.lit(0.0),
                ).alias("Net_STCG"),
                pl.max_horizontal(
                    pl.col("Realized_STCL").abs() - pl.col("Realized_STCG").clip(lower_bound=0.0),
                    pl.lit(0.0),
                ).alias("Remaining_STCL"),
            )
            .with_columns(
                # Step 2: Remaining STCL vs LTCG
                pl.max_horizontal(
                    pl.col("Realized_LTCG").clip(lower_bound=0.0) - pl.col("Remaining_STCL"),
                    pl.lit(0.0),
                ).alias("LTCG_After_STCL"),
            )
            .with_columns(
                # Step 3: LTCL vs Remaining LTCG
                pl.max_horizontal(
                    pl.col("LTCG_After_STCL") - pl.col("Realized_LTCL").abs(), pl.lit(0.0)
                ).alias("Net_LTCG"),
            )
            .with_columns(
                pl.min_horizontal(pl.col("Net_LTCG"), pl.col("LTCG_Exemption_Remaining"))
                .clip(lower_bound=0.0)
                .alias("LTCG_Exemption_Used"),
            )
            .with_columns(
                (
                    (pl.col("Net_STCG") * pl.lit(blended_stcg_rate))
                    + ((pl.col("Net_LTCG") - pl.col("LTCG_Exemption_Used")) * pl.lit(blended_ltcg_rate))
                    + (
                        pl.col("Taxable_Dividends").clip(lower_bound=0.0)
                        * pl.col("Estimated_Ordinary_Income_Tax_Rate")
                    )
                ).alias("Projected_Tax_Bill"),
                (pl.col("Unrealized_Losses").abs()).alias("Harvesting_Offset_Remaining"),
            )
            .with_columns(
                pl.min_horizontal(
                    pl.col("Harvesting_Offset_Remaining"),
                    (pl.col("Net_STCG") + pl.col("Net_LTCG")).clip(lower_bound=0.0),
                ).alias("Tax_Harvesting_Capacity"),
                pl.when(pl.col("Realized_Gain") > 0)
                .then((pl.col("Projected_Tax_Bill") / pl.col("Realized_Gain")) * 100.0)
                .otherwise(0.0)
                .alias("Effective_Tax_Rate_Pct"),
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
                    "Effective_Tax_Rate_Pct",
                    "Harvesting_Offset_Remaining",
                    "Tax_Harvesting_Capacity",
                    "Check_Required_Lot_Count",
                    "Check_Required_Market_Value",
                    "Check_Required_Unrealized_PL",
                    pl.lit("REALIZED_ONLY").alias("Forecast_Basis"),
                ]
            )
            .sort("MONTH_START_DATE")
        )

        return df_monthly_tax
