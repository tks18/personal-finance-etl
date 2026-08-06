from collections.abc import Mapping
from typing import Any, cast

import polars as pl


class MonthlyCashflowSummaryBuilder:
    """
    Builds p_tf_Monthly_Cashflow_Summary — a single wide row per month that
    consolidates every cashflow dimension:

    Income:
        Total_Income = Active_Income + Passive_Income
        Passive_Income = Dividend_Income + Interest_Income

    Expense:
        Total_Expense = Core_Expense + NonCore_Expense

    Investments (from net transfers to investment accounts):
        Total_Investment_Deployed  — from f_tf_Investment_Purchase_Data
        Total_Investment_Redeemed  — from f_tf_Investment_Sale_Data
        Net_Investment_Flow        — Deployed - Redeemed
        Equity_Deployed            — CLASS = 'Equity' (Stocks + ETFs)
            Stocks_Deployed        — TYPE = 'Direct Stocks' (or similar)
            ETFs_Deployed          — TYPE = 'ETFs'
        MF_Deployed                — CLASS = 'Mutual Funds'
        Other_Deployed             — everything else

    Surplus / Savings:
        Gross_Surplus              — Total_Income - Total_Expense
        Net_Surplus_After_Invest   — Gross_Surplus - Net_Investment_Flow
        Savings_Rate_Pct           — Gross_Surplus / Total_Income
        Investment_Rate_Pct        — Net_Investment_Flow / Total_Income

    MoM deltas for the most important lines (trailing comparison).
    """

    def __init__(
        self,
        dfs: Mapping[str, pl.DataFrame | pl.LazyFrame],
        base_lf: dict[str, Any],
        rules,
    ):
        self.dfs = dfs
        self.base_lf = base_lf
        self.rules = rules

    def build(self) -> pl.LazyFrame:
        lf_monthly = self.base_lf.get("lf_monthly_totals")
        if lf_monthly is None:
            return pl.LazyFrame()

        # ── Step 1: Income bifurcation from lf_inc_agg ────────────────────────
        lf_inc_agg = self.base_lf.get("lf_inc_agg")

        if lf_inc_agg is not None:
            lf_inc_split = (
                lf_inc_agg.with_columns(
                    pl.col("DATE").dt.month_start().alias("MONTH_START_DATE"),
                )
                .group_by("MONTH_START_DATE")
                .agg(
                    pl.col("INCOME").sum().fill_null(0.0).alias("Total_Income_Check"),
                    pl.col("INCOME")
                    .filter(pl.col("Is_Active_Income").fill_null(False))
                    .sum()
                    .fill_null(0.0)
                    .alias("Active_Income"),
                    pl.col("INCOME")
                    .filter(pl.col("Is_Dividend_Income").fill_null(False))
                    .sum()
                    .fill_null(0.0)
                    .alias("Dividend_Income"),
                    pl.col("INCOME")
                    .filter(pl.col("Is_Interest_Income").fill_null(False))
                    .sum()
                    .fill_null(0.0)
                    .alias("Interest_Income"),
                )
                .with_columns(
                    (pl.col("Dividend_Income") + pl.col("Interest_Income")).alias("Passive_Income"),
                )
            )
            lf_monthly = lf_monthly.join(lf_inc_split, on="MONTH_START_DATE", how="left").sort(
                "MONTH_START_DATE"  # Sort guard after join
            )
            lf_monthly = lf_monthly.with_columns(
                pl.col("Active_Income").fill_null(0.0),
                pl.col("Dividend_Income").fill_null(0.0),
                pl.col("Interest_Income").fill_null(0.0),
                pl.col("Passive_Income").fill_null(0.0),
            )
        else:
            lf_monthly = lf_monthly.with_columns(
                pl.lit(0.0).alias("Active_Income"),
                pl.lit(0.0).alias("Passive_Income"),
                pl.lit(0.0).alias("Dividend_Income"),
                pl.lit(0.0).alias("Interest_Income"),
            )

        # ── Step 2: Expense bifurcation ───────────────────────────────────────
        # Core comes from base_metrics (already aggregated as Total_Core_Expense)
        lf_monthly = lf_monthly.with_columns(
            (pl.col("Total_Expense") - pl.col("Total_Core_Expense")).alias("NonCore_Expense"),
        )

        # ── Step 3: Investment activity from purchase/sale facts ──────────────
        df_buys = self.dfs.get("df_f_tf_inv_purchase")
        df_sells = self.dfs.get("df_f_tf_inv_sale")
        df_master = self.dfs.get("df_d_tf_investment_master")

        if df_buys is not None and df_master is not None:
            lf_buys = cast(
                pl.LazyFrame, df_buys.lazy() if isinstance(df_buys, pl.DataFrame) else df_buys
            )
            lf_master = cast(
                pl.LazyFrame,
                df_master.lazy() if isinstance(df_master, pl.DataFrame) else df_master,
            )
            # Enrich buys with instrument class/type from master
            lf_buys_enriched = lf_buys.join(
                lf_master.select(["ISIN", "INSTRUMENT_CLASS", "INSTRUMENT_TYPE"]),
                on="ISIN",
                how="left",
            ).with_columns(
                pl.col("Date").dt.month_start().alias("MONTH_START_DATE"),
                pl.col("INSTRUMENT_CLASS").fill_null("Unknown"),
                pl.col("INSTRUMENT_TYPE").fill_null("Unknown"),
            )

            lf_inv_deployed = (
                lf_buys_enriched.group_by("MONTH_START_DATE")
                .agg(
                    pl.col("Value").sum().fill_null(0.0).alias("Total_Investment_Deployed"),
                    # Equity = Stocks + ETFs
                    pl.col("Value")
                    .filter(pl.col("INSTRUMENT_CLASS").str.to_lowercase().str.contains( "(?i)stocks|etfs"))
                    .sum()
                    .fill_null(0.0)
                    .alias("Equity_Deployed"),
                    # Direct stocks
                    pl.col("Value")
                    .filter(
                        pl.col("INSTRUMENT_CLASS").str.to_lowercase().str.contains(
                            "(?i)direct|stock"
                        )
                    )
                    .sum()
                    .fill_null(0.0)
                    .alias("Stocks_Deployed"),
                    # ETFs
                    pl.col("Value")
                    .filter(pl.col("INSTRUMENT_CLASS").str.to_lowercase().str.contains("etf"))
                    .sum()
                    .fill_null(0.0)
                    .alias("ETFs_Deployed"),
                    # Mutual Funds
                    pl.col("Value")
                    .filter(
                        pl.col("INSTRUMENT_CLASS").str.to_lowercase().str.contains(
                            "(?i)mutual|fund"
                        )
                    )
                    .sum()
                    .fill_null(0.0)
                    .alias("MF_Deployed"),
                )
                .with_columns(
                    (
                        pl.col("Total_Investment_Deployed")
                        - pl.col("Equity_Deployed")
                        - pl.col("MF_Deployed")
                    )
                    .clip(lower_bound=0.0)
                    .alias("Other_Deployed"),
                )
            )
            lf_monthly = lf_monthly.join(lf_inv_deployed, on="MONTH_START_DATE", how="left").sort(
                "MONTH_START_DATE"
            )
            lf_monthly = lf_monthly.with_columns(
                pl.col("Total_Investment_Deployed").fill_null(0.0),
                pl.col("Equity_Deployed").fill_null(0.0),
                pl.col("Stocks_Deployed").fill_null(0.0),
                pl.col("ETFs_Deployed").fill_null(0.0),
                pl.col("MF_Deployed").fill_null(0.0),
                pl.col("Other_Deployed").fill_null(0.0),
            )
        else:
            lf_monthly = lf_monthly.with_columns(
                pl.lit(0.0).alias("Total_Investment_Deployed"),
                pl.lit(0.0).alias("Equity_Deployed"),
                pl.lit(0.0).alias("Stocks_Deployed"),
                pl.lit(0.0).alias("ETFs_Deployed"),
                pl.lit(0.0).alias("MF_Deployed"),
                pl.lit(0.0).alias("Other_Deployed"),
            )

        if df_sells is not None:
            lf_sells = cast(
                pl.LazyFrame, df_sells.lazy() if isinstance(df_sells, pl.DataFrame) else df_sells
            )
            lf_inv_redeemed = (
                lf_sells.with_columns(pl.col("Date").dt.month_start().alias("MONTH_START_DATE"))
                .group_by("MONTH_START_DATE")
                .agg(
                    pl.col("Sell Value").sum().fill_null(0.0).alias("Total_Investment_Redeemed")
                )
            )
            lf_monthly = lf_monthly.join(lf_inv_redeemed, on="MONTH_START_DATE", how="left").sort(
                "MONTH_START_DATE"
            )
            lf_monthly = lf_monthly.with_columns(
                pl.col("Total_Investment_Redeemed").fill_null(0.0),
            )
        else:
            lf_monthly = lf_monthly.with_columns(pl.lit(0.0).alias("Total_Investment_Redeemed"))

        # ── Step 4: Net investment flow & surplus ─────────────────────────────
        lf_monthly = lf_monthly.with_columns(
            (
                pl.col("Total_Investment_Deployed") - pl.col("Total_Investment_Redeemed")
            ).alias("Net_Investment_Flow"),
            (pl.col("Total_Income") - pl.col("Total_Expense")).alias("Gross_Surplus"),
        ).with_columns(
            (pl.col("Gross_Surplus") - pl.col("Net_Investment_Flow")).alias(
                "Net_Surplus_After_Invest"
            ),
            pl.when(pl.col("Total_Income") > 0)
            .then(pl.col("Gross_Surplus") / pl.col("Total_Income"))
            .otherwise(0.0)
            .alias("Savings_Rate_Pct"),
            pl.when(pl.col("Total_Income") > 0)
            .then(pl.col("Net_Investment_Flow") / pl.col("Total_Income"))
            .otherwise(0.0)
            .alias("Investment_Rate_Pct"),
            pl.when(pl.col("Total_Income") > 0)
            .then(pl.col("Active_Income") / pl.col("Total_Income"))
            .otherwise(0.0)
            .alias("Active_Income_Share_Pct"),
            pl.when(pl.col("Total_Income") > 0)
            .then(pl.col("Passive_Income") / pl.col("Total_Income"))
            .otherwise(0.0)
            .alias("Passive_Income_Share_Pct"),
            pl.when(pl.col("Total_Expense") > 0)
            .then(pl.col("Total_Core_Expense") / pl.col("Total_Expense"))
            .otherwise(0.0)
            .alias("Core_Expense_Share_Pct"),
            pl.when(pl.col("Total_Investment_Deployed") > 0)
            .then(pl.col("Equity_Deployed") / pl.col("Total_Investment_Deployed"))
            .otherwise(0.0)
            .alias("Equity_Pct_of_Deployed"),
            pl.when(pl.col("Total_Investment_Deployed") > 0)
            .then(pl.col("MF_Deployed") / pl.col("Total_Investment_Deployed"))
            .otherwise(0.0)
            .alias("MF_Pct_of_Deployed"),
        )

        # ── Step 5: MoM deltas (sort is already guaranteed above) ─────────────
        lf_monthly = lf_monthly.sort("MONTH_START_DATE").with_columns(
            (pl.col("Total_Income") - pl.col("Total_Income").shift(1)).alias("Income_MoM_Delta"),
            (pl.col("Total_Expense") - pl.col("Total_Expense").shift(1)).alias("Expense_MoM_Delta"),
            (pl.col("Net_Investment_Flow") - pl.col("Net_Investment_Flow").shift(1)).alias(
                "Investment_MoM_Delta"
            ),
            pl.when(pl.col("Total_Income").shift(1) > 0)
            .then(
                (pl.col("Total_Income") - pl.col("Total_Income").shift(1))
                / pl.col("Total_Income").shift(1)
            )
            .otherwise(None)
            .alias("Income_MoM_Pct"),
            pl.when(pl.col("Total_Expense").shift(1) > 0)
            .then(
                (pl.col("Total_Expense") - pl.col("Total_Expense").shift(1))
                / pl.col("Total_Expense").shift(1)
            )
            .otherwise(None)
            .alias("Expense_MoM_Pct"),
        )

        # ── Step 6: Trailing averages (3M) ────────────────────────────────────
        lf_monthly = lf_monthly.with_columns(
            pl.col("Total_Income").rolling_mean(3).alias("Trailing_3M_Avg_Income"),
            pl.col("Total_Expense").rolling_mean(3).alias("Trailing_3M_Avg_Expense"),
            pl.col("Net_Investment_Flow").rolling_mean(3).alias("Trailing_3M_Avg_Investment"),
            pl.col("Savings_Rate_Pct").rolling_mean(3).alias("Trailing_3M_Avg_Savings_Rate"),
        )

        # ── Step 7: YEAR_MONTH & flags ────────────────────────────────────────
        lf_monthly = lf_monthly.with_columns(
            pl.col("MONTH_START_DATE").cast(pl.String).str.slice(0, 7).alias("YEAR_MONTH"),
            (pl.col("Gross_Surplus") > 0).alias("Is_Surplus_Month"),
            (pl.col("Net_Investment_Flow") >= pl.col("Total_Income") * self.rules.budget.income_allocation.investment_pct).alias(
                "Is_Investment_Target_Met"
            ),
        )

        return lf_monthly.select(
            [
                "MONTH_START_DATE", "MONTH_END_DATE", "YEAR_MONTH",
                # Income bifurcation
                "Total_Income",
                "Active_Income",
                "Passive_Income",
                "Dividend_Income",
                "Interest_Income",
                "Active_Income_Share_Pct",
                "Passive_Income_Share_Pct",
                # Expense bifurcation
                "Total_Expense",
                "Total_Core_Expense",
                "NonCore_Expense",
                "Core_Expense_Share_Pct",
                # Investments deployed (buys)
                "Total_Investment_Deployed",
                "Equity_Deployed",
                "Stocks_Deployed",
                "ETFs_Deployed",
                "MF_Deployed",
                "Other_Deployed",
                "Equity_Pct_of_Deployed",
                "MF_Pct_of_Deployed",
                # Redemptions & net flow
                "Total_Investment_Redeemed",
                "Net_Investment_Flow",
                # Surplus & rates
                "Gross_Surplus",
                "Net_Surplus_After_Invest",
                "Savings_Rate_Pct",
                "Investment_Rate_Pct",
                # MoM deltas
                "Income_MoM_Delta",
                "Expense_MoM_Delta",
                "Investment_MoM_Delta",
                "Income_MoM_Pct",
                "Expense_MoM_Pct",
                # Trailing averages
                "Trailing_3M_Avg_Income",
                "Trailing_3M_Avg_Expense",
                "Trailing_3M_Avg_Investment",
                "Trailing_3M_Avg_Savings_Rate",
                # Flags
                "Is_Surplus_Month",
                "Is_Investment_Target_Met",
            ]
        )
