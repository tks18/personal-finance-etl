"""Run-scoped analytics coordination context and context initialization.

Owns
----
- RunContext: Container holding immutable input DataFrames, FY macro parameters,
  date intervals, and FX rate providers for a single quant execution run.
- AnalyticsContextManager: Validates and initializes RunContext from DataFrames or files,
  identifying unique actionable ISINs across purchases, sales, and market observations.

Does not own
-------------
- Raw extraction parsing (owned by application.investments.input_adapter).
- Lot state mutation (owned by domain.investments.lots.fifo).
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

import polars as pl

from personal_finance_etl.application.investments.input_adapter import TaxDataLoader
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.contracts.application import EngineStatusMessage
from personal_finance_etl.contracts.logging import LogLevel, StatusQueue
from personal_finance_etl.domain.market.fx import FXRateProvider
from personal_finance_etl.domain.market.macro import FYMacroParametersTable


@dataclass
class RunContext:
    """Holds shared state (loaded data, FY table, config) for the execution run."""

    df_p: pl.DataFrame
    df_s: pl.DataFrame
    df_m: pl.DataFrame
    isin_master: dict[str, dict[str, Any]]
    df_b: pl.DataFrame | None
    fy_table: FYMacroParametersTable
    start_date: date | None
    end_date: date | None
    rules: FinancialRules
    df_fx: pl.DataFrame | None = None
    run_id: str = "UNKNOWN"

    def __post_init__(self) -> None:
        default_curr = getattr(self.rules, "DEFAULT_CURRENCY_ID", "INR_INR")
        self.fx_provider = FXRateProvider(self.df_fx, default_curr)

    @classmethod
    def load(
        cls,
        p_path: str,
        s_path: str,
        m_path: str,
        i_path: str,
        b_path: str,
        t_path: str,
        rules: FinancialRules,
        fx_path: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> "RunContext":
        df_p, df_s, df_m, isin_master, df_b, df_fx = TaxDataLoader.load_all(
            p_path, s_path, m_path, i_path, b_path, fx_path=fx_path
        )
        try:
            df_t = pl.read_csv(t_path)
            fy_table = FYMacroParametersTable(df_t, rules=rules)
        except Exception as e:
            raise Exception(f"Failed to load mandatory Macro Parameters CSV: {e}") from e

        return cls(
            df_p=df_p,
            df_s=df_s,
            df_m=df_m,
            isin_master=isin_master,
            df_b=df_b,
            fy_table=fy_table,
            start_date=start_date,
            end_date=end_date,
            rules=rules,
            df_fx=df_fx,
        )

    @classmethod
    def from_dataframes(
        cls,
        df_p: pl.DataFrame,
        df_s: pl.DataFrame,
        df_m: pl.DataFrame,
        df_i: pl.DataFrame,
        df_b: pl.DataFrame,
        df_t: pl.DataFrame,
        rules: FinancialRules,
        df_fx: pl.DataFrame | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        run_id: str = "UNKNOWN",
    ) -> "RunContext":
        loaded_p, loaded_s, loaded_m, is_m, loaded_b, loaded_fx = (
            TaxDataLoader.load_from_dataframes(
                df_p, df_s, df_m, df_i, df_b, df_fx=df_fx
            )
        )
        fy_table = FYMacroParametersTable(df_t, rules=rules)

        return cls(
            df_p=loaded_p,
            df_s=loaded_s,
            df_m=loaded_m,
            isin_master=is_m,
            df_b=loaded_b,
            fy_table=fy_table,
            start_date=start_date,
            end_date=end_date,
            rules=rules,
            df_fx=loaded_fx,
            run_id=run_id,
        )


class AnalyticsContextManager:
    """Manages the initialization of the quantitative analytics engine context."""

    def __init__(self, status_queue: StatusQueue | Any | None = None):
        self.status_queue = status_queue

    def _report(self, msg: str, progress: float, level: LogLevel = LogLevel.INFO) -> None:
        if self.status_queue:
            self.status_queue.put(
                EngineStatusMessage(msg=msg, progress=progress, level=level)
            )

    def initialize(
        self,
        df_p: pl.DataFrame,
        df_s: pl.DataFrame,
        df_m: pl.DataFrame,
        df_i: pl.DataFrame,
        df_b: pl.DataFrame,
        df_t: pl.DataFrame,
        df_fx: pl.DataFrame,
        start_date: date | None,
        end_date: date | None,
        rules: FinancialRules | None,
        run_id: str = "UNKNOWN",
    ) -> tuple[RunContext, list[str]]:
        self._report("Loading DataFrame memory structures...", 0.01, LogLevel.STEP)

        if rules is None:
            raise ValueError("Financial rules must be provided")

        ctx = RunContext.from_dataframes(
            df_p,
            df_s,
            df_m,
            df_i,
            df_b,
            df_t,
            rules,
            df_fx,
            start_date,
            end_date,
            run_id=run_id,
        )

        self._report("Data loaded into Context successfully.", 0.05, LogLevel.INFO)

        isins_p = (
            [str(x) for x in ctx.df_p["ISIN"].unique().to_list()]
            if "ISIN" in ctx.df_p.columns
            else []
        )
        isins_s = (
            [str(x) for x in ctx.df_s["ISIN"].unique().to_list()]
            if "ISIN" in ctx.df_s.columns
            else []
        )
        isins_m = (
            [str(x) for x in ctx.df_m["ISIN"].unique().to_list()]
            if "ISIN" in ctx.df_m.columns
            else []
        )
        isins = sorted(set(isins_p + isins_s + isins_m))

        return ctx, isins


__all__ = [
    "AnalyticsContextManager",
    "RunContext",
]
