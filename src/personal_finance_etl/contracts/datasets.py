"""Authoritative canonical dataset identifiers for lakehouse contracts.

Owns
----
- DatasetId: Closed string-serializable enum vocabulary identifying all canonical datasets.

Does not own
------------
- Physical table mapping or schemas (owned by infrastructure.warehouse).
- Extraction batch logic (owned by contracts.extraction).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["DatasetId"]


class DatasetId(StrEnum):
    """Authoritative logical identifier for all canonical PFETL datasets."""

    # --- Household Evidence & Dimensions (Bronze / Silver) ---
    HOUSEHOLD_ZCATEGORY = "household_zcategory"
    HOUSEHOLD_ASSET_GROUP = "household_asset_group"
    HOUSEHOLD_ASSETS = "household_assets"
    HOUSEHOLD_CURRENCY = "household_currency"
    HOUSEHOLD_INOUTCOME = "household_inoutcome"
    HOUSEHOLD_OPENING_BALANCES = "household_opening_balances"

    # --- Investment Master & Evidence (Bronze) ---
    INVESTMENT_MF_ISIN_MAPPING = "investment_mf_isin_mapping"
    INVESTMENT_BENCHMARK_MAPPING = "investment_benchmark_mapping"
    INVESTMENT_BENCHMARK_MASTER = "investment_benchmark_master"
    INVESTMENT_MACRO_PARAMETERS = "investment_macro_parameters"
    INVESTMENT_US_STOCK_TRANSACTIONS = "investment_us_stock_transactions"
    INVESTMENT_MF_ORDERS = "investment_mf_orders"
    INVESTMENT_STOCK_ORDERS = "investment_stock_orders"

    # --- Market Evidence (Bronze) ---
    MARKET_MF_HOLDINGS = "market_mf_holdings"
    MARKET_CURRENCY_MAPPING = "market_currency_mapping"
    MARKET_CURRENCY_FX_RATES = "market_currency_fx_rates"
    MARKET_STOCK_HOLDINGS = "market_stock_holdings"
    MARKET_BENCHMARK_HISTORY = "market_benchmark_history"
    MARKET_US_STOCK_PRICES = "market_us_stock_prices"

    # --- Common / Transitional Evidence (Bronze) ---
    COMMON_COLUMN_MASTER = "common_column_master"

    # --- Silver Dimensions ---
    COMMON_CALENDAR = "common_calendar"
    WEALTH_INCOME_CATEGORY = "wealth_income_category"
    WEALTH_INCOME_SUBCATEGORY = "wealth_income_subcategory"
    WEALTH_EXPENSE_CATEGORY = "wealth_expense_category"
    WEALTH_EXPENSE_SUBCATEGORY = "wealth_expense_subcategory"
    WEALTH_ASSET_CATEGORY = "wealth_asset_category"
    WEALTH_ASSET_SUBCATEGORY = "wealth_asset_subcategory"
    COMMON_CURRENCY = "common_currency"
    INVESTMENT_BENCHMARK_MASTER_DIM = "investment_benchmark_master_dim"
    COMMON_CURRENCY_FX_RATES = "common_currency_fx_rates"
    INVESTMENT_MASTER = "investment_master"
    INVESTMENT_MACRO_PARAMETERS_DIM = "investment_macro_parameters_dim"

    # --- Silver Facts ---
    WEALTH_INCOME_TRANSACTIONS = "wealth_income_transactions"
    WEALTH_EXPENSE_TRANSACTIONS = "wealth_expense_transactions"
    WEALTH_TRANSFER_TRANSACTIONS = "wealth_transfer_transactions"
    WEALTH_OPENING_BALANCES = "wealth_opening_balances"
    INVESTMENT_MARKET_DATA = "investment_market_data"
    INVESTMENT_PURCHASE_DATA = "investment_purchase_data"
    INVESTMENT_SALE_DATA = "investment_sale_data"
    INVESTMENT_BENCHMARK_DATA = "investment_benchmark_data"
    INVESTMENT_LOT_ANALYTICS = "investment_lot_analytics"
    INVESTMENT_REALIZED_EVENTS = "investment_realized_events"
    INVESTMENT_RECONCILIATION_EVENTS = "investment_reconciliation_events"
    TAX_EVENTS = "tax_events"

    # --- Gold Presentation ---
    TAX_YEAR_SUMMARY = "tax_year_summary"
    TAX_INCOME_BREAKDOWN = "tax_income_breakdown"
    TAX_RECONCILIATION = "tax_reconciliation"
    WEALTH_CORE_MONTHLY = "wealth_core_monthly"
    WEALTH_ASSET_BREAKDOWN = "wealth_asset_breakdown"
    WEALTH_CASHFLOW_EXPENSE_BREAKDOWN = "wealth_cashflow_expense_breakdown"
    WEALTH_CASHFLOW_INCOME_BREAKDOWN = "wealth_cashflow_income_breakdown"
    FIRE_ANALYTICS = "fire_analytics"
    WEALTH_BUDGET_VARIANCE = "wealth_budget_variance"
    INVESTMENT_PORTFOLIO_SUMMARY = "investment_portfolio_summary"
    WEALTH_CASHFLOW_EFFICIENCY = "wealth_cashflow_efficiency"
    WEALTH_CASHFLOW_ACTIVITY_SUMMARY = "wealth_cashflow_activity_summary"
    INVESTMENT_BY_ISIN = "investment_by_isin"
    INVESTMENT_BY_SUBTYPE = "investment_by_subtype"
    INVESTMENT_BY_CLASS = "investment_by_class"
    INVESTMENT_BY_INSTRUMENT_TYPE = "investment_by_instrument_type"
    INVESTMENT_BY_SECTOR = "investment_by_sector"
    INVESTMENT_BY_INDUSTRY = "investment_by_industry"
    INVESTMENT_BY_PORTFOLIO = "investment_by_portfolio"
    INVESTMENT_BY_GEO = "investment_by_geo"
    INVESTMENT_BY_COUNTRY = "investment_by_country"
    INVESTMENT_BY_CURRENCY = "investment_by_currency"
