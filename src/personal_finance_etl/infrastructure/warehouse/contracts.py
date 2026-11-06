"""Authoritative catalog of Pre-Bronze, Bronze, and Silver data lakehouse contracts.

Owns
----
- PreBronzeDataContract, BronzeDataContract, and DataContract dataclass definitions.
- Standard Pre-Bronze provenance column constants.
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

from personal_finance_etl.config.sources.change_detection import SyncStrategy
from personal_finance_etl.contracts.datasets import DatasetId, IdentityRequirement

# Standard Pre-Bronze operational provenance column names
PRE_BRONZE_ARTIFACT_ID: str = "__artifact_id__"
PRE_BRONZE_SOURCE_ID: str = "__source_id__"
PRE_BRONZE_DATASET_ID: str = "__dataset_id__"
PRE_BRONZE_PROVENANCE_COLUMNS: tuple[str, ...] = (
    PRE_BRONZE_ARTIFACT_ID,
    PRE_BRONZE_SOURCE_ID,
    PRE_BRONZE_DATASET_ID,
)

__all__ = [
    "PRE_BRONZE_ARTIFACT_ID",
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
    "BRONZE_CONTRACT_REGISTRY",
    "DATA_CONTRACT_REGISTRY",
]


@dataclass(frozen=True, slots=True)
class PreBronzeDataContract:
    """Authoritative persistence contract for a Pre-Bronze warehouse dataset.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical logical dataset identity.
    physical_table : str
        PFETL-controlled physical table name in DuckDB (e.g. 'pre_bronze.pb_household_zcategory').
    sync_strategy : SyncStrategy, default=SyncStrategy.INCREMENTAL
        Warehouse synchronization mode (full-replace vs incremental).
    provenance_required : bool, default=True
        Whether rows must carry explicit operational provenance metadata.
    """

    dataset_id: DatasetId
    physical_table: str
    sync_strategy: SyncStrategy = SyncStrategy.INCREMENTAL
    provenance_required: bool = True


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


@dataclass
class BronzeDataContract:
    """Relationship between extraction attributes, sync categories, and Bronze tables."""

    dataset_id: DatasetId
    extraction_attribute: str
    sync_category: str
    physical_table: str
    is_full_replace: bool
    identity_requirement: IdentityRequirement
    grain: str


BRONZE_CONTRACT_REGISTRY: list[BronzeDataContract] = [
    BronzeDataContract(
        DatasetId.HOUSEHOLD_ZCATEGORY,
        "zcategory",
        "sqlite_source",
        "bronze.r_SQLite_ZCategory",
        True,
        IdentityRequirement.REQUIRED,
        "Household Category (Z_PK)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_ASSET_GROUP,
        "assetgroup",
        "sqlite_source",
        "bronze.r_SQLite_AssetGroup",
        True,
        IdentityRequirement.REQUIRED,
        "Household Asset Group (Z_PK)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_ASSETS,
        "assets",
        "sqlite_source",
        "bronze.r_SQLite_Assets",
        True,
        IdentityRequirement.REQUIRED,
        "Household Asset (Z_PK)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_CURRENCY,
        "currency",
        "sqlite_source",
        "bronze.r_SQLite_Currency",
        True,
        IdentityRequirement.REQUIRED,
        "Household Currency (Z_PK)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_INOUTCOME,
        "inoutcome",
        "sqlite_source",
        "bronze.r_SQLite_InOutcome",
        True,
        IdentityRequirement.REQUIRED,
        "Household Transaction (ZUID)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_MF_ISIN_MAPPING,
        "stg_mf_isin_mapping",
        "mf_isin",
        "bronze.r_MF_ISIN_Mapping",
        True,
        IdentityRequirement.REQUIRED,
        "Mutual Fund Scheme Mapping (Scheme Name)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_BENCHMARK_MAPPING,
        "stg_benchmark_mapping",
        "benchmark_mapping",
        "bronze.r_Benchmark_Mapping",
        True,
        IdentityRequirement.REQUIRED,
        "Benchmark Asset Mapping (ISIN)",
    ),
    BronzeDataContract(
        DatasetId.HOUSEHOLD_OPENING_BALANCES,
        "raw_opening_balances",
        "opening_balances",
        "bronze.r_Opening_Balances",
        True,
        IdentityRequirement.REQUIRED,
        "Asset Opening Balance (Account, Date)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_BENCHMARK_MASTER,
        "raw_benchmark_master",
        "benchmark_master",
        "bronze.r_Benchmark_Master",
        True,
        IdentityRequirement.REQUIRED,
        "Benchmark Definition (ID)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_MACRO_PARAMETERS,
        "raw_macro_parameters",
        "macro_parameters",
        "bronze.r_Macro_Parameters",
        True,
        IdentityRequirement.REQUIRED,
        "Financial Year Macro Parameter (FY)",
    ),
    BronzeDataContract(
        DatasetId.COMMON_COLUMN_MASTER,
        "column_master",
        "column_master",
        "bronze.r_Column_Master",
        True,
        IdentityRequirement.REQUIRED,
        "Canonical Column Specification (Physical Table, Canonical Column)",
    ),
    BronzeDataContract(
        DatasetId.MARKET_MF_HOLDINGS,
        "mf_market_data_raw",
        "mf_holdings",
        "bronze.r_MF_Market_Data",
        False,
        IdentityRequirement.NONE,
        "Mutual Fund Holding Evidence Snapshot (Scheme, Folio, Date)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS,
        "us_stock_transactions_raw",
        "us_stock_transactions",
        "bronze.r_US_Stock_Transactions",
        False,
        IdentityRequirement.NONE,
        "US Stock Trade Evidence (Symbol, Date, Quantity, Price)",
    ),
    BronzeDataContract(
        DatasetId.MARKET_CURRENCY_MAPPING,
        "currency_mapping_raw",
        "currency_mapping",
        "bronze.r_Currency_Mapping",
        True,
        IdentityRequirement.REQUIRED,
        "Currency Code Mapping (From Currency, To Currency)",
    ),
    BronzeDataContract(
        DatasetId.MARKET_CURRENCY_FX_RATES,
        "currency_fx_raw",
        "currency_history",
        "bronze.r_Currency_FX_Data",
        False,
        IdentityRequirement.NONE,
        "Daily Currency FX Rate Time-Series (Base, Quote, Date)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_MF_ORDERS,
        "mf_transactions_raw",
        "mf_orders",
        "bronze.r_MF_Transactions",
        False,
        IdentityRequirement.NONE,
        "Mutual Fund Order Evidence (Folio, Date, Units, Amount)",
    ),
    BronzeDataContract(
        DatasetId.MARKET_STOCK_HOLDINGS,
        "stock_market_data_raw",
        "stock_pl",
        "bronze.r_Stock_Market_Data",
        False,
        IdentityRequirement.NONE,
        "Stock Holding Evidence Snapshot (Symbol, ISIN, Date)",
    ),
    BronzeDataContract(
        DatasetId.INVESTMENT_STOCK_ORDERS,
        "stock_transactions_raw",
        "stock_orders",
        "bronze.r_Stock_Transactions",
        False,
        IdentityRequirement.NONE,
        "Stock Trade Order Evidence (ISIN, Trade Date, Quantity, Price)",
    ),
    BronzeDataContract(
        DatasetId.MARKET_BENCHMARK_HISTORY,
        "benchmark_history_raw",
        "benchmark_history",
        "bronze.r_Benchmark_Data",
        False,
        IdentityRequirement.NONE,
        "Daily Benchmark Valuation Time-Series (Benchmark Code, Date)",
    ),
    BronzeDataContract(
        DatasetId.MARKET_US_STOCK_PRICES,
        "us_stock_market_data_raw",
        "us_stock_market",
        "bronze.r_US_Stock_Prices",
        False,
        IdentityRequirement.NONE,
        "Daily US Stock Closing Price Time-Series (Ticker, Date)",
    ),
]

# Authoritative registry for Pre-Bronze warehouse layer
PRE_BRONZE_CONTRACT_REGISTRY: list[PreBronzeDataContract] = [
    PreBronzeDataContract(
        dataset_id=b.dataset_id,
        physical_table=f"pre_bronze.pb_{b.dataset_id.value}",
        sync_strategy=(
            SyncStrategy.FULL_REPLACE if b.is_full_replace else SyncStrategy.INCREMENTAL
        ),
        provenance_required=True,
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
        "silver.d_Calendar",
        "Common",
        "Calendar Day (Date)",
        "CoreEngine",
        10,
    ),
    DataContract(
        DatasetId.WEALTH_INCOME_CATEGORY,
        "df_d_income_category",
        "silver",
        "silver.d_Income_Category",
        "Wealth",
        "Income Category (Category_Id)",
        "CoreEngine",
        20,
    ),
    DataContract(
        DatasetId.WEALTH_INCOME_SUBCATEGORY,
        "df_d_income_subcategory",
        "silver",
        "silver.d_Income_Subcategory",
        "Wealth",
        "Income Subcategory (Subcategory_Id)",
        "CoreEngine",
        30,
    ),
    DataContract(
        DatasetId.WEALTH_EXPENSE_CATEGORY,
        "df_d_expense_category",
        "silver",
        "silver.d_Expense_Category",
        "Wealth",
        "Expense Category (Category_Id)",
        "CoreEngine",
        40,
    ),
    DataContract(
        DatasetId.WEALTH_EXPENSE_SUBCATEGORY,
        "df_d_expense_subcategory",
        "silver",
        "silver.d_Expense_Subcategory",
        "Wealth",
        "Expense Subcategory (Subcategory_Id)",
        "CoreEngine",
        50,
    ),
    DataContract(
        DatasetId.WEALTH_ASSET_CATEGORY,
        "df_d_asset_category",
        "silver",
        "silver.d_Asset_Category",
        "Wealth",
        "Asset Category (Category_Id)",
        "CoreEngine",
        60,
    ),
    DataContract(
        DatasetId.WEALTH_ASSET_SUBCATEGORY,
        "df_d_asset_subcategory",
        "silver",
        "silver.d_Asset_SubCategory",
        "Wealth",
        "Asset Subcategory (Subcategory_Id)",
        "CoreEngine",
        70,
    ),
    DataContract(
        DatasetId.COMMON_CURRENCY,
        "df_d_currency",
        "silver",
        "silver.d_Currency",
        "Common",
        "Currency Specification (Currency_Id)",
        "CoreEngine",
        80,
    ),
    DataContract(
        DatasetId.INVESTMENT_BENCHMARK_MASTER_DIM,
        "df_d_benchmark_master",
        "silver",
        "silver.d_Investment_Benchmark_Master",
        "Investments",
        "Benchmark Master Specification (Benchmark_Code)",
        "CoreEngine",
        90,
    ),
    DataContract(
        DatasetId.COMMON_CURRENCY_FX_RATES,
        "df_f_currency_fx_rates",
        "silver",
        "silver.f_Currency_FX_Rates",
        "Common",
        "Daily Currency Exchange Rate (Base_Currency, Target_Currency, Date)",
        "CoreEngine",
        95,
    ),
    DataContract(
        DatasetId.INVESTMENT_MASTER,
        "df_d_investment_master",
        "silver",
        "silver.d_Investment_Master",
        "Investments",
        "Security Master Instrument (ISIN)",
        "CoreEngine",
        100,
    ),
    DataContract(
        DatasetId.INVESTMENT_MACRO_PARAMETERS_DIM,
        "df_d_macro_parameters",
        "silver",
        "silver.d_Macro_Parameters",
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
        "silver.f_Income_Transactions",
        "Wealth",
        "Ledger Income Transaction (Tx_Id)",
        "CoreEngine",
        120,
    ),
    DataContract(
        DatasetId.WEALTH_EXPENSE_TRANSACTIONS,
        "df_f_expense_transactions",
        "silver",
        "silver.f_Expense_Transactions",
        "Wealth",
        "Ledger Expense Transaction (Tx_Id)",
        "CoreEngine",
        130,
    ),
    DataContract(
        DatasetId.WEALTH_TRANSFER_TRANSACTIONS,
        "df_f_transfer_transactions",
        "silver",
        "silver.f_Transfer_Transactions",
        "Wealth",
        "Ledger Account Transfer (Tx_Id)",
        "CoreEngine",
        140,
    ),
    DataContract(
        DatasetId.WEALTH_OPENING_BALANCES,
        "df_f_opening_balances",
        "silver",
        "silver.f_Opening_Balances",
        "Wealth",
        "Account Opening Balance (Asset_Id, Date)",
        "CoreEngine",
        150,
    ),
    DataContract(
        DatasetId.INVESTMENT_MARKET_DATA,
        "df_f_investment_market_data",
        "silver",
        "silver.f_Investment_Market_Data",
        "Investments",
        "Investment Daily Market Quote (ISIN, Date)",
        "CoreEngine",
        160,
    ),
    DataContract(
        DatasetId.INVESTMENT_PURCHASE_DATA,
        "df_f_tf_inv_purchase",
        "silver",
        "silver.f_Investment_Purchase_Data",
        "Investments",
        "Investment Buy Order (Trade_Id)",
        "CoreEngine",
        170,
    ),
    DataContract(
        DatasetId.INVESTMENT_SALE_DATA,
        "df_f_tf_inv_sale",
        "silver",
        "silver.f_Investment_Sale_Data",
        "Investments",
        "Investment Sell Order (Trade_Id)",
        "CoreEngine",
        180,
    ),
    DataContract(
        DatasetId.INVESTMENT_BENCHMARK_DATA,
        "df_f_investment_benchmark_data",
        "silver",
        "silver.f_Investment_Benchmark_Data",
        "Investments",
        "Daily Benchmark Valuation (Benchmark_Code, Date)",
        "CoreEngine",
        190,
    ),
    DataContract(
        DatasetId.INVESTMENT_LOT_ANALYTICS,
        "df_f_investment_analytics_lot",
        "silver",
        "silver.f_Investment_Analytics_Lot",
        "Investments",
        "Tax Lot Position Snapshot (ISIN, Lot_Id, Closing_Date)",
        "InvestmentQuantEngine",
        200,
    ),
    DataContract(
        DatasetId.INVESTMENT_REALIZED_EVENTS,
        "df_f_investment_realized_events",
        "silver",
        "silver.f_Investment_Realized_Events",
        "Investments",
        "Realized Capital Gain/Loss Event (Event_Id)",
        "InvestmentQuantEngine",
        205,
    ),
    DataContract(
        DatasetId.INVESTMENT_RECONCILIATION_EVENTS,
        "df_f_investment_reconciliation_events",
        "silver",
        "silver.f_Investment_Reconciliation_Events",
        "Investments",
        "Investment Reconciliation Audit Event (Event_Id)",
        "InvestmentQuantEngine",
        206,
    ),
    DataContract(
        DatasetId.TAX_EVENTS,
        "df_f_tax_events",
        "silver",
        "silver.f_Tax_Events",
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
        "gold.Tax_Year_Summary",
        "Taxes",
        "FY",
        "TaxEngine",
        302,
    ),
    DataContract(
        DatasetId.TAX_INCOME_BREAKDOWN,
        "df_p_tax_income_breakdown",
        "gold",
        "gold.Tax_Income_Breakdown",
        "Taxes",
        "FY-Head-SubHead-Source",
        "TaxEngine",
        303,
    ),
    DataContract(
        DatasetId.TAX_RECONCILIATION,
        "df_p_tax_reconciliation",
        "gold",
        "gold.Tax_Reconciliation",
        "Taxes",
        "FY-SubHead",
        "TaxEngine",
        304,
    ),
    DataContract(
        DatasetId.WEALTH_CORE_MONTHLY,
        "df_p_tf_wealth_monthly_totals",
        "gold",
        "gold.Core_Monthly_Fact",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        110,
    ),
    DataContract(
        DatasetId.WEALTH_ASSET_BREAKDOWN,
        "df_p_tf_net_worth_monthly_summary",
        "gold",
        "gold.Wealth_Asset_Breakdown",
        "Wealth",
        "Month-Asset",
        "WealthPresentationEngine",
        110,
    ),
    DataContract(
        DatasetId.WEALTH_CASHFLOW_EXPENSE_BREAKDOWN,
        "df_p_tf_category_spend_analytics",
        "gold",
        "gold.Cashflow_Expense_Breakdown",
        "Wealth",
        "Month-ExpenseCategory",
        "WealthPresentationEngine",
        120,
    ),
    DataContract(
        DatasetId.WEALTH_CASHFLOW_INCOME_BREAKDOWN,
        "df_p_tf_income_streams_monthly",
        "gold",
        "gold.Cashflow_Income_Breakdown",
        "Wealth",
        "Month-IncomeCategory",
        "WealthPresentationEngine",
        130,
    ),
    DataContract(
        DatasetId.FIRE_ANALYTICS,
        "df_p_tf_wealth_risk_analytics",
        "gold",
        "gold.Wealth_FIRE_Analytics",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        140,
    ),
    DataContract(
        DatasetId.WEALTH_BUDGET_VARIANCE,
        "df_p_tf_budget_forecast_monthly",
        "gold",
        "gold.Forecast_Budget_Variance",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        160,
    ),
    DataContract(
        DatasetId.INVESTMENT_PORTFOLIO_SUMMARY,
        "df_p_tf_investment_analytics",
        "gold",
        "gold.Investment_Portfolio_Summary",
        "Investments",
        "Month-ISIN",
        "InvestmentQuantEngine",
        170,
    ),
    DataContract(
        DatasetId.WEALTH_CASHFLOW_EFFICIENCY,
        "df_p_tf_monthly_cashflow_summary",
        "gold",
        "gold.Cashflow_Efficiency_Analytics",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        180,
    ),
    DataContract(
        DatasetId.WEALTH_CASHFLOW_ACTIVITY_SUMMARY,
        "df_p_tf_cashflow_activity_summary",
        "gold",
        "gold.Cashflow_Activity_Summary",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        190,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_ISIN,
        "df_f_investment_analytics_isin",
        "gold",
        "gold.Investment_By_ISIN",
        "Investments",
        "Date-ISIN",
        "InvestmentQuantEngine",
        200,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_SUBTYPE,
        "df_f_investment_analytics_subtype",
        "gold",
        "gold.Investment_By_Subtype",
        "Investments",
        "Date-Subtype",
        "InvestmentQuantEngine",
        210,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_CLASS,
        "df_f_investment_analytics_class",
        "gold",
        "gold.Investment_By_Class",
        "Investments",
        "Date-Class",
        "InvestmentQuantEngine",
        220,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_INSTRUMENT_TYPE,
        "df_f_investment_analytics_instrument_type",
        "gold",
        "gold.Investment_By_Instrument_Type",
        "Investments",
        "Date-InstrumentType",
        "InvestmentQuantEngine",
        230,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_SECTOR,
        "df_f_investment_analytics_sector",
        "gold",
        "gold.Investment_By_Sector",
        "Investments",
        "Date-Sector",
        "InvestmentQuantEngine",
        240,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_INDUSTRY,
        "df_f_investment_analytics_industry",
        "gold",
        "gold.Investment_By_Industry",
        "Investments",
        "Date-Industry",
        "InvestmentQuantEngine",
        250,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_PORTFOLIO,
        "df_f_investment_analytics_portfolio",
        "gold",
        "gold.Investment_By_Portfolio",
        "Investments",
        "Date",
        "InvestmentQuantEngine",
        260,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_GEO,
        "df_f_investment_analytics_geo",
        "gold",
        "gold.Investment_By_Geo",
        "Investments",
        "Date-Geo",
        "InvestmentQuantEngine",
        270,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_COUNTRY,
        "df_f_investment_analytics_country",
        "gold",
        "gold.Investment_By_Country",
        "Investments",
        "Date-Country",
        "InvestmentQuantEngine",
        280,
    ),
    DataContract(
        DatasetId.INVESTMENT_BY_CURRENCY,
        "df_f_investment_analytics_currency",
        "gold",
        "gold.Investment_By_Currency",
        "Investments",
        "Date-Currency",
        "InvestmentQuantEngine",
        290,
    ),
]
