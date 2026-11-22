"""Authoritative catalog of Pre-Bronze, Bronze, and Silver data lakehouse contracts.

Owns
----
- PreBronzeDataContract, BronzeDataContract, and DataContract dataclass definitions.
- Standard Pre-Bronze provenance column constants.
- WarehouseLayer enumeration and managed warehouse schema taxonomies.
- PRE_BRONZE_CONTRACT_REGISTRY: Catalog of Pre-Bronze warehouse persistence contracts.
- BRONZE_CONTRACT_REGISTRY: Catalog of Bronze ingestion layer contracts.
- DATA_CONTRACT_REGISTRY: Catalog of Silver and Gold analytical presentation contracts.

Does not own
-------------
- DDL generation and catalog validation logic (owned by infrastructure.warehouse.registry).
- Table upsert execution (owned by infrastructure.warehouse.pre_bronze/bronze/silver).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from personal_finance_etl.config.sources.change_detection import SyncStrategy
from personal_finance_etl.contracts.datasets import DatasetId, IdentityRequirement
from personal_finance_etl.contracts.sources import SourceBindingId

# Standard Pre-Bronze operational provenance column names
PRE_BRONZE_ARTIFACT_ID: str = "__artifact_id__"
PRE_BRONZE_SOURCE_ID: str = "__source_id__"
PRE_BRONZE_BINDING_ID: str = "__binding_id__"
PRE_BRONZE_DATASET_ID: str = "__dataset_id__"
PRE_BRONZE_PROVENANCE_COLUMNS: tuple[str, ...] = (
    PRE_BRONZE_ARTIFACT_ID,
    PRE_BRONZE_SOURCE_ID,
    PRE_BRONZE_BINDING_ID,
    PRE_BRONZE_DATASET_ID,
)


class WarehouseLayer(StrEnum):
    """Authoritative warehouse analytical layer classifications."""

    PRE_BRONZE = "pre_bronze"
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    META = "meta"


# Authoritative, centralized tuple of all managed warehouse schemas in DuckDB
MANAGED_WAREHOUSE_SCHEMAS: tuple[str, ...] = (
    WarehouseLayer.PRE_BRONZE.value,
    WarehouseLayer.BRONZE.value,
    WarehouseLayer.SILVER.value,
    WarehouseLayer.GOLD.value,
    WarehouseLayer.META.value,
)

# Persisted tabular data schemas (excluding meta) subject to orphan table pruning and metrics
PERSISTED_DATA_SCHEMAS: tuple[str, ...] = (
    WarehouseLayer.PRE_BRONZE.value,
    WarehouseLayer.BRONZE.value,
    WarehouseLayer.SILVER.value,
    WarehouseLayer.GOLD.value,
)

__all__ = [
    "MANAGED_WAREHOUSE_SCHEMAS",
    "PERSISTED_DATA_SCHEMAS",
    "PRE_BRONZE_ARTIFACT_ID",
    "PRE_BRONZE_BINDING_ID",
    "PRE_BRONZE_CONTRACT_REGISTRY",
    "PRE_BRONZE_DATASET_ID",
    "PRE_BRONZE_PROVENANCE_COLUMNS",
    "PRE_BRONZE_SOURCE_ID",
    "BronzeDataContract",
    "DataContract",
    "DatasetId",
    "IdentityRequirement",
    "PreBronzeDataContract",
    "SyncStrategy",
    "WarehouseLayer",
    "BRONZE_CONTRACT_REGISTRY",
    "CANDIDATE_BRONZE_CONTRACT_REGISTRY",
    "DATA_CONTRACT_REGISTRY",
]


@dataclass(frozen=True, slots=True)
class PreBronzeDataContract:
    """Authoritative persistence contract for a Pre-Bronze warehouse dataset.

    Parameters
    ----------
    binding_id : SourceBindingId
        Authoritative physical source binding identity.
    physical_table : str
        PFETL-controlled physical table name in DuckDB (e.g. 'pre_bronze.sqlite_source__household_zcategory').
    sync_strategy : SyncStrategy, default=SyncStrategy.INCREMENTAL
        Warehouse synchronization mode (full-replace vs incremental).
    provenance_required : bool, default=True
        Whether rows must carry explicit operational provenance metadata.
    dataset_id : DatasetId | None, default=None
        Transitional canonical dataset identity. Removal Owner: Phase 055 (decommissioning legacy SourceDatasetConfig).
    """

    binding_id: SourceBindingId
    physical_table: str
    sync_strategy: SyncStrategy = SyncStrategy.INCREMENTAL
    provenance_required: bool = True
    dataset_id: DatasetId | None = None

    def __init__(
        self,
        binding_id: SourceBindingId | str | None = None,
        physical_table: str = "",
        sync_strategy: SyncStrategy = SyncStrategy.INCREMENTAL,
        provenance_required: bool = True,
        dataset_id: DatasetId | str | None = None,
    ) -> None:
        resolved_binding: SourceBindingId
        if binding_id is None and dataset_id is not None:
            raw_id = dataset_id.value if isinstance(dataset_id, DatasetId) else str(dataset_id)
            resolved_binding = SourceBindingId(raw_id)
        elif binding_id is not None:
            resolved_binding = SourceBindingId(str(binding_id))
        else:
            raise ValueError("PreBronzeDataContract requires either binding_id or dataset_id.")

        resolved_ds = (
            dataset_id
            if isinstance(dataset_id, DatasetId)
            else DatasetId(dataset_id)
            if dataset_id is not None
            else None
        )
        object.__setattr__(self, "binding_id", resolved_binding)
        object.__setattr__(self, "physical_table", physical_table)
        object.__setattr__(self, "sync_strategy", sync_strategy)
        object.__setattr__(self, "provenance_required", provenance_required)
        object.__setattr__(self, "dataset_id", resolved_ds)


@dataclass
class DataContract:
    """Publication contract for analytical Silver and Gold warehouse datasets."""

    dataset_id: DatasetId
    contract_id: str
    layer: str
    physical_table: str
    domain: str
    grain: str
    producer: str
    publication_order: int


_DATASET_SYNC_CATEGORY_MAP: dict[DatasetId, str] = {
    DatasetId.HOUSEHOLD_ZCATEGORY: "sqlite_source",
    DatasetId.HOUSEHOLD_ASSET_GROUP: "sqlite_source",
    DatasetId.HOUSEHOLD_ASSETS: "sqlite_source",
    DatasetId.HOUSEHOLD_CURRENCY: "sqlite_source",
    DatasetId.HOUSEHOLD_INOUTCOME: "sqlite_source",
    DatasetId.HOUSEHOLD_CATEGORIES: "sqlite_source",
    DatasetId.HOUSEHOLD_ASSET_CATEGORIES: "sqlite_source",
    DatasetId.HOUSEHOLD_ACCOUNTS: "sqlite_source",
    DatasetId.COMMON_CURRENCIES: "sqlite_source",
    DatasetId.HOUSEHOLD_TRANSACTIONS: "sqlite_source",
    DatasetId.HOUSEHOLD_ACCOUNT_BALANCES: "opening_balances",
    DatasetId.MARKET_STOCK_HOLDINGS: "stock_pl",
    DatasetId.MARKET_MF_HOLDINGS: "mf_holdings",
    DatasetId.INVESTMENT_STOCK_ORDERS: "stock_orders",
    DatasetId.INVESTMENT_MF_ORDERS: "mf_orders",
    DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS: "us_stock_transactions",
    DatasetId.INVESTMENT_MF_ISIN_MAPPING: "mf_isin",
    DatasetId.INVESTMENT_BENCHMARK_MAPPING: "benchmark_mapping",
    DatasetId.HOUSEHOLD_OPENING_BALANCES: "opening_balances",
    DatasetId.INVESTMENT_BENCHMARK_MASTER: "benchmark_master",
    DatasetId.INVESTMENT_MACRO_PARAMETERS: "macro_parameters",
    DatasetId.MARKET_CURRENCY_MAPPING: "currency_mapping",
    DatasetId.MARKET_CURRENCY_FX_RATES: "currency_history",
    DatasetId.MARKET_BENCHMARK_HISTORY: "benchmark_history",
    DatasetId.MARKET_US_STOCK_PRICES: "us_stock_market",
    DatasetId.COMMON_COLUMN_MASTER: "column_master",
}


@dataclass
class BronzeDataContract:
    """Canonical Bronze lakehouse contract."""

    dataset_id: DatasetId
    physical_table: str
    is_full_replace: bool
    identity_requirement: IdentityRequirement
    grain: str

    @property
    def sync_category(self) -> str:
        """Control Plane artifact synchronization category."""
        return _DATASET_SYNC_CATEGORY_MAP.get(self.dataset_id, self.dataset_id.value)


BRONZE_CONTRACT_REGISTRY: list[BronzeDataContract] = [
    BronzeDataContract(
        DatasetId.HOUSEHOLD_ZCATEGORY,
        "bronze.household_zcategory",
        True,
        IdentityRequirement.REQUIRED,
        "Household Category (Z_PK)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_ASSET_GROUP,
        "bronze.household_asset_group",
        True,
        IdentityRequirement.REQUIRED,
        "Household Asset Group (Z_PK)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_ASSETS,
        "bronze.household_assets",
        True,
        IdentityRequirement.REQUIRED,
        "Household Asset (Z_PK)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_CURRENCY,
        "bronze.household_currency",
        True,
        IdentityRequirement.REQUIRED,
        "Household Currency (Z_PK)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_INOUTCOME,
        "bronze.household_inoutcome",
        True,
        IdentityRequirement.REQUIRED,
        "Household Transaction (ZUID)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_MF_ISIN_MAPPING,
        "bronze.investment_mf_isin_mapping",
        True,
        IdentityRequirement.REQUIRED,
        "Mutual Fund Scheme Mapping (Scheme Name)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_BENCHMARK_MAPPING,
        "bronze.investment_benchmark_mapping",
        True,
        IdentityRequirement.REQUIRED,
        "Benchmark Asset Mapping (ISIN)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_OPENING_BALANCES,
        "bronze.household_opening_balances",
        True,
        IdentityRequirement.REQUIRED,
        "Asset Opening Balance (Account, Date)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_BENCHMARK_MASTER,
        "bronze.investment_benchmark_master",
        True,
        IdentityRequirement.REQUIRED,
        "Benchmark Definition (ID)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_MACRO_PARAMETERS,
        "bronze.investment_macro_parameters",
        True,
        IdentityRequirement.REQUIRED,
        "Financial Year Macro Parameter (FY)",
    ),
    BronzeDataContract(
        DatasetId.COMMON_COLUMN_MASTER,
        "bronze.common_column_master",
        True,
        IdentityRequirement.REQUIRED,
        "Canonical Column Specification (Physical Table, Canonical Column)",
    ),
    BronzeDataContract(
        DatasetId.MARKET_MF_HOLDINGS,
        "bronze.market_mf_holdings",
        False,
        IdentityRequirement.NONE,
        "Mutual Fund Holding Evidence Snapshot (Scheme, Folio, Date)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS,
        "bronze.investment_us_stock_transactions",
        False,
        IdentityRequirement.NONE,
        "US Stock Trade Evidence (Symbol, Date, Quantity, Price)",
    ),
    BronzeDataContract(
        DatasetId.MARKET_CURRENCY_MAPPING,
        "bronze.market_currency_mapping",
        True,
        IdentityRequirement.REQUIRED,
        "Currency Code Mapping (From Currency, To Currency)",
    ),
    BronzeDataContract(
        DatasetId.MARKET_CURRENCY_FX_RATES,
        "bronze.market_currency_fx_rates",
        False,
        IdentityRequirement.NONE,
        "Daily Currency FX Rate Time-Series (Base, Quote, Date)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_MF_ORDERS,
        "bronze.investment_mf_orders",
        False,
        IdentityRequirement.NONE,
        "Mutual Fund Order Evidence (Folio, Date, Units, Amount)",
    ),
    BronzeDataContract(
        DatasetId.MARKET_STOCK_HOLDINGS,
        "bronze.market_stock_holdings",
        False,
        IdentityRequirement.NONE,
        "Stock Holding Evidence Snapshot (Symbol, ISIN, Date)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_STOCK_ORDERS,
        "bronze.investment_stock_orders",
        False,
        IdentityRequirement.NONE,
        "Stock Trade Order Evidence (ISIN, Trade Date, Quantity, Price)",
    ),
    BronzeDataContract(
        DatasetId.MARKET_BENCHMARK_HISTORY,
        "bronze.market_benchmark_history",
        False,
        IdentityRequirement.NONE,
        "Daily Benchmark Valuation Time-Series (Benchmark Code, Date)",
    ),
    BronzeDataContract(
        DatasetId.MARKET_US_STOCK_PRICES,
        "bronze.market_us_stock_prices",
        False,
        IdentityRequirement.NONE,
        "Daily US Stock Closing Price Time-Series (Ticker, Date)",
    ),
]

# Candidate canonical contracts for Phase 052 household migration (parallel coexistence)
CANDIDATE_BRONZE_CONTRACT_REGISTRY: list[BronzeDataContract] = [
    BronzeDataContract(
        DatasetId.HOUSEHOLD_CATEGORIES,
        "bronze.household_categories",
        True,
        IdentityRequirement.REQUIRED,
        "Household Canonical Category (category_id)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_ASSET_CATEGORIES,
        "bronze.household_asset_categories",
        True,
        IdentityRequirement.REQUIRED,
        "Household Canonical Asset Category (asset_category_id)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_ACCOUNTS,
        "bronze.household_accounts",
        True,
        IdentityRequirement.REQUIRED,
        "Household Canonical Account (asset_id)",
    ),
    BronzeDataContract(
        DatasetId.COMMON_CURRENCIES,
        "bronze.common_currencies",
        True,
        IdentityRequirement.REQUIRED,
        "Common Currency (currency_id)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_TRANSACTIONS,
        "bronze.household_transactions",
        True,
        IdentityRequirement.REQUIRED,
        "Household Canonical Transaction (transaction_id)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_ACCOUNT_BALANCES,
        "bronze.household_account_balances",
        True,
        IdentityRequirement.REQUIRED,
        "Household Account Opening Balance (opening_balance_id)",
    ),
]

_DATASET_BASELINE_SOURCE_MAP: dict[DatasetId, str] = {
    DatasetId.HOUSEHOLD_ZCATEGORY: "household_db",
    DatasetId.HOUSEHOLD_ASSET_GROUP: "household_db",
    DatasetId.HOUSEHOLD_ASSETS: "household_db",
    DatasetId.HOUSEHOLD_CURRENCY: "household_db",
    DatasetId.HOUSEHOLD_INOUTCOME: "household_db",
    DatasetId.INVESTMENT_MF_ISIN_MAPPING: "mf_isin_csv",
    DatasetId.INVESTMENT_BENCHMARK_MAPPING: "benchmark_mapping_csv",
    DatasetId.HOUSEHOLD_OPENING_BALANCES: "opening_balance_csv",
    DatasetId.INVESTMENT_BENCHMARK_MASTER: "benchmark_master_csv",
    DatasetId.INVESTMENT_MACRO_PARAMETERS: "macro_parameters_csv",
    DatasetId.COMMON_COLUMN_MASTER: "column_master_csv",
    DatasetId.MARKET_MF_HOLDINGS: "mf_holdings_excel",
    DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS: "us_stock_transactions",
    DatasetId.MARKET_CURRENCY_MAPPING: "currency_mapping_csv",
    DatasetId.INVESTMENT_MF_ORDERS: "mf_orders_excel",
    DatasetId.MARKET_STOCK_HOLDINGS: "stock_pl_excel",
    DatasetId.INVESTMENT_STOCK_ORDERS: "stock_orders_excel",
}

# Authoritative registry for Pre-Bronze warehouse layer
PRE_BRONZE_CONTRACT_REGISTRY: list[PreBronzeDataContract] = [
    PreBronzeDataContract(
        binding_id=SourceBindingId(
            f"{_DATASET_BASELINE_SOURCE_MAP.get(b.dataset_id, 'provider_market_data')}__{b.dataset_id.value}"
        ),
        physical_table=(
            f"pre_bronze.{_DATASET_BASELINE_SOURCE_MAP.get(b.dataset_id, 'provider_market_data')}__{b.dataset_id.value}"
        ),
        sync_strategy=(
            SyncStrategy.FULL_REPLACE if b.is_full_replace else SyncStrategy.INCREMENTAL
        ),
        provenance_required=True,
        dataset_id=b.dataset_id,
    )
    for b in BRONZE_CONTRACT_REGISTRY
]

# Authoritative registry for Silver and Gold analytical layers
DATA_CONTRACT_REGISTRY: list[DataContract] = [
    # --- Silver Dimensions ---
    DataContract(
        DatasetId.COMMON_CALENDAR,
        "df_d_calendar",
        "silver",
        "silver.common_calendar",
        "Common",
        "Calendar Day (Date)",
        "CoreEngine",
        10,
    ),
    DataContract(
        DatasetId.WEALTH_INCOME_CATEGORY,
        "df_d_income_category",
        "silver",
        "silver.wealth_income_category",
        "Wealth",
        "Income Category (Category_Id)",
        "CoreEngine",
        20,
    ),
    DataContract(
        DatasetId.WEALTH_INCOME_SUBCATEGORY,
        "df_d_income_subcategory",
        "silver",
        "silver.wealth_income_subcategory",
        "Wealth",
        "Income Subcategory (Subcategory_Id)",
        "CoreEngine",
        30,
    ),
    DataContract(
        DatasetId.WEALTH_EXPENSE_CATEGORY,
        "df_d_expense_category",
        "silver",
        "silver.wealth_expense_category",
        "Wealth",
        "Expense Category (Category_Id)",
        "CoreEngine",
        40,
    ),
    DataContract(
        DatasetId.WEALTH_EXPENSE_SUBCATEGORY,
        "df_d_expense_subcategory",
        "silver",
        "silver.wealth_expense_subcategory",
        "Wealth",
        "Expense Subcategory (Subcategory_Id)",
        "CoreEngine",
        50,
    ),
    DataContract(
        DatasetId.WEALTH_ASSET_CATEGORY,
        "df_d_asset_category",
        "silver",
        "silver.wealth_asset_category",
        "Wealth",
        "Asset Category (Category_Id)",
        "CoreEngine",
        60,
    ),
    DataContract(
        DatasetId.WEALTH_ASSET_SUBCATEGORY,
        "df_d_asset_subcategory",
        "silver",
        "silver.wealth_asset_subcategory",
        "Wealth",
        "Asset Subcategory (Subcategory_Id)",
        "CoreEngine",
        70,
    ),
    DataContract(
        DatasetId.COMMON_CURRENCY,
        "df_d_currency",
        "silver",
        "silver.common_currency",
        "Common",
        "Currency Specification (Currency_Id)",
        "CoreEngine",
        80,
    ),
    DataContract(
        DatasetId.INVESTMENT_BENCHMARK_MASTER_DIM,
        "df_d_benchmark_master",
        "silver",
        "silver.investment_benchmark_master_dim",
        "Investments",
        "Benchmark Master Specification (Benchmark_Code)",
        "CoreEngine",
        90,
    ),
    DataContract(
        DatasetId.COMMON_CURRENCY_FX_RATES,
        "df_f_currency_fx_rates",
        "silver",
        "silver.common_currency_fx_rates",
        "Common",
        "Daily Currency Exchange Rate (Base_Currency, Target_Currency, Date)",
        "CoreEngine",
        95,
    ),
    DataContract(
        DatasetId.INVESTMENT_MASTER,
        "df_d_investment_master",
        "silver",
        "silver.investment_master",
        "Investments",
        "Security Master Instrument (ISIN)",
        "CoreEngine",
        100,
    ),
    DataContract(
        DatasetId.INVESTMENT_MACRO_PARAMETERS_DIM,
        "df_d_macro_parameters",
        "silver",
        "silver.investment_macro_parameters_dim",
        "Investments",
        "Financial Year Macro Assumptions (FY)",
        "CoreEngine",
        110,
    ),
    # --- Silver Facts ---
    DataContract(
        DatasetId.WEALTH_INCOME_TRANSACTIONS,
        "df_f_income_transactions",
        "silver",
        "silver.wealth_income_transactions",
        "Wealth",
        "Ledger Income Transaction (Tx_Id)",
        "CoreEngine",
        120,
    ),
    DataContract(
        DatasetId.WEALTH_EXPENSE_TRANSACTIONS,
        "df_f_expense_transactions",
        "silver",
        "silver.wealth_expense_transactions",
        "Wealth",
        "Ledger Expense Transaction (Tx_Id)",
        "CoreEngine",
        130,
    ),
    DataContract(
        DatasetId.WEALTH_TRANSFER_TRANSACTIONS,
        "df_f_transfer_transactions",
        "silver",
        "silver.wealth_transfer_transactions",
        "Wealth",
        "Ledger Account Transfer (Tx_Id)",
        "CoreEngine",
        140,
    ),
    DataContract(
        DatasetId.WEALTH_OPENING_BALANCES,
        "df_f_opening_balances",
        "silver",
        "silver.wealth_opening_balances",
        "Wealth",
        "Account Opening Balance (Asset_Id, Date)",
        "CoreEngine",
        150,
    ),
    DataContract(
        DatasetId.INVESTMENT_MARKET_DATA,
        "df_f_investment_market_data",
        "silver",
        "silver.investment_market_data",
        "Investments",
        "Investment Daily Market Quote (ISIN, Date)",
        "CoreEngine",
        160,
    ),
    DataContract(
        DatasetId.INVESTMENT_PURCHASE_DATA,
        "df_f_tf_inv_purchase",
        "silver",
        "silver.investment_purchase_data",
        "Investments",
        "Investment Buy Order (Trade_Id)",
        "CoreEngine",
        170,
    ),
    DataContract(
        DatasetId.INVESTMENT_SALE_DATA,
        "df_f_tf_inv_sale",
        "silver",
        "silver.investment_sale_data",
        "Investments",
        "Investment Sell Order (Trade_Id)",
        "CoreEngine",
        180,
    ),
    DataContract(
        DatasetId.INVESTMENT_BENCHMARK_DATA,
        "df_f_investment_benchmark_data",
        "silver",
        "silver.investment_benchmark_data",
        "Investments",
        "Daily Benchmark Valuation (Benchmark_Code, Date)",
        "CoreEngine",
        190,
    ),
    DataContract(
        DatasetId.INVESTMENT_LOT_ANALYTICS,
        "df_f_investment_analytics_lot",
        "silver",
        "silver.investment_lot_analytics",
        "Investments",
        "Tax Lot Position Snapshot (ISIN, Lot_Id, Closing_Date)",
        "InvestmentQuantEngine",
        200,
    ),
    DataContract(
        DatasetId.INVESTMENT_REALIZED_EVENTS,
        "df_f_investment_realized_events",
        "silver",
        "silver.investment_realized_events",
        "Investments",
        "Realized Capital Gain/Loss Event (Event_Id)",
        "InvestmentQuantEngine",
        205,
    ),
    DataContract(
        DatasetId.INVESTMENT_RECONCILIATION_EVENTS,
        "df_f_investment_reconciliation_events",
        "silver",
        "silver.investment_reconciliation_events",
        "Investments",
        "Investment Reconciliation Audit Event (Event_Id)",
        "InvestmentQuantEngine",
        206,
    ),
    DataContract(
        DatasetId.TAX_EVENTS,
        "df_f_tax_events",
        "silver",
        "silver.tax_events",
        "Taxes",
        "Tax Assessment Event (Event_Id)",
        "TaxEngine",
        300,
    ),
    # --- Gold Presentation ---
    DataContract(
        DatasetId.TAX_YEAR_SUMMARY,
        "df_p_tax_year_summary",
        "gold",
        "gold.tax_year_summary",
        "Taxes",
        "FY",
        "TaxEngine",
        302,
    ),
    DataContract(
        DatasetId.TAX_INCOME_BREAKDOWN,
        "df_p_tax_income_breakdown",
        "gold",
        "gold.tax_income_breakdown",
        "Taxes",
        "FY-Head-SubHead-Source",
        "TaxEngine",
        303,
    ),
    DataContract(
        DatasetId.TAX_RECONCILIATION,
        "df_p_tax_reconciliation",
        "gold",
        "gold.tax_reconciliation",
        "Taxes",
        "FY-SubHead",
        "TaxEngine",
        304,
    ),
    DataContract(
        DatasetId.WEALTH_CORE_MONTHLY,
        "df_p_tf_wealth_monthly_totals",
        "gold",
        "gold.wealth_core_monthly",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        110,
    ),
    DataContract(
        DatasetId.WEALTH_ASSET_BREAKDOWN,
        "df_p_tf_net_worth_monthly_summary",
        "gold",
        "gold.wealth_asset_breakdown",
        "Wealth",
        "Month-Asset",
        "WealthPresentationEngine",
        110,
    ),
    DataContract(
        DatasetId.WEALTH_CASHFLOW_EXPENSE_BREAKDOWN,
        "df_p_tf_category_spend_analytics",
        "gold",
        "gold.wealth_cashflow_expense_breakdown",
        "Wealth",
        "Month-ExpenseCategory",
        "WealthPresentationEngine",
        120,
    ),
    DataContract(
        DatasetId.WEALTH_CASHFLOW_INCOME_BREAKDOWN,
        "df_p_tf_income_streams_monthly",
        "gold",
        "gold.wealth_cashflow_income_breakdown",
        "Wealth",
        "Month-IncomeCategory",
        "WealthPresentationEngine",
        130,
    ),
    DataContract(
        DatasetId.FIRE_ANALYTICS,
        "df_p_tf_wealth_risk_analytics",
        "gold",
        "gold.fire_analytics",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        140,
    ),
    DataContract(
        DatasetId.WEALTH_BUDGET_VARIANCE,
        "df_p_tf_budget_forecast_monthly",
        "gold",
        "gold.wealth_budget_variance",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        160,
    ),
    DataContract(
        DatasetId.INVESTMENT_PORTFOLIO_SUMMARY,
        "df_p_tf_investment_analytics",
        "gold",
        "gold.investment_portfolio_summary",
        "Investments",
        "Month-ISIN",
        "InvestmentQuantEngine",
        170,
    ),
    DataContract(
        DatasetId.WEALTH_CASHFLOW_EFFICIENCY,
        "df_p_tf_monthly_cashflow_summary",
        "gold",
        "gold.wealth_cashflow_efficiency",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        180,
    ),
    DataContract(
        DatasetId.WEALTH_CASHFLOW_ACTIVITY_SUMMARY,
        "df_p_tf_cashflow_activity_summary",
        "gold",
        "gold.wealth_cashflow_activity_summary",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        190,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_ISIN,
        "df_f_investment_analytics_isin",
        "gold",
        "gold.investment_by_isin",
        "Investments",
        "Date-ISIN",
        "InvestmentQuantEngine",
        200,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_SUBTYPE,
        "df_f_investment_analytics_subtype",
        "gold",
        "gold.investment_by_subtype",
        "Investments",
        "Date-Subtype",
        "InvestmentQuantEngine",
        210,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_CLASS,
        "df_f_investment_analytics_class",
        "gold",
        "gold.investment_by_class",
        "Investments",
        "Date-Class",
        "InvestmentQuantEngine",
        220,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_INSTRUMENT_TYPE,
        "df_f_investment_analytics_instrument_type",
        "gold",
        "gold.investment_by_instrument_type",
        "Investments",
        "Date-InstrumentType",
        "InvestmentQuantEngine",
        230,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_SECTOR,
        "df_f_investment_analytics_sector",
        "gold",
        "gold.investment_by_sector",
        "Investments",
        "Date-Sector",
        "InvestmentQuantEngine",
        240,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_INDUSTRY,
        "df_f_investment_analytics_industry",
        "gold",
        "gold.investment_by_industry",
        "Investments",
        "Date-Industry",
        "InvestmentQuantEngine",
        250,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_PORTFOLIO,
        "df_f_investment_analytics_portfolio",
        "gold",
        "gold.investment_by_portfolio",
        "Investments",
        "Date",
        "InvestmentQuantEngine",
        260,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_GEO,
        "df_f_investment_analytics_geo",
        "gold",
        "gold.investment_by_geo",
        "Investments",
        "Date-Geo",
        "InvestmentQuantEngine",
        270,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_COUNTRY,
        "df_f_investment_analytics_country",
        "gold",
        "gold.investment_by_country",
        "Investments",
        "Date-Country",
        "InvestmentQuantEngine",
        280,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_CURRENCY,
        "df_f_investment_analytics_currency",
        "gold",
        "gold.investment_by_currency",
        "Investments",
        "Date-Currency",
        "InvestmentQuantEngine",
        290,
    ),
]
