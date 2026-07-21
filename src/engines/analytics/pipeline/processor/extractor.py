import polars as pl

from src.engines.analytics.pipeline.context import RunContext


class IsinDataExtractor:
    @staticmethod
    def extract(ctx: RunContext, isin: str):
        p_inst = ctx.df_p.filter(pl.col("ISIN") == isin).sort("Date").to_dicts()
        s_inst = ctx.df_s.filter(pl.col("ISIN") == isin).sort("Date").to_dicts()

        m_inst = (
            ctx.df_m.filter(pl.col("ISIN") == isin)
            .sort("Date")
            .group_by("Date", maintain_order=True)
            .agg(
                [
                    pl.col("Quantity").sum().alias("Quantity"),
                    pl.col("Closing Price").last().alias("Closing Price"),
                    pl.col("Buy Value").sum().alias("Buy Value"),
                ]
            )
            .to_dicts()
        )
        master_row = ctx.isin_master.get(isin, {})
        return p_inst, s_inst, m_inst, master_row
