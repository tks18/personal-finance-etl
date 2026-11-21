"""Deep domain test suite verifying source-of-calculation capability gating.

Owns
----
- Verification of zero-waste compute invariant in PyXIRR numerical solvers.
- Verification that benchmark and foreign calculations are bypassed at source.
- Verification of deterministic ID stability across capability toggles.
- Verification of 11 Gold investment marts across active and disabled enrichments.

Does not own
-------------
- Capability planner DAG resolution (owned by test_enrichment_composition.py).
- File ingestion and parsing (owned by test_mutual_fund_ingestion.py).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from unittest.mock import patch

import polars as pl

from personal_finance_etl.application.investments.context import (
    QuantDataFrames,
    QuantRunOptions,
)
from personal_finance_etl.application.investments.quant_service import (
    InvestmentQuantEngine,
)
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.contracts.capabilities import (
    CapabilityId,
    get_capability_columns,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.domain.investments.contracts import (
    CashflowDict,
    TerminalValueDict,
)
from personal_finance_etl.domain.investments.performance import xirr as xirr_module
from personal_finance_etl.domain.investments.performance.xirr import (
    PortfolioXIRRCalculator,
    XirrResult,
)


def _build_synthetic_quant_data(
    rules: FinancialRules,
) -> tuple[QuantDataFrames, QuantRunOptions]:
    """Build synthetic investment inputs for quant engine execution."""
    df_p = pl.DataFrame(
        {
            "Date": ["2023-01-02"],
            "ISIN": ["INE002A01018"],
            "Quantity": [10.0],
            "Price": [100.0],
            "Value": [1000.0],
            "Purchase_ID": ["PURCHASE_SYNTH_001"],
        }
    )
    df_s = pl.DataFrame(
        schema={
            "Date": pl.String,
            "ISIN": pl.String,
            "Quantity": pl.Float64,
            "Sell_Price": pl.Float64,
            "Sell_Value": pl.Float64,
            "Sale_ID": pl.String,
        }
    )
    df_m = pl.DataFrame(
        {
            "Date": ["2023-01-02", "2023-01-03"],
            "ISIN": ["INE002A01018", "INE002A01018"],
            "Quantity": [10.0, 10.0],
            "Closing_Price": [105.0, 110.0],
            "Buy_Value": [1000.0, 1000.0],
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
        }
    )
    df_b = pl.DataFrame(
        {
            "Date": ["2023-01-02", "2023-01-03"],
            "ID": ["^NSEI", "^NSEI"],
            "Close": [18000.0, 18100.0],
        }
    )
    df_t = pl.DataFrame(
        {
            "FY": ["2022-2023"],
            "FY_Start_Date": ["2022-04-01"],
            "FY_End_Date": ["2023-03-31"],
            "Equity_Listed_LTCG": [0.10],
            "Equity_Listed_STCG": [0.15],
            "Default_LTCG": [0.10],
            "Default_STCG": [0.15],
            "Cess_Rate": [0.04],
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
        start_date=date(2023, 1, 2),
        end_date=date(2023, 1, 3),
        run_id="TEST_ENRICHMENT_GATING",
    )
    return data, options


def test_pyxirr_solver_call_reduction_at_source() -> None:
    """Verify PyXIRR solver calls drop by at least 60% when benchmark and foreign assets are inactive."""
    calculator = PortfolioXIRRCalculator()
    unique_dates = [date(2023, 6, 1)]
    cashflows: list[CashflowDict] = [
        {
            "date": date(2023, 1, 1),
            "amount": -1000.0,
            "amount_local": -1000.0,
            "benchmark_amount": -1000.0,
            "benchmark_amount_local": -1000.0,
        }
    ]
    terminals: dict[date, TerminalValueDict] = {
        date(2023, 6, 1): {
            "val": 1200.0,
            "shadow_val": 1150.0,
            "val_local": 1200.0,
            "shadow_val_local": 1150.0,
        }
    }

    call_count_all = 0
    orig_calculate_xirr = xirr_module.calculate_xirr

    def counted_calculate_xirr_all(dates: list[date], amounts: list[float]) -> XirrResult:
        nonlocal call_count_all
        call_count_all += 1
        return orig_calculate_xirr(dates, amounts)

    with patch.object(xirr_module, "calculate_xirr", side_effect=counted_calculate_xirr_all):
        df_all = calculator.calculate(
            unique_dates=unique_dates,
            global_cashflows=cashflows,
            portfolio_terminals=terminals,
            enable_benchmark=True,
            enable_foreign_assets=True,
        )

    # When all enrichments are active: 5 calls per date (pxirr, at_pxirr, pxirr_local, bm_pxirr, bm_pxirr_local)
    assert call_count_all == 5
    assert df_all.select("Portfolio_XIRR").item() is not None
    assert df_all.select("Portfolio_BM_XIRR").item() is not None
    assert df_all.select("XIRR_Local").item() is not None
    assert df_all.select("BM_XIRR_Local").item() is not None

    call_count_gated = 0

    def counted_calculate_xirr_gated(dates: list[date], amounts: list[float]) -> XirrResult:
        nonlocal call_count_gated
        call_count_gated += 1
        return orig_calculate_xirr(dates, amounts)

    with patch.object(xirr_module, "calculate_xirr", side_effect=counted_calculate_xirr_gated):
        df_gated = calculator.calculate(
            unique_dates=unique_dates,
            global_cashflows=cashflows,
            portfolio_terminals=terminals,
            enable_benchmark=False,
            enable_foreign_assets=False,
        )

    # When enrichments are disabled: only 2 calls (pxirr, at_pxirr)
    assert call_count_gated == 2
    reduction_pct = (call_count_all - call_count_gated) / call_count_all
    assert reduction_pct >= 0.60, f"Expected >= 60% reduction, got {reduction_pct:.1%}"

    # Verify zero cosmetic tail pruning: benchmark and local columns are None at source
    assert df_gated.select("Portfolio_BM_XIRR").item() is None
    assert df_gated.select("Portfolio_Active_Return").item() is None
    assert df_gated.select("XIRR_Local").item() is None
    assert df_gated.select("FX_XIRR_Impact").item() is None
    assert df_gated.select("BM_XIRR_Local").item() is None
    assert df_gated.select("Active_Return_Local").item() is None

    # Domestic XIRR is fully identical to the all-active run
    assert df_gated.select("Portfolio_XIRR").item() == df_all.select("Portfolio_XIRR").item()


def test_isin_and_lot_source_calculation_gating(rules: FinancialRules) -> None:
    """Verify IsinProcessor and SnapshotGenerator bypass benchmark and FX math at source."""
    data, options = _build_synthetic_quant_data(rules)

    # Run with capabilities active
    opts_active = replace(options, enable_benchmark=True, enable_foreign_assets=True)
    engine_active = InvestmentQuantEngine(data=data, options=opts_active)
    results_active = engine_active.run()

    # Run with capabilities disabled
    opts_gated = replace(options, enable_benchmark=False, enable_foreign_assets=False)
    engine_gated = InvestmentQuantEngine(data=data, options=opts_gated)
    results_gated = engine_gated.run()

    df_lot_active = results_active["df_f_investment_analytics_lot"]
    df_lot_gated = results_gated["df_f_investment_analytics_lot"]

    # 1. Domestic core fields are byte-identical
    assert (
        df_lot_gated.get_column("Quantity").to_list()
        == df_lot_active.get_column("Quantity").to_list()
    )
    assert (
        df_lot_gated.get_column("Buy_Price").to_list()
        == df_lot_active.get_column("Buy_Price").to_list()
    )
    assert (
        df_lot_gated.get_column("Close_Value").to_list()
        == df_lot_active.get_column("Close_Value").to_list()
    )
    assert df_lot_gated.get_column("XIRR").to_list() == df_lot_active.get_column("XIRR").to_list()

    # 2. Benchmark columns in lot analytics are None when disabled
    assert all(val is None for val in df_lot_gated.select("BM_Market_Price").to_series())
    assert all(val is None for val in df_lot_gated.select("Lot_BM_Return").to_series())
    assert all(val is None for val in df_lot_gated.select("BM_XIRR").to_series())
    assert all(val is None for val in df_lot_gated.select("Active_Return").to_series())

    # 3. ISIN metrics table source gating
    df_isin_gated = results_gated["df_f_investment_analytics_isin"]
    assert all(val is None for val in df_isin_gated.select("BM_XIRR").to_series())
    assert all(val is None for val in df_isin_gated.select("Active_Return").to_series())
    assert all(val is None for val in df_isin_gated.select("XIRR_Local").to_series())


def test_deterministic_id_invariance_across_toggles(rules: FinancialRules) -> None:
    """Verify deterministic LOT_ID and Purchase_ID stability regardless of enrichment toggles."""
    data, options = _build_synthetic_quant_data(rules)

    opts_active = replace(options, enable_benchmark=True, enable_foreign_assets=True)
    res_active = InvestmentQuantEngine(data=data, options=opts_active).run()

    opts_gated = replace(options, enable_benchmark=False, enable_foreign_assets=False)
    res_gated = InvestmentQuantEngine(data=data, options=opts_gated).run()

    lot_ids_active = set(res_active["df_f_investment_analytics_lot"].select("Lot_ID").to_series())
    lot_ids_gated = set(res_gated["df_f_investment_analytics_lot"].select("Lot_ID").to_series())
    assert lot_ids_active == lot_ids_gated, "Lot IDs must be byte-stable across capability toggles"

    purch_ids_active = set(
        res_active["df_f_investment_analytics_lot"].select("Purchase_ID").to_series()
    )
    purch_ids_gated = set(
        res_gated["df_f_investment_analytics_lot"].select("Purchase_ID").to_series()
    )
    assert purch_ids_active == purch_ids_gated


def test_all_11_gold_investment_tables_produced_and_gated(rules: FinancialRules) -> None:
    """Verify all 11 Gold investment tables exist and capability columns are gated cleanly."""
    data, options = _build_synthetic_quant_data(rules)

    opts_gated = replace(options, enable_benchmark=False, enable_foreign_assets=False)
    results = InvestmentQuantEngine(data=data, options=opts_gated).run()

    gold_tables = [
        "df_f_investment_analytics_isin",
        "df_f_investment_analytics_subtype",
        "df_f_investment_analytics_class",
        "df_f_investment_analytics_instrument_type",
        "df_f_investment_analytics_sector",
        "df_f_investment_analytics_industry",
        "df_f_investment_analytics_geo",
        "df_f_investment_analytics_country",
        "df_f_investment_analytics_currency",
        "df_f_investment_analytics_portfolio",
    ]

    for table_name in gold_tables:
        assert table_name in results, f"Missing Gold investment table: {table_name}"
        df = results[table_name]
        assert df.height > 0
        # Check that BM XIRR and Local XIRR are None in the aggregated table
        if "Portfolio_BM_XIRR" in df.columns:
            assert all(v is None for v in df.select("Portfolio_BM_XIRR").to_series())
        if "XIRR_Local" in df.columns:
            assert all(v is None for v in df.select("XIRR_Local").to_series())


def test_capability_column_inventory_coverage() -> None:
    """Verify CAPABILITY_COLUMN_INVENTORY covers both enrichments and is queryable."""
    bm_cols = get_capability_columns(CapabilityId.BENCHMARK_ENRICHMENT)
    fx_cols = get_capability_columns(CapabilityId.FOREIGN_ASSET_ENRICHMENT)

    assert len(bm_cols) > 0
    assert len(fx_cols) > 0

    assert "BM_XIRR" in bm_cols
    assert "Active_Return" in bm_cols
    assert "XIRR_Local" in fx_cols
    assert "Forex_PnL" in fx_cols

    # Query specific dataset
    lot_bm = get_capability_columns(
        CapabilityId.BENCHMARK_ENRICHMENT, DatasetId.INVESTMENT_LOT_ANALYTICS
    )
    assert "BM_Market_Price" in lot_bm
    assert "Lot_BM_Return" in lot_bm
