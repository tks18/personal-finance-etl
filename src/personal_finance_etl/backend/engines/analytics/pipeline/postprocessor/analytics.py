from datetime import date
from typing import Any

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.engines.analytics.rules.macro import FYMacroParametersTable
from personal_finance_etl.backend.utils.helpers import to_date_obj


class AdvancedAnalyticsCalculator:
    """Calculates Sharpe, Sortino, Calmar, MDD ratios for portfolio and its benchmark."""

    def __init__(self, fy_table: FYMacroParametersTable, rules: FinancialRules | None) -> None:
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
                pt_entry = portfolio_terminals.get(d_obj, portfolio_terminals.get(d, {}))
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
                    cf_records.append({"Date_Obj": d_obj, "injection": -float(cf["amount"])})

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
                    pl.when((pl.col("val").shift(1) + pl.when(pl.col("net_injection") > 0).then(pl.col("net_injection")).otherwise(0.0)) > 0)
                    .then(
                        (pl.col("val") - pl.col("val").shift(1) - pl.col("net_injection"))
                        / (pl.col("val").shift(1) + pl.when(pl.col("net_injection") > 0).then(pl.col("net_injection")).otherwise(0.0))
                    )
                    .otherwise(0.0)
                    .alias("daily_return")
                )
                .with_columns((pl.col("daily_return") + 1.0).cum_prod().alias("cum_return"))
                .with_columns(
                    pl.col("cum_return").cum_max().alias("peak_cum"),
                )
                .with_columns(
                    pl.when(pl.col("peak_cum") > 0)
                    .then((pl.col("cum_return") - pl.col("peak_cum")) / pl.col("peak_cum"))
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
