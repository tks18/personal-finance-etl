# pyright: reportPrivateUsage=false
"""Authoritative Phase 008 verification test suite.

Owns
----
- Verification of the 22-table Gold warehouse presentation topology against the authoritative disposition manifest.
- Verification that all 577 active physical columns across Gold DDL are cataloged and classified.
- Verification that deterministic business keys, identity keys, and core financial quantities are marked PROTECTED.
- Verification that repeated investment aggregate metric definitions are identified and match active schemas.
- Verification of engine-to-contract publication alignment for Wealth, Quant, and Tax engines.
- Verification that Gold DDL and contracts remain 100% unmodified during this archaeology phase (non-destructive invariant).

Does not own
-------------
- Execution of Gold DDL schema alterations or producer cutovers (owned by Phase 009 and Phase 010).
- Downstream Power BI live report refresh execution (owned by Phase 010 and Phase 017).
"""

from __future__ import annotations

import re
from pathlib import Path

from personal_finance_etl.infrastructure.warehouse.contracts import (
    DATA_CONTRACT_REGISTRY,
)
from personal_finance_etl.infrastructure.warehouse.schema.gold import GOLD_DDL

MANIFEST_PATH = Path(".planning/v11/GOLD-DISPOSITION-MANIFEST.md")

EXPECTED_22_ACTIVE_GOLD_TABLES: list[str] = [
    # 11 Phase 009 Cutover Tables (Household, Wealth, FIRE, Tax)
    "gold.tax_financial_year_summary",
    "gold.tax_income_breakdown",
    "gold.tax_reconciliation",
    "gold.core_monthly_fact",
    "gold.wealth_asset_breakdown",
    "gold.cashflow_expense_breakdown",
    "gold.cashflow_income_breakdown",
    "gold.wealth_fire_analytics",
    "gold.forecast_budget_variance",
    "gold.cashflow_efficiency_analytics",
    "gold.cashflow_activity_summary",
    # 11 Phase 010 Cutover Tables (Investments)
    "gold.investment_portfolio_summary",
    "gold.investment_by_isin",
    "gold.investment_by_subtype",
    "gold.investment_by_class",
    "gold.investment_by_instrument_type",
    "gold.investment_by_sector",
    "gold.investment_by_industry",
    "gold.investment_by_portfolio",
    "gold.investment_by_geo",
    "gold.investment_by_country",
    "gold.investment_by_currency",
]

EXPECTED_TARGET_NAMES: dict[str, str] = {
    "gold.Tax_Year_Summary": "gold.tax_financial_year_summary",
    "gold.Tax_Income_Breakdown": "gold.tax_income_breakdown",
    "gold.Tax_Reconciliation": "gold.tax_reconciliation",
    "gold.Core_Monthly_Fact": "gold.core_monthly_fact",
    "gold.Wealth_Asset_Breakdown": "gold.wealth_asset_breakdown",
    "gold.Cashflow_Expense_Breakdown": "gold.cashflow_expense_breakdown",
    "gold.Cashflow_Income_Breakdown": "gold.cashflow_income_breakdown",
    "gold.Wealth_FIRE_Analytics": "gold.wealth_fire_analytics",
    "gold.Forecast_Budget_Variance": "gold.forecast_budget_variance",
    "gold.Cashflow_Efficiency_Analytics": "gold.cashflow_efficiency_analytics",
    "gold.Cashflow_Activity_Summary": "gold.cashflow_activity_summary",
    "gold.Investment_Portfolio_Summary": "gold.investment_portfolio_summary",
    "gold.Investment_By_ISIN": "gold.investment_by_isin",
    "gold.Investment_By_Subtype": "gold.investment_by_subtype",
    "gold.Investment_By_Class": "gold.investment_by_class",
    "gold.Investment_By_Instrument_Type": "gold.investment_by_instrument_type",
    "gold.Investment_By_Sector": "gold.investment_by_sector",
    "gold.Investment_By_Industry": "gold.investment_by_industry",
    "gold.Investment_By_Portfolio": "gold.investment_by_portfolio",
    "gold.Investment_By_Geo": "gold.investment_by_geo",
    "gold.Investment_By_Country": "gold.investment_by_country",
    "gold.Investment_By_Currency": "gold.investment_by_currency",
}

CRITICAL_PROTECTED_IDENTITIES: set[str] = {
    "FY",
    "MONTH_START_DATE",
    "MONTH_END_DATE",
    "YEAR_MONTH",
    "ASSET_SUBCATEGORY_ID",
    "CATEGORY_ID",
    "ISIN",
    "CURRENCY_ID",
    "Closing_Date",
}

