import warnings
from datetime import date

import polars as pl

from src.engines.analytics.pipeline.context import RunContext
from src.utils.helpers import get_fy_start_year, to_date_obj

warnings.filterwarnings(
    "ignore", message="Sortedness of columns cannot be checked when 'by' groups provided"
)


class RealizedGainsCalculator:
    """Calculates FY realized gains."""

    def __init__(self, ctx: RunContext):
        self.ctx = ctx

    def _build_empty_fy_frame(self, unique_dates: list[date]) -> pl.DataFrame:
        df_dates_list = []
        for d in unique_dates:
            d_obj = to_date_obj(d)
            if not d_obj:
                continue
            fy_sy = get_fy_start_year(d_obj)
            limit = self.ctx.fy_table.get_equity_ltcg_exemption(date(fy_sy, 4, 1))
            df_dates_list.append(
                {
                    "Closing_Date": d,
                    "Date_Obj": d_obj,
                    "event_fy_sy": fy_sy,
                    "FY": f"{fy_sy}-{str(fy_sy + 1)[-2:]}",
                    "FY_Realized_LTCG": 0.0,
                    "FY_Realized_STCG": 0.0,
                    "FY_Realized_LTCL": 0.0,
                    "FY_Realized_STCL": 0.0,
                    "FY_Realized_Loss": 0.0,
                    "FY_LTCG_Remaining_Exemption": float(limit),
                }
            )
        return pl.DataFrame(df_dates_list)

    def calculate(
        self, lazy_df: pl.LazyFrame, unique_dates: list[date], realized_events: list[dict]
    ) -> pl.LazyFrame:
        df_fy_empty = self._build_empty_fy_frame(unique_dates)

        if realized_events:
            df_events = pl.DataFrame(realized_events)
            df_dates = (
                df_fy_empty.select(["Closing_Date", "Date_Obj", "event_fy_sy"])
                .sort(["event_fy_sy", "Date_Obj"])
                .with_columns(pl.col("Date_Obj").set_sorted())
            )

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
                    pl.when((pl.col("gain_type") == "LTCG") & (pl.col("gain") >= 0))
                    .then(pl.col("gain"))
                    .otherwise(0.0)
                    .alias("is_ltcg"),
                    pl.when(
                        (pl.col("gain_type") == "LTCG")
                        & (pl.col("gain") >= 0)
                        & (pl.col("tax_type") == "equity")
                    )
                    .then(pl.col("gain"))
                    .otherwise(0.0)
                    .alias("is_eq_ltcg"),
                    pl.when((pl.col("gain_type") == "STCG") & (pl.col("gain") >= 0))
                    .then(pl.col("gain"))
                    .otherwise(0.0)
                    .alias("is_stcg"),
                    pl.when((pl.col("gain_type") == "LTCG") & pl.col("is_loss"))
                    .then(pl.col("gain"))
                    .otherwise(0.0)
                    .alias("is_ltcl"),
                    pl.when((pl.col("gain_type") == "STCG") & pl.col("is_loss"))
                    .then(pl.col("gain"))
                    .otherwise(0.0)
                    .alias("is_stcl"),
                )
            )

            df_daily_events = (
                df_events.group_by(["date", "event_fy_sy"])
                .agg(
                    [
                        pl.col("is_ltcg").sum().alias("daily_ltcg"),
                        pl.col("is_eq_ltcg").sum().alias("daily_eq_ltcg"),
                        pl.col("is_stcg").sum().alias("daily_stcg"),
                        pl.col("is_ltcl").sum().alias("daily_ltcl"),
                        pl.col("is_stcl").sum().alias("daily_stcl"),
                    ]
                )
                .sort(["event_fy_sy", "date"])
                .with_columns(pl.col("date").set_sorted())
            )

            df_daily_events = df_daily_events.with_columns(
                [
                    pl.col("daily_ltcg")
                    .cum_sum()
                    .over("event_fy_sy", order_by="date")
                    .alias("cum_ltcg"),
                    pl.col("daily_eq_ltcg")
                    .cum_sum()
                    .over("event_fy_sy", order_by="date")
                    .alias("cum_eq_ltcg"),
                    pl.col("daily_stcg")
                    .cum_sum()
                    .over("event_fy_sy", order_by="date")
                    .alias("cum_stcg"),
                    pl.col("daily_ltcl")
                    .cum_sum()
                    .over("event_fy_sy", order_by="date")
                    .alias("cum_ltcl"),
                    pl.col("daily_stcl")
                    .cum_sum()
                    .over("event_fy_sy", order_by="date")
                    .alias("cum_stcl"),
                ]
            )

            df_fy_joined = (
                df_dates.join_asof(
                    df_daily_events,
                    left_on="Date_Obj",
                    right_on="date",
                    by="event_fy_sy",
                    strategy="backward",
                )
                .fill_null(0.0)
                .with_columns(pl.col("event_fy_sy").cast(pl.Int64))
            )

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
                pl.col("cum_ltcl").round(4).alias("FY_Realized_LTCL"),
                pl.col("cum_stcl").round(4).alias("FY_Realized_STCL"),
                (pl.col("cum_ltcl") + pl.col("cum_stcl")).round(4).alias("FY_Realized_Loss"),
                pl.max_horizontal(0.0, pl.col("exemption_limit") - pl.col("cum_eq_ltcg"))
                .round(4)
                .alias("FY_LTCG_Remaining_Exemption"),
            ).select(
                [
                    "Closing_Date",
                    "FY",
                    "FY_Realized_LTCG",
                    "FY_Realized_STCG",
                    "FY_Realized_LTCL",
                    "FY_Realized_STCL",
                    "FY_Realized_Loss",
                    "FY_LTCG_Remaining_Exemption",
                ]
            )

            lazy_df = lazy_df.join(df_fy_joined.lazy(), on="Closing_Date", how="left").with_columns(
                (pl.col("FY_Realized_LTCG") * pl.col("Lot_Weight_%")).alias("FY_Realized_LTCG"),
                (pl.col("FY_Realized_STCG") * pl.col("Lot_Weight_%")).alias("FY_Realized_STCG"),
                (pl.col("FY_Realized_LTCL") * pl.col("Lot_Weight_%")).alias("FY_Realized_LTCL"),
                (pl.col("FY_Realized_STCL") * pl.col("Lot_Weight_%")).alias("FY_Realized_STCL"),
                (pl.col("FY_Realized_Loss") * pl.col("Lot_Weight_%")).alias("FY_Realized_Loss"),
            )

        else:
            lazy_df = lazy_df.join(
                df_fy_empty.select(
                    [
                        "Closing_Date",
                        "FY",
                        "FY_Realized_LTCG",
                        "FY_Realized_STCG",
                        "FY_Realized_LTCL",
                        "FY_Realized_STCL",
                        "FY_Realized_Loss",
                        "FY_LTCG_Remaining_Exemption",
                    ]
                ).lazy(),
                on="Closing_Date",
                how="left",
            ).with_columns(
                (pl.col("FY_Realized_LTCG") * pl.col("Lot_Weight_%")).alias("FY_Realized_LTCG"),
                (pl.col("FY_Realized_STCG") * pl.col("Lot_Weight_%")).alias("FY_Realized_STCG"),
                (pl.col("FY_Realized_LTCL") * pl.col("Lot_Weight_%")).alias("FY_Realized_LTCL"),
                (pl.col("FY_Realized_STCL") * pl.col("Lot_Weight_%")).alias("FY_Realized_STCL"),
                (pl.col("FY_Realized_Loss") * pl.col("Lot_Weight_%")).alias("FY_Realized_Loss"),
            )

        return lazy_df
