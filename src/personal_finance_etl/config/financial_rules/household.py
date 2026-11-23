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


class IncomeGroupingRules(BaseModel):
    """Configurable thresholds and patterns for dynamic income subcategory grouping."""

    salary_category_name: str = Field(
        default="Salary",
        description="Category name identifying primary salary income for allowance grouping.",
    )
    allowance_name_pattern: str = Field(
        default="allowance",
        description="Case-insensitive substring pattern identifying allowance subcategories.",
    )
    allowance_group_name: str = Field(
        default="Allowances",
        description="Category group display name assigned to matched allowance subcategories.",
    )
    active_group_threshold: float = Field(
        default=0.50,
        ge=0.0,
        le=1.0,
        description="Top cumulative proportion assigned to distinct subcategory.",
    )
    min_tail_frequency: int = Field(
        default=3,
        ge=1,
        description="Minimum frequency below which low-frequency items group to Other.",
    )


class IncomeRules(BaseModel):
    """Container grouping household income classification rules."""

    active: ActiveIncomeRules = Field(default_factory=ActiveIncomeRules)
    dividends: DividendIncomeRules = Field(default_factory=DividendIncomeRules)
    interest: InterestIncomeRules = Field(default_factory=InterestIncomeRules)
    non_cash: NonCashIncomeRules = Field(default_factory=NonCashIncomeRules)
    grouping: IncomeGroupingRules = Field(default_factory=IncomeGroupingRules)


class CoreExpenseRules(BaseModel):
    """Category and subcategory identifiers for essential, nondiscretionary living expenses."""

    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class ExpenseAnalyticsRules(BaseModel):
    """Configurable parameters for household expense spending and variance analytics."""

    short_window_months: int = Field(
        default=3,
        ge=1,
        description="Short-term trailing months window for moving average spend.",
    )
    medium_window_months: int = Field(
        default=6,
        ge=1,
        description="Medium-term trailing months window for moving average spend.",
    )
    long_window_months: int = Field(
        default=12,
        ge=1,
        description="Long-term trailing months window for moving average spend.",
    )
    investment_group_patterns: list[str] = Field(
        default_factory=lambda: ["invest", "saving"],
        description="Keywords in CATEGORY_GROUPS identifying investment outflows.",
    )
    fixed_group_patterns: list[str] = Field(
        default_factory=lambda: [
            "fixed",
            "utilities",
            "rent",
            "insurance",
            "tax",
            "emi",
            "loan",
        ],
        description="Keywords in CATEGORY_GROUPS identifying fixed non-discretionary expenses.",
    )
    consistency_score_cap: float = Field(
        default=10.0,
        gt=0.0,
        description="Upper bound cap on spend consistency score ratio.",
    )
    creep_spend_multiplier: float = Field(
        default=1.15,
        gt=0.0,
        description="Multiplier on short-term average spend indicating expenditure creep.",
    )
    creep_frequency_multiplier: float = Field(
        default=1.10,
        gt=0.0,
        description="Multiplier on short-term frequency indicating transaction frequency creep.",
    )
    creep_spike_multiplier: float = Field(
        default=1.50,
        gt=0.0,
        description="Multiplier indicating extreme single-month spending surge.",
    )


class ExpenseRules(BaseModel):
    """Container grouping household expense classification rules."""

    core: CoreExpenseRules = Field(default_factory=CoreExpenseRules)
    analytics: ExpenseAnalyticsRules = Field(default_factory=ExpenseAnalyticsRules)


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
    investing_analysis_offset_months: int = Field(
        default=-1,
        description="Relative month offset for cashflow investing analysis window boundary.",
    )


class DigitalAssetRules(BaseModel):
    """Category identifiers for digital and cryptocurrency assets."""

    category_ids: list[str] = Field(default_factory=list)


class AssetRules(BaseModel):
    """Container grouping household asset classification and cashflow conduit rules."""

    illiquid: IlliquidAssetRules = Field(default_factory=IlliquidAssetRules)
    cashflow: CashflowAssetRules = Field(default_factory=CashflowAssetRules)
    digital: DigitalAssetRules = Field(default_factory=DigitalAssetRules)