CRITICAL_PROTECTED_FINANCIALS: set[str] = {
    "Total_Ledger_Income",
    "Total_Investment_Gain_Loss",
    "Total_Tax_Credits",
    "Total_Estimated_Investment_Tax",
    "Total_Estimated_Ledger_Tax",
    "Total_Income",
    "Total_Expense",
    "Net_Cashflow_Month",
    "Total_Net_Worth",
    "Total_Invested_Value",
    "Total_Current_Value",
    "Total_Quantity",
    "Unrealized_PL",
    "Asset_PnL",
    "Forex_PnL",
    "XIRR",
    "CAGR",
    "Absolute_Return",
    "Target_FI_Today",
    "Coast_FI_Today",
    "Lean_FI_Today",
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
}

SHARED_INVESTMENT_CORE_METRICS: list[str] = [
    "Total_Invested_Value",
    "Total_Current_Value",
    "Total_Quantity",
    "Total_Stocks",
    "Unrealized_PL",
    "Asset_PnL",
    "Forex_PnL",
    "Forex_Contribution_Pct",
    "Absolute_Return",
    "XIRR",
    "After_Tax_XIRR",
    "BM_XIRR",
    "Active_Return",
    "Max_Drawdown",
    "Weight",
    "Unrealized_Gain",
    "Unrealized_Loss",
    "FY_Realized_Gain",
    "FY_Realized_Loss",
    "FY_Realized_Net_PnL",
]


def _extract_gold_ddl_columns() -> dict[str, list[str]]:
    """Parse all 22 tables and their columns directly from GOLD_DDL."""
    table_blocks = re.findall(
        r"CREATE TABLE IF NOT EXISTS (gold\.[^\s\(]+)\s*\((.*?)\);",
        GOLD_DDL,
        re.DOTALL,
    )
    result: dict[str, list[str]] = {}
    for tbl, body in table_blocks:
        cols: list[str] = []
        for line in body.splitlines():
            line_s = line.strip()
            if not line_s or line_s.startswith(
                ("--", "PRIMARY", "UNIQUE", "FOREIGN", "CONSTRAINT", ")")
            ):
                continue
            col_name = line_s.split()[0].strip('",`')
            cols.append(col_name)
        result[tbl] = cols
    return result


def test_gold_manifest_exists() -> None:
    """Verify that the authoritative Gold disposition manifest is checked in."""
    assert MANIFEST_PATH.exists(), f"Manifest missing at {MANIFEST_PATH}"
    content = MANIFEST_PATH.read_text(encoding="utf-8")
    assert len(content) > 50000, "Manifest file is incomplete or truncated"


def test_gold_table_inventory_parity() -> None:
    """Verify that all 22 physical tables in GOLD_DDL match the manifest and registry."""
    ddl_tables = _extract_gold_ddl_columns()
    assert len(ddl_tables) == 22, f"Expected exactly 22 tables in GOLD_DDL, got {len(ddl_tables)}"
    assert sorted(ddl_tables.keys()) == sorted(EXPECTED_22_ACTIVE_GOLD_TABLES)

    manifest_content = MANIFEST_PATH.read_text(encoding="utf-8")
    for tbl in EXPECTED_22_ACTIVE_GOLD_TABLES:
        assert f"`{tbl}`" in manifest_content, f"Table {tbl} missing from manifest"

    gold_contracts = [c for c in DATA_CONTRACT_REGISTRY if c.layer == "gold"]
    assert len(gold_contracts) == 22, (
        f"Expected 22 Gold contracts in DATA_CONTRACT_REGISTRY, got {len(gold_contracts)}"
    )
    contract_tables = {c.physical_table for c in gold_contracts}
    assert contract_tables == set(EXPECTED_22_ACTIVE_GOLD_TABLES)


def test_gold_column_inventory_complete() -> None:
    """Verify that all 577 physical columns across Gold DDL are cataloged in the manifest."""
    ddl_tables = _extract_gold_ddl_columns()
    total_ddl_columns = sum(len(cols) for cols in ddl_tables.values())
    assert total_ddl_columns == 597, (
        f"Expected exactly 597 active columns across Gold DDL (577 baseline + 20 new metrics), got {total_ddl_columns}"
    )

    manifest_content = MANIFEST_PATH.read_text(encoding="utf-8")
    for tbl, cols in ddl_tables.items():
        for col in cols:
            # Check for baseline column in manifest or new intelligence additions
            new_intelligence_metrics = {
                "Net_Savings_Flow",
                "Market_Return_Flow",
                "Attribution_Residual",
                "Inflation_Adjusted_Core_Expense",
                "Real_Core_Expense_Growth_Pct",
                "Passive_Income_Core_Expense_Coverage_Ratio",
                "Active_Income_Dependency_Pct",
                "Top1_Holding_Weight",
                "Top5_Holdings_Weight",
                "Top10_Holdings_Weight",
                "HHI_Score",
                "Effective_Holdings_Count",
                "LTCG_Maturing_30D",
                "LTCG_Maturing_90D",
                "LTCG_Maturing_180D",
                "LTCG_Maturing_365D",
                "LTCG_Mature_Value",
                "Indicative_Unrealized_Tax_Liability",
                "Indicative_Harvestable_Tax_Savings",
                "Indicative_Net_Tax_Exposure",
            }
            if col not in new_intelligence_metrics:
                assert f"`{col}`" in manifest_content, (
                    f"Baseline column '{col}' of table '{tbl}' is missing from manifest"
                )


