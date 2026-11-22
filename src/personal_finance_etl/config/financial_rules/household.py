"""Household financial policy models.

Owns
----
- Income classification rules (active, dividends, interest, non-cash).
- Core and non-core expense classification rules.
- Budget allocation targets, smoothing parameters, and overspend alerts.
- Asset liquidity and cashflow conduit classifications.

Does not own
-------------
- Portfolio investment policies (owned by config.financial_rules.investments).
- Tax statutory rates and rules (owned by config.financial_rules.tax).
"""

from pydantic import BaseModel, Field


class ActiveIncomeRules(BaseModel):
    """Category and subcategory identifiers for active/earned employment income."""

    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class DividendIncomeRules(BaseModel):
    """Category and subcategory identifiers for equity and mutual fund dividend income."""

    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class InterestIncomeRules(BaseModel):
    """Category and subcategory identifiers for fixed deposit and savings interest income."""

    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class NonCashIncomeRules(BaseModel):
    """Category and subcategory identifiers for non-cash accruals and perks."""

    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class IncomeRules(BaseModel):
    """Container grouping household income classification rules."""

    active: ActiveIncomeRules = Field(default_factory=ActiveIncomeRules)
    dividends: DividendIncomeRules = Field(default_factory=DividendIncomeRules)
    interest: InterestIncomeRules = Field(default_factory=InterestIncomeRules)
    non_cash: NonCashIncomeRules = Field(default_factory=NonCashIncomeRules)


class CoreExpenseRules(BaseModel):
    """Category and subcategory identifiers for essential, nondiscretionary living expenses."""

    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class ExpenseRules(BaseModel):
    """Container grouping household expense classification rules."""

    core: CoreExpenseRules = Field(default_factory=CoreExpenseRules)


class IncomeAllocationRules(BaseModel):
    """Budget target percentages for core expenses, non-core expenses, and investments."""

    core_expense_pct: float = Field(
        default=0.40,
        description="Max % of smoothed income allocated to core/fixed expenses (40% default).",
    )
    non_core_expense_pct: float = Field(
        default=0.20,
        description="Max % of smoothed income allocated to non-core/discretionary expenses (20% default).",
    )
    investment_pct: float = Field(
        default=0.30,
        description="Minimum % of smoothed income to invest/save via net transfers (30% default).",
    )


class BudgetAlerts(BaseModel):
    """Overspend warning thresholds and emergency fund target months."""

    overspend_alert_threshold: float = Field(
        default=0.05,
        description="Fractional overage above budget target that triggers Is_Overspent flags (5% default).",
    )
    emergency_fund_target_months: int = Field(
        default=6,
        description="Target number of months of core expenses to hold as emergency fund.",
    )


class BudgetSmoothing(BaseModel):
    """Trailing window configuration for recency-weighted income smoothing."""

    income_smoothing_months: int = Field(
        default=3,
        description="Number of trailing months used for recency-weighted income smoothing.",
    )


class BudgetRules(BaseModel):
    """Container grouping household budget allocation, alerts, and smoothing rules."""

    income_allocation: IncomeAllocationRules = Field(default_factory=IncomeAllocationRules)
    alerts: BudgetAlerts = Field(default_factory=BudgetAlerts)
    smoothing: BudgetSmoothing = Field(default_factory=BudgetSmoothing)


class IlliquidAssetRules(BaseModel):
    """Category identifiers for illiquid physical and real assets."""

    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class CashflowAssetRules(BaseModel):
    """Classification rules mapping accounts to cashflow statement activities."""

    cash_pools: list[str] = Field(default_factory=list)
    non_cash_pnl_sources: list[str] = Field(default_factory=list)
    working_capital_conduits: list[str] = Field(default_factory=list)
    investing_activities: list[str] = Field(default_factory=list)
    financing_liabilities: list[str] = Field(default_factory=list)


class DigitalAssetRules(BaseModel):
    """Category identifiers for digital and cryptocurrency assets."""

    category_ids: list[str] = Field(default_factory=list)


class AssetRules(BaseModel):
    """Container grouping household asset classification and cashflow conduit rules."""

    illiquid: IlliquidAssetRules = Field(default_factory=IlliquidAssetRules)
    cashflow: CashflowAssetRules = Field(default_factory=CashflowAssetRules)
    digital: DigitalAssetRules = Field(default_factory=DigitalAssetRules)
