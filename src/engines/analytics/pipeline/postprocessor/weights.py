import polars as pl

class PortfolioWeightsCalculator:
    """Calculates Portfolio Weights."""
    @staticmethod
    def calculate(lazy_df: pl.LazyFrame) -> pl.LazyFrame:
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
        return lazy_df
