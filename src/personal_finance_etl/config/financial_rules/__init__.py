"""Domain-specific financial rules and policy definitions.

Owns
----
- Policy models partitioned by financial domain (household, investments, tax, fire).
- Authoritative composed FinancialRules model.
- Strict validation of financial rules, income subcategories, and mutual exclusivity.

Does not own
-------------
- Application execution state (owned by application.*).
- Execution settings or filesystem paths (owned by config.settings).
"""

from personal_finance_etl.config.financial_rules.fire import (
    AssumptionsRules,
    CMAAssumptions,
    FireAssumptions,
    GlidePathConfig,
    GuytonKlingerConfig,
    HumanCapitalConfig,
    InflationModelConfig,
    JumpDiffusionConfig,
    MacroAssumptions,
    MarkovRegimeConfig,
    MonteCarloAssumptions,
)
from personal_finance_etl.config.financial_rules.household import (
    ActiveIncomeRules,
    AssetRules,
    BudgetAlerts,
    BudgetRules,
    BudgetSmoothing,
    CashflowAssetRules,
    CoreExpenseRules,
    DigitalAssetRules,
    DividendIncomeRules,
    ExpenseRules,
    IlliquidAssetRules,
    IncomeAllocationRules,
    IncomeRules,
    InterestIncomeRules,
    NonCashIncomeRules,
)
from personal_finance_etl.config.financial_rules.investments import (
    InvestmentInstrumentRules,
    PortfolioManagementRules,
)
from personal_finance_etl.config.financial_rules.model import FinancialRules
from personal_finance_etl.config.financial_rules.tax import (
    InvestmentExclusionsConfig,
    TaxabilityType,
    TaxAssumptions,
    TaxHeadConfig,
    TaxMethodType,
    TaxRates,
    TaxSubHeadConfig,
)

__all__ = [
    "ActiveIncomeRules",
    "AssetRules",
    "AssumptionsRules",
    "BudgetAlerts",
    "BudgetRules",
    "BudgetSmoothing",
    "CMAAssumptions",
    "CashflowAssetRules",
    "CoreExpenseRules",
    "DigitalAssetRules",
    "DividendIncomeRules",
    "ExpenseRules",
    "FinancialRules",
    "FireAssumptions",
    "GlidePathConfig",
    "GuytonKlingerConfig",
    "HumanCapitalConfig",
    "IlliquidAssetRules",
    "IncomeAllocationRules",
    "IncomeRules",
    "InflationModelConfig",
    "InterestIncomeRules",
    "InvestmentExclusionsConfig",
    "InvestmentInstrumentRules",
    "JumpDiffusionConfig",
    "MacroAssumptions",
    "MarkovRegimeConfig",
    "MonteCarloAssumptions",
    "NonCashIncomeRules",
    "PortfolioManagementRules",
    "TaxAssumptions",
    "TaxHeadConfig",
    "TaxMethodType",
    "TaxRates",
    "TaxSubHeadConfig",
    "TaxabilityType",
]
