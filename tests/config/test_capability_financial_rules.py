"""Tests for capability-scoped FinancialRules models and structural invariants.

Owns
----
- Positive verification of capability combinations across multi-capability fixtures.
- Positive verification of canonical fixtures and user's live personal finance rules.
- Negative verification of zero-legacy compatibility (rejection of legacy root keys).
- Negative verification of domain mathematical invariants (holding periods, tax rates,
  probability bounds, Markov stochastic matrix normalization, numerical constraints).
- Verification of disjoint classification invariants across cash pools, illiquid, and PnL sources.
- Verification of plan-capability rule alignment and diagnostic issue emission.

Does not own
-------------
- TOML persistence or file discovery (owned by infrastructure layer).
- Columnar DuckDB schema validation (owned by infrastructure.warehouse).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from personal_finance_etl.config.financial_rules import (
    AssetRules,
    CashflowAssetRules,
    FinancialRules,
    FireAssumptions,
    HouseholdCapabilityRules,
    HumanCapitalConfig,
    IlliquidAssetRules,
    InvestmentsCapabilityRules,
    JumpDiffusionConfig,
    MarkovRegimeConfig,
    MonteCarloAssumptions,
    TaxCapabilityRules,
    TaxRates,
    WealthCapabilityRules,
)
from personal_finance_etl.contracts import (
    CapabilityId,
    DiagnosticSeverity,
    ExecutionPlan,
)

# ---------------------------------------------------------------------------
# Positive Tests: Multi-Capability Fixtures
# ---------------------------------------------------------------------------


def test_minimal_household_fixture(fixtures_dir: Path) -> None:
    """Verify loading minimal household rules without tax, fire, or wealth rules."""
    path = fixtures_dir / "financial_rules_minimal_household.toml"
    rules = FinancialRules.from_toml(path)

    assert rules.household is not None
    assert "2" in rules.household.income.active.category_ids
    assert "CB261E83-6B2F-4D5B-A25B-B5C9CDA1C0F5" in rules.household.expense.core.category_ids
    assert rules.household.budget.smoothing.income_smoothing_months == 3

    # Wealth, Tax, and FIRE are absent or default
    assert rules.tax is None
    assert rules.fire is None
    assert rules.wealth.assets.cashflow.cash_pools == []

    # Accessing assumptions on minimal rules raises AttributeError
    with pytest.raises(AttributeError, match="must be configured to access assumptions"):
        _ = rules.assumptions

    # Plan validation: HOUSEHOLD_CORE only passes without error
    plan = ExecutionPlan(
        plan_fingerprint="test_plan_household",
        requested_capabilities=(CapabilityId.HOUSEHOLD_CORE,),
        resolved_capabilities=(CapabilityId.HOUSEHOLD_CORE,),
        required_bronze_datasets=(),
        optional_bronze_datasets=(),
        active_silver_datasets=(),
        active_gold_datasets=(),
        required_external_enrichments=(),
        ordered_engine_stages=(),
    )
    issues = rules.validate_against_plan(plan)
    assert len(issues) == 0


def test_household_wealth_fixture(fixtures_dir: Path) -> None:
    """Verify loading household + wealth capability rules."""
    path = fixtures_dir / "financial_rules_household_wealth.toml"
    rules = FinancialRules.from_toml(path)

    assert rules.household is not None
    assert rules.wealth is not None
    assert "2" in rules.household.income.active.category_ids
    assert "1" in rules.wealth.assets.cashflow.cash_pools
    assert "a87da9a8-c539-4889-825d-404d841a0a8f" in rules.wealth.assets.illiquid.category_ids
    assert rules.tax is None
    assert rules.fire is None

    plan = ExecutionPlan(
        plan_fingerprint="test_plan_wealth",
        requested_capabilities=(CapabilityId.HOUSEHOLD_CORE, CapabilityId.WEALTH),
        resolved_capabilities=(CapabilityId.HOUSEHOLD_CORE, CapabilityId.WEALTH),
        required_bronze_datasets=(),
        optional_bronze_datasets=(),
        active_silver_datasets=(),
        active_gold_datasets=(),
        required_external_enrichments=(),
        ordered_engine_stages=(),
    )
    issues = rules.validate_against_plan(plan)
    assert len(issues) == 0


def test_household_investments_tax_fixture(fixtures_dir: Path) -> None:
    """Verify loading household + investments + tax capability rules."""
    path = fixtures_dir / "financial_rules_household_investments_tax.toml"
    rules = FinancialRules.from_toml(path)

    assert rules.household is not None
    assert rules.investments is not None
    assert rules.tax is not None
    assert rules.fire is None

    assert rules.investments.default_currency_id == "INR_INR"
    assert rules.tax.rates.equity_ltcg == 0.125
    assert rules.tax.ltcg_threshold_months["equity_listed"] == 12

    plan = ExecutionPlan(
        plan_fingerprint="test_plan_invest_tax",
        requested_capabilities=(
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
            CapabilityId.TAX,
        ),
        resolved_capabilities=(
            CapabilityId.HOUSEHOLD_CORE,
            CapabilityId.INVESTMENT_ACCOUNTING,
            CapabilityId.TAX,
        ),
        required_bronze_datasets=(),
        optional_bronze_datasets=(),
        active_silver_datasets=(),
        active_gold_datasets=(),
        required_external_enrichments=(),
        ordered_engine_stages=(),
    )
    issues = rules.validate_against_plan(plan)
    assert len(issues) == 0


def test_canonical_financial_rules_fixture(rules_path: Path) -> None:
    """Verify loading canonical fully-composed financial_rules.toml."""
    rules = FinancialRules.from_toml(rules_path)

    assert rules.household is not None
    assert rules.wealth is not None
    assert rules.investments is not None
    assert rules.tax is not None
    assert rules.fire is not None
    assert rules.benchmark is not None

    assert rules.DEFAULT_CURRENCY_ID == "INR_INR"
    assert rules.benchmark.default_benchmark_index == "NIFTY 50"
    assert rules.benchmark.fallback_risk_free_rate == 0.06
    assert rules.benchmark.track_benchmark_alpha is True
    assert rules.income.active.category_ids
    assert rules.expense.core.category_ids
    assert rules.budget.smoothing.income_smoothing_months == 3
    assert rules.assets.cashflow.cash_pools
    assert rules.portfolio_management.rebalance_tolerance_pct_points == 5.0
    assert rules.assumptions.tax is not None
    assert rules.assumptions.fire is not None


def test_user_live_financial_rules() -> None:
    """Verify loading user's live restructured personal finance rules."""
    live_path = Path(
        "G:/My Drive/Docs/Financial Docs/Financial Planner/Analysis/ETL App/shan_personal_finance_rules.toml"
    )
    if not live_path.exists():
        pytest.skip(f"Live file not accessible: {live_path}")

    rules = FinancialRules.from_toml(live_path)
    assert rules.household is not None
    assert rules.wealth is not None
    assert rules.investments is not None
    assert rules.tax is not None
    assert rules.fire is not None
    assert rules.benchmark is not None

    assert rules.DEFAULT_CURRENCY_ID == "INR_INR"
    assert rules.portfolio_management.rebalance_tolerance_pct_points == 5.0
    assert len(rules.wealth.assets.cashflow.cash_pools) > 0
    assert len(rules.wealth.assets.illiquid.category_ids) > 0
    assert rules.fire.monte_carlo.iterations >= 100


