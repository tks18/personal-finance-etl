"""
Pipeline Context.
Holds shared state (loaded data, FY table, config) for the execution run.
"""

from dataclasses import dataclass
from datetime import date
import polars as pl

from src.engines.rules.tax import FYTaxRateTable
from src.engines.io.loader import TaxDataLoader


@dataclass
class RunContext:
    df_p: pl.DataFrame
    df_s: pl.DataFrame
    df_m: pl.DataFrame
    isin_master: dict
    df_b: pl.DataFrame | None
    fy_table: FYTaxRateTable
    start_date: date | None
    end_date: date | None

    @classmethod
    def load(
        cls,
        p_path: str,
        s_path: str,
        m_path: str,
        i_path: str,
        b_path: str,
        t_path: str,
        start_date: date | None = None,
        end_date: date | None = None
    ) -> "RunContext":
        df_p, df_s, df_m, isin_master, df_b = TaxDataLoader.load_all(
            p_path, s_path, m_path, i_path, b_path
        )
        try:
            df_t = pl.read_csv(t_path)
            fy_table = FYTaxRateTable(df_t)
        except Exception as e:
            raise Exception(f"Failed to load mandatory Tax Rates CSV: {e}")

        return cls(
            df_p=df_p,
            df_s=df_s,
            df_m=df_m,
            isin_master=isin_master,
            df_b=df_b,
            fy_table=fy_table,
            start_date=start_date,
            end_date=end_date
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
        start_date: date | None = None,
        end_date: date | None = None
    ) -> "RunContext":
        df_p, df_s, df_m, isin_master, df_b = TaxDataLoader.load_from_dataframes(
            df_p, df_s, df_m, df_i, df_b
        )
        fy_table = FYTaxRateTable(df_t)

        return cls(
            df_p=df_p,
            df_s=df_s,
            df_m=df_m,
            isin_master=isin_master,
            df_b=df_b,
            fy_table=fy_table,
            start_date=start_date,
            end_date=end_date
        )
