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

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.dates import to_date_obj
from personal_finance_etl.domain.investments.contracts import CashflowDict, TerminalValueDict
from personal_finance_etl.domain.market.macro import FYMacroParametersTable


def _build_terminal_records(
    unique_dates: list[date],
    portfolio_terminals: dict[date, TerminalValueDict] | dict[date, dict[str, float]],
) -> pl.DataFrame:
    """Build a sorted valuation dataframe across evaluation dates.

    Parameters
    ----------
    unique_dates : list[date]
        Unique evaluation dates.
    portfolio_terminals : dict[date, TerminalValueDict] | dict[date, dict[str, float]]
        Terminal valuation snapshots.

    Returns
    -------
    pl.DataFrame
        Valuation series dataframe.
    """
    pt_records: list[dict[str, object]] = []
    for d in unique_dates:
        d_obj = to_date_obj(d)
        if d_obj:
            pt_entry = portfolio_terminals.get(d_obj, portfolio_terminals.get(d, {}))
            pt_records.append(
                {
                    "Closing_Date": d,
                    "Date_Obj": d_obj,
                    "val": pt_entry.get("val", 0.0),
                    "shadow_val": pt_entry.get("shadow_val", 0.0),
                }
            )
    if not pt_records:
        return pl.DataFrame()
    return pl.DataFrame(pt_records).sort("Date_Obj")


def _aggregate_net_injections(cashflows: list[CashflowDict]) -> pl.DataFrame:
    """Aggregate cash flows by date to compute net injection amounts.

    Parameters
    ----------
    cashflows : list[CashflowDict]
        Portfolio cash flows.

    Returns
    -------
    pl.DataFrame
        Net injection aggregated by Date_Obj.
    """
    cf_records: list[dict[str, object]] = []
    for cf in cashflows:
        d_obj = to_date_obj(cf.get("date"))
        if d_obj:
            cf_records.append({"Date_Obj": d_obj, "injection": -float(cf.get("amount") or 0.0)})

    if not cf_records:
        return pl.DataFrame()

    return (
        pl.DataFrame(cf_records)
        .group_by("Date_Obj")
        .agg(pl.col("injection").sum().alias("net_injection"))
    )


def _compute_drawdown_series(df_pt: pl.DataFrame, df_cf: pl.DataFrame) -> pl.DataFrame:
    """Calculate daily returns, cumulative peak returns, and running Max Drawdown (MDD).

    Parameters
    ----------
    df_pt : pl.DataFrame
        Terminal valuations dataframe.
    df_cf : pl.DataFrame
        Aggregated net injections dataframe.

    Returns
    -------
    pl.DataFrame
        Valuation dataframe enriched with Portfolio_Max_Drawdown.
    """
    if not df_cf.is_empty():
        df_pt = df_pt.join(df_cf, on="Date_Obj", how="left").with_columns(
            pl.col("net_injection").fill_null(0.0)
        )
    else:
        df_pt = df_pt.with_columns(pl.lit(0.0).alias("net_injection"))

    return (
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
                (pl.col("val") - pl.col("val").shift(1) - pl.col("net_injection"))
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


class AdvancedAnalyticsCalculator:
    """Calculates Max Drawdown (MDD) tracking and portfolio baseline returns."""

    def __init__(self, fy_table: FYMacroParametersTable, rules: FinancialRules | None) -> None:
        self.fy_table = fy_table
        self.rules = rules

    def calculate(
        self,
        df_port: pl.DataFrame,
        unique_dates: list[date],
        portfolio_terminals: dict[date, TerminalValueDict] | dict[date, dict[str, float]],
        cashflows: list[CashflowDict],
    ) -> pl.DataFrame:
        """Compute net-injection-adjusted returns and running Max Drawdown (MDD) tracking.

        Parameters
        ----------
        df_port : pl.DataFrame
            Portfolio time series dataframe containing Closing_Date.
        unique_dates : list[date]
            Chronological list of closing dates.
        portfolio_terminals : dict[date, TerminalValueDict] | dict[date, dict[str, float]]
            Daily terminal valuations mapping date to val and shadow_val.
        cashflows : list[CashflowDict]
            Raw cashflows used to calculate cumulative net capital injections.

        Returns
        -------
        pl.DataFrame
            Augmented dataframe with Portfolio_Max_Drawdown.
        """
        df_pt = _build_terminal_records(unique_dates, portfolio_terminals)

        if not df_pt.is_empty():
            df_cf = _aggregate_net_injections(cashflows)
            df_pt = _compute_drawdown_series(df_pt, df_cf)
            return df_port.join(
                df_pt.select(["Closing_Date", "Portfolio_Max_Drawdown"]),
                on="Closing_Date",
                how="left",
            )

        return df_port.with_columns(pl.lit(0.0).alias("Portfolio_Max_Drawdown"))


class HarvestRecommendationCalculator:
    """Calculates Stepup and Harvest Recommendations."""

    @staticmethod
    def calculate(lazy_df: pl.LazyFrame, rules: FinancialRules) -> pl.LazyFrame:
        """Generate capital gains tax harvesting and step-up recommendations.

        Parameters
        ----------
        lazy_df : pl.LazyFrame
            Incoming daily snapshot lazy frame with unrealized gains and holding classification.
        rules : FinancialRules
            Configuration rules containing tax harvesting wait thresholds and exclusions.

        Returns
        -------
        pl.LazyFrame
            Augmented lazy frame with Stepup_Eligible, Can_Harvest_Loss, and Harvest_Recommendation.
        """
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
