"""Tax policy models and Indian statutory assumption configurations.

Owns
----
- Statutory tax rates across equity, foreign equity, debt, and gold (LTCG / STCG).
- Sub-head and head classification for taxable, non-taxable, and exempt income.
- Mutual exclusivity validation across tax heads, sub-heads, and tax credit categories.
- Investment exclusion configurations for capital gains processing.

Does not own
-------------
- Macroeconomic and FIRE forecasting assumptions (owned by config.financial_rules.fire).
- Investment instruments categorization (owned by config.financial_rules.investments).
- Tax engine computation or lot-matching logic (owned by domain.tax).
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

TaxabilityType = Literal["taxable", "non_taxable", "review"]
TaxMethodType = Literal["ordinary_rate", "capital_gains", "exempt", "review"]


class TaxRates(BaseModel):
    equity_ltcg: float = Field(
        0.125, description="LTCG tax rate for listed Indian equity (Section 112A)."
    )
    equity_stcg: float = Field(
        0.20, description="STCG tax rate for listed Indian equity (Section 111A)."
    )
    # Foreign listed equity (US stocks via LRS) — post-Budget 2024:
    #   LTCG (> 24 months): 12.5% concessional rate (same as Default_LTCG).
    #   STCG (≤ 24 months): investor's income-tax slab rate (same as Default_STCG).
    foreign_equity_ltcg: float = Field(
        0.125,
        description="LTCG tax rate for foreign listed equity (US stocks via LRS) — 12.5% post-Budget 2024.",
    )
    foreign_equity_stcg: float = Field(
        0.30, description="STCG tax rate for foreign listed equity (US stocks via LRS) — slab rate."
    )
    debt_ltcg: float = Field(0.20, description="LTCG tax rate for debt.")
    debt_stcg: float = Field(0.30, description="STCG tax rate for debt.")
    gold_ltcg: float = Field(0.20, description="LTCG tax rate for gold.")
    gold_stcg: float = Field(0.30, description="STCG tax rate for gold.")


class TaxSubHeadConfig(BaseModel):
    tax_head_display_name: str
    sub_head_display_name: str
    cat_ids: list[str] = Field(default_factory=list)
    sub_cat_ids: list[str] = Field(default_factory=list)
    tax_credit_sub_cat_ids: list[str] = Field(default_factory=list)
    taxability: TaxabilityType = "review"
    tax_method: TaxMethodType = "review"

    @model_validator(mode="after")
    def validate_tax_credit_ids(self) -> Self:
        income_ids = set(self.sub_cat_ids)
        credit_ids = set(self.tax_credit_sub_cat_ids)
        if len(income_ids) != len(self.sub_cat_ids):
            raise ValueError("Duplicate sub_cat_ids configured for a tax sub-head.")
        if len(credit_ids) != len(self.tax_credit_sub_cat_ids):
            raise ValueError("Duplicate tax_credit_sub_cat_ids configured for a tax sub-head.")
        overlap = income_ids.intersection(credit_ids)
        if overlap:
            raise ValueError(
                "A subcategory UID cannot be configured as both income and tax credit: "
                f"{sorted(overlap)}"
            )
        return self


class TaxHeadConfig(BaseModel):
    sub_heads: dict[str, TaxSubHeadConfig] = Field(default_factory=dict)


class InvestmentExclusionsConfig(BaseModel):
    stcg_sub_cat_ids: list[str] = Field(default_factory=list)
    ltcg_sub_cat_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_exclusions(self) -> Self:
        for field_name, values in (
            ("stcg_sub_cat_ids", self.stcg_sub_cat_ids),
            ("ltcg_sub_cat_ids", self.ltcg_sub_cat_ids),
        ):
            if any(not uid or not uid.strip() for uid in values):
                raise ValueError(f"{field_name} cannot contain blank UIDs.")
            if any(uid != uid.strip() for uid in values):
                raise ValueError(f"{field_name} cannot contain UIDs with surrounding whitespace.")
            if len(set(values)) != len(values):
                raise ValueError(f"Duplicate UIDs found in {field_name}.")

        stcg = set(self.stcg_sub_cat_ids)
        ltcg = set(self.ltcg_sub_cat_ids)
        overlap = stcg.intersection(ltcg)
        if overlap:
            raise ValueError(
                f"Overlapping sub_cat_ids between STCG and LTCG exclusions: {sorted(overlap)}"
            )
        return self


class TaxAssumptions(BaseModel):
    debt_mf_cutoff_date: str = Field(
        ..., description="Date before which debt mutual funds have indexation benefits."
    )
    harvest_wait_days_threshold: int = Field(
        ...,
        description="Minimum days to wait before re-buying a harvested instrument to avoid wash-sale rules.",
    )
    ltcg_threshold_months: dict[str, int] = Field(
        ...,
        description="Holding period thresholds in calendar months for Long Term Capital Gains across asset classes.",
    )
    fallback_equity_ltcg_exemption: float = Field(
        ..., description="Annual tax-free exemption limit for equity Long Term Capital Gains."
    )
    rates: TaxRates = Field(
        default_factory=lambda: TaxRates(
            equity_ltcg=0.125,
            equity_stcg=0.20,
            foreign_equity_ltcg=0.125,
            foreign_equity_stcg=0.30,
            debt_ltcg=0.20,
            debt_stcg=0.30,
            gold_ltcg=0.20,
            gold_stcg=0.30,
        )
    )
    heads_of_income: dict[str, TaxHeadConfig] = Field(default_factory=dict)
    residual_income: dict[str, TaxHeadConfig] = Field(default_factory=dict)
    exempt_income: dict[str, TaxHeadConfig] = Field(default_factory=dict)
    investment_exclusions: InvestmentExclusionsConfig = Field(
        default_factory=InvestmentExclusionsConfig
    )

    @model_validator(mode="after")
    def validate_mutual_exclusivity(self) -> Self:
        seen_sub_cats: dict[str, str] = {}
        seen_credit_sub_cats: dict[str, str] = {}
        seen_cats: dict[str, str] = {}
        seen_head_subhead: set[tuple[str, str]] = set()

        # Combine all heads for global mutual exclusivity check
        all_heads: list[tuple[str, TaxHeadConfig]] = []
        all_heads.extend(self.heads_of_income.items())
        all_heads.extend(self.exempt_income.items())
        all_heads.extend(self.residual_income.items())

        for head_name, head_config in all_heads:
            for sub_name, sub_config in head_config.sub_heads.items():
                head_sub_key = (head_name.strip().lower(), sub_name.strip().lower())
                if head_sub_key in seen_head_subhead:
                    raise ValueError(
                        f"Duplicate sub-head declaration '{sub_name}' found under head '{head_name}'."
                    )
                seen_head_subhead.add(head_sub_key)

                for sub_cat in sub_config.sub_cat_ids:
                    if sub_cat in seen_sub_cats:
                        raise ValueError(
                            f"Duplicate sub_cat_id {sub_cat} found in {head_name}.{sub_name} "
                            f"(already configured in {seen_sub_cats[sub_cat]})"
                        )
                    if sub_cat in seen_credit_sub_cats:
                        raise ValueError(
                            f"Subcategory UID {sub_cat} in {head_name}.{sub_name} is configured as both income and tax credit "
                            f"(already in tax credit {seen_credit_sub_cats[sub_cat]})."
                        )
                    seen_sub_cats[sub_cat] = f"{head_name}.{sub_name}"

                for credit_sub_cat in sub_config.tax_credit_sub_cat_ids:
                    if credit_sub_cat in seen_credit_sub_cats:
                        raise ValueError(
                            f"Duplicate tax_credit_sub_cat_id {credit_sub_cat} found in {head_name}.{sub_name} "
                            f"(already configured in {seen_credit_sub_cats[credit_sub_cat]})"
                        )
                    if credit_sub_cat in seen_sub_cats:
                        raise ValueError(
                            f"Subcategory UID {credit_sub_cat} in {head_name}.{sub_name} is configured as both income and tax credit "
                            f"(already in income {seen_sub_cats[credit_sub_cat]})."
                        )
                    seen_credit_sub_cats[credit_sub_cat] = f"{head_name}.{sub_name}"

                for cat in sub_config.cat_ids:
                    if cat in seen_cats:
                        raise ValueError(
                            f"Duplicate cat_id {cat} found in {head_name}.{sub_name} "
                            f"(already configured in {seen_cats[cat]})"
                        )
                    seen_cats[cat] = f"{head_name}.{sub_name}"

        # Ensure investment exclusions do not clash with ordinary income heads or tax credits
        for exclusion_type, exclusion_uids in (
            ("stcg", self.investment_exclusions.stcg_sub_cat_ids),
            ("ltcg", self.investment_exclusions.ltcg_sub_cat_ids),
        ):
            for uid in exclusion_uids:
                if uid in seen_sub_cats:
                    raise ValueError(
                        f"Subcategory UID {uid} in investment_exclusions.{exclusion_type} is already "
                        f"configured in {seen_sub_cats[uid]}."
                    )
                if uid in seen_credit_sub_cats:
                    raise ValueError(
                        f"Subcategory UID {uid} in investment_exclusions.{exclusion_type} is configured "
                        f"as a tax credit in {seen_credit_sub_cats[uid]}."
                    )
                seen_sub_cats[uid] = f"investment_exclusions.{exclusion_type}"

        return self
