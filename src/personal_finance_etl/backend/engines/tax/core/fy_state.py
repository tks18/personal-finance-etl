import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.engines.tax.utils.date_utils import add_fy_if_missing


class FYStateBuilder:
    """Builds the final silver.f_Tax_FY_State table."""

    def __init__(
        self,
        lf_events: pl.LazyFrame,
        lf_set_offs: pl.LazyFrame,
        lf_liability: pl.LazyFrame,
        df_income: pl.DataFrame,
        df_subcategory: pl.DataFrame,
        rules: FinancialRules | None = None,
    ):
        self.lf_events = lf_events
        self.lf_set_offs = lf_set_offs
        self.lf_liability = lf_liability
        self.df_income = df_income
        self.df_subcategory = df_subcategory
        self.rules = rules

    def _step_base_aggregations(self) -> pl.LazyFrame:
        """Group raw tax events by FY and aggregate income, gains, losses, and check-required counts."""
        # 1. Base Aggregations from df_events
        return self.lf_events.group_by("FY").agg(
            [
                pl.col("Gross_Amount").sum().alias("Event_Gross"),
                pl.when(pl.col("Tax_Method") == "ordinary_rate")
                .then(pl.col("Taxable_Amount"))
                .otherwise(0.0)
                .sum()
                .alias("Ordinary_Taxable_Income"),
                pl.when(
                    (pl.col("Tax_Method") == "capital_gains")
                    & (pl.col("Gain_Type") == "ST")
                    & (pl.col("Realized_Gain_Loss") > 0)
                )
                .then(pl.col("Realized_Gain_Loss"))
                .otherwise(0.0)
                .sum()
                .alias("STCG"),
                pl.when(
                    (pl.col("Tax_Method") == "capital_gains")
                    & (pl.col("Gain_Type") == "LT")
                    & (pl.col("Realized_Gain_Loss") > 0)
                )
                .then(pl.col("Realized_Gain_Loss"))
                .otherwise(0.0)
                .sum()
                .alias("LTCG"),
                pl.when(
                    (pl.col("Tax_Method") == "capital_gains")
                    & (pl.col("Gain_Type") == "ST")
                    & (pl.col("Realized_Gain_Loss") < 0)
                )
                .then(pl.col("Realized_Gain_Loss"))
                .otherwise(0.0)
                .sum()
                .alias("STCL"),
                pl.when(
                    (pl.col("Tax_Method") == "capital_gains")
                    & (pl.col("Gain_Type") == "LT")
                    & (pl.col("Realized_Gain_Loss") < 0)
                )
                .then(pl.col("Realized_Gain_Loss"))
                .otherwise(0.0)
                .sum()
                .alias("LTCL"),
                pl.when(pl.col("Tax_Status") == "CHECK_REQUIRED")
                .then(1)
                .otherwise(0)
                .sum()
                .alias("Check_Required_Count"),
            ]
        )

    def _step_excluded_income(self, df_base: pl.LazyFrame) -> pl.LazyFrame:
        """Join non-taxable ledger income per FY and derive Gross_Income and Tax_Relevant_Income."""
        # 2. Excluded Non-Taxable
        df_ledger = self.df_income.lazy().join(
            self.df_subcategory.lazy().select(["UID", "Taxability"]),
            left_on="CATEGORY_ID",
            right_on="UID",
            how="left",
        )
        df_ledger = add_fy_if_missing(df_ledger, "DATE")

        df_excluded = (
            df_ledger.filter(pl.col("Taxability") == "non_taxable")
            .group_by("FY")
            .agg(pl.col("BASE_AMOUNT").sum().alias("Excluded_Non_Taxable_Income"))
        )

        df_base = df_base.join(df_excluded, on="FY", how="left").fill_null(0.0)
        df_base = df_base.with_columns(
            (pl.col("Event_Gross") + pl.col("Excluded_Non_Taxable_Income")).alias("Gross_Income")
        ).with_columns(
            (pl.col("Gross_Income") - pl.col("Excluded_Non_Taxable_Income")).alias(
                "Tax_Relevant_Income"
            )
        )
        return df_base

    def _step_liability_and_setoffs(self, df_base: pl.LazyFrame) -> pl.LazyFrame:
        """Join estimated tax liability and ST/LT capital-loss set-off data onto df_base."""
        # 3. Liability / Set-offs
        df_liab = self.lf_liability.group_by("FY").agg(
            [
                pl.when(pl.col("Tax_Method") == "ordinary_rate")
                .then(pl.col("Net_Tax"))
                .otherwise(0.0)
                .sum()
                .alias("Estimated_Ordinary_Tax"),
                pl.when(pl.col("Tax_Method") == "capital_gains")
                .then(pl.col("Net_Tax"))
                .otherwise(0.0)
                .sum()
                .alias("Estimated_Capital_Gains_Tax"),
                pl.col("Net_Tax").sum().alias("Estimated_Gross_Tax"),
            ]
        )
        df_base = df_base.join(df_liab, on="FY", how="left").fill_null(0.0)

        df_so_st = (
            self.lf_set_offs.filter(
                (pl.col("Tax_Method") == "capital_gains") & (pl.col("Gain_Type") == "ST")
            )
            .group_by("FY")
            .agg(
                [
                    pl.col("Set_Off_Amount").sum().alias("ST_Set_Off"),
                    pl.col("Carried_Forward_Loss").abs().sum().alias("Closing_STCL"),
                    pl.col("Net_Taxable_Income").sum().alias("Net_Taxable_STCG"),
                    pl.col("STCL_Used_Against_STCG").sum().alias("STCL_Used_Against_STCG"),
                    pl.col("STCL_Used_Against_LTCG").sum().alias("STCL_Used_Against_LTCG"),
                    pl.col("Brought_Forward_STCL").sum().alias("Brought_Forward_STCL"),
                ]
            )
        )
        df_so_lt = (
            self.lf_set_offs.filter(
                (pl.col("Tax_Method") == "capital_gains") & (pl.col("Gain_Type") == "LT")
            )
            .group_by("FY")
            .agg(
                [
                    pl.col("Set_Off_Amount").sum().alias("LT_Set_Off"),
                    pl.col("Carried_Forward_Loss").abs().sum().alias("Closing_LTCL"),
                    pl.col("Net_Taxable_Income").sum().alias("Net_Taxable_LTCG"),
                    pl.col("LTCL_Used_Against_LTCG").sum().alias("LTCL_Used_Against_LTCG"),
                    pl.col("Brought_Forward_LTCL").sum().alias("Brought_Forward_LTCL"),
                ]
            )
        )

        df_base = (
            df_base.join(df_so_st, on="FY", how="left")
            .join(df_so_lt, on="FY", how="left")
            .fill_null(0.0)
        )

        df_base = df_base.with_columns(
            [
                # Brought_Forward values now come from set-off data (populated by LossSetOffProcessor)
                pl.col("Brought_Forward_STCL").fill_null(0.0),
                pl.col("Brought_Forward_LTCL").fill_null(0.0),
                # Granular set-off breakdown (Step 1 + Step 2 + BF)
                pl.col("STCL_Used_Against_STCG").fill_null(0.0),
                pl.col("STCL_Used_Against_LTCG").fill_null(0.0),
                pl.col("LTCL_Used_Against_LTCG").fill_null(0.0),
            ]
        )
        return df_base

    def _step_tax_credits(self, df_base: pl.LazyFrame) -> pl.LazyFrame:
        """Aggregate observed TDS/advance-tax credits and compute Estimated_Net_Tax_Position."""
        # 4. Observed_Tax_Credits — aggregate TDS / advance-tax income entries per FY.
        # tax_credit_sub_cat_ids in each TaxSubHeadConfig identifies sub-categories whose
        # BASE_AMOUNT represents tax already paid (TDS deducted, advance-tax instalments).
        # Sign is normalized with .abs() because credits are often recorded as negatives.
        credit_sub_cat_ids: list[str] = []
        if self.rules:
            all_heads = list(self.rules.assumptions.tax.heads_of_income.items())
            all_heads.append(("Residual", self.rules.assumptions.tax.residual_income))
            all_heads.append(("Exempt_Income", self.rules.assumptions.tax.exempt_income))
            for _head_name, head_config in all_heads:
                for _sub_name, sub_config in head_config.sub_heads.items():
                    credit_sub_cat_ids.extend(sub_config.tax_credit_sub_cat_ids)

        if credit_sub_cat_ids:
            lf_income_with_fy = add_fy_if_missing(self.df_income.lazy(), "DATE")
            df_credits_agg = (
                lf_income_with_fy.filter(pl.col("CATEGORY_ID").is_in(credit_sub_cat_ids))
                .group_by("FY")
                .agg(pl.col("BASE_AMOUNT").sum().abs().alias("Observed_Tax_Credits"))
            )
            df_base = (
                df_base.join(df_credits_agg, on="FY", how="left")
                .with_columns(pl.col("Observed_Tax_Credits").fill_null(0.0))
            )
        else:
            df_base = df_base.with_columns(pl.lit(0.0).alias("Observed_Tax_Credits"))

        df_base = df_base.with_columns(
            (pl.col("Estimated_Gross_Tax") - pl.col("Observed_Tax_Credits")).alias(
                "Estimated_Net_Tax_Position"
            )
        )
        return df_base

    def build(self) -> pl.LazyFrame:
        """Build the f_Tax_FY_State silver table.

        Orchestrates four sequential steps:
        1. Base aggregations from raw tax events.
        2. Excluded non-taxable income join.
        3. Liability and capital-loss set-off joins.
        4. Tax credit aggregation and net position.
        """
        df_base = self._step_base_aggregations()
        df_base = self._step_excluded_income(df_base)
        df_base = self._step_liability_and_setoffs(df_base)
        df_base = self._step_tax_credits(df_base)

        schema_cols = [
            "FY",
            "Gross_Income",
            "Excluded_Non_Taxable_Income",
            "Tax_Relevant_Income",
            "Ordinary_Taxable_Income",
            "STCG",
            "LTCG",
            "STCL",
            "LTCL",
            "Brought_Forward_STCL",
            "Brought_Forward_LTCL",
            "STCL_Used_Against_STCG",
            "STCL_Used_Against_LTCG",
            "LTCL_Used_Against_LTCG",
            "Closing_STCL",
            "Closing_LTCL",
            "Net_Taxable_STCG",
            "Net_Taxable_LTCG",
            "Estimated_Ordinary_Tax",
            "Estimated_Capital_Gains_Tax",
            "Estimated_Gross_Tax",
            "Observed_Tax_Credits",
            "Estimated_Net_Tax_Position",
            "Check_Required_Count",
        ]

        return df_base.select(schema_cols)
