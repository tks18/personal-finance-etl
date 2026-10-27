"""Household inflation modeling and CPI series construction.

Owns
----
- InflationBuilder: Constructs monthly continuous inflation rates and cumulative CPI index series.
- CPI index derivation from Macro Parameters and fallback rates.
- CpiResult contract mapping with calculation provenance.

Does not own
-------------
- Macro parameter source extraction (owned by infrastructure.providers).
- Investment valuation adjustments (owned by domain.wealth.net_worth).
- Physical table storage or DuckDB registration (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date
from typing import TypedDict

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.calculation import CalculationStatus, CpiResult

__all__ = ["InflationBuilder", "InflationCalendarResult"]


class InflationCalendarResult(TypedDict):
    """Result of inflation and calendar timeline processing."""

    lf_months: pl.LazyFrame
    lf_inflation: pl.LazyFrame
    cpi_latest: float
    cpi_result: CpiResult


class InflationBuilder:
    """Constructs monthly continuous inflation rates and cumulative CPI index series."""

    def __init__(
        self, dfs: Mapping[str, pl.DataFrame | pl.LazyFrame], rules: FinancialRules
    ) -> None:
        self.dfs = dfs
        self.rules = rules

    def _build_monthly_calendar(self, lf_open: pl.LazyFrame, lf_cal: pl.LazyFrame) -> pl.LazyFrame:
        """Derive monthly start and end dates from the earliest opening balance to today."""
        lf_min_date = lf_open.select(pl.col("ZTXDATESTR").min().alias("min_open_date")).fill_null(
            date(2000, 1, 1)
        )

        return (
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

    def _build_inflation_series(
        self, lf_months: pl.LazyFrame, lf_macro: pl.LazyFrame
    ) -> pl.LazyFrame:
        """Construct continuous monthly inflation rate and cumulative CPI index series."""
        return (
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

    def build(self) -> InflationCalendarResult:
        """Build continuous monthly calendar and inflation series.

        Returns
        -------
        InflationCalendarResult
            Dictionary containing:
            - lf_months: Monthly calendar boundaries from earliest opening date to today.
            - lf_inflation: Monthly continuous YoY inflation rate and cumulative CPI_INDEX.
            - cpi_latest: Float value of latest CPI index.
            - cpi_result: Strongly-typed CpiResult with status and provenance.
        """
        f_open = self.dfs.get("df_f_opening_balances")
        d_cal = self.dfs.get("df_d_calendar")
        d_macro = self.dfs.get("df_d_macro_parameters")

        if f_open is None or d_cal is None or d_macro is None:
            return {
                "lf_months": pl.LazyFrame(),
                "lf_inflation": pl.LazyFrame(),
                "cpi_latest": float("nan"),
                "cpi_result": CpiResult(
                    value=None,
                    status=CalculationStatus.MISSING_INPUT,
                    reason="Required inputs missing (f_open, d_cal, or d_macro)",
                ),
            }

        lf_open = f_open.lazy() if isinstance(f_open, pl.DataFrame) else f_open
        lf_cal = (d_cal.lazy() if isinstance(d_cal, pl.DataFrame) else d_cal).rename(
            {"Date": "DATE", "Year": "YEAR", "Month": "MONTH"}
        )
        lf_macro = (d_macro.lazy() if isinstance(d_macro, pl.DataFrame) else d_macro).select(
            pl.col("FY_Start_Date").cast(pl.Date), pl.col("Inflation_Rate").cast(pl.Float64)
        )

        lf_months = self._build_monthly_calendar(lf_open, lf_cal)
        lf_inflation = self._build_inflation_series(lf_months, lf_macro)
        cpi_result = self._resolve_latest_cpi(lf_inflation)

        return {
            "lf_months": lf_months,
            "lf_inflation": lf_inflation,
            "cpi_latest": cpi_result.as_float(fallback=float("nan")),
            "cpi_result": cpi_result,
        }

    def _resolve_latest_cpi(self, lf_inflation: pl.LazyFrame) -> CpiResult:
        try:
            # Materialization Boundary: SCALAR_EXTRACTION
            # Materialize single terminal row to extract scalar latest CPI index value
            cpi_latest_df = (
                lf_inflation.sort("MONTH_START_DATE").tail(1).select("CPI_INDEX").collect()
            )
            if cpi_latest_df.is_empty():
                return CpiResult(
                    value=None,
                    status=CalculationStatus.NO_OBSERVATION,
                    reason="No observations available in inflation series",
                )
            val = cpi_latest_df.item()
            if (
                val is not None
                and isinstance(val, (int, float))
                and not math.isnan(val)
                and not math.isinf(val)
            ):
                return CpiResult(
                    value=float(val),
                    status=CalculationStatus.VALID,
                )
            return CpiResult(
                value=None,
                status=CalculationStatus.INVALID_INPUT,
                reason="Derived latest CPI_INDEX is null, NaN, or non-finite",
            )
        except Exception as err:
            return CpiResult(
                value=None,
                status=CalculationStatus.COMPUTATION_ERROR,
                reason=str(err),
            )
