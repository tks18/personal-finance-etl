from dataclasses import dataclass


@dataclass
class DataContract:
    contract_id: str
    layer: str
    physical_table: str
    domain: str
    grain: str
    producer: str
    publication_order: int


@dataclass
class BronzeDataContract:
    """Defines the relationship between raw extraction attributes, control plane sync categories, and physical DuckDB tables."""

    extraction_attribute: str
    sync_category: str
    physical_table: str
    is_full_replace: bool


BRONZE_CONTRACT_REGISTRY: list[BronzeDataContract] = [
    BronzeDataContract("zcategory", "sqlite_source", "bronze.r_SQLite_ZCategory", True),
    BronzeDataContract("assetgroup", "sqlite_source", "bronze.r_SQLite_AssetGroup", True),
    BronzeDataContract("assets", "sqlite_source", "bronze.r_SQLite_Assets", True),
    BronzeDataContract("currency", "sqlite_source", "bronze.r_SQLite_Currency", True),
    BronzeDataContract("inoutcome", "sqlite_source", "bronze.r_SQLite_InOutcome", True),
    BronzeDataContract("stg_mf_isin_mapping", "mf_isin", "bronze.r_MF_ISIN_Mapping", True),
    BronzeDataContract(
        "stg_benchmark_mapping", "benchmark_mapping", "bronze.r_Benchmark_Mapping", True
    ),
    BronzeDataContract(
        "raw_opening_balances", "opening_balances", "bronze.r_Opening_Balances", True
    ),
    BronzeDataContract(
        "raw_benchmark_master", "benchmark_master", "bronze.r_Benchmark_Master", True
    ),
    BronzeDataContract(
        "raw_macro_parameters", "macro_parameters", "bronze.r_Macro_Parameters", True
    ),
    BronzeDataContract("column_master", "column_master", "bronze.r_Column_Master", True),
    BronzeDataContract("mf_market_data_raw", "mf_holdings", "bronze.r_MF_Market_Data", False),
    BronzeDataContract("mf_transactions_raw", "mf_orders", "bronze.r_MF_Transactions", False),
    BronzeDataContract("stock_market_data_raw", "stock_pl", "bronze.r_Stock_Market_Data", False),
    BronzeDataContract(
        "stock_transactions_raw", "stock_orders", "bronze.r_Stock_Transactions", False
    ),
]

