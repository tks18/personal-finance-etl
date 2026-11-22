"""Authoritative catalog of Bronze and Silver data lakehouse contracts.

Owns
----
- DataContract and BronzeDataContract dataclass definitions.
- BRONZE_CONTRACT_REGISTRY: Catalog of Bronze ingestion layer contracts.
- DATA_CONTRACT_REGISTRY: Catalog of Silver and Gold analytical presentation contracts.

Does not own
-------------
- DDL generation and catalog validation logic (owned by infrastructure.warehouse.registry).
- Table upsert execution (owned by infrastructure.warehouse.bronze/silver).
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "BronzeDataContract",
    "DataContract",
    "BRONZE_CONTRACT_REGISTRY",
    "DATA_CONTRACT_REGISTRY",
]


@dataclass
class DataContract:
    """Publication contract for analytical Silver and Gold warehouse datasets."""

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

    extraction_attribute: str
    sync_category: str
    physical_table: str
    is_full_replace: bool


BRONZE_CONTRACT_REGISTRY: list[BronzeDataContract] = [
    BronzeDataContract("household_zcategory", "sqlite_source", "bronze.household_zcategory", True),
    BronzeDataContract(
        "household_asset_group", "sqlite_source", "bronze.household_asset_group", True
    ),
    BronzeDataContract("household_assets", "sqlite_source", "bronze.household_assets", True),
    BronzeDataContract("household_currency", "sqlite_source", "bronze.household_currency", True),
    BronzeDataContract("household_inoutcome", "sqlite_source", "bronze.household_inoutcome", True),
    BronzeDataContract("column_master", "column_master", "bronze.column_master", True),
    BronzeDataContract(
        "mutual_fund_instrument_mapping",
        "mutual_fund_instrument_mapping",
        "bronze.mutual_fund_instrument_mapping",
        True,
    ),
    BronzeDataContract(
        "instrument_master",
        "instrument_master",
        "bronze.instrument_master",
        True,
    ),
    BronzeDataContract("opening_balances", "opening_balances", "bronze.opening_balances", True),
    BronzeDataContract("benchmark_master", "benchmark_master", "bronze.benchmark_master", True),
    BronzeDataContract(
        "financial_year_parameters",
        "financial_year_parameters",
        "bronze.financial_year_parameters",
        True,
    ),
    BronzeDataContract(
        "currency_reference",
        "currency_reference",
        "bronze.currency_reference",
        True,
    ),
    BronzeDataContract("mf_market_data", "mf_holdings", "bronze.mf_market_data", False),
    BronzeDataContract("mf_transactions", "mf_orders", "bronze.mf_transactions", False),
    BronzeDataContract("stock_market_data", "stock_pl", "bronze.stock_market_data", False),
    BronzeDataContract("stock_transactions", "stock_orders", "bronze.stock_transactions", False),
    BronzeDataContract(
        "us_stock_transactions",
        "us_stock_transactions",
        "bronze.us_stock_transactions",
        False,
    ),
    BronzeDataContract("currency_fx_rates", "currency_history", "bronze.currency_fx_rates", False),
    BronzeDataContract("benchmark_history", "benchmark_history", "bronze.benchmark_history", False),
    BronzeDataContract("us_stock_prices", "us_stock_market", "bronze.us_stock_prices", False),
]

# Lightweight registry for Silver and Gold analytical layers
DATA_CONTRACT_REGISTRY: list[DataContract] = [
    # --- Silver Dimensions ---
    DataContract(
        "df_d_calendar", "silver", "silver.dim_calendar", "Common", "Day", "CoreEngine", 10
    ),
    DataContract(
        "df_d_income_category",
        "silver",
        "silver.dim_income_category",
        "Wealth",
        "Category",
        "CoreEngine",
        20,
    ),
    DataContract(
        "df_d_income_subcategory",
        "silver",
        "silver.dim_income_subcategory",
        "Wealth",
        "Subcategory",
        "CoreEngine",
        30,
    ),
    DataContract(
        "df_d_expense_category",
        "silver",
        "silver.dim_expense_category",
        "Wealth",
        "Category",
        "CoreEngine",
        40,
    ),
    DataContract(
        "df_d_expense_subcategory",
        "silver",
        "silver.dim_expense_subcategory",
        "Wealth",
        "Subcategory",
        "CoreEngine",
        50,
    ),
    DataContract(
        "df_d_asset_category",
        "silver",
        "silver.dim_asset_category",
        "Wealth",
        "Category",
        "CoreEngine",
        60,
    ),
    DataContract(
        "df_d_asset_subcategory",
        "silver",
        "silver.dim_asset_subcategory",
        "Wealth",
        "Subcategory",
        "CoreEngine",
        70,
    ),
    DataContract(
        "df_d_currency", "silver", "silver.dim_currency", "Common", "Currency", "CoreEngine", 80
    ),
    DataContract(
        "df_d_benchmark_master",
        "silver",
        "silver.dim_benchmark_master",
        "Investments",
        "Benchmark",
        "CoreEngine",
        90,
    ),
    DataContract(
        "df_f_currency_fx_rates",
        "silver",
        "silver.fact_currency_fx_rates",
        "Common",
        "Date-Currency",
        "CoreEngine",
        95,
    ),
    DataContract(
        "df_d_investment_master",
        "silver",
        "silver.dim_instrument_master",
        "Investments",
        "ISIN",
        "CoreEngine",
        100,
    ),
    DataContract(
        "df_d_macro_parameters",
        "silver",
        "silver.ref_financial_year_parameters",
        "Investments",
        "FinancialYear",
        "CoreEngine",
        110,
    ),
    # --- Silver Facts ---
    DataContract(
        "df_f_income_transactions",
        "silver",
        "silver.fact_income_transactions",
        "Wealth",
        "Transaction",
        "CoreEngine",
        120,
    ),
    DataContract(
        "df_f_expense_transactions",
        "silver",
        "silver.fact_expense_transactions",
        "Wealth",
        "Transaction",
        "CoreEngine",
        130,
    ),
    DataContract(
        "df_f_transfer_transactions",
        "silver",
        "silver.fact_transfer_transactions",
        "Wealth",
        "Transaction",
        "CoreEngine",
        140,
    ),
    DataContract(
        "df_f_opening_balances",
        "silver",
        "silver.fact_opening_balances",
        "Wealth",
        "Balance",
        "CoreEngine",
        150,
    ),
    DataContract(
        "df_f_investment_market_data",
        "silver",
        "silver.fact_investment_market_data",
        "Investments",
        "Quote",
        "CoreEngine",
        160,
    ),
    DataContract(
        "df_f_tf_inv_purchase",
        "silver",
        "silver.fact_investment_purchases",
        "Investments",
        "Trade",
        "CoreEngine",
        170,
    ),
    DataContract(
        "df_f_tf_inv_sale",
        "silver",
        "silver.fact_investment_sales",
        "Investments",
        "Trade",
        "CoreEngine",
        180,
    ),
    DataContract(
        "df_f_investment_benchmark_data",
        "silver",
        "silver.fact_investment_benchmark_data",
        "Investments",
        "Quote",
        "CoreEngine",
        190,
    ),
    DataContract(
        "df_f_investment_analytics_lot",
        "silver",
        "silver.fact_investment_lot_analytics",
        "Investments",
        "ISIN-Lot",
        "InvestmentQuantEngine",
        200,
    ),
    DataContract(
        "df_f_investment_realized_events",
        "silver",
        "silver.fact_investment_realized_events",
        "Investments",
        "RealizedEvent",
        "InvestmentQuantEngine",
        205,
    ),
    DataContract(
        "df_f_investment_reconciliation_events",
        "silver",
        "silver.fact_investment_reconciliation_events",
        "Investments",
        "ReconEvent",
        "InvestmentQuantEngine",
        206,
    ),
    DataContract(
        "df_f_tax_events",
        "silver",
        "silver.fact_tax_events",
        "Taxes",
        "TaxEvent",
        "TaxEngine",
        300,
    ),
    # --- Gold Presentation ---
    DataContract(
        "df_p_tax_year_summary",
        "gold",
        "gold.Tax_Year_Summary",
        "Taxes",
        "FY",
        "TaxEngine",
        302,
    ),
    DataContract(
        "df_p_tax_income_breakdown",
        "gold",
        "gold.Tax_Income_Breakdown",
        "Taxes",
        "FY-Head-SubHead-Source",
        "TaxEngine",
        303,
    ),
    DataContract(
        "df_p_tax_reconciliation",
        "gold",
        "gold.Tax_Reconciliation",
        "Taxes",
        "FY-SubHead",
        "TaxEngine",
        304,
    ),
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
    DataContract(
        "df_f_investment_analytics_geo",
        "gold",
        "gold.Investment_By_Geo",
        "Investments",
        "Date-Geo",
        "InvestmentQuantEngine",
        270,
    ),
    DataContract(
        "df_f_investment_analytics_country",
        "gold",
        "gold.Investment_By_Country",
        "Investments",
        "Date-Country",
        "InvestmentQuantEngine",
        280,
    ),
    DataContract(
        "df_f_investment_analytics_currency",
        "gold",
        "gold.Investment_By_Currency",
        "Investments",
        "Date-Currency",
        "InvestmentQuantEngine",
        290,
    ),
]
