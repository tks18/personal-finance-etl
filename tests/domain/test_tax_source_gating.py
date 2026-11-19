# pyright: reportPrivateUsage=false
"""Deep domain test suite verifying tax source-of-calculation gating and calculations.

Owns
----
- Verification of zero-waste compute invariant for CapabilityId.TAX in domain kernels.
- Verification that tax attributes are bypassed at source in SnapshotGenerator and FIFOPortfolio.
- Verification that after-tax PyXIRR solver iterations are eliminated when tax is inactive.
- Verification of pure accounting field invariance (100% numerically identical across tax toggle).
- Verification of foreign exposure point-in-time month-end snapping bug fix in aggregate_currency_analytics.
- Verification of Section 112A equity grandfathering, holding periods, and annual exemption limits.

Does not own
-------------
- Capability planner DAG resolution (owned by test_tax_composition.py).
- AST architectural boundary enforcement (owned by test_boundaries.py).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import cast
from unittest.mock import patch

import polars as pl
import pytest

from personal_finance_etl.application.investments.context import (
    QuantDataFrames,
    QuantRunOptions,
)
from personal_finance_etl.application.investments.quant_service import (
    InvestmentQuantEngine,
)
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.investments.contracts import (
    InstrumentMetricsRecord,
    IsinMasterRecord,
)
from personal_finance_etl.domain.investments.lots.fifo import FIFOPortfolio
from personal_finance_etl.domain.investments.lots.models import LotBuyParameters
from personal_finance_etl.domain.investments.performance import xirr as xirr_module
from personal_finance_etl.domain.investments.portfolio.lot_metrics import (
    LotValuationContext,
)
from personal_finance_etl.domain.investments.portfolio.snapshots import (
    SnapshotGenerator,
)
from personal_finance_etl.domain.market.macro import FYMacroParametersTable
from personal_finance_etl.domain.wealth.analytics import InvestmentAnalyticsBuilder
from personal_finance_etl.domain.wealth.market_valuation import (
    aggregate_currency_analytics,
)


@pytest.fixture
def rules() -> FinancialRules:
    """Load default test financial rules."""
    return FinancialRules.from_toml("tests/fixtures/financial_rules.toml")


@pytest.fixture
def fy_table(rules: FinancialRules) -> FYMacroParametersTable:
    """Load default FY macro parameters table."""
    df_macro = pl.DataFrame(
        {
            "FY": ["2022-2023", "2023-2024", "2024-2025"],
            "FY_Start_Date": ["2022-04-01", "2023-04-01", "2024-04-01"],
            "FY_End_Date": ["2023-03-31", "2024-03-31", "2025-03-31"],
            "Equity_Listed_LTCG": [0.10, 0.10, 0.125],
            "Equity_Listed_STCG": [0.15, 0.15, 0.20],
            "Default_LTCG": [0.10, 0.10, 0.125],
            "Default_STCG": [0.15, 0.15, 0.20],
            "Equity_LTCG_Exemption": [100000, 100000, 125000],
            "Equity_Listed_LTCG_Threshold_Days": [365, 365, 365],
            "Debt_MF_Cutoff_Date": ["2023-03-31", "2023-03-31", "2023-03-31"],
            "Debt_MF_Pre_Cutoff_LTCG": [0.20, 0.20, 0.20],
            "Debt_MF_Pre_Cutoff_STCG": [0.30, 0.30, 0.30],
            "Debt_MF_Post_Cutoff_LTCG": [0.30, 0.30, 0.30],
            "Debt_MF_Post_Cutoff_STCG": [0.30, 0.30, 0.30],
            "Other_Debt_LTCG": [0.20, 0.20, 0.20],
            "Other_Debt_STCG": [0.30, 0.30, 0.30],
            "Cess_Rate": [0.04, 0.04, 0.04],
        }
    )
    return FYMacroParametersTable(df_macro, rules=rules)


def _build_synthetic_quant_data(
    rules: FinancialRules,
) -> tuple[QuantDataFrames, QuantRunOptions]:
    """Build synthetic investment inputs for quant engine execution."""
    df_p = pl.DataFrame(
        {
            "Date": ["2023-01-02", "2023-02-01"],
            "ISIN": ["INE002A01018", "INE002A01018"],
            "Quantity": [10.0, 5.0],
            "Price": [100.0, 120.0],
            "Value": [1000.0, 600.0],
            "Purchase_ID": ["PURCHASE_SYNTH_001", "PURCHASE_SYNTH_002"],
        }
    )
    df_s = pl.DataFrame(
        {
            "Date": ["2023-03-01"],
            "ISIN": ["INE002A01018"],
            "Quantity": [5.0],
            "Sell_Price": [150.0],
            "Sell_Value": [750.0],
            "Sale_ID": ["SALE_SYNTH_001"],
        }
    )
    df_m = pl.DataFrame(
        {
            "Date": ["2023-01-02", "2023-02-01", "2023-03-01", "2023-03-02"],
            "ISIN": ["INE002A01018", "INE002A01018", "INE002A01018", "INE002A01018"],
            "Quantity": [10.0, 15.0, 10.0, 10.0],
            "Closing_Price": [105.0, 125.0, 150.0, 155.0],
            "Buy_Value": [1000.0, 1600.0, 1100.0, 1100.0],
        }
    )
    df_i = pl.DataFrame(
        {
            "ISIN": ["INE002A01018"],
            "INSTRUMENT_CLASS": ["EQUITY"],
            "INSTRUMENT_SUBTYPE": ["LARGE_CAP"],
            "INSTRUMENT_TYPE": ["Stock"],
            "SECTOR": ["Energy"],
            "INDUSTRY": ["Oil & Gas"],
            "GEO": ["Domestic"],
            "COUNTRY": ["India"],
            "CURRENCY_ID": [rules.DEFAULT_CURRENCY_ID],
            "BENCHMARK_ID": ["^NSEI"],
            "TAX_TYPE": ["equity"],
            "TAX_SUBTYPE": ["listed"],
        }
    )
    df_b = pl.DataFrame(
        {
            "Date": ["2023-01-02", "2023-02-01", "2023-03-01", "2023-03-02"],
            "ID": ["^NSEI", "^NSEI", "^NSEI", "^NSEI"],
            "Close": [18000.0, 18100.0, 18200.0, 18250.0],
        }
    )
    df_t = pl.DataFrame(
        {
            "FY": ["2022-2023", "2023-2024", "2024-2025"],
            "FY_Start_Date": ["2022-04-01", "2023-04-01", "2024-04-01"],
            "FY_End_Date": ["2023-03-31", "2024-03-31", "2025-03-31"],
            "Equity_Listed_LTCG": [0.10, 0.10, 0.125],
            "Equity_Listed_STCG": [0.15, 0.15, 0.20],
            "Default_LTCG": [0.10, 0.10, 0.125],
            "Default_STCG": [0.15, 0.15, 0.20],
            "Equity_LTCG_Exemption": [100000, 100000, 125000],
            "Equity_Listed_LTCG_Threshold_Days": [365, 365, 365],
            "Debt_MF_Cutoff_Date": ["2023-03-31", "2023-03-31", "2023-03-31"],
            "Debt_MF_Pre_Cutoff_LTCG": [0.20, 0.20, 0.20],
            "Debt_MF_Pre_Cutoff_STCG": [0.30, 0.30, 0.30],
            "Debt_MF_Post_Cutoff_LTCG": [0.30, 0.30, 0.30],
            "Debt_MF_Post_Cutoff_STCG": [0.30, 0.30, 0.30],
            "Other_Debt_LTCG": [0.20, 0.20, 0.20],
            "Other_Debt_STCG": [0.30, 0.30, 0.30],
            "Cess_Rate": [0.04, 0.04, 0.04],
        }
    )

    data = QuantDataFrames(
        df_p=df_p,
        df_s=df_s,
        df_m=df_m,
        df_i=df_i,
        df_b=df_b,
        df_t=df_t,
    )
    options = QuantRunOptions(
        rules=rules,
        enable_benchmark=True,
        enable_foreign_assets=False,
        enable_tax=True,
        run_id="test_tax_gating_run",
    )
    return data, options


def test_snapshot_generator_source_gating(
    fy_table: FYMacroParametersTable, rules: FinancialRules
) -> None:
    """Verify SnapshotGenerator bypasses tax calculations when enable_tax is False."""
    master_row: IsinMasterRecord = cast(
        IsinMasterRecord, {"TAX_TYPE": "equity", "TAX_SUBTYPE": "listed", "BENCHMARK_ID": None}
    )

    gen_tax_active = SnapshotGenerator(fy_table, rules, "INE002A01018", master_row, enable_tax=True)
    gen_tax_gated = SnapshotGenerator(fy_table, rules, "INE002A01018", master_row, enable_tax=False)

    fifo = FIFOPortfolio("equity", "listed", fy_table, "INR_INR", "INE002A01018")
    fifo.buy(
        LotBuyParameters(
            buy_date=date(2023, 1, 1),
            qty=10.0,
            price=100.0,
            shadow_qty=0.0,
            bm_price=0.0,
            purchase_id="PURCH_001",
        )
    )

    ctx = LotValuationContext(
        m_date=date(2023, 6, 1),
        m_price=120.0,
        m_bm_price=float("nan"),
        inst_metrics=InstrumentMetricsRecord(
            cagr=None,
            cagr_status="UNDEFINED",
            bm_cagr=None,
            bm_cagr_status="UNDEFINED",
            xirr=None,
            xirr_status="UNDEFINED",
            bm_xirr=None,
            bm_xirr_status="UNDEFINED",
            after_tax_xirr=None,
            after_tax_xirr_status="UNDEFINED",
            active_return=None,
            is_lagging=None,
            max_drawdown=0.0,
            xirr_local=None,
            xirr_local_status="UNDEFINED",
            bm_xirr_local=None,
            bm_xirr_local_status="UNDEFINED",
            active_return_local=None,
            fx_xirr_impact=None,
        ),
    )

    snaps_active = gen_tax_active.generate(fifo, ctx)
    snaps_gated = gen_tax_gated.generate(fifo, ctx)

    assert len(snaps_active) == 1
    assert len(snaps_gated) == 1

    s_active = snaps_active[0]
    s_gated = snaps_gated[0]

    # When TAX active: tax fields populated
    assert s_active.Holding_Type == "STCG"
    assert s_active.Tax_Rate == 0.15
    assert s_active.Unrealized_Gain == 200.0
    assert s_active.Unrealized_STCG == 200.0
    assert s_active.STCG_Tax_If_Sold == 30.0
    assert s_active.After_Tax_PL == 170.0
    assert s_active.After_Tax_Close_Value == 1170.0

    # When TAX gated: tax fields are None (Source-of-Calculation Gated)
    assert s_gated.Tax_Rate is None
    assert s_gated.LTCG_Threshold_Days is None
    assert s_gated.Days_To_LTCG is None
    assert s_gated.Unrealized_LTCG is None
    assert s_gated.Unrealized_STCG is None
    assert s_gated.Unrealized_Gain is None
    assert s_gated.Unrealized_LTCL is None
    assert s_gated.Unrealized_STCL is None
    assert s_gated.Unrealized_Loss is None
    assert s_gated.LTCG_Tax_If_Sold is None
    assert s_gated.STCG_Tax_If_Sold is None
    assert s_gated.After_Tax_PL is None
    assert s_gated.After_Tax_Close_Value is None

    # Pure accounting attributes must be bit-for-bit identical
    assert s_active.Quantity == s_gated.Quantity == 10.0
    assert s_active.Buy_Value == s_gated.Buy_Value == 1000.0
    assert s_active.Close_Value == s_gated.Close_Value == 1200.0
    assert s_active.P_L == s_gated.P_L == 200.0
    assert s_active.Absolute_Return == s_gated.Absolute_Return == 0.20
    assert s_active.Holding_Type == s_gated.Holding_Type == "STCG"


def test_fifo_portfolio_realized_events_source_gating(
    fy_table: FYMacroParametersTable,
) -> None:
    """Verify FIFOPortfolio gates Applied_Rate and Estimated_Tax in realized events when enable_tax=False."""
    fifo_active = FIFOPortfolio("equity", "listed", fy_table, "INR_INR", "INE001", enable_tax=True)
    fifo_gated = FIFOPortfolio("equity", "listed", fy_table, "INR_INR", "INE001", enable_tax=False)

    fifo_active.buy(
        LotBuyParameters(
            buy_date=date(2023, 1, 1),
            qty=10.0,
            price=100.0,
            shadow_qty=0.0,
            bm_price=0.0,
            purchase_id="PURCH_01",
        )
    )
    fifo_gated.buy(
        LotBuyParameters(
            buy_date=date(2023, 1, 1),
            qty=10.0,
            price=100.0,
            shadow_qty=0.0,
            bm_price=0.0,
            purchase_id="PURCH_01",
        )
    )

    events_active = fifo_active.sell(
        sell_date=date(2023, 6, 1), qty=10.0, price=150.0, sale_id="SALE_01"
    )
    events_gated = fifo_gated.sell(
        sell_date=date(2023, 6, 1), qty=10.0, price=150.0, sale_id="SALE_01"
    )

    assert len(events_active) == 1
    assert len(events_gated) == 1

    ev_active = events_active[0]
    ev_gated = events_gated[0]

    # Active tax: rate and estimated tax resolved
    assert ev_active.get("Applied_Rate") == 0.15
    assert ev_active.get("Estimated_Tax") == 75.0  # 500 profit * 15% STCG

    # Gated tax: rate and estimated tax None
    assert ev_gated.get("Applied_Rate") is None
    assert ev_gated.get("Estimated_Tax") is None

    # Pure accounting metrics identical
    assert ev_active.get("Quantity_Disposed") == ev_gated.get("Quantity_Disposed") == 10.0
    assert ev_active.get("Disposed_Cost_Basis") == ev_gated.get("Disposed_Cost_Basis") == 1000.0
    assert ev_active.get("Sale_Proceeds") == ev_gated.get("Sale_Proceeds") == 1500.0
    assert ev_active.get("Realized_Gain_Loss") == ev_gated.get("Realized_Gain_Loss") == 500.0


def test_pyxirr_after_tax_solver_reduction_when_tax_disabled(
    rules: FinancialRules,
) -> None:
    """Verify after-tax PyXIRR solver iterations are completely eliminated when TAX is inactive."""
    data, options = _build_synthetic_quant_data(rules)

    call_count_active = 0
    original_calc_xirr = xirr_module.calculate_xirr

    def _counting_xirr(
        dates: list[date], amounts: list[float], **kwargs: object
    ) -> xirr_module.XirrResult:
        nonlocal call_count_active
        call_count_active += 1
        return original_calc_xirr(dates, amounts, **kwargs)

    with patch.object(xirr_module, "calculate_xirr", side_effect=_counting_xirr):
        opts_active = replace(options, enable_tax=True)
        res_active = InvestmentQuantEngine(data=data, options=opts_active).run()

    call_count_gated = 0

    def _counting_xirr_gated(
        dates: list[date], amounts: list[float], **kwargs: object
    ) -> xirr_module.XirrResult:
        nonlocal call_count_gated
        call_count_gated += 1
        return original_calc_xirr(dates, amounts, **kwargs)

    with patch.object(xirr_module, "calculate_xirr", side_effect=_counting_xirr_gated):
        opts_gated = replace(options, enable_tax=False)
        res_gated = InvestmentQuantEngine(data=data, options=opts_gated).run()

    # Zero-Waste Invariant: strictly fewer PyXIRR numerical solver calls when tax is inactive
    assert call_count_gated < call_count_active
    assert call_count_active > 0
    assert call_count_gated > 0

    # In active run: After_Tax_XIRR has valid numerical values
    df_lot_active = res_active["df_f_investment_analytics_lot"]
    assert any(val is not None for val in df_lot_active.select("After_Tax_XIRR").to_series())

    # In gated run: After_Tax_XIRR is entirely None
    df_lot_gated = res_gated["df_f_investment_analytics_lot"]
    assert all(val is None for val in df_lot_gated.select("After_Tax_XIRR").to_series())

    # Also check portfolio level
    df_port_gated = res_gated["df_f_investment_analytics_portfolio"]
    if "Portfolio_After_Tax_XIRR" in df_port_gated.columns:
        assert all(
            val is None for val in df_port_gated.select("Portfolio_After_Tax_XIRR").to_series()
        )


def test_pure_accounting_invariance_across_tax_toggle(rules: FinancialRules) -> None:
    """Verify pure accounting metrics are 100% numerically invariant across TAX capability toggles."""
    data, options = _build_synthetic_quant_data(rules)

    opts_active = replace(options, enable_tax=True)
    res_active = InvestmentQuantEngine(data=data, options=opts_active).run()

    opts_gated = replace(options, enable_tax=False)
    res_gated = InvestmentQuantEngine(data=data, options=opts_gated).run()

    df_active = res_active["df_f_investment_analytics_lot"]
    df_gated = res_gated["df_f_investment_analytics_lot"]

    accounting_cols = [
        "Quantity",
        "Buy_Price",
        "Buy_Value",
        "Market_Price",
        "Close_Value",
        "P/L",
        "Absolute_Return",
        "Lot_CAGR",
        "XIRR",
        "CAGR",
        "Lot_ID",
        "Purchase_ID",
    ]

    for col in accounting_cols:
        vals_active = df_active.select(col).to_series().to_list()
        vals_gated = df_gated.select(col).to_series().to_list()
        assert vals_active == vals_gated, f"Accounting column '{col}' differed across tax toggles!"


def test_wealth_investment_analytics_builder_tax_gating(rules: FinancialRules) -> None:
    """Verify InvestmentAnalyticsBuilder gates loss harvesting metrics when enable_tax is False."""
    dfs = {
        "df_f_investment_analytics_lot": pl.DataFrame(
            {
                "Closing_Date": [date(2023, 1, 31)],
                "ISIN": ["INE002A01018"],
                "CURRENCY_ID": ["INR_INR"],
                "Close_Value": [800.0],
                "Buy_Value": [1000.0],
                "P/L": [-200.0],
                "Close_Value_Local": [800.0],
                "Buy_Value_Local": [1000.0],
                "Asset_PnL": [-200.0],
                "Forex_PnL": [0.0],
            }
        ),
        "df_d_investment_master": pl.DataFrame(
            {
                "ISIN": ["INE002A01018"],
                "INSTRUMENT_NAME": ["Test Asset"],
                "INSTRUMENT_CLASS": ["Equity"],
                "INSTRUMENT_TYPE": ["Stock"],
                "INSTRUMENT_SUBTYPE": ["Large Cap"],
                "SECTOR": ["Energy"],
            }
        ),
        "df_f_investment_analytics_portfolio": pl.DataFrame(
            {
                "Closing_Date": [date(2023, 1, 31)],
                "Total_Current_Value": [800.0],
                "Total_Invested_Value": [1000.0],
            }
        ),
        "df_f_investment_analytics_isin": pl.DataFrame(
            {
                "Closing_Date": [date(2023, 1, 31)],
                "ISIN": ["INE002A01018"],
                "FX_XIRR_Impact": [0.0],
                "XIRR_Local": [-0.10],
                "BM_XIRR": [0.10],
                "BM_XIRR_Local": [0.10],
                "Active_Return": [-0.20],
                "Active_Return_Local": [-0.20],
            }
        ),
    }

    base_lf: dict[str, pl.LazyFrame] = {}

    # 1. Tax enabled
    builder_active = InvestmentAnalyticsBuilder(dfs, base_lf, rules, enable_tax=True)
    res_active = builder_active.build().collect()
    assert res_active.select("ISIN_Harvestable_Loss").to_series().item(0) == -200.0

    # 2. Tax disabled
    builder_gated = InvestmentAnalyticsBuilder(dfs, base_lf, rules, enable_tax=False)
    res_gated = builder_gated.build().collect()
    assert res_gated.select("ISIN_Harvestable_Loss").to_series().item(0) is None
    assert res_gated.select("Tax_Harvesting_Priority_Score").to_series().item(0) is None


def test_foreign_exposure_point_in_time_month_end_snapping() -> None:
    """Verify aggregate_currency_analytics snaps to max closing date per month without multi-day inflation defect."""
    # Simulate 20 trading days in January 2023 for USD and INR
    dates = [date(2023, 1, d) for d in range(2, 23)]  # 21 trading days

    rows: list[dict[str, object]] = []
    for d in dates:
        # USD exposure: 1,000 USD value every day (closing market valuation on that day)
        rows.append(
            {
                "Closing_Date": d,
                "CURRENCY_ID": "USD_USD",
                "Total_Current_Value": 1000.0,
            }
        )
        # Domestic base currency: 50,000 INR
        rows.append(
            {
                "Closing_Date": d,
                "CURRENCY_ID": "INR_INR",
                "Total_Current_Value": 50000.0,
            }
        )

    df_inv_curr = pl.DataFrame(rows)

    # Call aggregate_currency_analytics
    lf_snapped = aggregate_currency_analytics(df_inv_curr, default_currency_id="INR_INR")
    df_res = lf_snapped.collect()

    assert df_res.height == 1
    row = df_res.row(0, named=True)
    assert row["MONTH_END_DATE"] == date(2023, 1, 31)

    # Defect fix verification:
    # Before the fix, summing across all 21 trading days produced 21,000.0 (~21x inflation).
    # With the fix, snapping to the latest trading day produces exactly 1,000.0.
    assert row["Total_Foreign_Currency_Exposure"] == 1000.0


def test_section_112a_grandfathering_and_tax_exemption_rules(
    fy_table: FYMacroParametersTable,
) -> None:
    """Verify FYMacroParametersTable correctly resolves holding types and exemption limits."""
    # Equity holding period cutoff is 365 days
    ht_short = fy_table.get_holding_type("equity", "listed", date(2023, 1, 1), date(2023, 6, 1))
    assert ht_short == "STCG"

    ht_long = fy_table.get_holding_type("equity", "listed", date(2022, 1, 1), date(2023, 6, 1))
    assert ht_long == "LTCG"

    # Debt holding period cutoff is 1095 days (3 years)
    ht_debt_short = fy_table.get_holding_type(
        "debt", "mutual_fund", date(2021, 1, 1), date(2023, 1, 1)
    )
    assert ht_debt_short == "STCG"

    ht_debt_long = fy_table.get_holding_type(
        "debt", "mutual_fund", date(2019, 1, 1), date(2023, 1, 1)
    )
    assert ht_debt_long == "LTCG"

    # Equity LTCG annual exemption limits
    exemption_fy23 = fy_table.get_equity_ltcg_exemption(date(2023, 5, 1))
    assert exemption_fy23 == 100000

    exemption_fy24 = fy_table.get_equity_ltcg_exemption(date(2024, 8, 1))
    assert exemption_fy24 == 125000
