import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules


class LiabilityCalculator:
    """Computes final FY-level tax liability using rates sourced from base tax events.

    Rate resolution strategy
    ------------------------
    ``lf_tax_events`` (output of ``BaseEventsBuilder``) already carries a correct
    per-event ``Applied_Rate`` resolved at disposal time:

    * **INVESTMENT_REALIZED** events → rate from ``FYMacroParametersTable.get_tax_rates()``
      (macro CSV, same source as ``snapshot.py``).
    * **LEDGER** events → ``Estimated_Ordinary_Income_Tax_Rate`` from macro CSV, or
      ``fallback_ordinary_income_rate`` from ``FinancialRules`` TOML.

    We compute a **taxable-amount-weighted average** ``Applied_Rate`` per
    ``FY × Gain_Type × Tax_Method`` from those per-event rates, then apply it to
    ``Net_Taxable_Income`` from ``lf_set_offs`` (which reflects post-netting income
    after capital-loss set-offs).  This keeps tax rates asset-class-aware even after
    the set-off processor has collapsed events to FY × Gain_Type aggregates.

    LTCG exemption
    --------------
    The Section 112A equity LTCG exemption is applied before computing ``Gross_Tax``
    using ``rules.assumptions.tax.fallback_equity_ltcg_exemption`` as the threshold.
    """

    def __init__(
        self,
        lf_tax_events: pl.LazyFrame,
        lf_set_offs: pl.LazyFrame,
        rules: FinancialRules | None,
    ):
        self.lf_tax_events = lf_tax_events
        self.lf_set_offs = lf_set_offs
        self.rules = rules

    def calculate(self) -> pl.LazyFrame:
        """Calculate final tax liability and return a per-FY × Gain_Type LazyFrame."""
        schema = {
            "FY": pl.Utf8,
            "Income_Head": pl.Utf8,
            "Tax_Method": pl.Utf8,
            "Gain_Type": pl.Utf8,
            "Net_Taxable_Income": pl.Float64,
            "Applied_Rate": pl.Float64,
            "Gross_Tax": pl.Float64,
            "Cess_Amount": pl.Float64,
            "Net_Tax": pl.Float64,
        }

        if not self.rules:
            return pl.LazyFrame(schema=schema)

        ltcg_exemption = self.rules.assumptions.tax.fallback_equity_ltcg_exemption

        # Weighted Applied_Rate per FY × Gain_Type (larger gains drive the rate)
        lf_weighted_rates = (
            self.lf_tax_events.filter(
                (pl.col("Tax_Sub_Head") != "CHECK_REQUIRED")
                & pl.col("Applied_Rate").is_not_null()
                & (pl.col("Taxable_Amount").abs() > 0)
            )
            .group_by(["FY", "Gain_Type", "Tax_Method", "Income_Head"])
            .agg(
                [
                    (
                        (pl.col("Taxable_Amount").abs() * pl.col("Applied_Rate")).sum()
                        / pl.col("Taxable_Amount").abs().sum()
                    ).alias("Applied_Rate"),
                ]
            )
        )

        # Post-netting Net_Taxable_Income from set-off processor
        lf_net_income = self.lf_set_offs.select(
            [
                "FY",
                "Income_Head",
                "Tax_Method",
                "Gain_Type",
                "Net_Taxable_Income",
            ]
        ).filter(pl.col("Net_Taxable_Income") > 0)

        # Join rate onto post-set-off income
        lf_joined = lf_net_income.join(
            lf_weighted_rates,
            on=["FY", "Income_Head", "Tax_Method", "Gain_Type"],
            how="left",
        )

        # Apply LTCG exemption and compute Gross_Tax → Cess → Net_Tax
        lf_liability = lf_joined.with_columns(
            # Deduct LTCG exemption before computing tax (Section 112A threshold)
            pl.when(
                (pl.col("Tax_Method") == "capital_gains") & (pl.col("Gain_Type") == "LT")
            )
            .then(
                pl.max_horizontal(
                    pl.lit(0.0),
                    pl.col("Net_Taxable_Income") - pl.lit(ltcg_exemption),
                )
            )
            .otherwise(pl.col("Net_Taxable_Income"))
            .alias("Taxable_After_Exemption")
        ).with_columns(
            (pl.col("Taxable_After_Exemption") * pl.col("Applied_Rate").fill_null(0.0)).alias(
                "Gross_Tax"
            )
        ).with_columns(
            (pl.col("Gross_Tax") * pl.lit(0.04)).alias("Cess_Amount"),  # 4% Health & Education Cess
            (pl.col("Gross_Tax") * pl.lit(1.04)).alias("Net_Tax"),
        ).drop("Taxable_After_Exemption")

        return lf_liability.select(list(schema.keys()))