# A lightweight registry for Silver and Gold analytical layers
DATA_CONTRACT_REGISTRY: list[DataContract] = [
    # --- Silver Dimensions ---
    DataContract("df_d_calendar", "silver", "silver.d_Calendar", "Common", "Day", "CoreEngine", 10),
    DataContract(
        "df_d_income_category",
        "silver",
        "silver.d_Income_Category",
        "Wealth",
        "Category",
        "CoreEngine",
        20,
    ),
    DataContract(
        "df_d_income_subcategory",
        "silver",
        "silver.d_Income_Subcategory",
        "Wealth",
        "Subcategory",
        "CoreEngine",
        30,
    ),
    DataContract(
        "df_d_expense_category",
        "silver",
        "silver.d_Expense_Category",
        "Wealth",
        "Category",
        "CoreEngine",
        40,
    ),
    DataContract(
        "df_d_expense_subcategory",
        "silver",
        "silver.d_Expense_Subcategory",
        "Wealth",
        "Subcategory",
        "CoreEngine",
        50,
    ),
    DataContract(
        "df_d_asset_category",
        "silver",
        "silver.d_Asset_Category",
        "Wealth",
        "Category",
        "CoreEngine",
        60,
    ),
    DataContract(
        "df_d_asset_subcategory",
        "silver",
        "silver.d_Asset_SubCategory",
        "Wealth",
        "Subcategory",
        "CoreEngine",
        70,
    ),
    DataContract(
        "df_d_currency", "silver", "silver.d_Currency", "Common", "Currency", "CoreEngine", 80
    ),
    DataContract(
        "df_d_benchmark_master",
        "silver",
        "silver.d_Investment_Benchmark_Master",
        "Investments",
        "Benchmark",
        "CoreEngine",
        90,
    ),
    DataContract(
        "df_d_investment_master",
        "silver",
        "silver.d_Investment_Master",
        "Investments",
        "ISIN",
        "CoreEngine",
        100,
    ),
    DataContract(
        "df_d_macro_parameters",
        "silver",
        "silver.d_Macro_Parameters",
        "Investments",
        "FinancialYear",
        "CoreEngine",
        110,
    ),
    # --- Silver Facts ---
    DataContract(
        "df_f_income_transactions",
        "silver",
        "silver.f_Income_Transactions",
        "Wealth",
        "Transaction",
        "CoreEngine",
        120,
    ),
    DataContract(
        "df_f_expense_transactions",
        "silver",
        "silver.f_Expense_Transactions",
        "Wealth",
        "Transaction",
        "CoreEngine",
        130,
    ),
    DataContract(
        "df_f_transfer_transactions",
        "silver",
        "silver.f_Transfer_Transactions",
        "Wealth",
        "Transaction",
        "CoreEngine",
        140,
    ),
    DataContract(
        "df_f_opening_balances",
        "silver",
        "silver.f_Opening_Balances",
        "Wealth",
        "Balance",
        "CoreEngine",
        150,
    ),
    DataContract(
        "df_f_investment_market_data",
        "silver",
        "silver.f_Investment_Market_Data",
        "Investments",
        "Quote",
        "CoreEngine",
        160,
    ),
    DataContract(
        "df_f_tf_inv_purchase",
        "silver",
        "silver.f_Investment_Purchase_Data",
        "Investments",
        "Trade",
        "CoreEngine",
        170,
    ),
    DataContract(
        "df_f_tf_inv_sale",
        "silver",
        "silver.f_Investment_Sale_Data",
        "Investments",
        "Trade",
        "CoreEngine",
        180,
    ),
    DataContract(
        "df_f_investment_benchmark_data",
        "silver",
        "silver.f_Investment_Benchmark_Data",
        "Investments",
        "Quote",
        "CoreEngine",
        190,
    ),
    DataContract(
        "df_f_investment_analytics_lot",
        "silver",
        "silver.f_Investment_Analytics_Lot",
        "Investments",
        "ISIN-Lot",
        "InvestmentQuantEngine",
        200,
    ),
    # --- Gold Presentation ---
    DataContract(
        "df_p_tf_wealth_monthly_totals",
        "gold",
        "gold.Core_Monthly_Fact",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        110,
    ),
    DataContract(
        "df_p_tf_net_worth_monthly_summary",
        "gold",
        "gold.Wealth_Asset_Breakdown",
        "Wealth",
        "Month-Asset",
        "WealthPresentationEngine",
        110,
    ),
    DataContract(
        "df_p_tf_category_spend_analytics",
        "gold",
        "gold.Cashflow_Expense_Breakdown",
        "Wealth",
        "Month-ExpenseCategory",
        "WealthPresentationEngine",
        120,
    ),
    DataContract(
        "df_p_tf_income_streams_monthly",
        "gold",
        "gold.Cashflow_Income_Breakdown",
        "Wealth",
        "Month-IncomeCategory",
        "WealthPresentationEngine",
        130,
    ),
    DataContract(
        "df_p_tf_wealth_risk_analytics",
        "gold",
        "gold.Wealth_FIRE_Analytics",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        140,
    ),
    DataContract(
        "df_p_tf_tax_liability_forecast",
        "gold",
        "gold.Forecast_Tax_Liability",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        150,
    ),
    DataContract(
        "df_p_tf_budget_forecast_monthly",
        "gold",
        "gold.Forecast_Budget_Variance",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        160,
    ),
    DataContract(
        "df_p_tf_investment_analytics",
        "gold",
        "gold.Investment_Portfolio_Summary",
        "Investments",
        "Month-ISIN",
        "InvestmentQuantEngine",
        170,
    ),
    DataContract(
        "df_p_tf_monthly_cashflow_summary",
        "gold",
        "gold.Cashflow_Efficiency_Analytics",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        180,
    ),
    DataContract(
        "df_p_tf_cashflow_activity_summary",
        "gold",
        "gold.Cashflow_Activity_Summary",
        "Wealth",
        "Month",
        "WealthPresentationEngine",
        190,
    ),
    DataContract(
        "df_f_investment_analytics_isin",
        "gold",
        "gold.Investment_By_ISIN",
        "Investments",
        "Date-ISIN",
        "InvestmentQuantEngine",
        200,
    ),
    DataContract(
        "df_f_investment_analytics_subtype",
        "gold",
        "gold.Investment_By_Subtype",
        "Investments",
        "Date-Subtype",
        "InvestmentQuantEngine",
        210,
    ),
    DataContract(
        "df_f_investment_analytics_class",
        "gold",
        "gold.Investment_By_Class",
        "Investments",
        "Date-Class",
        "InvestmentQuantEngine",
        220,
    ),
    DataContract(
        "df_f_investment_analytics_instrument_type",
        "gold",
        "gold.Investment_By_Instrument_Type",
        "Investments",
        "Date-InstrumentType",
        "InvestmentQuantEngine",
        230,
    ),
    DataContract(
        "df_f_investment_analytics_sector",
        "gold",
        "gold.Investment_By_Sector",
        "Investments",
        "Date-Sector",
        "InvestmentQuantEngine",
        240,
    ),
    DataContract(
        "df_f_investment_analytics_industry",
        "gold",
        "gold.Investment_By_Industry",
        "Investments",
        "Date-Industry",
        "InvestmentQuantEngine",
        250,
    ),
    DataContract(
        "df_f_investment_analytics_portfolio",
        "gold",
        "gold.Investment_By_Portfolio",
        "Investments",
        "Date",
        "InvestmentQuantEngine",
        260,
    ),
]


def get_contract_by_table(physical_table: str) -> DataContract | None:
    for contract in DATA_CONTRACT_REGISTRY:
        if contract.physical_table.lower() == physical_table.lower():
            return contract
    return None
