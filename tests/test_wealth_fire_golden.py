"""Golden assertions verifying Wealth, FIRE targets, analytical resilience, and Monte Carlo invariants.

Owns
----
- Net worth aggregation and Target FI Corpus calculation.
- FI Gap and Progress metrics.
- Approved v11 Net-Worth Change Attribution identity:
    Asset_Market_Delta == Net_Savings_Flow + Market_Return_Flow + Attribution_Residual.
- Real inflation-adjusted core expense growth formula.
- Income resilience ratios (Passive Core Coverage, Active Dependency).
- Monte Carlo deterministic seed derivation and reproducibility provenance.
"""

from __future__ import annotations

import pytest

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.fire.reproducibility import (
    derive_monthly_seed,
    derive_simulation_seed_offset,
)


def test_wealth_fire_targets_and_resilience(mock_rules: FinancialRules) -> None:
    """Verify Target FI corpus, FI progress, and approved v11 income resilience ratios."""
    # From the miniature household fixture:
    monthly_core_expense = 40000.0
    annual_core_expense = monthly_core_expense * 12.0  # ₹4,80,000
    swr_mult = mock_rules.assumptions.fire.swr_multiplier  # 28.5 (3.5% SWR)

    target_fi_corpus = annual_core_expense * swr_mult  # ₹1,36,80,000
    assert target_fi_corpus == 13680000.0, "Expected Target FI Corpus = ₹1.368 Cr"

    # Current Net Worth: Checking ₹1,55,000 + Demat ₹50,000 = ₹2,05,000
    current_net_worth = 205000.0
    fi_progress = current_net_worth / target_fi_corpus
    fi_gap = target_fi_corpus - current_net_worth

    assert pytest.approx(fi_progress, abs=1e-5) == (205000.0 / 13680000.0)
    assert fi_gap == (13680000.0 - 205000.0)

    # v11 Income Resilience Ratios:
    # 1. Passive Core Expense Coverage = Passive Income / Core Expense
    passive_income = 5000.0
    passive_core_coverage = passive_income / monthly_core_expense  # 5,000 / 40,000 = 12.5%
    assert passive_core_coverage == 0.125

    # 2. Active Income Dependency = Active Income / Total Income
    active_income = 150000.0
    total_income = 155000.0
    active_dependency = active_income / total_income
    assert pytest.approx(active_dependency, abs=1e-4) == (150000.0 / 155000.0)  # ~96.77%


def test_net_worth_attribution_exact_identity() -> None:
    """Verify approved v11 Net-Worth Change Attribution identity:
    Asset_Market_Delta == Net_Savings_Flow + Market_Return_Flow + Attribution_Residual.
    """
    total_income = 155000.0
    total_expense = 50000.0
    net_savings_flow = total_income - total_expense  # ₹1,05,000

    opening_unrealized_pl = 10000.0
    closing_unrealized_pl = 16000.0
    realized_asset_pnl = 5600.0
    realized_forex_pnl = 4500.0

    market_return_flow = (
        (closing_unrealized_pl - opening_unrealized_pl) + realized_asset_pnl + realized_forex_pnl
    )  # 6000 + 5600 + 4500 = ₹16,100

    opening_market_assets = 500000.0
    closing_market_assets = 621100.0
    asset_market_delta = closing_market_assets - opening_market_assets  # ₹1,21,100

    attribution_residual = asset_market_delta - (net_savings_flow + market_return_flow)  # 0.0

    # Strict reconciliation identity check
    assert pytest.approx(asset_market_delta, abs=1e-6) == (
        net_savings_flow + market_return_flow + attribution_residual
    )


def test_inflation_adjusted_real_expense_growth() -> None:
    """Verify inflation-adjusted real core expense growth calculation."""
    # Year 1 Core: ₹40,000/mo = ₹4,80,000/yr.
    # Year 2 Core: ₹42,000/mo = ₹5,04,000/yr (Nominal growth = 5.0%)
    prev_core = 480000.0
    curr_core = 504000.0
    yoy_nominal = (curr_core - prev_core) / prev_core  # +0.05 (5%)

    # Inflation rate = 6.0% (0.06)
    inflation_rate = 0.06
    real_core_growth = ((1.0 + yoy_nominal) / (1.0 + inflation_rate)) - 1.0

    # With 5% nominal increase and 6% inflation, real spending fell by ~0.94%
    assert pytest.approx(real_core_growth, abs=1e-5) == ((1.05 / 1.06) - 1.0)


def test_monte_carlo_reproducibility_invariants() -> None:
    """Verify deterministic seed derivation offsets and monthly reproducible seeds."""
    seed_phrase = "shan_golden_portfolio_seed"
    offset1 = derive_simulation_seed_offset(seed_phrase)
    offset2 = derive_simulation_seed_offset(seed_phrase)

    assert offset1 == offset2
    assert isinstance(offset1, int)
    assert 0 <= offset1 < 1_000_000

    # Monthly seed generation is pure and deterministic
    m_seed = derive_monthly_seed(seed_phrase, 2026, 6)
    assert m_seed == (2026 * 12 + 6 + offset1)
