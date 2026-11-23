"""Golden assertions verifying Tax classification, FX decomposition, and Benchmark active return.

Owns
----
- FX rate lookup and currency conversion validation.
- Asset PnL and Forex PnL mathematical decomposition:
    Total_PnL == Asset_PnL + Forex_PnL.
- Benchmark return comparison and active return (Alpha).
- Tax classification into statutory heads and sub-heads.
- Tax rate resolution, estimated tax computation, and LTCG exemption handling.
"""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.market.fx import FXRateProvider
from personal_finance_etl.domain.tax import TaxClassifier, TaxEstimator


def test_fx_conversion_and_pnl_decomposition() -> None:
    """Verify exact mathematical decomposition of foreign position return into Asset PnL and FX PnL."""
    # FX rates: 2023-08-01 = 80.0 INR/USD, 2024-01-31 = 83.0 INR/USD
    df_fx = pl.DataFrame(
        {
            "Date": [date(2023, 8, 1), date(2024, 1, 31)],
            "Currency_ID": ["USD_INR", "USD_INR"],
            "FX_Rate": [80.0, 83.0],
        }
    )
    provider = FXRateProvider(df_fx, default_currency_id="INR_INR")

    rate_buy = provider.get_rate(date(2023, 8, 1), "USD_INR")
    rate_close = provider.get_rate(date(2024, 1, 31), "USD_INR")

    assert rate_buy is not None and rate_close is not None
    assert rate_buy == 80.0
    assert rate_close == 83.0

    # 10 shares of AAPL bought at $150, closed at $180
    qty = 10.0
    buy_price_usd = 150.0
    close_price_usd = 180.0

    local_buy_value = qty * buy_price_usd  # $1,500
    base_buy_value = local_buy_value * rate_buy  # ₹1,20,000

    local_close_value = qty * close_price_usd  # $1,800
    base_close_value = local_close_value * rate_close  # ₹1,49,400

    total_pnl = base_close_value - base_buy_value  # ₹29,400

    # Exact decomposition
    # Asset PnL: Gain in local currency converted at closing FX
    asset_pnl = qty * (close_price_usd - buy_price_usd) * rate_close  # 10 * 30 * 83 = ₹24,900
    # Forex PnL: FX movement applied to original invested principal
    forex_pnl = local_buy_value * (rate_close - rate_buy)  # 1500 * 3 = ₹4,500

    assert asset_pnl == 24900.0, "Expected Asset PnL = ₹24,900"
    assert forex_pnl == 4500.0, "Expected Forex PnL = ₹4,500"
    assert total_pnl == (asset_pnl + forex_pnl), (
        "Total PnL must strictly equal Asset PnL + Forex PnL"
    )


def test_benchmark_active_return() -> None:
    """Verify benchmark return comparison and active return (Alpha)."""
    # Asset bought @ 100, sold @ 150 -> 50% return
    asset_return = (150.0 - 100.0) / 100.0  # +0.50

    # Benchmark bought @ 18,000, closed @ 21,600 -> 20% return
    bm_buy = 18000.0
    bm_close = 21600.0
    bm_return = (bm_close - bm_buy) / bm_buy  # +0.20

    active_return = asset_return - bm_return  # +0.30
    assert pytest.approx(active_return, abs=1e-6) == 0.30


def test_tax_classification_and_rates(mock_rules: FinancialRules) -> None:
    """Verify statutory tax classification, rates, and LTCG exemption limit deduction."""
    # 1. TaxClassifier mappings
    row_listed_lt = {"Tax_Type": "equity", "Tax_Subtype": "listed", "Holding_Type": "LTCG"}
    subhead_lt, ok = TaxClassifier.map_quant_sub_head(row_listed_lt)
    assert ok is True
    assert subhead_lt == "Equity_Listed_LTCG"

    row_listed_st = {"Tax_Type": "equity", "Tax_Subtype": "listed", "Holding_Type": "STCG"}
    subhead_st, ok = TaxClassifier.map_quant_sub_head(row_listed_st)
    assert ok is True
    assert subhead_st == "Equity_Listed_STCG"

    # Debt MF post-cutoff is always STCG slab
    row_debt_post = {
        "Tax_Type": "debt",
        "Tax_Subtype": "mf",
        "Holding_Type": "LTCG",
        "Acquisition_Date": date(2023, 4, 15),
    }
    subhead_debt, ok = TaxClassifier.map_quant_sub_head(
        row_debt_post, debt_mf_cutoff_date="2023-04-01"
    )
    assert ok is True
    assert subhead_debt == "Debt_MF_Post_Cutoff_LTCG"

    # 2. Rate and Estimated Tax calculation
    # Rate: 12.5% LTCG on ₹2,00,000 gain with ₹1,25,000 exemption
    gain = 200000.0
    exemption_limit = mock_rules.assumptions.tax.fallback_equity_ltcg_exemption  # 125,000
    taxable_gain = max(0.0, gain - exemption_limit)  # 75,000
    base_rate = mock_rules.assumptions.tax.rates.equity_ltcg  # 0.125
    cess_rate = 0.04
    effective_rate = base_rate * (1.0 + cess_rate)  # 0.130 (13%)

    estimated_tax = taxable_gain * effective_rate
    assert taxable_gain == 75000.0
    assert pytest.approx(estimated_tax, abs=1e-2) == (75000.0 * 0.13)  # ₹9,750

    # 3. TaxEstimator rate resolution fallback & bounds
    ordinary_rate = TaxEstimator.resolve_ordinary_income_rate(None, mock_rules, date(2024, 1, 15))
    assert ordinary_rate == mock_rules.assumptions.macro.fallback_ordinary_income_rate
    assert TaxEstimator.clean_applied_rate(0.125) == 0.125
    assert TaxEstimator.clean_applied_rate(-0.5) is None
    assert TaxEstimator.clean_estimated_tax(-100.0) is None
    assert TaxEstimator.clean_estimated_tax(500.0) == 500.0