def test_rules_convenience_properties(rules_path: Path) -> None:
    """Verify domain calculation convenience properties provide backwards-compatible views."""
    rules = FinancialRules.from_toml(rules_path)

    assert rules.income == rules.household.income
    assert rules.expense == rules.household.expense
    assert rules.budget == rules.household.budget
    assert rules.assets == rules.wealth.assets
    assert rules.portfolio_management == rules.investments.portfolio_management
    assert rules.DEFAULT_CURRENCY_ID == rules.investments.default_currency_id
    assert rules.MF_SCHEME_MAPPINGS == rules.investments.mf_scheme_mappings
    assert rules.assumptions.tax == rules.tax


# ---------------------------------------------------------------------------
# Negative Tests: Strict Rejection of Legacy Root Keys
# ---------------------------------------------------------------------------


def test_reject_legacy_income_root_key(tmp_path: Path) -> None:
    """Verify rejection of legacy top-level [income] table without [household]."""
    p = tmp_path / "legacy_income.toml"
    p.write_text('[income]\ncategories = ["Salary"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Non-capability root keys.*forbidden"):
        FinancialRules.from_toml(p)


def test_reject_legacy_expense_root_key(tmp_path: Path) -> None:
    """Verify rejection of legacy top-level [expense] table."""
    p = tmp_path / "legacy_expense.toml"
    p.write_text('[expense]\ncategories = ["Groceries"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Non-capability root keys.*forbidden"):
        FinancialRules.from_toml(p)


def test_reject_legacy_assets_root_key(tmp_path: Path) -> None:
    """Verify rejection of legacy top-level [assets] table."""
    p = tmp_path / "legacy_assets.toml"
    p.write_text('[assets]\ncash_pools = ["Checking"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="Non-capability root keys.*forbidden"):
        FinancialRules.from_toml(p)


def test_reject_legacy_assumptions_root_key(tmp_path: Path) -> None:
    """Verify rejection of legacy top-level [assumptions] table."""
    p = tmp_path / "legacy_assumptions.toml"
    p.write_text("[assumptions.macro]\ninflation_rate = 0.06\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Non-capability root keys.*forbidden"):
        FinancialRules.from_toml(p)


# ---------------------------------------------------------------------------
# Negative Tests: Domain Policy & Mathematical Invariants
# ---------------------------------------------------------------------------


def test_holding_period_must_be_positive() -> None:
    """Verify statutory holding periods must be strictly positive (> 0)."""
    with pytest.raises(ValidationError, match="must be strictly positive"):
        TaxCapabilityRules(
            rates=TaxRates(),
            ltcg_threshold_months={"equity": 0},
            debt_mf_cutoff_date="2023-03-31",
            harvest_wait_days_threshold=90,
            fallback_equity_ltcg_exemption=125000.0,
        )

    with pytest.raises(ValidationError, match="must be strictly positive"):
        TaxCapabilityRules(
            rates=TaxRates(),
            ltcg_threshold_months={"debt": -6},
            debt_mf_cutoff_date="2023-03-31",
            harvest_wait_days_threshold=90,
            fallback_equity_ltcg_exemption=125000.0,
        )


def test_tax_rate_cannot_be_negative() -> None:
    """Verify statutory tax rates cannot be negative (< 0)."""
    with pytest.raises(ValidationError, match="cannot be negative"):
        TaxRates(equity_ltcg=-0.05)

    with pytest.raises(ValidationError, match="cannot be negative"):
        TaxRates(equity_stcg=-0.15)


def test_merton_jump_probability_bounds() -> None:
    """Verify Merton jump diffusion arrival rate lambda must be in [0.0, 1.0]."""
    with pytest.raises(ValidationError, match="must be bounded"):
        JumpDiffusionConfig(jump_probability_annual=-0.01)

    with pytest.raises(ValidationError, match="must be bounded"):
        JumpDiffusionConfig(jump_probability_annual=1.5)


def test_human_capital_probability_bounds() -> None:
    """Verify Human Capital shock probability must be bounded between 0.0 and 1.0."""
    with pytest.raises(ValidationError, match="must be bounded"):
        HumanCapitalConfig(shock_probability=-0.1)

    with pytest.raises(ValidationError, match="must be bounded"):
        HumanCapitalConfig(shock_probability=1.2)


def test_markov_matrix_row_sum_must_equal_one() -> None:
    """Verify Markov transition matrix rows must sum to 1.0."""
    invalid_matrix = [
        [0.5, 0.2, 0.1],  # Sum = 0.8 != 1.0
        [0.15, 0.80, 0.05],
        [0.10, 0.15, 0.75],
    ]
    with pytest.raises(ValidationError, match="must sum strictly to 1.0"):
        MarkovRegimeConfig(transition_matrix=invalid_matrix)


def test_monte_carlo_iterations_must_be_at_least_100() -> None:
    """Verify Monte Carlo simulation iterations must be >= 100."""
    with pytest.raises(ValidationError, match="iterations must be at least 100"):
        MonteCarloAssumptions(
            iterations=50,
            max_months=360,
            annual_volatility=0.15,
            real_return_floor=-0.05,
            desired_target_age=50,
            date_of_birth="1990-01-01",
        )


def test_volatility_must_be_positive() -> None:
    """Verify Monte Carlo volatility must be strictly positive (> 0)."""
    with pytest.raises(ValidationError, match="annual_volatility must be strictly positive"):
        MonteCarloAssumptions(
            iterations=1000,
            max_months=360,
            annual_volatility=0.0,
            real_return_floor=-0.05,
            desired_target_age=50,
            date_of_birth="1990-01-01",
        )


def test_fire_model_max_months_must_be_positive() -> None:
    """Verify FIRE simulation max_months must be strictly positive (> 0)."""
    with pytest.raises(ValidationError, match="max_months must be strictly positive"):
        MonteCarloAssumptions(
            iterations=1000,
            max_months=0,
            annual_volatility=0.15,
            real_return_floor=-0.05,
            desired_target_age=50,
            date_of_birth="1990-01-01",
        )


def test_fire_model_swr_multiplier_must_be_positive() -> None:
    """Verify FIRE safe withdrawal rate multiplier must be strictly positive (> 0)."""
    with pytest.raises(ValidationError, match="SWR multiplier must be strictly positive"):
        FireAssumptions(
            swr_multiplier=0.0,
            coast_fi_real_return=0.04,
            coast_fi_years=10,
            lean_fi_ratio=0.75,
            fallback_trailing_return=0.12,
            cape_swr_floor=0.03,
            cape_swr_ceiling=0.05,
            cape_swr_base=0.04,
            human_capital_max_age=60.0,
            human_capital_discount_rate=0.08,
        )


def test_disjoint_cash_pools_vs_illiquid_overlap() -> None:
    """Verify disjoint classification between cash pools and illiquid assets."""
    with pytest.raises(ValidationError, match="Disjoint classification violation"):
        WealthCapabilityRules(
            assets=AssetRules(
                cashflow=CashflowAssetRules(cash_pools=["Checking_A", "Savings_B"]),
                illiquid=IlliquidAssetRules(category_ids=["Checking_A", "Real_Estate"]),
            )
        )


def test_disjoint_cash_pools_vs_non_cash_pnl_overlap() -> None:
    """Verify disjoint classification between cash pools and non-cash PnL sources."""
    with pytest.raises(ValidationError, match="Disjoint classification violation"):
        WealthCapabilityRules(
            assets=AssetRules(
                cashflow=CashflowAssetRules(
                    cash_pools=["Checking_A", "Wallet"],
                    non_cash_pnl_sources=["Checking_A"],
                ),
            )
        )


# ---------------------------------------------------------------------------
# Plan Alignment Diagnostic Tests
# ---------------------------------------------------------------------------


def test_plan_validation_detects_missing_tax_rules() -> None:
    """Verify plan validation detects missing [tax] section when CapabilityId.TAX is requested."""
    rules = FinancialRules(
        household=HouseholdCapabilityRules(),
        wealth=WealthCapabilityRules(),
        investments=InvestmentsCapabilityRules(),
        tax=None,  # Missing!
        fire=None,
    )
    plan = ExecutionPlan(
        plan_fingerprint="plan_with_tax",
        requested_capabilities=(CapabilityId.TAX,),
        resolved_capabilities=(CapabilityId.TAX,),
        required_bronze_datasets=(),
        optional_bronze_datasets=(),
        active_silver_datasets=(),
        active_gold_datasets=(),
        required_external_enrichments=(),
        ordered_engine_stages=(),
    )
    issues = rules.validate_against_plan(plan)
    assert len(issues) == 1
    assert issues[0].field == "tax"
    assert issues[0].severity == DiagnosticSeverity.ERROR
    assert "requires a configured [tax] section" in issues[0].message


def test_plan_validation_detects_missing_fire_rules() -> None:
    """Verify plan validation detects missing [fire] section when CapabilityId.FIRE is requested."""
    rules = FinancialRules(
        household=HouseholdCapabilityRules(),
        wealth=WealthCapabilityRules(),
        investments=InvestmentsCapabilityRules(),
        tax=TaxCapabilityRules(
            rates=TaxRates(),
            ltcg_threshold_months={"equity": 12},
            debt_mf_cutoff_date="2023-03-31",
            harvest_wait_days_threshold=90,
            fallback_equity_ltcg_exemption=125000.0,
        ),
        fire=None,  # Missing!
    )
    plan = ExecutionPlan(
        plan_fingerprint="plan_with_fire",
        requested_capabilities=(CapabilityId.FIRE,),
        resolved_capabilities=(CapabilityId.FIRE,),
        required_bronze_datasets=(),
        optional_bronze_datasets=(),
        active_silver_datasets=(),
        active_gold_datasets=(),
        required_external_enrichments=(),
        ordered_engine_stages=(),
    )
    issues = rules.validate_against_plan(plan)
    assert len(issues) == 1
    assert issues[0].field == "fire"
    assert issues[0].severity == DiagnosticSeverity.ERROR
    assert "requires a configured [fire] section" in issues[0].message