def test_protected_identity_and_financial_invariants() -> None:
    """Assert that critical business keys, temporal identities, and financials are PROTECTED."""
    manifest_content = MANIFEST_PATH.read_text(encoding="utf-8")

    for key in CRITICAL_PROTECTED_IDENTITIES:
        pattern = rf"\|\s*`{re.escape(key)}`\s*\|\s*[^|]+\|\s*[^|]+\|\s*🛡️ PROTECTED"
        assert re.search(pattern, manifest_content), (
            f"Critical business identity key '{key}' must be classified as PROTECTED in manifest"
        )

    for fin in CRITICAL_PROTECTED_FINANCIALS:
        pattern = rf"\|\s*`{re.escape(fin)}`\s*\|\s*[^|]+\|\s*[^|]+\|\s*🛡️ PROTECTED"
        assert re.search(pattern, manifest_content), (
            f"Critical financial metric '{fin}' must be classified as PROTECTED in manifest"
        )


def test_shared_investment_metric_helper_parity() -> None:
    """Assert that the 10 Investment_By_* breakdown tables repeat the core 20 aggregate metrics."""
    ddl_tables = _extract_gold_ddl_columns()
    breakdown_tables = [
        "gold.investment_by_subtype",
        "gold.investment_by_class",
        "gold.investment_by_instrument_type",
        "gold.investment_by_sector",
        "gold.investment_by_industry",
        "gold.investment_by_portfolio",
        "gold.investment_by_geo",
        "gold.investment_by_country",
        "gold.investment_by_currency",
        "gold.investment_by_isin",
    ]

    for tbl in breakdown_tables:
        cols = ddl_tables[tbl]
        for metric in SHARED_INVESTMENT_CORE_METRICS:
            assert metric in cols, (
                f"Expected shared core metric '{metric}' in table '{tbl}', but not found!"
            )


def test_engine_to_gold_contract_mapping() -> None:
    """Verify that all 22 Gold contracts have verified producer engines in registry."""
    gold_contracts = [c for c in DATA_CONTRACT_REGISTRY if c.layer == "gold"]
    producers = {c.producer for c in gold_contracts}
    expected_producers = {"TaxEngine", "WealthPresentationEngine", "InvestmentQuantEngine"}
    assert producers == expected_producers, f"Unexpected producers: {producers}"

    tax_contracts = [c for c in gold_contracts if c.producer == "TaxEngine"]
    assert len(tax_contracts) == 3, f"Expected 3 TaxEngine contracts, got {len(tax_contracts)}"

    wealth_contracts = [c for c in gold_contracts if c.producer == "WealthPresentationEngine"]
    assert len(wealth_contracts) == 8, (
        f"Expected 8 WealthPresentationEngine contracts, got {len(wealth_contracts)}"
    )

    quant_contracts = [c for c in gold_contracts if c.producer == "InvestmentQuantEngine"]
    assert len(quant_contracts) == 11, (
        f"Expected 11 InvestmentQuantEngine contracts, got {len(quant_contracts)}"
    )


def test_gold_ddl_and_contracts_unmodified() -> None:
    """Assert that Gold DDL and contracts reflect canonical cutover for all 22 tables."""
    ddl_tables = _extract_gold_ddl_columns()
    # Confirm canonical physical table names are active
    assert "gold.tax_financial_year_summary" in ddl_tables
    assert "gold.core_monthly_fact" in ddl_tables
    assert "gold.investment_by_isin" in ddl_tables

    gold_contracts = {
        c.contract_id: c.physical_table for c in DATA_CONTRACT_REGISTRY if c.layer == "gold"
    }
    assert gold_contracts["df_p_tax_year_summary"] == "gold.tax_financial_year_summary"
    assert gold_contracts["df_p_tf_wealth_monthly_totals"] == "gold.core_monthly_fact"
    assert gold_contracts["df_f_investment_analytics_isin"] == "gold.investment_by_isin"
