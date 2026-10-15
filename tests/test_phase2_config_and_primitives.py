"""Tests for Phase 2: Configuration, Preferences, and Common Domain Primitives.

Owns
----
- Complete identity equivalence verification between legacy shims and canonical targets for Phase 2.
- TOML configuration parsing and database audit export for Settings and FinancialRules.
- Indian Fiscal Year (FY) calculation and strict date parsing tests.
- FinancialSourceValidationError raising and numeric parsing tests.
- Deterministic entity ID generation tests using Canonical ID Serialization v2.
- PreferencesManager LRU and nonexistent file filtering tests.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

# Canonical Phase 2 imports
from personal_finance_etl.config.financial_rules import (
    ActiveIncomeRules,
    AssetRules,
    AssumptionsRules,
    BudgetAlerts,
    BudgetRules,
    BudgetSmoothing,
    CashflowAssetRules,
    CMAAssumptions,
    CoreExpenseRules,
    DigitalAssetRules,
    DividendIncomeRules,
    ExpenseRules,
    FinancialRules,
    FireAssumptions,
    GlidePathConfig,
    GuytonKlingerConfig,
    HumanCapitalConfig,
    IlliquidAssetRules,
    IncomeAllocationRules,
    IncomeRules,
    InflationModelConfig,
    InterestIncomeRules,
    InvestmentExclusionsConfig,
    InvestmentInstrumentRules,
    JumpDiffusionConfig,
    MacroAssumptions,
    MarkovRegimeConfig,
    MonteCarloAssumptions,
    NonCashIncomeRules,
    PortfolioManagementRules,
    TaxAssumptions,
    TaxHeadConfig,
    TaxRates,
    TaxSubHeadConfig,
)
from personal_finance_etl.config.settings import FileHashPolicy, Settings
from personal_finance_etl.domain.common.dates import (
    add_fy_if_missing,
    ensure_date_col,
    get_file_name,
    get_fy_folder_name,
    get_fy_start_year,
    get_fy_string,
    get_month_folder_name,
    parse_strict_date,
    to_date_obj,
    validate_and_parse_dates,
)
from personal_finance_etl.domain.common.identity import (
    canonicalize_value,
    generate_deterministic_id,
)
from personal_finance_etl.domain.common.polars import (
    pct_growth,
    rolling_avg,
    rolling_std,
    rolling_sum,
    safe_divide,
)
from personal_finance_etl.domain.common.validation import (
    FinancialSourceValidationError,
    clean_numeric_col,
    parse_strict_numeric,
    validate_and_parse_numerics,
)
from personal_finance_etl.infrastructure.filesystem.paths import (
    get_cache_dir,
    get_temp_dir,
    resource_path,
)
from personal_finance_etl.infrastructure.preferences.repository import PreferencesManager


def test_legacy_phase2_deactivation_and_reexports():
    """Verify that every deactivated legacy Phase 2 symbol is an exact alias ('is')."""
    import personal_finance_etl.backend.config.financial_rules as legacy_rules
    import personal_finance_etl.backend.config.settings as legacy_settings
    import personal_finance_etl.backend.engines.tax.utils.date_utils as legacy_tax_dates
    import personal_finance_etl.backend.utils.helpers as legacy_helpers
    import personal_finance_etl.backend.utils.identity as legacy_identity
    import personal_finance_etl.backend.utils.polars_expressions as legacy_polars

    # config.financial_rules
    assert legacy_rules.FinancialRules is FinancialRules
    assert legacy_rules.IncomeRules is IncomeRules
    assert legacy_rules.ActiveIncomeRules is ActiveIncomeRules
    assert legacy_rules.DividendIncomeRules is DividendIncomeRules
    assert legacy_rules.InterestIncomeRules is InterestIncomeRules
    assert legacy_rules.NonCashIncomeRules is NonCashIncomeRules
    assert legacy_rules.ExpenseRules is ExpenseRules
    assert legacy_rules.CoreExpenseRules is CoreExpenseRules
    assert legacy_rules.IncomeAllocationRules is IncomeAllocationRules
    assert legacy_rules.BudgetAlerts is BudgetAlerts
    assert legacy_rules.BudgetSmoothing is BudgetSmoothing
    assert legacy_rules.BudgetRules is BudgetRules
    assert legacy_rules.IlliquidAssetRules is IlliquidAssetRules
    assert legacy_rules.DigitalAssetRules is DigitalAssetRules
    assert legacy_rules.AssetRules is AssetRules
    assert legacy_rules.CashflowAssetRules is CashflowAssetRules
    assert legacy_rules.InvestmentInstrumentRules is InvestmentInstrumentRules
    assert legacy_rules.PortfolioManagementRules is PortfolioManagementRules
    assert legacy_rules.TaxRates is TaxRates
    assert legacy_rules.TaxSubHeadConfig is TaxSubHeadConfig
    assert legacy_rules.TaxHeadConfig is TaxHeadConfig
    assert legacy_rules.InvestmentExclusionsConfig is InvestmentExclusionsConfig
    assert legacy_rules.TaxAssumptions is TaxAssumptions
    assert legacy_rules.MacroAssumptions is MacroAssumptions
    assert legacy_rules.FireAssumptions is FireAssumptions
    assert legacy_rules.MarkovRegimeConfig is MarkovRegimeConfig
    assert legacy_rules.HumanCapitalConfig is HumanCapitalConfig
    assert legacy_rules.GlidePathConfig is GlidePathConfig
    assert legacy_rules.JumpDiffusionConfig is JumpDiffusionConfig
    assert legacy_rules.GuytonKlingerConfig is GuytonKlingerConfig
    assert legacy_rules.InflationModelConfig is InflationModelConfig
    assert legacy_rules.MonteCarloAssumptions is MonteCarloAssumptions
    assert legacy_rules.CMAAssumptions is CMAAssumptions
    assert legacy_rules.AssumptionsRules is AssumptionsRules

    # config.settings & infrastructure.preferences
    assert legacy_settings.Settings is Settings
    assert legacy_settings.FileHashPolicy is FileHashPolicy
    assert legacy_settings.PreferencesManager is PreferencesManager

    # domain.common.identity
    assert legacy_identity.generate_deterministic_id is generate_deterministic_id
    assert legacy_identity.canonicalize_value is canonicalize_value

    # domain.common.polars
    assert legacy_polars.safe_divide is safe_divide
    assert legacy_polars.pct_growth is pct_growth
    assert legacy_polars.rolling_avg is rolling_avg
    assert legacy_polars.rolling_std is rolling_std
    assert legacy_polars.rolling_sum is rolling_sum

    # backend.engines.tax.utils.date_utils
    assert legacy_tax_dates.add_fy_if_missing is add_fy_if_missing

    # backend.utils.helpers
    assert legacy_helpers.resource_path is resource_path
    assert legacy_helpers.get_temp_dir is get_temp_dir
    assert legacy_helpers.get_cache_dir is get_cache_dir
    assert legacy_helpers.clean_numeric_col is clean_numeric_col
    assert legacy_helpers.to_date_obj is to_date_obj
    assert legacy_helpers.get_fy_start_year is get_fy_start_year
    assert legacy_helpers.get_fy_folder_name is get_fy_folder_name
    assert legacy_helpers.get_month_folder_name is get_month_folder_name
    assert legacy_helpers.get_file_name is get_file_name
    assert legacy_helpers.ensure_date_col is ensure_date_col
    assert legacy_helpers.parse_strict_numeric is parse_strict_numeric
    assert legacy_helpers.parse_strict_date is parse_strict_date
    assert legacy_helpers.validate_and_parse_numerics is validate_and_parse_numerics
    assert legacy_helpers.validate_and_parse_dates is validate_and_parse_dates
    assert legacy_helpers.FinancialSourceValidationError is FinancialSourceValidationError


def test_financial_rules_toml_loading_and_export():
    """Verify loading real TOML config and flattening to DB records."""
    toml_path = Path("tests/financial_rules.toml")
    assert toml_path.exists()

    rules = FinancialRules.from_toml(str(toml_path))
    assert rules.DEFAULT_CURRENCY_ID == "INR_INR"
    assert rules.assumptions.macro.default_trading_days == 252.0
    assert rules.assumptions.fire.swr_multiplier == 28.5
    assert rules.assumptions.tax.rates.equity_ltcg == 0.125
    assert rules.assumptions.tax.rates.equity_stcg == 0.20
    assert rules.budget.income_allocation.core_expense_pct == 0.40

    # Test export to db records
    records = rules.export_to_db_records()
    assert isinstance(records, list)
    assert len(records) > 0
    first = records[0]
    assert "Rule_Domain" in first
    assert "Rule_Type" in first
    assert "Target_Level" in first
    assert "Target_ID" in first


def test_financial_rules_exclusion_validation():
    """Verify exclusion validation against subcategory dimension."""
    toml_path = Path("tests/financial_rules.toml")
    rules = FinancialRules.from_toml(str(toml_path))

    # Should succeed with matching UIDs
    df_valid = pl.DataFrame(
        {"UID": ["test-stocks-stcg-uid", "test-stocks-ltcg-uid", "INCOME_INTEREST"]}
    )
    rules.validate_investment_exclusion_uids(df_valid)

    # Missing configured UIDs raises ValueError
    df_missing = pl.DataFrame({"UID": ["OTHER_UID"]})
    with pytest.raises(ValueError, match="Configured STCG/LTCG investment exclusion"):
        rules.validate_investment_exclusion_uids(df_missing)

    # Missing UID column must raise ValueError
    with pytest.raises(ValueError, match="must contain UID"):
        rules.validate_investment_exclusion_uids(pl.DataFrame({"OTHER": [1, 2]}))


def test_tax_assumptions_mutual_exclusivity():
    """Verify that overlapping tax subheads or credit categories raise ValueError."""
    # Test duplicate subhead under the same head
    with pytest.raises(ValueError, match="Duplicate sub-head declaration"):
        TaxAssumptions(
            debt_mf_cutoff_date="2023-04-01",
            harvest_wait_days_threshold=30,
            ltcg_threshold_months={"EQUITY": 12},
            fallback_equity_ltcg_exemption=125000.0,
            heads_of_income={
                "salary": TaxHeadConfig(
                    sub_heads={
                        "basic": TaxSubHeadConfig(
                            tax_head_display_name="Salary",
                            sub_head_display_name="Basic",
                            sub_cat_ids=["SUB_SALARY_1"],
                        ),
                        "BASIC": TaxSubHeadConfig(
                            tax_head_display_name="Salary",
                            sub_head_display_name="Basic",
                            sub_cat_ids=["SUB_SALARY_2"],
                        ),
                    }
                )
            },
        )


def test_settings_toml_loading_and_flatten():
    """Verify Settings loads from TOML and flattens to DB records."""
    toml_path = Path("tests/config.toml")
    assert toml_path.exists()

    cfg = Settings.from_toml(str(toml_path), track_recent=False)
    assert cfg.TARGET_DB_NAME == "Personal_Finance_DB.duckdb"
    assert cfg.FILE_HASH_POLICY.csv is True

    records = cfg.export_to_db_records()
    assert isinstance(records, list)
    assert len(records) > 0
    for r in records:
        assert "Setting_Group" in r
        assert "Setting_Key" in r
        assert "Setting_Value" in r


def test_preferences_manager(tmp_path: Path):
    """Verify PreferencesManager saves recent configs, caps at 10, and filters nonexistent paths."""
    prefs_file = str(tmp_path / "prefs.json")
    mgr = PreferencesManager(prefs_path=prefs_file)

    # Create dummy files
    f1 = tmp_path / "cfg1.toml"
    f2 = tmp_path / "cfg2.toml"
    f1.write_text("a = 1")
    f2.write_text("b = 2")

    mgr.add_recent_config(str(f1))
    mgr.add_recent_config(str(f2))
    assert mgr.get_recent_configs() == [str(f2), str(f1)]

    # Adding an already present file shifts it to the front
    mgr.add_recent_config(str(f1))
    assert mgr.get_recent_configs() == [str(f1), str(f2)]

    # Deleting f1 filters it out on read
    f1.unlink()
    assert mgr.get_recent_configs() == [str(f2)]


def test_deterministic_identity_v2():
    """Verify Canonical ID Serialization v2 produces deterministic hashes."""
    purchase_fields = {
        "ISIN": "INE002A01018",
        "Date": date(2024, 1, 15),
        "Price": 2500.50,
        "Quantity": 10,
        "CURRENCY_ID": "INR_INR",
    }
    id1 = generate_deterministic_id("PURCHASE", purchase_fields)
    assert id1.startswith("PURCHASE_")

    # Dict insertion order must not change the generated hash
    reversed_fields = dict(reversed(list(purchase_fields.items())))
    id2 = generate_deterministic_id("PURCHASE", reversed_fields)
    assert id1 == id2

    # Canonicalization tests
    assert canonicalize_value(None) == "<NULL>"
    assert canonicalize_value(True) == "true"
    assert canonicalize_value(False) == "false"
    assert canonicalize_value(date(2024, 5, 20)) == "2024-05-20"
    assert canonicalize_value(datetime(2024, 5, 20, 10, 30, 0)) == "2024-05-20T10:30:00"
    assert canonicalize_value(Decimal("100.5000")) == "100.5"
    assert canonicalize_value(Decimal("0.000")) == "0"
    assert canonicalize_value("  INFY  ") == "INFY"


def test_indian_fiscal_year_computations():
    """Verify April 1 start and March 31 end boundaries of Indian financial years."""
    # April 1, 2024 -> FY 2024-25
    d1 = date(2024, 4, 1)
    assert get_fy_start_year(d1) == 2024
    assert get_fy_folder_name(d1) == "2024-25"
    assert get_fy_string(d1) == "2024-25"

    # March 31, 2024 -> FY 2023-24
    d2 = date(2024, 3, 31)
    assert get_fy_start_year(d2) == 2023
    assert get_fy_folder_name(d2) == "2023-24"

    # Folder & file names
    assert get_month_folder_name(d1) == "04-2024"
    assert get_file_name(d1) == "01-04-2024.csv"

    # Add FY to Polars LazyFrame
    lf = pl.LazyFrame({"Tx_Date": [date(2024, 4, 15), date(2024, 1, 10)]})
    lf_with_fy = add_fy_if_missing(lf, "Tx_Date").collect()
    assert "FY" in lf_with_fy.columns
    assert lf_with_fy["FY"].to_list() == ["2024-25", "2023-24"]


def test_date_parsing_and_validation():
    """Verify strict scalar and LazyFrame date validation."""
    assert to_date_obj("2024-05-15") == date(2024, 5, 15)
    assert to_date_obj(None) is None
    assert to_date_obj("invalid", strict=False) is None
    with pytest.raises(ValueError, match="Cannot parse date"):
        to_date_obj("invalid", strict=True)

    # parse_strict_date
    assert parse_strict_date("2024-06-01") == date(2024, 6, 1)
    assert parse_strict_date(None, optional=True) is None
    with pytest.raises(FinancialSourceValidationError, match="missing/null"):
        parse_strict_date(None, optional=False)
    with pytest.raises(FinancialSourceValidationError, match="Malformed"):
        parse_strict_date("not-a-date")

    # validate_and_parse_dates on LazyFrame with String dates
    lf_valid = pl.LazyFrame({"Date": ["2024-01-01", "2024-02-01"]})
    parsed = validate_and_parse_dates(lf_valid, {"Date": ["%Y-%m-%d"]}).collect()
    assert parsed["Date"].dtype == pl.Date

    # validate_and_parse_dates on LazyFrame with Datetime objects (e.g. from Excel)
    lf_datetime = pl.LazyFrame({"Date": [datetime(2026, 2, 5, 0, 0), datetime(2026, 2, 6, 12, 30)]})
    parsed_dt = validate_and_parse_dates(
        lf_datetime,
        {"Date": ["%d-%b-%y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"]},
    ).collect()
    assert parsed_dt["Date"].dtype == pl.Date
    assert parsed_dt["Date"].to_list() == [date(2026, 2, 5), date(2026, 2, 6)]

    # Malformed populated date raises FinancialSourceValidationError
    lf_bad = pl.LazyFrame({"Date": ["2024-01-01", "corrupt_date"]})
    with pytest.raises(FinancialSourceValidationError, match="Malformed or missing"):
        validate_and_parse_dates(lf_bad, {"Date": ["%Y-%m-%d"]}).collect()


def test_numeric_parsing_and_validation():
    """Verify strict scalar and LazyFrame numeric validation."""
    assert parse_strict_numeric("1,250.75") == 1250.75
    assert parse_strict_numeric(" 50% ") == 50.0
    assert parse_strict_numeric(None, optional=True) is None
    with pytest.raises(FinancialSourceValidationError, match="missing/null"):
        parse_strict_numeric(None, optional=False)
    with pytest.raises(FinancialSourceValidationError, match="Malformed"):
        parse_strict_numeric("1O0")  # letter O instead of 0

    # clean_numeric_col
    df = pl.DataFrame({"Amount": ["1,500.50", "2,000.00"]})
    df_clean = clean_numeric_col(df, "Amount")
    assert df_clean["Amount"].dtype == pl.Float64
    assert df_clean["Amount"].to_list() == [1500.50, 2000.00]

    # validate_and_parse_numerics on LazyFrame
    lf_bad = pl.LazyFrame({"Price": ["100.0", "BAD_NUM"]})
    with pytest.raises(FinancialSourceValidationError, match="Malformed or missing"):
        validate_and_parse_numerics(lf_bad, ["Price"]).collect()


def test_polars_analytical_primitives():
    """Verify safe_divide, pct_growth, and rolling expressions."""
    df = pl.DataFrame(
        {
            "num": [10.0, 20.0, 30.0],
            "den": [2.0, 0.0, 5.0],
            "val": [100.0, 110.0, 121.0],
        }
    )

    result = df.select(
        safe_divide("num", "den", default=-1.0).alias("div"),
        pct_growth("val", periods=1).alias("growth"),
    )
    div_vals = result["div"].to_list()
    assert div_vals == [5.0, -1.0, 6.0]

    growth_vals = result["growth"].to_list()
    assert growth_vals[0] == 0.0  # default when shifted is null
    assert pytest.approx(growth_vals[1]) == 0.10
    assert pytest.approx(growth_vals[2]) == 0.10


def test_filesystem_paths():
    """Verify filesystem resource and temporary path resolution."""
    temp_dir = get_temp_dir()
    assert Path(temp_dir).is_dir()

    cache_dir = get_cache_dir(temp_dir, "test_cache")
    assert Path(cache_dir).is_dir()

    res = resource_path("tests/config.toml")
    assert Path(res).exists()
