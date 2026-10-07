"""
Pipeline Context.
Holds shared state (loaded data, FY table, config) for the execution run.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.engines.analytics.io.loader import TaxDataLoader
from personal_finance_etl.backend.engines.analytics.rules.macro import FYMacroParametersTable


class FXRateProvider:
    def __init__(self, df_fx: pl.DataFrame | None):
        self.fx_map: dict[tuple[date, str], float] = {}
        if df_fx is not None and not df_fx.is_empty():
            # Fast O(1) dictionary
            df_fx = df_fx.sort(["Date"])
            for row in df_fx.to_dicts():
                d = row["Date"]
                if isinstance(d, str):
                    d = date.fromisoformat(d)
                self.fx_map[(d, row["Currency_ID"])] = float(row["FX_Rate"])

    def get_rate(self, d: date, currency_id: str) -> float:
        if currency_id == "INR_INR" or not currency_id:
            return 1.0

        rate = self.fx_map.get((d, currency_id))
        if rate is not None:
            return rate

        # Fallback to latest available rate
        # Search backwards up to 30 days
        for i in range(1, 31):
            fallback_date = d - timedelta(days=i)
            rate = self.fx_map.get((fallback_date, currency_id))
            if rate is not None:
                return rate

        return 1.0


@dataclass
class RunContext:
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

    def __post_init__(self):
        self.fx_provider = FXRateProvider(self.df_fx)

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
    ) -> "RunContext":
        loaded_p, loaded_s, loaded_m, is_m, loaded_b, loaded_fx = (
            TaxDataLoader.load_from_dataframes(df_p, df_s, df_m, df_i, df_b, df_fx=df_fx)
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
        )
