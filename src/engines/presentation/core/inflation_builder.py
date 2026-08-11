from collections.abc import Mapping
from datetime import date
from typing import Any

import polars as pl

from src.config.financial_rules import FinancialRules


class InflationBuilder:
    def __init__(self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], rules: FinancialRules):
        self.dfs = dfs
        self.rules = rules

    def build(self) -> dict[str, Any]:
        f_open = self.dfs.get("df_f_opening_balances")
        d_cal = self.dfs.get("df_d_calendar")
        d_macro = self.dfs.get("df_d_macro_parameters")

        if f_open is None or d_cal is None or d_macro is None:
            return {}

        lf_open = f_open.lazy() if isinstance(f_open, pl.DataFrame) else f_open
        lf_cal = (d_cal.lazy() if isinstance(d_cal, pl.DataFrame) else d_cal).rename(
            {"Date": "DATE", "Year": "YEAR", "Month": "MONTH"}
        )
        lf_macro = (d_macro.lazy() if isinstance(d_macro, pl.DataFrame) else d_macro).select(
            pl.col("FY_Start_Date").cast(pl.Date), pl.col("Inflation_Rate").cast(pl.Float64)
        )

        lf_min_date = lf_open.select(pl.col("ZTXDATESTR").min().alias("min_open_date")).fill_null(
            date(2000, 1, 1)
        )

        lf_months = (
            lf_cal.group_by(["YEAR", "MONTH"])
            .agg(
                [
                    pl.col("DATE").min().alias("MONTH_START_DATE"),
                    pl.col("DATE").max().alias("MONTH_END_DATE"),
                ]
            )
            .filter(pl.col("MONTH_START_DATE") <= pl.lit(date.today()))
            .join(lf_min_date, how="cross")
            .filter(pl.col("MONTH_END_DATE") >= pl.col("min_open_date"))
            .drop("min_open_date")
            .sort(["YEAR", "MONTH"])
        )

        lf_inflation = (
            lf_months.sort("MONTH_START_DATE")
            .join_asof(
                lf_macro.sort("FY_Start_Date"),
                left_on="MONTH_START_DATE",
                right_on="FY_Start_Date",
                strategy="backward",
            )
            .with_columns(
                pl.col("Inflation_Rate")
                .fill_null(self.rules.assumptions.macro.fallback_inflation_rate)
                .alias("INFLATION_YOY_PCT")
            )
            .with_columns(
                ((pl.col("INFLATION_YOY_PCT") + 1.0).pow(1.0 / 12.0)).alias("monthly_factor")
            )
            .with_columns((pl.col("monthly_factor").cum_prod() * 100.0).alias("CPI_INDEX"))
            .select(["MONTH_START_DATE", "INFLATION_YOY_PCT", "CPI_INDEX"])
        )

        try:
            cpi_latest_df = (
                lf_inflation.sort("MONTH_START_DATE").tail(1).select("CPI_INDEX").collect()
            )
            if not cpi_latest_df.is_empty():
                cpi_latest = cpi_latest_df.item()
            else:
                cpi_latest = 100.0
        except Exception:
            cpi_latest = 100.0

        return {
            "lf_months": lf_months,
            "lf_inflation": lf_inflation,
            "cpi_latest": cpi_latest,
        }
