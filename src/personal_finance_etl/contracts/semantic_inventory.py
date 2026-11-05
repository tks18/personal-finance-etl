"""Authoritative canonical semantic inventory for Silver and Gold warehouse contracts.

Owns
----
- ColumnClassification: Closed enum vocabulary for Silver column semantic classifications.
- ColumnDisposition: Closed enum vocabulary for Silver column migration target dispositions.
- SilverContractSemantics: Precise row grain and identity specification for Silver contracts.
- SilverColumnDisposition: Detailed disposition manifest for every physical Silver column.
- GoldContractDependency: Structural dependency graph linking Gold presentation marts to Silver.
- SILVER_CONTRACT_SEMANTICS: Authoritative catalog of all 24 Silver contract specifications.
- SILVER_COLUMN_DISPOSITIONS: Authoritative manifest of all 534 physical Silver column dispositions.
- GOLD_CONTRACT_DEPENDENCIES: Authoritative dependency catalog for all 22 Gold contracts.
- Semantic query and diagnostic helpers (get_silver_contract_semantics, etc.).

Does not own
-------------
- Physical SQL DDL creation or execution (owned by infrastructure.warehouse.schema).
- Presentation layout or UI controls (owned by presentation layer).
- Financial logic and transformation algorithms (owned by domain layer).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from personal_finance_etl.contracts.datasets import DatasetId

__all__ = [
    "ALL_SILVER_COLUMN_DISPOSITIONS",
    "GOLD_CONTRACT_DEPENDENCIES",
    "SILVER_COLUMN_DISPOSITIONS",
    "SILVER_CONTRACT_SEMANTICS",
    "ColumnClassification",
    "ColumnDisposition",
    "GoldContractDependency",
    "SilverColumnDisposition",
    "SilverContractSemantics",
    "get_columns_by_classification",
    "get_columns_by_disposition",
    "get_gold_contract_dependency",
    "get_silver_column_disposition",
    "get_silver_contract_semantics",
]


class ColumnClassification(StrEnum):
    """Authoritative semantic classification of physical Silver warehouse columns."""

    CANONICAL_FINANCIAL = "canonical_financial"
    CANONICAL_IDENTITY = "canonical_identity"
    PROVENANCE_REFERENCE = "provenance_reference"
    SOURCE_TAXONOMY = "source_taxonomy"
    PROVIDER_METADATA = "provider_metadata"
    IMPLEMENTATION_RESIDUE = "implementation_residue"


class ColumnDisposition(StrEnum):
    """Authoritative target disposition for physical Silver warehouse columns."""

    RETAIN = "retain"
    RENAME = "rename"
    MOVE_TO_PROVENANCE = "move_to_provenance"
    MOVE_TO_PROVIDER_MAPPING = "move_to_provider_mapping"
    REMOVE_AFTER_CONSUMER_MIGRATION = "remove_after_consumer_migration"
    REVIEW_REQUIRED = "review_required"


@dataclass(frozen=True, slots=True)
class SilverContractSemantics:
    """Precise row grain, identity keys, and domain ownership for a Silver contract."""

    dataset_id: DatasetId
    physical_table: str
    row_grain: str
    identity_keys: tuple[str, ...]
    financial_domain: str
    current_producer: str
    future_capability_owner: str


@dataclass(frozen=True, slots=True)
class SilverColumnDisposition:
    """Classification, disposition, and migration rationale for a physical Silver column."""

    dataset_id: DatasetId
    physical_table: str
    column_name: str
    classification: ColumnClassification
    disposition: ColumnDisposition
    target_name: str | None = None
    rationale: str = ""
    is_active: bool = True
    closed_in_phase: str | None = None


@dataclass(frozen=True, slots=True)
class GoldContractDependency:
    """Dependency mapping linking a Gold presentation contract to input Silver contracts and columns."""

    dataset_id: DatasetId
    physical_table: str
    producer: str
    input_silver_datasets: tuple[DatasetId, ...]
    input_silver_columns: dict[DatasetId, tuple[str, ...]]
    output_grain: str
    domain: str
    external_presentation_dependency: str | None = None


# Authoritative semantic specifications for all 24 Silver contracts
SILVER_CONTRACT_SEMANTICS: dict[DatasetId, SilverContractSemantics] = {
    DatasetId.COMMON_CALENDAR: SilverContractSemantics(
        dataset_id=DatasetId.COMMON_CALENDAR,
        physical_table="silver.d_Calendar",
        row_grain="Calendar Day (Date)",
        identity_keys=("Date",),
        financial_domain="Common",
        current_producer="CoreEngine",
        future_capability_owner="common",
    ),
    DatasetId.WEALTH_INCOME_CATEGORY: SilverContractSemantics(
        dataset_id=DatasetId.WEALTH_INCOME_CATEGORY,
        physical_table="silver.d_Income_Category",
        row_grain="Income Category (Category_Id)",
        identity_keys=("UID",),
        financial_domain="Wealth",
        current_producer="CoreEngine",
        future_capability_owner="household",
    ),
    DatasetId.WEALTH_INCOME_SUBCATEGORY: SilverContractSemantics(
        dataset_id=DatasetId.WEALTH_INCOME_SUBCATEGORY,
        physical_table="silver.d_Income_Subcategory",
        row_grain="Income Subcategory (Subcategory_Id)",
        identity_keys=("UID",),
        financial_domain="Wealth",
        current_producer="CoreEngine",
        future_capability_owner="household",
    ),
    DatasetId.WEALTH_EXPENSE_CATEGORY: SilverContractSemantics(
        dataset_id=DatasetId.WEALTH_EXPENSE_CATEGORY,
        physical_table="silver.d_Expense_Category",
        row_grain="Expense Category (Category_Id)",
        identity_keys=("UID",),
        financial_domain="Wealth",
        current_producer="CoreEngine",
        future_capability_owner="household",
    ),
    DatasetId.WEALTH_EXPENSE_SUBCATEGORY: SilverContractSemantics(
        dataset_id=DatasetId.WEALTH_EXPENSE_SUBCATEGORY,
        physical_table="silver.d_Expense_Subcategory",
        row_grain="Expense Subcategory (Subcategory_Id)",
        identity_keys=("UID",),
        financial_domain="Wealth",
        current_producer="CoreEngine",
        future_capability_owner="household",
    ),
    DatasetId.WEALTH_ASSET_CATEGORY: SilverContractSemantics(
        dataset_id=DatasetId.WEALTH_ASSET_CATEGORY,
        physical_table="silver.d_Asset_Category",
        row_grain="Asset Category (Category_Id)",
        identity_keys=("UID",),
        financial_domain="Wealth",
        current_producer="CoreEngine",
        future_capability_owner="household",
    ),
    DatasetId.WEALTH_ASSET_SUBCATEGORY: SilverContractSemantics(
        dataset_id=DatasetId.WEALTH_ASSET_SUBCATEGORY,
        physical_table="silver.d_Asset_SubCategory",
        row_grain="Asset Subcategory (Subcategory_Id)",
        identity_keys=("UID",),
        financial_domain="Wealth",
        current_producer="CoreEngine",
        future_capability_owner="household",
    ),
    DatasetId.COMMON_CURRENCY: SilverContractSemantics(
        dataset_id=DatasetId.COMMON_CURRENCY,
        physical_table="silver.d_Currency",
        row_grain="Currency Specification (Currency_Id)",
        identity_keys=("UID",),
        financial_domain="Common",
        current_producer="CoreEngine",
        future_capability_owner="common",
    ),
    DatasetId.INVESTMENT_BENCHMARK_MASTER_DIM: SilverContractSemantics(
        dataset_id=DatasetId.INVESTMENT_BENCHMARK_MASTER_DIM,
        physical_table="silver.d_Investment_Benchmark_Master",
        row_grain="Benchmark Master Specification (Benchmark_Code)",
        identity_keys=("ID",),
        financial_domain="Investments",
        current_producer="CoreEngine",
        future_capability_owner="market",
    ),
    DatasetId.COMMON_CURRENCY_FX_RATES: SilverContractSemantics(
        dataset_id=DatasetId.COMMON_CURRENCY_FX_RATES,
        physical_table="silver.f_Currency_FX_Rates",
        row_grain="Daily Currency Exchange Rate (Base_Currency, Target_Currency, Date)",
        identity_keys=("Currency_ID", "Date"),
        financial_domain="Common",
        current_producer="CoreEngine",
        future_capability_owner="market",
    ),
    DatasetId.INVESTMENT_MASTER: SilverContractSemantics(
        dataset_id=DatasetId.INVESTMENT_MASTER,
        physical_table="silver.d_Investment_Master",
        row_grain="Security Master Instrument (ISIN)",
        identity_keys=("ISIN",),
        financial_domain="Investments",
        current_producer="CoreEngine",
        future_capability_owner="investments",
    ),
    DatasetId.INVESTMENT_MACRO_PARAMETERS_DIM: SilverContractSemantics(
        dataset_id=DatasetId.INVESTMENT_MACRO_PARAMETERS_DIM,
        physical_table="silver.d_Macro_Parameters",
        row_grain="Financial Year Macro Assumptions (FY)",
        identity_keys=("FY",),
        financial_domain="Investments",
        current_producer="CoreEngine",
        future_capability_owner="investments",
    ),
    DatasetId.WEALTH_INCOME_TRANSACTIONS: SilverContractSemantics(
        dataset_id=DatasetId.WEALTH_INCOME_TRANSACTIONS,
        physical_table="silver.f_Income_Transactions",
        row_grain="Ledger Income Transaction (Tx_Id)",
        identity_keys=("UID",),
        financial_domain="Wealth",
        current_producer="CoreEngine",
        future_capability_owner="household",
    ),
    DatasetId.WEALTH_EXPENSE_TRANSACTIONS: SilverContractSemantics(
        dataset_id=DatasetId.WEALTH_EXPENSE_TRANSACTIONS,
        physical_table="silver.f_Expense_Transactions",
        row_grain="Ledger Expense Transaction (Tx_Id)",
        identity_keys=("UID",),
        financial_domain="Wealth",
        current_producer="CoreEngine",
        future_capability_owner="household",
    ),
    DatasetId.WEALTH_TRANSFER_TRANSACTIONS: SilverContractSemantics(
        dataset_id=DatasetId.WEALTH_TRANSFER_TRANSACTIONS,
        physical_table="silver.f_Transfer_Transactions",
        row_grain="Ledger Account Transfer (Tx_Id)",
        identity_keys=("UID",),
        financial_domain="Wealth",
        current_producer="CoreEngine",
        future_capability_owner="household",
    ),
    DatasetId.WEALTH_OPENING_BALANCES: SilverContractSemantics(
        dataset_id=DatasetId.WEALTH_OPENING_BALANCES,
        physical_table="silver.f_Opening_Balances",
        row_grain="Account Opening Balance (Asset_Id, Date)",
        identity_keys=("Z_PK",),
        financial_domain="Wealth",
        current_producer="CoreEngine",
        future_capability_owner="household",
    ),
    DatasetId.INVESTMENT_MARKET_DATA: SilverContractSemantics(
        dataset_id=DatasetId.INVESTMENT_MARKET_DATA,
        physical_table="silver.f_Investment_Market_Data",
        row_grain="Investment Daily Market Quote (ISIN, Date)",
        identity_keys=("ISIN", "Date"),
        financial_domain="Investments",
        current_producer="CoreEngine",
        future_capability_owner="market",
    ),
    DatasetId.INVESTMENT_PURCHASE_DATA: SilverContractSemantics(
        dataset_id=DatasetId.INVESTMENT_PURCHASE_DATA,
        physical_table="silver.f_Investment_Purchase_Data",
        row_grain="Investment Buy Order (Trade_Id)",
        identity_keys=("Purchase_ID",),
        financial_domain="Investments",
        current_producer="CoreEngine",
        future_capability_owner="investments",
    ),
    DatasetId.INVESTMENT_SALE_DATA: SilverContractSemantics(
        dataset_id=DatasetId.INVESTMENT_SALE_DATA,
        physical_table="silver.f_Investment_Sale_Data",
        row_grain="Investment Sell Order (Trade_Id)",
        identity_keys=("Sale_ID",),
        financial_domain="Investments",
        current_producer="CoreEngine",
        future_capability_owner="investments",
    ),
    DatasetId.INVESTMENT_BENCHMARK_DATA: SilverContractSemantics(
        dataset_id=DatasetId.INVESTMENT_BENCHMARK_DATA,
        physical_table="silver.f_Investment_Benchmark_Data",
        row_grain="Daily Benchmark Valuation (Benchmark_Code, Date)",
        identity_keys=("ID", "Date"),
        financial_domain="Investments",
        current_producer="CoreEngine",
        future_capability_owner="market",
    ),
    DatasetId.INVESTMENT_LOT_ANALYTICS: SilverContractSemantics(
        dataset_id=DatasetId.INVESTMENT_LOT_ANALYTICS,
        physical_table="silver.f_Investment_Analytics_Lot",
        row_grain="Tax Lot Position Snapshot (ISIN, Lot_Id, Closing_Date)",
        identity_keys=("Lot_ID", "Closing_Date"),
        financial_domain="Investments",
        current_producer="InvestmentQuantEngine",
        future_capability_owner="investments",
    ),
    DatasetId.INVESTMENT_REALIZED_EVENTS: SilverContractSemantics(
        dataset_id=DatasetId.INVESTMENT_REALIZED_EVENTS,
        physical_table="silver.f_Investment_Realized_Events",
        row_grain="Realized Capital Gain/Loss Event (Event_Id)",
        identity_keys=("Realized_Event_ID",),
        financial_domain="Investments",
        current_producer="InvestmentQuantEngine",
        future_capability_owner="investments",
    ),
    DatasetId.INVESTMENT_RECONCILIATION_EVENTS: SilverContractSemantics(
        dataset_id=DatasetId.INVESTMENT_RECONCILIATION_EVENTS,
        physical_table="silver.f_Investment_Reconciliation_Events",
        row_grain="Investment Reconciliation Audit Event (Event_Id)",
        identity_keys=("Reconciliation_Event_ID",),
        financial_domain="Investments",
        current_producer="InvestmentQuantEngine",
        future_capability_owner="investments",
    ),
    DatasetId.TAX_EVENTS: SilverContractSemantics(
        dataset_id=DatasetId.TAX_EVENTS,
        physical_table="silver.f_Tax_Events",
        row_grain="Tax Assessment Event (Event_Id)",
        identity_keys=("Tax_Event_ID",),
        financial_domain="Taxes",
        current_producer="TaxEngine",
        future_capability_owner="tax",
    ),
}


# Authoritative dependency catalog for all 22 Gold contracts
GOLD_CONTRACT_DEPENDENCIES: dict[DatasetId, GoldContractDependency] = {
    DatasetId.TAX_YEAR_SUMMARY: GoldContractDependency(
        dataset_id=DatasetId.TAX_YEAR_SUMMARY,
        physical_table="gold.Tax_Year_Summary",
        producer="TaxEngine",
        input_silver_datasets=(
            DatasetId.TAX_EVENTS,
            DatasetId.WEALTH_INCOME_TRANSACTIONS,
            DatasetId.INVESTMENT_REALIZED_EVENTS,
            DatasetId.WEALTH_INCOME_SUBCATEGORY,
            DatasetId.INVESTMENT_MACRO_PARAMETERS_DIM,
        ),
        input_silver_columns={
            DatasetId.TAX_EVENTS: (
                "Tax_Event_ID",
                "FY",
                "Amount_INR",
                "Estimated_Tax",
                "Tax_Status",
                "Income_Head",
                "Tax_Sub_Head",
            ),
            DatasetId.WEALTH_INCOME_TRANSACTIONS: ("UID", "BASE_AMOUNT", "CATEGORY_ID", "DATE"),
            DatasetId.INVESTMENT_REALIZED_EVENTS: (
                "Realized_Event_ID",
                "Realized_Gain_Loss",
                "FY",
                "Estimated_Tax",
            ),
            DatasetId.WEALTH_INCOME_SUBCATEGORY: (
                "UID",
                "Tax_Income_Head",
                "Tax_Sub_Head",
                "Is_Investment_Exclusion",
                "Is_Tax_Credits",
            ),
            DatasetId.INVESTMENT_MACRO_PARAMETERS_DIM: ("FY", "FY_Start_Date", "FY_End_Date"),
        },
        output_grain="Financial Year (FY)",
        domain="Taxes",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.TAX_INCOME_BREAKDOWN: GoldContractDependency(
        dataset_id=DatasetId.TAX_INCOME_BREAKDOWN,
        physical_table="gold.Tax_Income_Breakdown",
        producer="TaxEngine",
        input_silver_datasets=(
            DatasetId.TAX_EVENTS,
            DatasetId.WEALTH_INCOME_TRANSACTIONS,
            DatasetId.WEALTH_INCOME_SUBCATEGORY,
        ),
        input_silver_columns={
            DatasetId.TAX_EVENTS: (
                "Tax_Event_ID",
                "FY",
                "Income_Head",
                "Tax_Sub_Head",
                "Source_Type",
                "Amount_INR",
                "Estimated_Tax",
                "Tax_Status",
            ),
            DatasetId.WEALTH_INCOME_TRANSACTIONS: ("UID", "BASE_AMOUNT", "CATEGORY_ID"),
            DatasetId.WEALTH_INCOME_SUBCATEGORY: ("UID", "Tax_Income_Head", "Tax_Sub_Head"),
        },
        output_grain=(
            "Financial Year and Income Head Breakdown (FY, Income_Head, Tax_Sub_Head, Source_Type)"
        ),
        domain="Taxes",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.TAX_RECONCILIATION: GoldContractDependency(
        dataset_id=DatasetId.TAX_RECONCILIATION,
        physical_table="gold.Tax_Reconciliation",
        producer="TaxEngine",
        input_silver_datasets=(
            DatasetId.TAX_EVENTS,
            DatasetId.WEALTH_INCOME_TRANSACTIONS,
            DatasetId.INVESTMENT_REALIZED_EVENTS,
            DatasetId.WEALTH_INCOME_SUBCATEGORY,
        ),
        input_silver_columns={
            DatasetId.TAX_EVENTS: (
                "Tax_Event_ID",
                "FY",
                "Tax_Sub_Head",
                "Amount_INR",
                "Estimated_Tax",
                "Tax_Status",
            ),
            DatasetId.WEALTH_INCOME_TRANSACTIONS: ("UID", "BASE_AMOUNT", "CATEGORY_ID"),
            DatasetId.INVESTMENT_REALIZED_EVENTS: ("Realized_Event_ID", "Realized_Gain_Loss", "FY"),
            DatasetId.WEALTH_INCOME_SUBCATEGORY: (
                "UID",
                "Tax_Sub_Head",
                "Is_Investment_Exclusion",
                "Is_Tax_Credits",
            ),
        },
        output_grain="Financial Year and Sub-Head Tax Reconciliation (FY, Tax_Sub_Head)",
        domain="Taxes",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.WEALTH_CORE_MONTHLY: GoldContractDependency(
        dataset_id=DatasetId.WEALTH_CORE_MONTHLY,
        physical_table="gold.Core_Monthly_Fact",
        producer="WealthPresentationEngine",
        input_silver_datasets=(
            DatasetId.COMMON_CALENDAR,
            DatasetId.WEALTH_INCOME_TRANSACTIONS,
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS,
            DatasetId.WEALTH_TRANSFER_TRANSACTIONS,
            DatasetId.WEALTH_OPENING_BALANCES,
            DatasetId.WEALTH_ASSET_SUBCATEGORY,
            DatasetId.COMMON_CURRENCY_FX_RATES,
            DatasetId.INVESTMENT_LOT_ANALYTICS,
        ),
        input_silver_columns={
            DatasetId.COMMON_CALENDAR: ("Date", "Month_Year", "Start_of_Month", "End_of_Month"),
            DatasetId.WEALTH_INCOME_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT", "ASSET_ID"),
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT", "ASSET_ID"),
            DatasetId.WEALTH_TRANSFER_TRANSACTIONS: (
                "UID",
                "DATE",
                "BASE_AMOUNT",
                "ASSET_ID",
                "TO_ASSET_ID",
            ),
            DatasetId.WEALTH_OPENING_BALANCES: (
                "Z_PK",
                "Date",
                "Opening_Amount",
                "ASSET_SUBCATEGORY_ID",
            ),
            DatasetId.WEALTH_ASSET_SUBCATEGORY: (
                "UID",
                "ASSET_NAME",
                "ledger_role",
                "cashflow_activity_type",
                "Is_Liquid",
            ),
            DatasetId.COMMON_CURRENCY_FX_RATES: ("Date", "Currency_ID", "FX_Rate"),
            DatasetId.INVESTMENT_LOT_ANALYTICS: (
                "Lot_ID",
                "Closing_Date",
                "Close_Value",
                "P/L",
                "Quantity",
            ),
        },
        output_grain="Monthly Ledger and Wealth Aggregation (Month)",
        domain="Wealth",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.WEALTH_ASSET_BREAKDOWN: GoldContractDependency(
        dataset_id=DatasetId.WEALTH_ASSET_BREAKDOWN,
        physical_table="gold.Wealth_Asset_Breakdown",
        producer="WealthPresentationEngine",
        input_silver_datasets=(
            DatasetId.COMMON_CALENDAR,
            DatasetId.WEALTH_INCOME_TRANSACTIONS,
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS,
            DatasetId.WEALTH_TRANSFER_TRANSACTIONS,
            DatasetId.WEALTH_OPENING_BALANCES,
            DatasetId.WEALTH_ASSET_CATEGORY,
            DatasetId.WEALTH_ASSET_SUBCATEGORY,
            DatasetId.COMMON_CURRENCY_FX_RATES,
            DatasetId.INVESTMENT_LOT_ANALYTICS,
        ),
        input_silver_columns={
            DatasetId.COMMON_CALENDAR: ("Date", "Month_Year", "Start_of_Month", "End_of_Month"),
            DatasetId.WEALTH_INCOME_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT", "ASSET_ID"),
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT", "ASSET_ID"),
            DatasetId.WEALTH_TRANSFER_TRANSACTIONS: (
                "UID",
                "DATE",
                "BASE_AMOUNT",
                "ASSET_ID",
                "TO_ASSET_ID",
            ),
            DatasetId.WEALTH_OPENING_BALANCES: (
                "Z_PK",
                "Date",
                "Opening_Amount",
                "ASSET_SUBCATEGORY_ID",
            ),
            DatasetId.WEALTH_ASSET_CATEGORY: ("UID", "ASSET_GROUP", "ledger_role"),
            DatasetId.WEALTH_ASSET_SUBCATEGORY: (
                "UID",
                "ASSET_NAME",
                "ASSET_GROUP_ID",
                "ledger_role",
                "Is_Liquid",
            ),
            DatasetId.COMMON_CURRENCY_FX_RATES: ("Date", "Currency_ID", "FX_Rate"),
            DatasetId.INVESTMENT_LOT_ANALYTICS: ("Lot_ID", "Closing_Date", "Close_Value"),
        },
        output_grain="Monthly Asset Breakdown (Month, Asset_Id)",
        domain="Wealth",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.WEALTH_CASHFLOW_EXPENSE_BREAKDOWN: GoldContractDependency(
        dataset_id=DatasetId.WEALTH_CASHFLOW_EXPENSE_BREAKDOWN,
        physical_table="gold.Cashflow_Expense_Breakdown",
        producer="WealthPresentationEngine",
        input_silver_datasets=(
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS,
            DatasetId.WEALTH_EXPENSE_CATEGORY,
            DatasetId.WEALTH_EXPENSE_SUBCATEGORY,
            DatasetId.COMMON_CALENDAR,
        ),
        input_silver_columns={
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT", "CATEGORY_ID"),
            DatasetId.WEALTH_EXPENSE_CATEGORY: ("UID", "CATEGORY_NAME"),
            DatasetId.WEALTH_EXPENSE_SUBCATEGORY: (
                "UID",
                "CATEGORY_NAME",
                "CATEGORY_ID",
                "Is_Core_Expense",
            ),
            DatasetId.COMMON_CALENDAR: ("Date", "Month_Year"),
        },
        output_grain="Monthly Expense Category Spend (Month, Category_Id)",
        domain="Wealth",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.WEALTH_CASHFLOW_INCOME_BREAKDOWN: GoldContractDependency(
        dataset_id=DatasetId.WEALTH_CASHFLOW_INCOME_BREAKDOWN,
        physical_table="gold.Cashflow_Income_Breakdown",
        producer="WealthPresentationEngine",
        input_silver_datasets=(
            DatasetId.WEALTH_INCOME_TRANSACTIONS,
            DatasetId.WEALTH_INCOME_CATEGORY,
            DatasetId.WEALTH_INCOME_SUBCATEGORY,
            DatasetId.COMMON_CALENDAR,
        ),
        input_silver_columns={
            DatasetId.WEALTH_INCOME_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT", "CATEGORY_ID"),
            DatasetId.WEALTH_INCOME_CATEGORY: ("UID", "CATEGORY_NAME"),
            DatasetId.WEALTH_INCOME_SUBCATEGORY: (
                "UID",
                "CATEGORY_NAME",
                "CATEGORY_ID",
                "Is_Active_Income",
                "Is_Passive_Income",
            ),
            DatasetId.COMMON_CALENDAR: ("Date", "Month_Year"),
        },
        output_grain="Monthly Income Category Streams (Month, Category_Id)",
        domain="Wealth",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.FIRE_ANALYTICS: GoldContractDependency(
        dataset_id=DatasetId.FIRE_ANALYTICS,
        physical_table="gold.Wealth_FIRE_Analytics",
        producer="WealthPresentationEngine",
        input_silver_datasets=(
            DatasetId.COMMON_CALENDAR,
            DatasetId.WEALTH_INCOME_TRANSACTIONS,
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS,
            DatasetId.WEALTH_OPENING_BALANCES,
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_MACRO_PARAMETERS_DIM,
        ),
        input_silver_columns={
            DatasetId.COMMON_CALENDAR: ("Date", "Month_Year", "Start_of_Month", "End_of_Month"),
            DatasetId.WEALTH_INCOME_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT"),
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS: (
                "UID",
                "DATE",
                "BASE_AMOUNT",
                "Is_Core_Expense",
            ),
            DatasetId.WEALTH_OPENING_BALANCES: ("Z_PK", "Date", "Opening_Amount"),
            DatasetId.INVESTMENT_LOT_ANALYTICS: ("Lot_ID", "Closing_Date", "Close_Value"),
            DatasetId.INVESTMENT_MACRO_PARAMETERS_DIM: ("FY", "Inflation_Rate", "Risk_Free_Rate"),
        },
        output_grain="Monthly FIRE Simulation and Risk Analytics (Month)",
        domain="Wealth",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.WEALTH_BUDGET_VARIANCE: GoldContractDependency(
        dataset_id=DatasetId.WEALTH_BUDGET_VARIANCE,
        physical_table="gold.Forecast_Budget_Variance",
        producer="WealthPresentationEngine",
        input_silver_datasets=(
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS,
            DatasetId.WEALTH_INCOME_TRANSACTIONS,
            DatasetId.COMMON_CALENDAR,
        ),
        input_silver_columns={
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT"),
            DatasetId.WEALTH_INCOME_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT"),
            DatasetId.COMMON_CALENDAR: ("Date", "Month_Year"),
        },
        output_grain="Monthly Budget Variance Analysis (Month)",
        domain="Wealth",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.INVESTMENT_PORTFOLIO_SUMMARY: GoldContractDependency(
        dataset_id=DatasetId.INVESTMENT_PORTFOLIO_SUMMARY,
        physical_table="gold.Investment_Portfolio_Summary",
        producer="InvestmentQuantEngine",
        input_silver_datasets=(
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_MASTER,
            DatasetId.COMMON_CALENDAR,
        ),
        input_silver_columns={
            DatasetId.INVESTMENT_LOT_ANALYTICS: (
                "Lot_ID",
                "Closing_Date",
                "ISIN",
                "Quantity",
                "Close_Value",
                "Buy_Value",
                "P/L",
                "XIRR",
            ),
            DatasetId.INVESTMENT_MASTER: (
                "ISIN",
                "INSTRUMENT_NAME",
                "INSTRUMENT_CLASS",
                "INSTRUMENT_SUBTYPE",
            ),
            DatasetId.COMMON_CALENDAR: ("Date", "Month_Year"),
        },
        output_grain="Monthly Portfolio Instrument Summary (Month, ISIN)",
        domain="Investments",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.WEALTH_CASHFLOW_EFFICIENCY: GoldContractDependency(
        dataset_id=DatasetId.WEALTH_CASHFLOW_EFFICIENCY,
        physical_table="gold.Cashflow_Efficiency_Analytics",
        producer="WealthPresentationEngine",
        input_silver_datasets=(
            DatasetId.WEALTH_INCOME_TRANSACTIONS,
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS,
            DatasetId.COMMON_CALENDAR,
        ),
        input_silver_columns={
            DatasetId.WEALTH_INCOME_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT"),
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT"),
            DatasetId.COMMON_CALENDAR: ("Date", "Month_Year"),
        },
        output_grain="Monthly Cashflow Efficiency Metrics (Month)",
        domain="Wealth",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.WEALTH_CASHFLOW_ACTIVITY_SUMMARY: GoldContractDependency(
        dataset_id=DatasetId.WEALTH_CASHFLOW_ACTIVITY_SUMMARY,
        physical_table="gold.Cashflow_Activity_Summary",
        producer="WealthPresentationEngine",
        input_silver_datasets=(
            DatasetId.WEALTH_INCOME_TRANSACTIONS,
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS,
            DatasetId.WEALTH_TRANSFER_TRANSACTIONS,
            DatasetId.WEALTH_ASSET_CATEGORY,
            DatasetId.WEALTH_ASSET_SUBCATEGORY,
            DatasetId.COMMON_CALENDAR,
        ),
        input_silver_columns={
            DatasetId.WEALTH_INCOME_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT", "ASSET_ID"),
            DatasetId.WEALTH_EXPENSE_TRANSACTIONS: ("UID", "DATE", "BASE_AMOUNT", "ASSET_ID"),
            DatasetId.WEALTH_TRANSFER_TRANSACTIONS: (
                "UID",
                "DATE",
                "BASE_AMOUNT",
                "ASSET_ID",
                "TO_ASSET_ID",
            ),
            DatasetId.WEALTH_ASSET_CATEGORY: ("UID", "cashflow_activity_type", "ledger_role"),
            DatasetId.WEALTH_ASSET_SUBCATEGORY: ("UID", "cashflow_activity_type", "ledger_role"),
            DatasetId.COMMON_CALENDAR: ("Date", "Month_Year"),
        },
        output_grain="Monthly Cashflow Activities by Operating/Investing/Financing (Month)",
        domain="Wealth",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.INVESTMENT_BY_ISIN: GoldContractDependency(
        dataset_id=DatasetId.INVESTMENT_BY_ISIN,
        physical_table="gold.Investment_By_ISIN",
        producer="InvestmentQuantEngine",
        input_silver_datasets=(
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_MASTER,
            DatasetId.INVESTMENT_BENCHMARK_DATA,
            DatasetId.COMMON_CURRENCY_FX_RATES,
        ),
        input_silver_columns={
            DatasetId.INVESTMENT_LOT_ANALYTICS: (
                "Lot_ID",
                "Closing_Date",
                "ISIN",
                "Quantity",
                "Buy_Value",
                "Close_Value",
                "P/L",
                "XIRR",
                "CAGR",
            ),
            DatasetId.INVESTMENT_MASTER: (
                "ISIN",
                "INSTRUMENT_NAME",
                "INSTRUMENT_CLASS",
                "INSTRUMENT_SUBTYPE",
                "CURRENCY_ID",
            ),
            DatasetId.INVESTMENT_BENCHMARK_DATA: ("Date", "ID", "Close"),
            DatasetId.COMMON_CURRENCY_FX_RATES: ("Date", "Currency_ID", "FX_Rate"),
        },
        output_grain="Daily Instrument Valuation and Performance (ISIN, Closing_Date)",
        domain="Investments",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.INVESTMENT_BY_SUBTYPE: GoldContractDependency(
        dataset_id=DatasetId.INVESTMENT_BY_SUBTYPE,
        physical_table="gold.Investment_By_Subtype",
        producer="InvestmentQuantEngine",
        input_silver_datasets=(
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_MASTER,
        ),
        input_silver_columns={
            DatasetId.INVESTMENT_LOT_ANALYTICS: (
                "Lot_ID",
                "Closing_Date",
                "ISIN",
                "Buy_Value",
                "Close_Value",
                "P/L",
            ),
            DatasetId.INVESTMENT_MASTER: ("ISIN", "INSTRUMENT_CLASS", "INSTRUMENT_SUBTYPE"),
        },
        output_grain=(
            "Daily Asset Subtype Valuation and Performance"
            " (INSTRUMENT_CLASS, INSTRUMENT_SUBTYPE, Closing_Date)"
        ),
        domain="Investments",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.INVESTMENT_BY_CLASS: GoldContractDependency(
        dataset_id=DatasetId.INVESTMENT_BY_CLASS,
        physical_table="gold.Investment_By_Class",
        producer="InvestmentQuantEngine",
        input_silver_datasets=(
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_MASTER,
        ),
        input_silver_columns={
            DatasetId.INVESTMENT_LOT_ANALYTICS: (
                "Lot_ID",
                "Closing_Date",
                "ISIN",
                "Buy_Value",
                "Close_Value",
                "P/L",
            ),
            DatasetId.INVESTMENT_MASTER: ("ISIN", "INSTRUMENT_CLASS"),
        },
        output_grain="Daily Asset Class Valuation and Performance (INSTRUMENT_CLASS, Closing_Date)",
        domain="Investments",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.INVESTMENT_BY_INSTRUMENT_TYPE: GoldContractDependency(
        dataset_id=DatasetId.INVESTMENT_BY_INSTRUMENT_TYPE,
        physical_table="gold.Investment_By_Instrument_Type",
        producer="InvestmentQuantEngine",
        input_silver_datasets=(
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_MASTER,
        ),
        input_silver_columns={
            DatasetId.INVESTMENT_LOT_ANALYTICS: (
                "Lot_ID",
                "Closing_Date",
                "ISIN",
                "Buy_Value",
                "Close_Value",
                "P/L",
            ),
            DatasetId.INVESTMENT_MASTER: ("ISIN", "INSTRUMENT_TYPE"),
        },
        output_grain=(
            "Daily Instrument Type Valuation and Performance (INSTRUMENT_TYPE, Closing_Date)"
        ),
        domain="Investments",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.INVESTMENT_BY_SECTOR: GoldContractDependency(
        dataset_id=DatasetId.INVESTMENT_BY_SECTOR,
        physical_table="gold.Investment_By_Sector",
        producer="InvestmentQuantEngine",
        input_silver_datasets=(
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_MASTER,
        ),
        input_silver_columns={
            DatasetId.INVESTMENT_LOT_ANALYTICS: (
                "Lot_ID",
                "Closing_Date",
                "ISIN",
                "Buy_Value",
                "Close_Value",
                "P/L",
            ),
            DatasetId.INVESTMENT_MASTER: ("ISIN", "SECTOR"),
        },
        output_grain="Daily Sector Valuation and Performance (SECTOR, Closing_Date)",
        domain="Investments",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.INVESTMENT_BY_INDUSTRY: GoldContractDependency(
        dataset_id=DatasetId.INVESTMENT_BY_INDUSTRY,
        physical_table="gold.Investment_By_Industry",
        producer="InvestmentQuantEngine",
        input_silver_datasets=(
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_MASTER,
        ),
        input_silver_columns={
            DatasetId.INVESTMENT_LOT_ANALYTICS: (
                "Lot_ID",
                "Closing_Date",
                "ISIN",
                "Buy_Value",
                "Close_Value",
                "P/L",
            ),
            DatasetId.INVESTMENT_MASTER: ("ISIN", "INDUSTRY"),
        },
        output_grain="Daily Industry Valuation and Performance (INDUSTRY, Closing_Date)",
        domain="Investments",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.INVESTMENT_BY_PORTFOLIO: GoldContractDependency(
        dataset_id=DatasetId.INVESTMENT_BY_PORTFOLIO,
        physical_table="gold.Investment_By_Portfolio",
        producer="InvestmentQuantEngine",
        input_silver_datasets=(
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_MASTER,
        ),
        input_silver_columns={
            DatasetId.INVESTMENT_LOT_ANALYTICS: (
                "Lot_ID",
                "Closing_Date",
                "ISIN",
                "Buy_Value",
                "Close_Value",
                "P/L",
            ),
            DatasetId.INVESTMENT_MASTER: ("ISIN",),
        },
        output_grain="Daily Overall Portfolio Valuation and Performance (Closing_Date)",
        domain="Investments",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.INVESTMENT_BY_GEO: GoldContractDependency(
        dataset_id=DatasetId.INVESTMENT_BY_GEO,
        physical_table="gold.Investment_By_Geo",
        producer="InvestmentQuantEngine",
        input_silver_datasets=(
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_MASTER,
        ),
        input_silver_columns={
            DatasetId.INVESTMENT_LOT_ANALYTICS: (
                "Lot_ID",
                "Closing_Date",
                "ISIN",
                "Buy_Value",
                "Close_Value",
                "P/L",
            ),
            DatasetId.INVESTMENT_MASTER: ("ISIN", "GEO"),
        },
        output_grain="Daily Geographic Valuation and Performance (GEO, Closing_Date)",
        domain="Investments",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.INVESTMENT_BY_COUNTRY: GoldContractDependency(
        dataset_id=DatasetId.INVESTMENT_BY_COUNTRY,
        physical_table="gold.Investment_By_Country",
        producer="InvestmentQuantEngine",
        input_silver_datasets=(
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_MASTER,
        ),
        input_silver_columns={
            DatasetId.INVESTMENT_LOT_ANALYTICS: (
                "Lot_ID",
                "Closing_Date",
                "ISIN",
                "Buy_Value",
                "Close_Value",
                "P/L",
            ),
            DatasetId.INVESTMENT_MASTER: ("ISIN", "COUNTRY"),
        },
        output_grain="Daily Country Valuation and Performance (COUNTRY, Closing_Date)",
        domain="Investments",
        external_presentation_dependency="PowerBI",
    ),
    DatasetId.INVESTMENT_BY_CURRENCY: GoldContractDependency(
        dataset_id=DatasetId.INVESTMENT_BY_CURRENCY,
        physical_table="gold.Investment_By_Currency",
        producer="InvestmentQuantEngine",
        input_silver_datasets=(
            DatasetId.INVESTMENT_LOT_ANALYTICS,
            DatasetId.INVESTMENT_MASTER,
            DatasetId.COMMON_CURRENCY,
        ),
        input_silver_columns={
            DatasetId.INVESTMENT_LOT_ANALYTICS: (
                "Lot_ID",
                "Closing_Date",
                "ISIN",
                "Buy_Value",
                "Close_Value",
                "P/L",
                "CURRENCY_ID",
            ),
            DatasetId.INVESTMENT_MASTER: ("ISIN", "CURRENCY_ID"),
            DatasetId.COMMON_CURRENCY: ("UID", "ISO"),
        },
        output_grain="Daily Currency Valuation and Performance (CURRENCY_ID, Closing_Date)",
        domain="Investments",
        external_presentation_dependency="PowerBI",
    ),
}


def _load_silver_column_dispositions() -> tuple[
    tuple[SilverColumnDisposition, ...], tuple[SilverColumnDisposition, ...]
]:
    """Load and validate the authoritative column disposition manifest from JSON."""
    json_path = Path(__file__).parent / "silver_column_dispositions.json"
    with open(json_path, encoding="utf-8") as f:
        raw_items = json.load(f)

    all_dispositions: list[SilverColumnDisposition] = []
    active_dispositions: list[SilverColumnDisposition] = []
    for item in raw_items:
        is_active = bool(item.get("is_active", True))
        disp = SilverColumnDisposition(
            dataset_id=DatasetId(item["dataset_id"]),
            physical_table=str(item["physical_table"]),
            column_name=str(item["column_name"]),
            classification=ColumnClassification(item["classification"]),
            disposition=ColumnDisposition(item["disposition"]),
            target_name=item["target_name"],
            rationale=str(item.get("rationale", "")),
            is_active=is_active,
            closed_in_phase=item.get("closed_in_phase"),
        )
        all_dispositions.append(disp)
        if is_active:
            active_dispositions.append(disp)
    return tuple(all_dispositions), tuple(active_dispositions)


# Authoritative column disposition manifest: ALL tracks complete audit history;
# SILVER_COLUMN_DISPOSITIONS tracks currently active physical Silver columns (522).
ALL_SILVER_COLUMN_DISPOSITIONS, SILVER_COLUMN_DISPOSITIONS = _load_silver_column_dispositions()


def get_silver_contract_semantics(dataset_id: DatasetId) -> SilverContractSemantics:
    """Retrieve the authoritative semantics for a Silver contract.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier to inspect.

    Returns
    -------
    SilverContractSemantics
        Contract semantics specification.

    Raises
    ------
    KeyError
        If dataset_id is not a registered Silver contract.
    """
    if dataset_id not in SILVER_CONTRACT_SEMANTICS:
        raise KeyError(f"DatasetId '{dataset_id}' is not a registered Silver contract.")
    return SILVER_CONTRACT_SEMANTICS[dataset_id]


def get_silver_column_disposition(
    dataset_id: DatasetId,
    column_name: str,
) -> SilverColumnDisposition:
    """Retrieve the disposition record for a specific Silver table column.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier.
    column_name : str
        Physical column name in the Silver table.

    Returns
    -------
    SilverColumnDisposition
        Column classification and disposition record.

    Raises
    ------
    KeyError
        If column is not found for the given dataset.
    """
    for entry in SILVER_COLUMN_DISPOSITIONS:
        if entry.dataset_id == dataset_id and entry.column_name == column_name:
            return entry
    raise KeyError(f"Column '{column_name}' not found in Silver contract '{dataset_id}'.")


def get_gold_contract_dependency(dataset_id: DatasetId) -> GoldContractDependency:
    """Retrieve the dependency specification for a Gold presentation contract.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical dataset identifier.

    Returns
    -------
    GoldContractDependency
        Gold dependency mapping record.

    Raises
    ------
    KeyError
        If dataset_id is not a registered Gold contract.
    """
    if dataset_id not in GOLD_CONTRACT_DEPENDENCIES:
        raise KeyError(f"DatasetId '{dataset_id}' is not a registered Gold contract.")
    return GOLD_CONTRACT_DEPENDENCIES[dataset_id]


def get_columns_by_classification(
    classification: ColumnClassification,
) -> list[SilverColumnDisposition]:
    """Filter Silver column dispositions by semantic classification.

    Parameters
    ----------
    classification : ColumnClassification
        Target semantic classification.

    Returns
    -------
    list[SilverColumnDisposition]
        Matching column disposition records.
    """
    return [c for c in SILVER_COLUMN_DISPOSITIONS if c.classification == classification]


def get_columns_by_disposition(
    disposition: ColumnDisposition,
) -> list[SilverColumnDisposition]:
    """Filter Silver column dispositions by target migration disposition.

    Parameters
    ----------
    disposition : ColumnDisposition
        Target migration disposition.

    Returns
    -------
    list[SilverColumnDisposition]
        Matching column disposition records.
    """
    return [c for c in SILVER_COLUMN_DISPOSITIONS if c.disposition == disposition]
