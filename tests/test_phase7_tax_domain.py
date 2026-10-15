"""Unit and regression tests for Phase 7: Tax Domain & Application Service.

Tests:
1. Strict object identity equivalence (`is`) across all legacy shims vs canonical modules.
2. TaxClassifier domain logic: quant sub-head mapping, cutoff logic, credit UIDs, subcategory dimension.
3. TaxEstimator rate resolution, finite number cleaning, and rate bounds.
4. BaseEventsBuilder / TaxEventNormalizer: ledger income, tax credits, quant FIFO events, deterministic IDs.
5. TaxGoldFormatter / TaxReconciler: year summary, income breakdown, and source evidence reconciliation.
6. TaxService / TaxEngine end-to-end streaming DAG execution.
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

# Legacy shims for identity testing
import personal_finance_etl.backend.engines.tax as legacy_tax_pkg
import personal_finance_etl.backend.engines.tax.core as legacy_tax_core
import personal_finance_etl.backend.engines.tax.core.base_events as legacy_base_events
import personal_finance_etl.backend.engines.tax.core.gold_formatter as legacy_gold_formatter
import personal_finance_etl.backend.engines.tax.tax_engine as legacy_tax_engine

# Canonical domain and application imports
from personal_finance_etl.application.tax import TaxEngine as AppTaxEngine
from personal_finance_etl.application.tax import TaxService as AppTaxService
from personal_finance_etl.application.tax.tax_service import TaxEngine, TaxService
from personal_finance_etl.config.financial_rules import (
    FinancialRules,
    InvestmentExclusionsConfig,
    TaxHeadConfig,
    TaxSubHeadConfig,
)
from personal_finance_etl.domain.tax import (
    TAX_EVENT_SCHEMA,
    BaseEventsBuilder,
    TaxClassifier,
    TaxEstimator,
    TaxEventNormalizer,
    TaxGoldFormatter,
    TaxReconciler,
    _batch_compute_tax_event_ids,
)


# ---------------------------------------------------------------------------
# 1. Strict Identity Equivalence Tests
# ---------------------------------------------------------------------------
def test_tax_shims_object_identity() -> None:
    """Verify 100% strict object identity equivalence on all legacy shims."""
    assert legacy_base_events.BaseEventsBuilder is BaseEventsBuilder
    assert legacy_base_events.TAX_EVENT_SCHEMA is TAX_EVENT_SCHEMA
    assert legacy_base_events._batch_compute_tax_event_ids is _batch_compute_tax_event_ids

    assert legacy_gold_formatter.TaxGoldFormatter is TaxGoldFormatter

    assert legacy_tax_engine.TaxEngine is TaxEngine
    assert legacy_tax_engine.TaxEngine is TaxService
    assert AppTaxEngine is TaxService
    assert AppTaxService is TaxService

    assert legacy_tax_core.BaseEventsBuilder is BaseEventsBuilder
    assert legacy_tax_core.TaxGoldFormatter is TaxGoldFormatter

    assert legacy_tax_pkg.TaxEngine is TaxService
    assert TaxEventNormalizer is BaseEventsBuilder
    assert TaxReconciler is TaxGoldFormatter


# ---------------------------------------------------------------------------
# Fixtures for Test Data
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_rules() -> FinancialRules:
    """Create a minimal FinancialRules instance for tax testing."""
    from pathlib import Path

    rules = FinancialRules.from_toml(Path("tests/financial_rules.toml"))
    rules.assumptions.tax.debt_mf_cutoff_date = "2023-03-31"
    rules.assumptions.tax.investment_exclusions = InvestmentExclusionsConfig(
        stcg_sub_cat_ids=["CAT_EXCL_STCG"],
        ltcg_sub_cat_ids=["CAT_EXCL_LTCG"],
    )
    rules.assumptions.tax.heads_of_income = {
        "Income from Other Sources": TaxHeadConfig(
            sub_heads={
                "Interest": TaxSubHeadConfig(
                    tax_head_display_name="Income from Other Sources",
                    sub_head_display_name="Interest Income",
                    tax_credit_sub_cat_ids=["CAT_CREDIT_TDS"],
                )
            }
        )
    }
    rules.assumptions.macro.fallback_ordinary_income_rate = 0.30
    return rules


@pytest.fixture
def mock_subcategory_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "UID": [
                "CAT_SALARY",
                "CAT_INTEREST",
                "CAT_EXCL_STCG",
                "CAT_EXCL_LTCG",
                "CAT_CREDIT_TDS",
                "CAT_NON_TAXABLE",
            ],
            "Tax_Income_Head": [
                "Salary",
                "Income from Other Sources",
                "Capital Gains",
                "Capital Gains",
                "TAX_CREDIT",
                "Exempt",
            ],
            "Tax_Sub_Head": [
                "Basic Salary",
                "Interest",
                "Equity_Listed_STCG",
                "Equity_Listed_LTCG",
                "TDS Credit",
                "Exempt",
            ],
            "Taxability": ["taxable", "taxable", "taxable", "taxable", "taxable", "non_taxable"],
            "Tax_Method": ["Slab", "Slab", "Special", "Special", "Credit", "None"],
            "Is_Investment_Exclusion": [False, False, True, True, False, False],
            "Is_Tax_Credits": [False, False, False, False, True, False],
        }
    )


@pytest.fixture
def mock_income_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "UID": ["INC_001", "INC_002", "INC_003", "INC_004"],
            "DATE": [date(2023, 6, 15), date(2023, 9, 20), date(2023, 11, 1), date(2024, 1, 10)],
            "CATEGORY_ID": ["CAT_SALARY", "CAT_CREDIT_TDS", "CAT_EXCL_STCG", "CAT_NON_TAXABLE"],
            "BASE_AMOUNT": [100000.0, 5000.0, 20000.0, 10000.0],
            "CURRENCY_ID": ["INR", "INR", "INR", "INR"],
        }
    )


@pytest.fixture
def mock_realized_df() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "Realized_Event_ID": ["REAL_001", "REAL_002"],
            "Disposal_Date": [date(2023, 8, 10), date(2023, 12, 5)],
            "Realized_Gain_Loss": [15000.0, -3000.0],
            "Tax_Type": ["equity", "debt"],
            "Tax_Subtype": ["listed", "mf_pre"],
            "Holding_Type": ["LTCG", "STCG"],
            "Applied_Rate": [0.10, 0.30],
            "Estimated_Tax": [1500.0, 0.0],
            "Currency_ID": ["INR", "INR"],
            "Lot_Source_Type": ["TRADE", "TRADE"],
            "ISIN": ["INE002A01018", "INF209K01157"],
            "Lot_ID": ["LOT_1", "LOT_2"],
        }
    )


# ---------------------------------------------------------------------------
# 2. TaxClassifier Domain Logic Tests
# ---------------------------------------------------------------------------
def test_tax_classifier_map_quant_sub_head() -> None:
    # Equity listed
    row_eq_st = {"Tax_Type": "equity", "Tax_Subtype": "listed", "Holding_Type": "STCG"}
    subhead, ok = TaxClassifier.map_quant_sub_head(row_eq_st)
    assert ok and subhead == "Equity_Listed_STCG"

    row_eq_lt = {"Tax_Type": "equity", "Tax_Subtype": "direct", "Holding_Type": "LTCG"}
    subhead, ok = TaxClassifier.map_quant_sub_head(row_eq_lt)
    assert ok and subhead == "Equity_Listed_LTCG"

    # Equity unlisted
    row_eq_unlisted = {"Tax_Type": "equity", "Tax_Subtype": "unlisted", "Holding_Type": "STCG"}
    subhead, ok = TaxClassifier.map_quant_sub_head(row_eq_unlisted)
    assert ok and subhead == "Equity_Unlisted_STCG"

    # US / Foreign equity
    row_foreign = {"Tax_Type": "equity", "Tax_Subtype": "us_stocks", "Holding_Type": "LTCG"}
    subhead, ok = TaxClassifier.map_quant_sub_head(row_foreign)
    assert ok and subhead == "Default_LTCG"

    # Debt MF pre/post explicit
    row_debt_pre = {"Tax_Type": "debt", "Tax_Subtype": "mf_pre", "Holding_Type": "LTCG"}
    subhead, ok = TaxClassifier.map_quant_sub_head(row_debt_pre)
    assert ok and subhead == "Debt_MF_Pre_Cutoff_LTCG"

    row_debt_post = {"Tax_Type": "debt", "Tax_Subtype": "mf_post", "Holding_Type": "STCG"}
    subhead, ok = TaxClassifier.map_quant_sub_head(row_debt_post)
    assert ok and subhead == "Debt_MF_Post_Cutoff_STCG"

    # Debt MF acquisition date vs cutoff
    cutoff = "2023-03-31"
    row_debt_acq_pre = {
        "Tax_Type": "debt",
        "Tax_Subtype": "mf",
        "Holding_Type": "LTCG",
        "Acquisition_Date": date(2023, 1, 15),
    }
    subhead, ok = TaxClassifier.map_quant_sub_head(row_debt_acq_pre, debt_mf_cutoff_date=cutoff)
    assert ok and subhead == "Debt_MF_Pre_Cutoff_LTCG"

    row_debt_acq_post = {
        "Tax_Type": "debt",
        "Tax_Subtype": "mf",
        "Holding_Type": "LTCG",
        "Acquisition_Date": date(2023, 4, 1),
    }
    subhead, ok = TaxClassifier.map_quant_sub_head(row_debt_acq_post, debt_mf_cutoff_date=cutoff)
    assert ok and subhead == "Debt_MF_Post_Cutoff_LTCG"

    # Gold, SGB, REIT
    row_gold = {"Tax_Type": "gold", "Holding_Type": "LTCG"}
    subhead, ok = TaxClassifier.map_quant_sub_head(row_gold)
    assert ok and subhead == "Gold_LTCG"

    row_sgb = {"Tax_Type": "sgb", "Holding_Type": "LTCG"}
    subhead, ok = TaxClassifier.map_quant_sub_head(row_sgb)
    assert ok and subhead == "SGB_LTCG"

    row_reit = {"Tax_Type": "reit", "Holding_Type": "STCG"}
    subhead, ok = TaxClassifier.map_quant_sub_head(row_reit)
    assert ok and subhead == "REIT_STCG"

    # Invalid / Unmapped
    row_bad = {"Tax_Type": "crypto", "Holding_Type": "STCG"}
    subhead, ok = TaxClassifier.map_quant_sub_head(row_bad)
    assert not ok and subhead == "CHECK_REQUIRED"


def test_tax_classifier_validation(
    mock_rules: FinancialRules, mock_subcategory_df: pl.DataFrame
) -> None:
    # Tax credit subhead map
    credit_map = TaxClassifier.build_tax_credit_subhead_map(mock_rules)
    assert credit_map == {"CAT_CREDIT_TDS": "Interest Income"}

    # Validation succeeds on valid df
    TaxClassifier.validate_tax_credit_uids(mock_subcategory_df, credit_map)
    TaxClassifier.validate_subcategory_dimension(mock_subcategory_df)

    # Validation fails on missing credit UID
    with pytest.raises(ValueError, match="do not exist in silver.d_Income_Subcategory"):
        TaxClassifier.validate_tax_credit_uids(mock_subcategory_df, {"CAT_NON_EXISTENT": "Head"})

    # Validation fails on duplicate dimension UID
    dup_df = pl.concat([mock_subcategory_df, mock_subcategory_df.slice(0, 1)])
    with pytest.raises(ValueError, match="contains duplicate UID"):
        TaxClassifier.validate_subcategory_dimension(dup_df)


# ---------------------------------------------------------------------------
# 3. TaxEstimator Domain Logic Tests
# ---------------------------------------------------------------------------
def test_tax_estimator(mock_rules: FinancialRules) -> None:
    # Fallback ordinary rate
    rate = TaxEstimator.resolve_ordinary_income_rate(None, mock_rules, date(2023, 6, 1))
    assert rate == 0.30

    # Rate when rules is None
    assert TaxEstimator.resolve_ordinary_income_rate(None, None, date(2023, 6, 1)) is None

    # Number cleaning
    assert TaxEstimator.clean_optional_finite_number(123.45) == 123.45
    assert TaxEstimator.clean_optional_finite_number("100.5") == 100.5
    assert TaxEstimator.clean_optional_finite_number(True) is None
    assert TaxEstimator.clean_optional_finite_number(float("inf")) is None
    assert TaxEstimator.clean_optional_finite_number("invalid") is None
    assert TaxEstimator.clean_optional_finite_number(None) is None

    # Applied rate bounding
    assert TaxEstimator.clean_applied_rate(0.15) == 0.15
    assert TaxEstimator.clean_applied_rate(-0.05) is None
    assert TaxEstimator.clean_applied_rate(1.05) is None

    # Estimated tax bounding
    assert TaxEstimator.clean_estimated_tax(500.0) == 500.0
    assert TaxEstimator.clean_estimated_tax(0.0) == 0.0
    assert TaxEstimator.clean_estimated_tax(-100.0) is None


# ---------------------------------------------------------------------------
# 4. BaseEventsBuilder / TaxEventNormalizer Tests
# ---------------------------------------------------------------------------
def test_base_events_builder(
    mock_rules: FinancialRules,
    mock_income_df: pl.DataFrame,
    mock_realized_df: pl.DataFrame,
    mock_subcategory_df: pl.DataFrame,
) -> None:
    builder = BaseEventsBuilder(
        df_income=mock_income_df,
        df_realized_events=mock_realized_df,
        df_subcategory=mock_subcategory_df,
        rules=mock_rules,
    )
    lf_events = builder.build()
    df_events = lf_events.collect()

    # Verify columns and schema
    for col_name, dtype in TAX_EVENT_SCHEMA.items():
        assert col_name in df_events.columns
        assert df_events.schema[col_name] == dtype

    # Verify event sources:
    # 1 LEDGER (Salary; CAT_EXCL_STCG excluded, CAT_NON_TAXABLE excluded, CAT_CREDIT_TDS is separate)
    # 1 TAX_CREDIT (CAT_CREDIT_TDS)
    # 2 QUANT (REAL_001, REAL_002)
    sources = df_events.get_column("Source_Type").to_list()
    assert sources.count("LEDGER") == 1
    assert sources.count("TAX_CREDIT") == 1
    assert sources.count("QUANT") == 2
    assert len(df_events) == 4

    # Verify deterministic Tax_Event_IDs are non-empty and unique
    tax_ids = df_events.get_column("Tax_Event_ID").to_list()
    assert len(tax_ids) == len(set(tax_ids))
    for tid in tax_ids:
        assert tid.startswith("TAX_")


def test_base_events_builder_exclusion_credit_overlap(
    mock_rules: FinancialRules,
    mock_income_df: pl.DataFrame,
    mock_realized_df: pl.DataFrame,
    mock_subcategory_df: pl.DataFrame,
) -> None:
    # Make a category both an exclusion and a tax credit
    mock_rules.assumptions.tax.investment_exclusions.stcg_sub_cat_ids.append("CAT_CREDIT_TDS")
    builder = BaseEventsBuilder(
        df_income=mock_income_df,
        df_realized_events=mock_realized_df,
        df_subcategory=mock_subcategory_df,
        rules=mock_rules,
    )
    with pytest.raises(
        ValueError, match="cannot be both an investment-gain exclusion and a tax credit"
    ):
        builder.build()


# ---------------------------------------------------------------------------
# 5. TaxGoldFormatter / TaxReconciler Tests
# ---------------------------------------------------------------------------
def test_tax_gold_formatter(
    mock_rules: FinancialRules,
    mock_income_df: pl.DataFrame,
    mock_realized_df: pl.DataFrame,
    mock_subcategory_df: pl.DataFrame,
) -> None:
    builder = BaseEventsBuilder(
        df_income=mock_income_df,
        df_realized_events=mock_realized_df,
        df_subcategory=mock_subcategory_df,
        rules=mock_rules,
    )
    lf_events = builder.build()

    formatter = TaxGoldFormatter(
        lf_events=lf_events,
        df_income=mock_income_df,
        df_subcategory=mock_subcategory_df,
        investment_exclusion_uids=["CAT_EXCL_STCG", "CAT_EXCL_LTCG"],
    )

    df_summary = formatter.format_tax_year_summary().collect()
    df_breakdown = formatter.format_tax_income_breakdown().collect()
    df_reconciliation = formatter.format_tax_reconciliation().collect()

    assert not df_summary.is_empty()
    assert "FY" in df_summary.columns
    assert "Total_Ledger_Income" in df_summary.columns
    assert "Total_Investment_Gain_Loss" in df_summary.columns
    assert "Total_Tax_Credits" in df_summary.columns

    assert not df_breakdown.is_empty()
    assert "Income_Head" in df_breakdown.columns
    assert "Event_Amount_INR" in df_breakdown.columns

    assert not df_reconciliation.is_empty()
    assert "Tax_Sub_Head" in df_reconciliation.columns
    assert "Tax_Event_Amount" in df_reconciliation.columns


# ---------------------------------------------------------------------------
# 6. End-to-End TaxService Execution Test
# ---------------------------------------------------------------------------
def test_tax_service_orchestration(
    mock_rules: FinancialRules,
    mock_income_df: pl.DataFrame,
    mock_realized_df: pl.DataFrame,
    mock_subcategory_df: pl.DataFrame,
) -> None:
    service = TaxService(
        df_income=mock_income_df,
        df_realized_events=mock_realized_df,
        df_subcategory=mock_subcategory_df,
        rules=mock_rules,
    )
    results = service.run()

    expected_tables = {
        "df_f_tax_events",
        "df_p_tax_year_summary",
        "df_p_tax_income_breakdown",
        "df_p_tax_reconciliation",
    }
    assert set(results.keys()) == expected_tables

    for table_name, df in results.items():
        assert isinstance(df, pl.DataFrame), f"{table_name} is not a DataFrame"
        assert len(df) > 0, f"{table_name} should not be empty"
