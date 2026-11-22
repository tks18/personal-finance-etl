"""Authoritative financial capability graph, descriptors, and topological resolution.

Owns
----
- CapabilityId: Closed enum vocabulary for financial execution capabilities.
- ExternalEnrichmentId: Authoritative identifiers for provider market enrichments.
- ContributionScope & ContributionDescriptor: Typed cross-capability contribution descriptors.
- CapabilityDescriptor: Immutable contract specifying evidence requirements and analytical outputs.
- CAPABILITY_REGISTRY: Authoritative catalog of all 7 financial capabilities.
- COMMON_PRODUCED_SILVER_DATASETS: Authoritative set of shared/common Silver datasets.
- ResolvedCapabilityGraph: Immutable resolved capability execution contract.
- CapabilityGraph: Immutable graph validator and topological dependency resolver.
- CapabilityGraphError: Dedicated exception for graph validation or cycle failures.

Does not own
-------------
- Runtime execution planning or pipeline orchestration (owned by application.pipeline).
- Financial transformation algorithms (owned by domain layer).
- Warehouse persistence or DDL (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from personal_finance_etl.contracts.datasets import (
    BRONZE_DATASET_ORIGIN_MAP,
    DatasetId,
)
from personal_finance_etl.contracts.semantic_inventory import (
    GOLD_CONTRACT_DEPENDENCIES,
    SILVER_CONTRACT_SEMANTICS,
)

__all__ = [
    "CAPABILITY_COLUMN_INVENTORY",
    "CAPABILITY_REGISTRY",
    "COMMON_PRODUCED_SILVER_DATASETS",
    "CapabilityDescriptor",
    "CapabilityGraph",
    "CapabilityGraphError",
    "CapabilityId",
    "ContributionDescriptor",
    "ContributionScope",
    "ExternalEnrichmentId",
    "FUTURE_CAPABILITY_CANDIDATES",
    "ResolvedCapabilityGraph",
    "get_capability_columns",
    "get_future_capability_bronze_requirements",
]


class CapabilityGraphError(Exception):
    """Raised when capability dependency graph validation or resolution fails."""


class CapabilityId(StrEnum):
    """Authoritative identifier for PFETL financial execution capabilities."""

    HOUSEHOLD_CORE = "household_core"
    INVESTMENT_ACCOUNTING = "investment_accounting"
    BENCHMARK_ENRICHMENT = "benchmark_enrichment"
    FOREIGN_ASSET_ENRICHMENT = "foreign_asset_enrichment"
    TAX = "tax"
    WEALTH = "wealth"
    FIRE = "fire"


class ExternalEnrichmentId(StrEnum):
    """Authoritative identifier for external provider-generated market data enrichments."""

    BENCHMARK_PRICES = "benchmark_prices"
    CURRENCY_FX_RATES = "currency_fx_rates"
    US_STOCK_PRICES = "us_stock_prices"


class ContributionScope(StrEnum):
    """Scope of an optional cross-capability financial contribution."""

    CALENDAR_BOUNDS = "calendar_bounds"
    CASHFLOW_MOVEMENTS = "cashflow_movements"
    PORTFOLIO_VALUATION = "portfolio_valuation"
    REALIZED_GAINS = "realized_gains"


@dataclass(frozen=True, slots=True)
class ContributionDescriptor:
    """Descriptor for an optional cross-capability financial contribution.

    Parameters
    ----------
    target_capability : CapabilityId
        The capability that receives the contribution.
    scope : ContributionScope
        The functional category of financial data contributed.
    description : str
        Human-readable summary of the cross-capability interaction.
    """

    target_capability: CapabilityId
    scope: ContributionScope
    description: str


@dataclass(frozen=True, slots=True)
class CapabilityDescriptor:
    """Immutable metadata and dependency contract for a financial execution capability.

    Parameters
    ----------
    capability_id : CapabilityId
        Authoritative logical identifier for the capability.
    description : str
        Human-readable summary of the financial execution responsibility.
    required_capabilities : tuple[CapabilityId, ...]
        Mandatory prerequisite capabilities that must be active.
    required_bronze_datasets : tuple[DatasetId, ...]
        Mandatory Bronze evidence datasets required to execute this capability.
    optional_bronze_datasets : tuple[DatasetId, ...]
        Optional Bronze evidence datasets consumed if present.
    produced_silver_datasets : tuple[DatasetId, ...]
        Canonical Silver datasets produced directly by this capability.
    produced_gold_datasets : tuple[DatasetId, ...]
        Decision-ready Gold analytical datasets produced by this capability.
    required_external_enrichments : tuple[ExternalEnrichmentId, ...]
        External market data provider enrichments required by this capability.
    optional_contributions : tuple[ContributionDescriptor, ...]
        Cross-capability contributions provided when peer capabilities are active.
    """

    capability_id: CapabilityId
    description: str
    required_capabilities: tuple[CapabilityId, ...] = ()
    required_bronze_datasets: tuple[DatasetId, ...] = ()
    optional_bronze_datasets: tuple[DatasetId, ...] = ()
    produced_silver_datasets: tuple[DatasetId, ...] = ()
    produced_gold_datasets: tuple[DatasetId, ...] = ()
    required_external_enrichments: tuple[ExternalEnrichmentId, ...] = ()
    optional_contributions: tuple[ContributionDescriptor, ...] = ()


# Shared / Common Silver datasets synthesized from active event boundaries
COMMON_PRODUCED_SILVER_DATASETS: frozenset[DatasetId] = frozenset(
    {
        DatasetId.COMMON_CALENDAR,
        DatasetId.COMMON_CURRENCY,
    }
)


# Authoritative catalog of all 7 financial capabilities
CAPABILITY_REGISTRY: dict[CapabilityId, CapabilityDescriptor] = {
    # 1. Household Core
    CapabilityId.HOUSEHOLD_CORE: CapabilityDescriptor(
        capability_id=CapabilityId.HOUSEHOLD_CORE,
        description="Household budgeting, income/expense/transfer transactions, and account balances.",
        required_capabilities=(),
        required_bronze_datasets=(
            DatasetId.HOUSEHOLD_ZCATEGORY,
            DatasetId.HOUSEHOLD_ASSET_GROUP,
            DatasetId.HOUSEHOLD_ASSETS,
            DatasetId.HOUSEHOLD_CURRENCY,
            DatasetId.HOUSEHOLD_INOUTCOME,
            DatasetId.HOUSEHOLD_OPENING_BALANCES,
        ),
        optional_bronze_datasets=(DatasetId.COMMON_COLUMN_MASTER,),
        produced_silver_datasets=(
            DatasetId.WEALTH_INCOME_CATEGORY,
            DatasetId.WEALTH_INCOME_SUBCATEGORY,
            DatasetId.WEALTH_EXPENSE_CATEGORY,
            DatasetId.WEALTH_EXPENSE_SUBCATEGORY,
            DatasetId.WEALTH_ASSET_CATEGORY,
            DatasetId.WEALTH_ASSET_SUBCATEGORY,
            DatasetId.WEALTH_INCOME_TRANSACTIONS,
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS,
            DatasetId.WEALTH_TRANSFER_TRANSACTIONS,
            DatasetId.WEALTH_OPENING_BALANCES,
        ),
        produced_gold_datasets=(
            DatasetId.WEALTH_CORE_MONTHLY,
            DatasetId.WEALTH_CASHFLOW_EXPENSE_BREAKDOWN,
            DatasetId.WEALTH_CASHFLOW_INCOME_BREAKDOWN,
            DatasetId.WEALTH_BUDGET_VARIANCE,
            DatasetId.WEALTH_CASHFLOW_EFFICIENCY,
            DatasetId.WEALTH_CASHFLOW_ACTIVITY_SUMMARY,
        ),
        required_external_enrichments=(),
        optional_contributions=(),
    ),
    # 2. Investment Accounting
    CapabilityId.INVESTMENT_ACCOUNTING: CapabilityDescriptor(
        capability_id=CapabilityId.INVESTMENT_ACCOUNTING,
        description="Investment order accounting, FIFO tax lot tracking, realized capital gains, and reconciliation.",
        required_capabilities=(),
        required_bronze_datasets=(
            DatasetId.INVESTMENT_MF_ISIN_MAPPING,
            DatasetId.INVESTMENT_MACRO_PARAMETERS,
            DatasetId.MARKET_MF_HOLDINGS,
            DatasetId.INVESTMENT_MF_ORDERS,
            DatasetId.MARKET_STOCK_HOLDINGS,
            DatasetId.INVESTMENT_STOCK_ORDERS,
        ),
        optional_bronze_datasets=(
            DatasetId.INVESTMENT_BENCHMARK_MAPPING,
            DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS,
            DatasetId.COMMON_COLUMN_MASTER,
        ),
        produced_silver_datasets=(
            DatasetId.INVESTMENT_MASTER,
            DatasetId.INVESTMENT_MACRO_PARAMETERS_DIM,
            DatasetId.INVESTMENT_MARKET_DATA,
            DatasetId.INVESTMENT_PURCHASE_DATA,
            DatasetId.INVESTMENT_SALE_DATA,
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_REALIZED_EVENTS,
            DatasetId.INVESTMENT_RECONCILIATION_EVENTS,
        ),
        produced_gold_datasets=(
            DatasetId.INVESTMENT_BY_ISIN,
            DatasetId.INVESTMENT_BY_SUBTYPE,
            DatasetId.INVESTMENT_BY_CLASS,
            DatasetId.INVESTMENT_BY_INSTRUMENT_TYPE,
            DatasetId.INVESTMENT_BY_SECTOR,
            DatasetId.INVESTMENT_BY_INDUSTRY,
            DatasetId.INVESTMENT_BY_PORTFOLIO,
            DatasetId.INVESTMENT_BY_GEO,
            DatasetId.INVESTMENT_BY_COUNTRY,
            DatasetId.INVESTMENT_BY_CURRENCY,
            DatasetId.INVESTMENT_PORTFOLIO_SUMMARY,
        ),
        required_external_enrichments=(),
        optional_contributions=(
            ContributionDescriptor(
                target_capability=CapabilityId.HOUSEHOLD_CORE,
                scope=ContributionScope.CASHFLOW_MOVEMENTS,
                description="Investment purchase and sale cash flows contribute to household budget and cashflow analytics.",
            ),
            ContributionDescriptor(
                target_capability=CapabilityId.WEALTH,
                scope=ContributionScope.PORTFOLIO_VALUATION,
                description="Investment positions and market valuations contribute to net worth breakdown and portfolio summary.",
            ),
            ContributionDescriptor(
                target_capability=CapabilityId.TAX,
                scope=ContributionScope.REALIZED_GAINS,
                description="Realized capital gains and losses contribute to tax assessment events.",
            ),
        ),
    ),
    # 3. Benchmark Enrichment
    CapabilityId.BENCHMARK_ENRICHMENT: CapabilityDescriptor(
        capability_id=CapabilityId.BENCHMARK_ENRICHMENT,
        description="Market benchmark tracking, comparative index history, and performance attribution.",
        required_capabilities=(CapabilityId.INVESTMENT_ACCOUNTING,),
        required_bronze_datasets=(
            DatasetId.INVESTMENT_BENCHMARK_MAPPING,
            DatasetId.INVESTMENT_BENCHMARK_MASTER,
            DatasetId.MARKET_BENCHMARK_HISTORY,
        ),
        optional_bronze_datasets=(),
        produced_silver_datasets=(
            DatasetId.INVESTMENT_BENCHMARK_MASTER_DIM,
            DatasetId.INVESTMENT_BENCHMARK_DATA,
        ),
        produced_gold_datasets=(),
        required_external_enrichments=(ExternalEnrichmentId.BENCHMARK_PRICES,),
        optional_contributions=(),
    ),
    # 4. Foreign Asset Enrichment
    CapabilityId.FOREIGN_ASSET_ENRICHMENT: CapabilityDescriptor(
        capability_id=CapabilityId.FOREIGN_ASSET_ENRICHMENT,
        description="Foreign asset valuation, USD stock price time-series, and daily currency exchange rate integration.",
        required_capabilities=(CapabilityId.INVESTMENT_ACCOUNTING,),
        required_bronze_datasets=(
            DatasetId.MARKET_CURRENCY_MAPPING,
            DatasetId.MARKET_CURRENCY_FX_RATES,
            DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS,
            DatasetId.MARKET_US_STOCK_PRICES,
        ),
        optional_bronze_datasets=(),
        produced_silver_datasets=(DatasetId.COMMON_CURRENCY_FX_RATES,),
        produced_gold_datasets=(),
        required_external_enrichments=(
            ExternalEnrichmentId.CURRENCY_FX_RATES,
            ExternalEnrichmentId.US_STOCK_PRICES,
        ),
        optional_contributions=(),
    ),
    # 5. Tax
    CapabilityId.TAX: CapabilityDescriptor(
        capability_id=CapabilityId.TAX,
        description="Statutory tax assessment, capital gains liability, income breakdown, and tax reconciliation.",
        required_capabilities=(
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
        ),
        required_bronze_datasets=(),
        optional_bronze_datasets=(),
        produced_silver_datasets=(DatasetId.TAX_EVENTS,),
        produced_gold_datasets=(
            DatasetId.TAX_YEAR_SUMMARY,
            DatasetId.TAX_INCOME_BREAKDOWN,
            DatasetId.TAX_RECONCILIATION,
        ),
        required_external_enrichments=(),
        optional_contributions=(),
    ),
    # 6. Wealth
    CapabilityId.WEALTH: CapabilityDescriptor(
        capability_id=CapabilityId.WEALTH,
        description="Net worth evolution, asset breakdown, monthly budget variance, and cashflow efficiency statements.",
        required_capabilities=(CapabilityId.HOUSEHOLD_CORE,),
        required_bronze_datasets=(),
        optional_bronze_datasets=(),
        produced_silver_datasets=(),
        produced_gold_datasets=(
            DatasetId.WEALTH_ASSET_BREAKDOWN,
            DatasetId.FIRE_ANALYTICS,
        ),
        required_external_enrichments=(),
        optional_contributions=(),
    ),
    # 7. FIRE
    CapabilityId.FIRE: CapabilityDescriptor(
        capability_id=CapabilityId.FIRE,
        description="Financial Independence Retire Early analytics and Monte Carlo stochastic portfolio simulation.",
        required_capabilities=(
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.WEALTH,
        ),
        required_bronze_datasets=(),
        optional_bronze_datasets=(),
        produced_silver_datasets=(),
        produced_gold_datasets=(),
        required_external_enrichments=(),
        optional_contributions=(),
    ),
}


# Candidate canonical Bronze dataset requirements for future capability cutovers
FUTURE_CAPABILITY_CANDIDATES: dict[CapabilityId, tuple[DatasetId, ...]] = {
    CapabilityId.HOUSEHOLD_CORE: (
        DatasetId.HOUSEHOLD_CATEGORIES,
        DatasetId.HOUSEHOLD_ASSET_CATEGORIES,
        DatasetId.HOUSEHOLD_ACCOUNTS,
        DatasetId.COMMON_CURRENCIES,
        DatasetId.HOUSEHOLD_TRANSACTIONS,
        DatasetId.HOUSEHOLD_ACCOUNT_BALANCES,
    ),
}


def get_future_capability_bronze_requirements(
    capability_id: CapabilityId,
) -> tuple[DatasetId, ...] | None:
    """Retrieve candidate canonical Bronze datasets for a future capability cutover.

    Parameters
    ----------
    capability_id : CapabilityId
        Target capability identifier.

    Returns
    -------
    tuple[DatasetId, ...] | None
        Tuple of candidate canonical DatasetIds if registered, else None.
    """
    return FUTURE_CAPABILITY_CANDIDATES.get(capability_id)


# Authoritative mapping of financial capabilities to their owned analytical columns across Silver and Gold
CAPABILITY_COLUMN_INVENTORY: dict[CapabilityId, dict[DatasetId, tuple[str, ...]]] = {
    CapabilityId.BENCHMARK_ENRICHMENT: {
        DatasetId.INVESTMENT_LOT_ANALYTICS: (
            "BENCHMARK_ID",
            "BM_Buy_Price",
            "BM_Market_Price",
            "Lot_BM_Return",
            "Lot_BM_CAGR",
            "Lot_BM_CAGR_Status",
            "Lot_BM_CAGR_Local",
            "BM_CAGR",
            "BM_CAGR_Status",
            "BM_XIRR",
            "BM_XIRR_Local",
            "Active_Return",
            "Active_Return_Local",
            "Lot_Alpha",
            "Is_Lagging_Benchmark",
        ),
        DatasetId.INVESTMENT_BY_ISIN: (
            "BM_CAGR",
            "BM_XIRR",
            "BM_XIRR_Local",
            "Active_Return",
            "Active_Return_Local",
            "Is_Lagging_Benchmark",
        ),
        DatasetId.INVESTMENT_PORTFOLIO_SUMMARY: (
            "ISIN_BM_XIRR",
            "ISIN_BM_XIRR_Local",
            "ISIN_Active_Return",
            "ISIN_Active_Return_Local",
        ),
        DatasetId.INVESTMENT_BY_CLASS: ("BM_XIRR", "Active_Return"),
        DatasetId.INVESTMENT_BY_SUBTYPE: ("BM_XIRR", "Active_Return"),
        DatasetId.INVESTMENT_BY_INSTRUMENT_TYPE: ("BM_XIRR", "Active_Return"),
        DatasetId.INVESTMENT_BY_SECTOR: ("BM_XIRR", "Active_Return"),
        DatasetId.INVESTMENT_BY_INDUSTRY: ("BM_XIRR", "Active_Return"),
        DatasetId.INVESTMENT_BY_GEO: ("BM_XIRR", "Active_Return"),
        DatasetId.INVESTMENT_BY_PORTFOLIO: ("BM_XIRR", "Active_Return"),
        DatasetId.INVESTMENT_BY_COUNTRY: (
            "BM_XIRR",
            "Active_Return",
            "BM_XIRR_Local",
            "Active_Return_Local",
        ),
        DatasetId.INVESTMENT_BY_CURRENCY: (
            "BM_XIRR",
            "Active_Return",
            "BM_XIRR_Local",
            "Active_Return_Local",
        ),
    },
    CapabilityId.FOREIGN_ASSET_ENRICHMENT: {
        DatasetId.INVESTMENT_LOT_ANALYTICS: (
            "CURRENCY_ID",
            "Buy_Value_Local",
            "Close_Value_Local",
            "Blended_FX_Buy_Rate",
            "Buy_Price_Local",
            "Market_Price_Local",
            "FX_Rate_Buy",
            "FX_Rate_Snap",
            "Currency_Appreciation_Pct",
            "Absolute_Return_Local",
            "Asset_PnL",
            "Forex_PnL",
            "Forex_Contribution_Pct",
            "Asset_Return_Pct",
            "Forex_Return_Pct",
            "Lot_CAGR_Local",
            "XIRR_Local",
            "FX_XIRR_Impact",
        ),
        DatasetId.INVESTMENT_BY_ISIN: (
            "CURRENCY_ID",
            "Total_Invested_Value_Local",
            "Total_Current_Value_Local",
            "Current_FX_Rate",
            "Blended_FX_Buy_Rate",
            "Currency_Appreciation_Pct",
            "Asset_PnL",
            "Forex_PnL",
            "Forex_Contribution_Pct",
            "XIRR_Local",
            "FX_XIRR_Impact",
        ),
        DatasetId.INVESTMENT_PORTFOLIO_SUMMARY: (
            "CURRENCY_ID",
            "ISIN_Market_Value_Local",
            "ISIN_Book_Value_Local",
            "ISIN_Asset_PnL",
            "ISIN_Forex_PnL",
            "ISIN_Forex_Contribution_Pct",
            "ISIN_XIRR_Local",
            "ISIN_FX_XIRR_Impact",
        ),
        DatasetId.INVESTMENT_BY_CLASS: ("Asset_PnL", "Forex_PnL", "Forex_Contribution_Pct"),
        DatasetId.INVESTMENT_BY_SUBTYPE: ("Asset_PnL", "Forex_PnL", "Forex_Contribution_Pct"),
        DatasetId.INVESTMENT_BY_INSTRUMENT_TYPE: (
            "Asset_PnL",
            "Forex_PnL",
            "Forex_Contribution_Pct",
        ),
        DatasetId.INVESTMENT_BY_SECTOR: ("Asset_PnL", "Forex_PnL", "Forex_Contribution_Pct"),
        DatasetId.INVESTMENT_BY_INDUSTRY: ("Asset_PnL", "Forex_PnL", "Forex_Contribution_Pct"),
        DatasetId.INVESTMENT_BY_GEO: ("Asset_PnL", "Forex_PnL", "Forex_Contribution_Pct"),
        DatasetId.INVESTMENT_BY_PORTFOLIO: ("Asset_PnL", "Forex_PnL", "Forex_Contribution_Pct"),
        DatasetId.INVESTMENT_BY_COUNTRY: (
            "Total_Invested_Value_Local",
            "Total_Current_Value_Local",
            "Current_FX_Rate",
            "Blended_FX_Buy_Rate",
            "Currency_Appreciation_Pct",
            "Asset_PnL",
            "Forex_PnL",
            "Forex_Contribution_Pct",
            "XIRR_Local",
            "BM_XIRR_Local",
            "Active_Return_Local",
            "FX_XIRR_Impact",
        ),
        DatasetId.INVESTMENT_BY_CURRENCY: (
            "Total_Invested_Value_Local",
            "Total_Current_Value_Local",
            "Current_FX_Rate",
            "Blended_FX_Buy_Rate",
            "Currency_Appreciation_Pct",
            "Asset_PnL",
            "Forex_PnL",
            "Forex_Contribution_Pct",
            "XIRR_Local",
            "BM_XIRR_Local",
            "Active_Return_Local",
            "FX_XIRR_Impact",
        ),
        DatasetId.WEALTH_CORE_MONTHLY: (
            "Closing_Forex_PnL",
            "Total_Foreign_Currency_Exposure",
            "Foreign_Exposure_Pct",
        ),
    },
    CapabilityId.TAX: {
        DatasetId.INVESTMENT_LOT_ANALYTICS: (
            "TAX_TYPE",
            "TAX_SUBTYPE",
            "Tax_Rate",
            "LTCG_Threshold_Days",
            "Days_To_LTCG",
            "Unrealized_LTCG",
            "Unrealized_STCG",
            "Unrealized_Gain",
            "Unrealized_LTCL",
            "Unrealized_STCL",
            "Unrealized_Loss",
            "LTCG_Tax_If_Sold",
            "STCG_Tax_If_Sold",
            "After_Tax_PL",
            "After_Tax_Close_Value",
            "After_Tax_XIRR",
            "FY",
            "FY_Realized_LTCG",
            "FY_Realized_STCG",
            "FY_Realized_Gain",
            "FY_Realized_LTCL",
            "FY_Realized_STCL",
            "FY_Realized_Loss",
            "FY_Realized_Net_PnL",
            "Equity_LTCG_Exemption",
            "Stepup_Eligible",
            "Can_Harvest_Loss",
            "Harvest_Recommendation",
        ),
        DatasetId.INVESTMENT_REALIZED_EVENTS: (
            "Applied_Rate",
            "Estimated_Tax",
        ),
        DatasetId.INVESTMENT_BY_ISIN: (
            "After_Tax_XIRR",
            "Unrealized_LTCG",
            "Unrealized_STCG",
            "Unrealized_Gain",
            "Unrealized_LTCL",
            "Unrealized_STCL",
            "Unrealized_Loss",
            "LTCG_Tax_If_Sold",
            "STCG_Tax_If_Sold",
            "FY_Realized_LTCG",
            "FY_Realized_STCG",
            "FY_Realized_Gain",
            "FY_Realized_LTCL",
            "FY_Realized_STCL",
            "FY_Realized_Loss",
            "FY_Realized_Net_PnL",
        ),
        DatasetId.INVESTMENT_PORTFOLIO_SUMMARY: (
            "ISIN_Harvestable_Loss",
            "Tax_Harvesting_Priority_Score",
        ),
        DatasetId.INVESTMENT_BY_SUBTYPE: (
            "After_Tax_XIRR",
            "FY_Realized_Gain",
            "FY_Realized_Loss",
            "FY_Realized_Net_PnL",
        ),
        DatasetId.INVESTMENT_BY_CLASS: (
            "After_Tax_XIRR",
            "FY_Realized_Gain",
            "FY_Realized_Loss",
            "FY_Realized_Net_PnL",
        ),
        DatasetId.INVESTMENT_BY_INSTRUMENT_TYPE: (
            "After_Tax_XIRR",
            "FY_Realized_Gain",
            "FY_Realized_Loss",
            "FY_Realized_Net_PnL",
        ),
        DatasetId.INVESTMENT_BY_SECTOR: (
            "After_Tax_XIRR",
            "FY_Realized_Gain",
            "FY_Realized_Loss",
            "FY_Realized_Net_PnL",
        ),
        DatasetId.INVESTMENT_BY_INDUSTRY: (
            "After_Tax_XIRR",
            "FY_Realized_Gain",
            "FY_Realized_Loss",
            "FY_Realized_Net_PnL",
        ),
        DatasetId.INVESTMENT_BY_GEO: (
            "After_Tax_XIRR",
            "FY_Realized_Gain",
            "FY_Realized_Loss",
            "FY_Realized_Net_PnL",
        ),
        DatasetId.INVESTMENT_BY_PORTFOLIO: (
            "After_Tax_XIRR",
            "FY_Realized_Gain",
            "FY_Realized_Loss",
            "FY_Realized_Net_PnL",
        ),
        DatasetId.INVESTMENT_BY_COUNTRY: (
            "After_Tax_XIRR",
            "FY_Realized_Gain",
            "FY_Realized_Loss",
            "FY_Realized_Net_PnL",
        ),
        DatasetId.INVESTMENT_BY_CURRENCY: (
            "After_Tax_XIRR",
            "FY_Realized_Gain",
            "FY_Realized_Loss",
            "FY_Realized_Net_PnL",
        ),
        DatasetId.TAX_EVENTS: (
            "Tax_Event_ID",
            "FY",
            "Event_Date",
            "Source_Type",
            "Source_ID",
            "Income_Head",
            "Tax_Sub_Head",
            "Amount_INR",
            "Applied_Rate",
            "Estimated_Tax",
            "CURRENCY_ID",
            "Tax_Status",
            "Tax_Status_Reason",
            "ISIN",
            "Lot_ID",
        ),
        DatasetId.TAX_YEAR_SUMMARY: (
            "FY",
            "Gross_Taxable_Income",
            "Estimated_Tax_Liability",
            "Taxes_Paid_Credits",
            "Net_Tax_Payable",
            "Ordinary_Income",
            "Ordinary_Tax_Estimate",
            "Equity_LTCG",
            "Equity_LTCG_Tax_Estimate",
            "Equity_STCG",
            "Equity_STCG_Tax_Estimate",
            "Debt_LTCG",
            "Debt_LTCG_Tax_Estimate",
            "Debt_STCG",
            "Debt_STCG_Tax_Estimate",
            "Other_Capital_Gains",
            "Other_Capital_Gains_Tax_Estimate",
            "Has_Partial_Estimates",
            "Has_Missing_Rates",
        ),
        DatasetId.TAX_INCOME_BREAKDOWN: (
            "FY",
            "Income_Head",
            "Tax_Sub_Head",
            "Source_Type",
            "Amount_INR",
            "Estimated_Tax",
            "Effective_Rate_Pct",
            "Event_Count",
            "Has_Partial_Estimates",
            "Has_Missing_Rates",
        ),
        DatasetId.TAX_RECONCILIATION: (
            "FY",
            "Tax_Sub_Head",
            "Income_Head",
            "Canonical_Event_Count",
            "Canonical_Total_Amount",
            "Quant_Event_Count",
            "Quant_Total_Amount",
            "Ledger_Taxable_Event_Count",
            "Ledger_Taxable_Total_Amount",
            "Excluded_Non_Taxable_Event_Count",
            "Excluded_Non_Taxable_Amount",
            "Excluded_Investment_Ledger_Event_Count",
            "Excluded_Investment_Ledger_Amount",
            "Reconciliation_Status",
            "Variance_Amount",
            "Has_Partial_Estimates",
            "Has_Missing_Rates",
        ),
    },
    CapabilityId.INVESTMENT_ACCOUNTING: {
        DatasetId.WEALTH_CORE_MONTHLY: (
            "Opening_Investment_Book_Value",
            "Closing_Investment_Book_Value",
            "Investment_Book_Value_Delta",
            "Opening_Investment_Market_Value",
            "Closing_Investment_Market_Value",
            "Investment_Market_Value_Delta",
            "Opening_Unrealized_PL",
            "Closing_Unrealized_PL",
            "Closing_Asset_PnL",
            "Opening_Investment_XIRR",
            "Closing_Investment_XIRR",
        ),
    },
    CapabilityId.WEALTH: {
        DatasetId.WEALTH_CORE_MONTHLY: (
            "Total_Assets_Market",
            "Total_Net_Worth_Market",
            "Opening_Balance_Asset_Market",
            "Closing_Balance_Asset_Market",
            "Asset_Market_Delta",
            "Liquid_Assets_Market",
        ),
    },
    CapabilityId.FIRE: {
        DatasetId.FIRE_ANALYTICS: (
            "Months_To_FI_Conservative_P90",
            "Months_To_FI_Base_P50",
            "Months_To_FI_Aggressive_P10",
            "Probability_Of_Success_Pct",
            "Years_To_FI_P50",
            "Projected_FI_Date_P50",
            "Runway_Months_Stressed_P10",
            "Runway_Months_Base_P50",
            "Terminal_Wealth_Nominal_P50",
            "Target_FI_Total_Future_Nominal",
            "Savings_Rate_Required",
        ),
    },
}


def get_capability_columns(
    capability_id: CapabilityId,
    dataset_id: DatasetId | None = None,
) -> tuple[str, ...]:
    """Retrieve owned analytical columns for a specific capability and optional dataset.

    Parameters
    ----------
    capability_id : CapabilityId
        Financial capability to query.
    dataset_id : DatasetId | None, default None
        Target dataset identifier. If None, returns all distinct columns across all datasets.

    Returns
    -------
    tuple[str, ...]
        Tuple of owned column names.
    """
    table_map = CAPABILITY_COLUMN_INVENTORY.get(capability_id, {})
    if dataset_id is not None:
        return table_map.get(dataset_id, ())
    all_cols: list[str] = []
    for cols in table_map.values():
        all_cols.extend(cols)
    return tuple(dict.fromkeys(all_cols))


@dataclass(frozen=True, slots=True)
class ResolvedCapabilityGraph:
    """Immutable resolved capability plan contract.

    Parameters
    ----------
    requested_capabilities : tuple[CapabilityId, ...]
        The set of capabilities explicitly requested by caller or configuration.
    active_capabilities : tuple[CapabilityId, ...]
        Topologically sorted list of all active capabilities including transitive dependencies.
    required_bronze_datasets : frozenset[DatasetId]
        All mandatory Bronze datasets required across all active capabilities.
    optional_bronze_datasets : frozenset[DatasetId]
        All optional Bronze datasets consumed across active capabilities.
    produced_silver_datasets : frozenset[DatasetId]
        All Silver datasets produced by active capabilities, including shared common datasets.
    produced_gold_datasets : frozenset[DatasetId]
        All Gold presentation datasets produced across active capabilities.
    required_external_enrichments : frozenset[ExternalEnrichmentId]
        All external provider market data enrichments required by active capabilities.
    active_contributions : tuple[ContributionDescriptor, ...]
        Active cross-capability contributions where both source and target capability are active.
    """

    requested_capabilities: tuple[CapabilityId, ...]
    active_capabilities: tuple[CapabilityId, ...]
    required_bronze_datasets: frozenset[DatasetId]
    optional_bronze_datasets: frozenset[DatasetId]
    produced_silver_datasets: frozenset[DatasetId]
    produced_gold_datasets: frozenset[DatasetId]
    required_external_enrichments: frozenset[ExternalEnrichmentId]
    active_contributions: tuple[ContributionDescriptor, ...]


class CapabilityGraph:
    """Immutable financial capability graph validator and topological dependency resolver.

    Parameters
    ----------
    registry : dict[CapabilityId, CapabilityDescriptor] | None, optional
        Custom capability descriptor dictionary. Defaults to authoritative CAPABILITY_REGISTRY.
    """

    def __init__(
        self,
        registry: dict[CapabilityId, CapabilityDescriptor] | None = None,
    ) -> None:
        self._registry: dict[CapabilityId, CapabilityDescriptor] = (
            dict(registry) if registry is not None else dict(CAPABILITY_REGISTRY)
        )
        self.validate()

    @property
    def registry(self) -> dict[CapabilityId, CapabilityDescriptor]:
        """Return a defensive copy of the capability registry.

        Returns
        -------
        dict[CapabilityId, CapabilityDescriptor]
            Defensive copy of registered capability descriptors.
        """
        return dict(self._registry)

    def get_descriptor(self, capability_id: CapabilityId) -> CapabilityDescriptor:
        """Retrieve the descriptor for a registered capability.

        Parameters
        ----------
        capability_id : CapabilityId
            Authoritative capability identifier to inspect.

        Returns
        -------
        CapabilityDescriptor
            The registered immutable capability descriptor.

        Raises
        ------
        CapabilityGraphError
            If capability_id is not registered.
        """
        if capability_id not in self._registry:
            raise CapabilityGraphError(
                f"Unknown capability '{capability_id}'. Not found in capability registry."
            )
        return self._registry[capability_id]

    def validate(self) -> None:
        """Validate structural integrity, acyclicity, and dataset boundaries of the capability graph.

        Raises
        ------
        CapabilityGraphError
            If any dependency cycle, unknown dependency, invalid dataset, or conflicting owner is found.
        """
        # 1. Key alignment check
        for cid, desc in self._registry.items():
            if cid != desc.capability_id:
                raise CapabilityGraphError(
                    f"Capability key mismatch: registry key '{cid}' != descriptor '{desc.capability_id}'."
                )

        # 2. Prerequisite dependency check
        for cid, desc in self._registry.items():
            for req in desc.required_capabilities:
                if req not in self._registry:
                    raise CapabilityGraphError(
                        f"Capability '{cid}' requires unregistered capability '{req}'."
                    )

        # 3. Cycle detection using Tarjan's / DFS
        self._detect_cycles()

        # 4. Dataset validity check
        all_bronze_ids = set(BRONZE_DATASET_ORIGIN_MAP.keys())
        all_silver_ids = set(SILVER_CONTRACT_SEMANTICS.keys())
        all_gold_ids = set(GOLD_CONTRACT_DEPENDENCIES.keys())

        produced_silver_claims: dict[DatasetId, CapabilityId] = {}
        produced_gold_claims: dict[DatasetId, CapabilityId] = {}

        for cid, desc in self._registry.items():
            # Validate Bronze datasets
            for b_id in desc.required_bronze_datasets:
                if b_id not in all_bronze_ids:
                    raise CapabilityGraphError(
                        f"Capability '{cid}' specifies unknown required Bronze dataset '{b_id}'."
                    )
            for b_id in desc.optional_bronze_datasets:
                if b_id not in all_bronze_ids:
                    raise CapabilityGraphError(
                        f"Capability '{cid}' specifies unknown optional Bronze dataset '{b_id}'."
                    )

            # Validate Silver produced datasets
            for s_id in desc.produced_silver_datasets:
                if s_id not in all_silver_ids:
                    raise CapabilityGraphError(
                        f"Capability '{cid}' specifies unknown produced Silver dataset '{s_id}'."
                    )
                if s_id in COMMON_PRODUCED_SILVER_DATASETS:
                    raise CapabilityGraphError(
                        f"Capability '{cid}' claims shared common dataset '{s_id}'. "
                        "Common datasets must not be claimed directly by individual capabilities."
                    )
                if s_id in produced_silver_claims:
                    existing_owner = produced_silver_claims[s_id]
                    raise CapabilityGraphError(
                        f"Conflicting Silver dataset ownership: '{s_id}' is claimed by both "
                        f"'{existing_owner}' and '{cid}'."
                    )
                produced_silver_claims[s_id] = cid

            # Validate Gold produced datasets
            for g_id in desc.produced_gold_datasets:
                if g_id not in all_gold_ids:
                    raise CapabilityGraphError(
                        f"Capability '{cid}' specifies unknown produced Gold dataset '{g_id}'."
                    )
                if g_id in produced_gold_claims:
                    existing_owner = produced_gold_claims[g_id]
                    raise CapabilityGraphError(
                        f"Conflicting Gold dataset ownership: '{g_id}' is claimed by both "
                        f"'{existing_owner}' and '{cid}'."
                    )
                produced_gold_claims[g_id] = cid

    def _detect_cycles(self) -> None:
        """Execute depth-first search cycle detection across all registered capabilities.

        Raises
        ------
        CapabilityGraphError
            If any circular dependency is detected.
        """
        # State: 0 = unvisited, 1 = visiting (in recursion stack), 2 = visited
        visited: dict[CapabilityId, int] = {cid: 0 for cid in self._registry}
        path: list[CapabilityId] = []

        def dfs(current: CapabilityId) -> None:
            visited[current] = 1
            path.append(current)
            for neighbor in self._registry[current].required_capabilities:
                if visited[neighbor] == 1:
                    cycle_start = path.index(neighbor)
                    cycle_path = " -> ".join(str(c) for c in path[cycle_start:] + [neighbor])
                    raise CapabilityGraphError(
                        f"Circular capability dependency detected: {cycle_path}"
                    )
                if visited[neighbor] == 0:
                    dfs(neighbor)
            path.pop()
            visited[current] = 2

        for cid in self._registry:
            if visited[cid] == 0:
                dfs(cid)

    def resolve(
        self,
        requested: Iterable[CapabilityId] | None = None,
    ) -> ResolvedCapabilityGraph:
        """Resolve requested capabilities topologically with all transitive dependencies.

        Parameters
        ----------
        requested : Iterable[CapabilityId] | None, optional
            Capabilities requested to run. If None, resolves all capabilities in the registry.

        Returns
        -------
        ResolvedCapabilityGraph
            Topologically sorted execution contract containing all active datasets and enrichments.

        Raises
        ------
        CapabilityGraphError
            If any requested capability is not registered.
        """
        requested_tuple = (
            tuple(requested) if requested is not None else tuple(self._registry.keys())
        )

        for cid in requested_tuple:
            if cid not in self._registry:
                raise CapabilityGraphError(
                    f"Requested capability '{cid}' is not registered in capability graph."
                )

        # Transitive dependency expansion using BFS/DFS
        active_set: set[CapabilityId] = set()

        def collect_deps(current: CapabilityId) -> None:
            if current in active_set:
                return
            active_set.add(current)
            for req in self._registry[current].required_capabilities:
                collect_deps(req)

        for cid in requested_tuple:
            collect_deps(cid)

        # Topological sort (Kahn's algorithm) restricted to active_set
        in_degree: dict[CapabilityId, int] = {cid: 0 for cid in active_set}
        for cid in active_set:
            desc = self._registry[cid]
            for req in desc.required_capabilities:
                if req in active_set:
                    in_degree[cid] += 1

        queue: list[CapabilityId] = [cid for cid, deg in in_degree.items() if deg == 0]
        # Sort queue deterministically by enum string value
        queue.sort(key=lambda c: c.value)

        sorted_capabilities: list[CapabilityId] = []
        while queue:
            current = queue.pop(0)
            sorted_capabilities.append(current)

            # Find all nodes in active_set that depend on current
            for other_cid in active_set:
                if current in self._registry[other_cid].required_capabilities:
                    in_degree[other_cid] -= 1
                    if in_degree[other_cid] == 0:
                        queue.append(other_cid)
                        queue.sort(key=lambda c: c.value)

        # Dataset aggregation across active capabilities
        req_bronze: set[DatasetId] = set()
        opt_bronze: set[DatasetId] = set()
        prod_silver: set[DatasetId] = set(COMMON_PRODUCED_SILVER_DATASETS)
        prod_gold: set[DatasetId] = set()
        req_enrichments: set[ExternalEnrichmentId] = set()
        active_contribs: list[ContributionDescriptor] = []

        active_tuple = tuple(sorted_capabilities)
        for cid in active_tuple:
            desc = self._registry[cid]
            req_bronze.update(desc.required_bronze_datasets)
            opt_bronze.update(desc.optional_bronze_datasets)
            prod_silver.update(desc.produced_silver_datasets)
            prod_gold.update(desc.produced_gold_datasets)
            req_enrichments.update(desc.required_external_enrichments)

            # Active contributions require BOTH source and target to be active
            for contrib in desc.optional_contributions:
                if contrib.target_capability in active_set:
                    active_contribs.append(contrib)

        return ResolvedCapabilityGraph(
            requested_capabilities=requested_tuple,
            active_capabilities=active_tuple,
            required_bronze_datasets=frozenset(req_bronze),
            optional_bronze_datasets=frozenset(opt_bronze),
            produced_silver_datasets=frozenset(prod_silver),
            produced_gold_datasets=frozenset(prod_gold),
            required_external_enrichments=frozenset(req_enrichments),
            active_contributions=tuple(active_contribs),
        )
