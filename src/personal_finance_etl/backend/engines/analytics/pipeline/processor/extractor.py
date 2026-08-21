from typing import Any

import polars as pl

from personal_finance_etl.backend.engines.analytics.pipeline.context import RunContext


class IsinDataExtractor:
    @staticmethod
    def extract(
        ctx: RunContext, isin: str
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        p_inst = ctx.df_p.filter(pl.col("ISIN") == isin).sort("Date").to_dicts()
        s_inst = ctx.df_s.filter(pl.col("ISIN") == isin).sort("Date").to_dicts()

        m_inst = (
            ctx.df_m.filter(pl.col("ISIN") == isin)
            .sort("Date")
            .group_by("Date", maintain_order=True)
            .agg(
                [
                    pl.col("Quantity").sum().alias("Quantity"),
                    pl.col("Closing_Price").last().alias("Closing_Price"),
                    pl.col("Buy_Value").sum().alias("Buy_Value"),
                ]
            )
            .to_dicts()
        )
        master_row = ctx.isin_master.get(isin, {})
        return p_inst, s_inst, m_inst, master_row
