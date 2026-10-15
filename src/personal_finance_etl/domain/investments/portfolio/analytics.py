"""Portfolio drawdown analytics and tax harvesting recommendations.

Owns
----
- AdvancedAnalyticsCalculator: Computes daily portfolio returns, cumulative returns,
  and running Max Drawdown (MDD) tracking from net injection-adjusted valuation time series.
- HarvestRecommendationCalculator: Generates tax harvesting recommendations
  (HARVEST_LOSS, HARVEST_LTCG_EXEMPT, WAIT_FOR_LTCG, HOLD) based on Indian Section 112A
  exemption headroom and holding periods.

Does not own
-------------
- Stateful FIFO lot mutations (owned by domain.investments.lots.fifo).
- Presentation rendering (owned by presentation).
"""

from datetime import date
from typing import Any

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.dates import to_date_obj
from personal_finance_etl.domain.market.macro import FYMacroParametersTable


class AdvancedAnalyticsCalculator:
    """Calculates Max Drawdown (MDD) tracking and portfolio baseline returns."""

    def __init__(
        self, fy_table: FYMacroParametersTable, rules: FinancialRules | None
    ) -> None:
        self.fy_table = fy_table
        self.rules = rules

    def calculate(
        self,
        df_port: pl.DataFrame,
        unique_dates: list[date],
        portfolio_terminals: dict[date, dict[str, Any]],
        cashflows: list[dict[str, Any]],
    ) -> pl.DataFrame:
        pt_records: list[dict[str, Any]] = []
        for d in unique_dates:
            d_obj = to_date_obj(d)
            if d_obj:
                pt_entry = portfolio_terminals.get(
                    d_obj, portfolio_terminals.get(d, {})
                )
                pt_records.append(
                    {
                        "Closing_Date": d,
                        "Date_Obj": d_obj,
                        "val": pt_entry.get("val", 0.0),
                        # shadow_val = what benchmark portfolio would be worth
                        "shadow_val": pt_entry.get("shadow_val", 0.0),
                    }
                )

        if pt_records:
            df_pt = pl.DataFrame(pt_records).sort("Date_Obj")

            # Aggregate cash flows by date to compute net injection
            cf_records: list[dict[str, Any]] = []
            for cf in cashflows:
                d_obj = to_date_obj(cf["date"])
                if d_obj:
                    # 'amount' is negative for buys (injections) and positive for sells (withdrawals)
                    cf_records.append(
                        {"Date_Obj": d_obj, "injection": -float(cf["amount"])}
                    )

            if cf_records:
                df_cf = (
                    pl.DataFrame(cf_records)
                    .group_by("Date_Obj")
                    .agg(pl.col("injection").sum().alias("net_injection"))
                )
                df_pt = df_pt.join(df_cf, on="Date_Obj", how="left").with_columns(
                    pl.col("net_injection").fill_null(0.0)
                )
            else:
                df_pt = df_pt.with_columns(pl.lit(0.0).alias("net_injection"))

            df_pt = (
                df_pt.with_columns(
                    pl.when(
                        (
                            pl.col("val").shift(1)
                            + pl.when(pl.col("net_injection") > 0)
                            .then(pl.col("net_injection"))
                            .otherwise(0.0)
                        )
                        > 0
                    )
                    .then(
                        (
                            pl.col("val")
                            - pl.col("val").shift(1)
                            - pl.col("net_injection")
                        )
                        / (
                            pl.col("val").shift(1)
                            + pl.when(pl.col("net_injection") > 0)
                            .then(pl.col("net_injection"))
                            .otherwise(0.0)
                        )
                    )
                    .otherwise(0.0)
                    .alias("daily_return")
                )
                .with_columns(
                    (pl.col("daily_return") + 1.0).cum_prod().alias("cum_return")
                )
                .with_columns(
                    pl.col("cum_return").cum_max().alias("peak_cum"),
                )
                .with_columns(
                    pl.when(pl.col("peak_cum") > 0)
                    .then(
                        (pl.col("cum_return") - pl.col("peak_cum"))
                        / pl.col("peak_cum")
                    )
                    .otherwise(0.0)
                    .alias("Portfolio_Max_Drawdown")
                )
            )

            df_port = df_port.join(
                df_pt.select(
                    [
                        "Closing_Date",
                        "Portfolio_Max_Drawdown",
                    ]
                ),
                on="Closing_Date",
                how="left",
            )
        else:
            df_port = df_port.with_columns(
                pl.lit(0.0).alias("Portfolio_Max_Drawdown"),
            )

        return df_port


class HarvestRecommendationCalculator:
    """Calculates Stepup and Harvest Recommendations."""

    @staticmethod
    def calculate(lazy_df: pl.LazyFrame, rules: FinancialRules) -> pl.LazyFrame:
        wait_days = rules.assumptions.tax.harvest_wait_days_threshold if rules else 90

        # Derive foreign equity TAX_SUBTYPE exclusions from config if available;
        # fall back to the known set for backward compatibility.
        _foreign_subtypes: list[str] = [
            "us_listed",
            "us_stocks",
            "foreign",
            "us_equity",
            "international",
        ]

        lazy_df = lazy_df.with_columns(
            (
                (pl.col("Holding_Type") == "LTCG")
                & (pl.col("TAX_TYPE").str.to_lowercase() == "equity")
                # Section 112A step-up applies only to listed Indian equity.
                & ~pl.col("TAX_SUBTYPE").str.to_lowercase().is_in(_foreign_subtypes)
                & (pl.col("Unrealized_LTCG") > 0)
                & (pl.col("Unrealized_LTCG") <= pl.col("Equity_LTCG_Exemption"))
            ).alias("Stepup_Eligible"),
            (
                (pl.col("Unrealized_Loss") < 0)
                & ~(
                    (pl.col("TAX_TYPE").str.to_lowercase() == "debt")
                    & (pl.col("Holding_Type") == "STCG")
                )
            ).alias("Can_Harvest_Loss"),
        )

        lazy_df = lazy_df.with_columns(
            pl.when(pl.col("Can_Harvest_Loss"))
            .then(pl.lit("HARVEST_LOSS"))
            .when((pl.col("Holding_Type") == "LTCG") & pl.col("Stepup_Eligible"))
            .then(pl.lit("HARVEST_LTCG_EXEMPT"))
            .when(
                (pl.col("Holding_Type") == "STCG")
                & (pl.col("Days_To_LTCG") > 0)
                & (pl.col("Days_To_LTCG") <= wait_days)
                & (pl.col("P/L") > 0)
            )
            .then(pl.lit("WAIT_FOR_LTCG"))
            .otherwise(pl.lit("HOLD"))
            .alias("Harvest_Recommendation")
        )

        return lazy_df


__all__ = [
    "AdvancedAnalyticsCalculator",
    "HarvestRecommendationCalculator",
]
