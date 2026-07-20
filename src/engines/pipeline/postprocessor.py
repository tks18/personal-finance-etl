"""
Pipeline PostProcessor.
Handles Portfolio-level calculations and lazy Polars joins.
"""

import math
from datetime import date

import polars as pl
from pyxirr import xirr

from src.engines.pipeline.context import RunContext
from src.utils.helpers import to_date_obj


class PostProcessor:
    def __init__(self, ctx: RunContext):
        self.ctx = ctx

    def run(
        self,
        lazy_df: pl.LazyFrame,
        unique_dates: list[date],
        global_cashflows: list[dict],
        portfolio_terminals: dict[date, dict],
        realized_events: list[dict],
    ) -> pl.LazyFrame:
        """
        Calculates portfolio metrics and lazily attaches them to the lot-level DataFrame.
        """

        # 1. Portfolio XIRR per closing date
        global_cashflows.sort(key=lambda x: x["date"])
        cf_ptr = 0
        port_rows = []
        port_dl: list[date] = []
        port_al: list[float] = []

        for d in unique_dates:
            d_obj = to_date_obj(d)
            if not d_obj:
                continue

            while cf_ptr < len(global_cashflows):
                cf_d = to_date_obj(global_cashflows[cf_ptr]["date"])
                if cf_d and cf_d <= d_obj:
                    port_dl.append(cf_d)
                    port_al.append(global_cashflows[cf_ptr]["amount"])
                    cf_ptr += 1
                else:
                    break

            pt_entry = portfolio_terminals.get(d_obj, portfolio_terminals.get(d, {}))
            t_val = pt_entry.get("val", 0.0)
            t_shadow = pt_entry.get("shadow_val", 0.0)

            if port_dl:
                port_dl.append(d_obj)
                port_al.append(t_val)
                try:
                    pxirr = xirr(port_dl, port_al) or 0.0
                except Exception:
                    pxirr = 0.0

                port_al[-1] = t_shadow
                try:
                    bm_pxirr = xirr(port_dl, port_al) or 0.0
                except Exception:
                    bm_pxirr = 0.0

                port_dl.pop()
                port_al.pop()
            else:
                pxirr = bm_pxirr = 0.0

            port_rows.append(
                {
                    "Closing_Date": d,
                    "Portfolio_XIRR": pxirr,
                    "Portfolio_BM_XIRR": bm_pxirr,
                    "Portfolio_Active_Return": pxirr - bm_pxirr,
                }
            )

        df_port = pl.DataFrame(port_rows)

        # Phase 1 & 2: Advanced Analytics (Sharpe, MDD, Sortino)
        pt_records = []
        for d in unique_dates:
            d_obj = to_date_obj(d)
            if d_obj:
                pt_entry = portfolio_terminals.get(d_obj, portfolio_terminals.get(d, {}))
                pt_records.append(
                    {"Closing_Date": d, "Date_Obj": d_obj, "val": pt_entry.get("val", 0.0)}
                )

        if pt_records:
            df_pt = pl.DataFrame(pt_records).sort("Date_Obj")
            df_pt = (
                df_pt.with_columns(pl.col("val").pct_change().fill_null(0.0).alias("daily_return"))
                .with_columns(
                    pl.col("daily_return")
                    .rolling_std(window_size=252, min_samples=1)
                    .fill_null(0.0)
                    .alias("volatility"),
                    pl.when(pl.col("daily_return") < 0)
                    .then(pl.col("daily_return"))
                    .otherwise(0.0)
                    .rolling_std(window_size=252, min_samples=1)
                    .fill_null(0.0)
                    .alias("downside_volatility"),
                    pl.col("val").cum_max().alias("peak_val"),
                )
                .with_columns(
                    pl.when(pl.col("peak_val") > 0)
                    .then((pl.col("val") - pl.col("peak_val")) / pl.col("peak_val"))
                    .otherwise(0.0)
                    .alias("Portfolio_Max_Drawdown")
                )
            )

            df_port = df_port.join(
                df_pt.select(
                    ["Closing_Date", "volatility", "downside_volatility", "Portfolio_Max_Drawdown"]
                ),
                on="Closing_Date",
                how="left",
            )
            risk_free_rate = 0.06  # Assuming 6% Risk Free Rate for India
            df_port = (
                df_port.with_columns(
                    (pl.col("volatility") * math.sqrt(252)).alias("ann_vol"),
                    (pl.col("downside_volatility") * math.sqrt(252)).alias("ann_down_vol"),
                )
                .with_columns(
                    pl.when(pl.col("ann_vol") > 0)
                    .then((pl.col("Portfolio_XIRR") - risk_free_rate) / pl.col("ann_vol"))
                    .otherwise(0.0)
                    .alias("Portfolio_Sharpe_Ratio"),
                    pl.when(pl.col("ann_down_vol") > 0)
                    .then((pl.col("Portfolio_XIRR") - risk_free_rate) / pl.col("ann_down_vol"))
                    .otherwise(0.0)
                    .alias("Portfolio_Sortino_Ratio"),
                )
                .drop(["volatility", "downside_volatility", "ann_vol", "ann_down_vol"])
            )
        else:
            df_port = df_port.with_columns(
                pl.lit(0.0).alias("Portfolio_Max_Drawdown"),
                pl.lit(0.0).alias("Portfolio_Sharpe_Ratio"),
                pl.lit(0.0).alias("Portfolio_Sortino_Ratio"),
            )

        lazy_df = lazy_df.join(df_port.lazy(), on="Closing_Date", how="left")

        # 2. Portfolio weights
        instr_val = lazy_df.group_by(["Closing_Date", "ISIN"]).agg(
            pl.col("Close_Value").sum().alias("Instrument_Close_Value")
        )
        port_tot = instr_val.group_by("Closing_Date").agg(
            pl.col("Instrument_Close_Value").sum().alias("Total_Portfolio_Value")
        )
        instr_val = instr_val.join(port_tot, on="Closing_Date", how="left").with_columns(
            (pl.col("Instrument_Close_Value") / pl.col("Total_Portfolio_Value"))
            .round(8)
            .alias("Portfolio_Weight_%")
        )
        lazy_df = lazy_df.join(
            instr_val.select(
                ["Closing_Date", "ISIN", "Instrument_Close_Value", "Portfolio_Weight_%"]
            ),
            on=["Closing_Date", "ISIN"],
            how="left",
        )
        lazy_df = (
            lazy_df.join(
                port_tot,
                on="Closing_Date",
                how="left",
            )
            .with_columns(
                (pl.col("Close_Value") / pl.col("Total_Portfolio_Value"))
                .round(8)
                .alias("Lot_Weight_%")
            )
            .drop("Total_Portfolio_Value", "Instrument_Close_Value")
        )

        # 3. FY realized gains (vectorized via Polars)
        if realized_events:
            df_events = pl.DataFrame(realized_events)

            df_dates_list = []
            for d in unique_dates:
                d_obj = to_date_obj(d)
                if not d_obj:
                    continue
                fy_sy = d_obj.year if d_obj.month >= 4 else d_obj.year - 1
                df_dates_list.append({"Closing_Date": d, "Date_Obj": d_obj, "event_fy_sy": fy_sy})
            df_dates = pl.DataFrame(df_dates_list).sort("Date_Obj")

            df_events = (
                df_events.with_columns(pl.col("date").cast(pl.Date))
                .with_columns(
                    pl.when(pl.col("date").dt.month() >= 4)
                    .then(pl.col("date").dt.year())
                    .otherwise(pl.col("date").dt.year() - 1)
                    .cast(pl.Int64)
                    .alias("event_fy_sy")
                )
                .with_columns(pl.col("tax_type").fill_null("equity").str.to_lowercase())
                .with_columns(
                    pl.when((pl.col("gain_type") == "LTCG") & (pl.col("gain") > 0))
                    .then(pl.col("gain"))
                    .otherwise(0.0)
                    .alias("is_ltcg"),
                    pl.when(
                        (pl.col("gain_type") == "LTCG")
                        & (pl.col("gain") > 0)
                        & (pl.col("tax_type") == "equity")
                    )
                    .then(pl.col("gain"))
                    .otherwise(0.0)
                    .alias("is_eq_ltcg"),
                    pl.when((pl.col("gain_type") == "STCG") & (pl.col("gain") > 0))
                    .then(pl.col("gain"))
                    .otherwise(0.0)
                    .alias("is_stcg"),
                    pl.when(pl.col("gain") < 0)
                    .then(pl.col("gain"))
                    .otherwise(0.0)
                    .alias("is_loss"),
                )
            )

            df_daily_events = (
                df_events.group_by(["date", "event_fy_sy"])
                .agg(
                    [
                        pl.col("is_ltcg").sum().alias("daily_ltcg"),
                        pl.col("is_eq_ltcg").sum().alias("daily_eq_ltcg"),
                        pl.col("is_stcg").sum().alias("daily_stcg"),
                        pl.col("is_loss").sum().alias("daily_loss"),
                    ]
                )
                .sort("date")
            )

            df_daily_events = df_daily_events.with_columns(
                [
                    pl.col("daily_ltcg").cum_sum().over("event_fy_sy").alias("cum_ltcg"),
                    pl.col("daily_eq_ltcg").cum_sum().over("event_fy_sy").alias("cum_eq_ltcg"),
                    pl.col("daily_stcg").cum_sum().over("event_fy_sy").alias("cum_stcg"),
                    pl.col("daily_loss").cum_sum().over("event_fy_sy").alias("cum_loss"),
                ]
            )

            df_fy_joined = df_dates.join_asof(
                df_daily_events,
                left_on="Date_Obj",
                right_on="date",
                by="event_fy_sy",
                strategy="backward",
            ).fill_null(0.0).with_columns(pl.col("event_fy_sy").cast(pl.Int64))

            exemption_limits = {
                fy_sy: self.ctx.fy_table.get_equity_ltcg_exemption(date(fy_sy, 4, 1))
                for fy_sy in df_dates["event_fy_sy"].unique()
            }
            exemption_df = pl.DataFrame(
                {
                    "event_fy_sy": list(exemption_limits.keys()),
                    "exemption_limit": list(exemption_limits.values()),
                }
            )

            df_fy_joined = df_fy_joined.join(exemption_df, on="event_fy_sy", how="left")

            df_fy_joined = df_fy_joined.with_columns(
                (
                    pl.col("event_fy_sy").cast(pl.String)
                    + "-"
                    + (pl.col("event_fy_sy") + 1).cast(pl.String).str.slice(2)
                ).alias("FY"),
                pl.col("cum_ltcg").round(4).alias("FY_Realized_LTCG"),
                pl.col("cum_stcg").round(4).alias("FY_Realized_STCG"),
                pl.col("cum_loss").round(4).alias("FY_Realized_Loss"),
                pl.max_horizontal(0.0, pl.col("exemption_limit") - pl.col("cum_eq_ltcg"))
                .round(4)
                .alias("FY_LTCG_Remaining_Exemption"),
            ).select(
                [
                    "Closing_Date",
                    "FY",
                    "FY_Realized_LTCG",
                    "FY_Realized_STCG",
                    "FY_Realized_Loss",
                    "FY_LTCG_Remaining_Exemption",
                ]
            )

            lazy_df = lazy_df.join(df_fy_joined.lazy(), on="Closing_Date", how="left")

        else:
            df_dates_list = []
            for d in unique_dates:
                d_obj = to_date_obj(d)
                if not d_obj:
                    continue
                fy_sy = d_obj.year if d_obj.month >= 4 else d_obj.year - 1
                limit = self.ctx.fy_table.get_equity_ltcg_exemption(date(fy_sy, 4, 1))
                df_dates_list.append(
                    {
                        "Closing_Date": d,
                        "FY": f"{fy_sy}-{str(fy_sy + 1)[-2:]}",
                        "FY_Realized_LTCG": 0.0,
                        "FY_Realized_STCG": 0.0,
                        "FY_Realized_Loss": 0.0,
                        "FY_LTCG_Remaining_Exemption": float(limit),
                    }
                )

            df_fy_empty = pl.DataFrame(df_dates_list)
            lazy_df = lazy_df.join(df_fy_empty.lazy(), on="Closing_Date", how="left")

        # 4. Stepup eligible flag
        lazy_df = lazy_df.with_columns(
            (
                (pl.col("Holding_Type") == "LTCG")
                & (pl.col("TAX_TYPE").str.to_lowercase() == "equity")
                & (pl.col("Unrealized_LTCG") > 0)
                & (pl.col("Unrealized_LTCG") <= pl.col("FY_LTCG_Remaining_Exemption"))
            ).alias("Stepup_Eligible")
        )

        # 5. Harvest recommendation
        lazy_df = lazy_df.with_columns(
            pl.when(pl.col("Unrealized_Loss") < 0)
            .then(pl.lit("HARVEST_LOSS"))
            .when(pl.col("Holding_Type") == "LTCG", pl.col("Stepup_Eligible"))
            .then(pl.lit("HARVEST_LTCG_EXEMPT"))
            .when(
                (pl.col("Holding_Type") == "STCG")
                & (pl.col("Days_To_LTCG") > 0)
                & (pl.col("Days_To_LTCG") <= 90)
                & (pl.col("P/L") > 0)
            )
            .then(pl.lit("WAIT_FOR_LTCG"))
            .otherwise(pl.lit("HOLD"))
            .alias("Harvest_Recommendation")
        )

        return lazy_df
