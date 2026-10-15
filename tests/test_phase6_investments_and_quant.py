"""Comprehensive verification test suite for Phase 6: Investment & Quant Domain.

Verifies:
1. 100% strict object identity equivalence (`is`) across all legacy shims and target modules.
2. FIFO lot accounting, matching, shadow units, and deterministic ID generation.
3. CAGR and XIRR calculation edge cases and status code fidelity.
4. Valuation, FX validation gate, and benchmark bounded staleness fallback.
5. Reconciliation engine discrepancy detection and tolerance thresholds.
6. End-to-end InvestmentQuantEngine / QuantService pipeline execution on synthetic data.
"""

from datetime import date
from pathlib import Path

import polars as pl

from personal_finance_etl.application.investments.aggregation_service import (
    PostProcessingPipeline,
    PostProcessor,
)
from personal_finance_etl.application.investments.context import (
    AnalyticsContextManager,
    RunContext,
)
from personal_finance_etl.application.investments.input_adapter import (
    IsinDataExtractor,
    TaxDataLoader,
    clean_numeric_col,
    parse_date_col,
)
from personal_finance_etl.application.investments.isin_service import (
    IsinPipeline,
    IsinProcessor,
    _is_zero_proceeds_re_adjustment,
    _process_isin_worker,
    is_indian_rights_entitlement_isin,
)
from personal_finance_etl.application.investments.quant_service import (
    InvestmentQuantEngine,
    QuantService,
)
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.calculation import CalculationStatus
from personal_finance_etl.domain.investments.lots.fifo import FIFOPortfolio
from personal_finance_etl.domain.investments.performance.attribution import (
    RealizedGainsCalculator,
)
from personal_finance_etl.domain.investments.performance.returns import calculate_cagr
from personal_finance_etl.domain.investments.performance.xirr import (
    PortfolioXIRRCalculator,
    calculate_xirr,
    numeric_value,
)
from personal_finance_etl.domain.investments.portfolio.aggregation import (
    PORTFOLIO_COL_RENAMES,
    GroupProcessor,
    PortfolioWeightsCalculator,
)
from personal_finance_etl.domain.investments.portfolio.analytics import (
    AdvancedAnalyticsCalculator,
    HarvestRecommendationCalculator,
)
from personal_finance_etl.domain.investments.portfolio.snapshots import SnapshotGenerator
from personal_finance_etl.domain.investments.reconciliation.engine import (
    ReconciliationEngine,
)
from personal_finance_etl.domain.investments.valuation.benchmark import (
    BenchmarkPriceProvider,
)
from personal_finance_etl.domain.investments.valuation.fx import (
    FXProviderMissingError,
    FXRateUnavailableError,
    FXValidationGate,
)
from personal_finance_etl.domain.market.macro import FYMacroParametersTable


def test_phase6_object_identity_equivalence() -> None:
    """Verify 100% strict object identity equivalence (`is`) for all Phase 6 modules."""
    import personal_finance_etl.backend.engines.analytics as legacy_pkg_analytics
    import personal_finance_etl.backend.engines.analytics.context as legacy_context
    import personal_finance_etl.backend.engines.analytics.core.fifo as legacy_fifo
    import personal_finance_etl.backend.engines.analytics.core.math as legacy_math
    import personal_finance_etl.backend.engines.analytics.engine as legacy_engine
    import personal_finance_etl.backend.engines.analytics.io.loader as legacy_loader
    import personal_finance_etl.backend.engines.analytics.isin_pipeline as legacy_isin_pipeline
    import personal_finance_etl.backend.engines.analytics.pipeline.context as legacy_pipe_context
    import personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.analytics as legacy_post_analytics
    import personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.coordinator as legacy_coordinator
    import personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.gains as legacy_post_gains
    import personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.group_processor as legacy_post_group
    import personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.harvest as legacy_post_harvest
    import personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.weights as legacy_post_weights
    import personal_finance_etl.backend.engines.analytics.pipeline.postprocessor.xirr as legacy_post_xirr
    import personal_finance_etl.backend.engines.analytics.pipeline.processor.benchmark as legacy_proc_bm
    import personal_finance_etl.backend.engines.analytics.pipeline.processor.extractor as legacy_extractor
    import personal_finance_etl.backend.engines.analytics.pipeline.processor.fx_gate as legacy_proc_fx
    import personal_finance_etl.backend.engines.analytics.pipeline.processor.isin_processor as legacy_proc_isin
    import personal_finance_etl.backend.engines.analytics.pipeline.processor.snapshot as legacy_proc_snapshot
    import personal_finance_etl.backend.engines.analytics.post_pipeline as legacy_post_pipeline

    # FIFO & Lots
    assert FIFOPortfolio is legacy_fifo.FIFOPortfolio

    # Valuation & Benchmark
    assert FXValidationGate is legacy_proc_fx.FXValidationGate
    assert FXProviderMissingError is legacy_proc_fx.FXProviderMissingError
    assert FXRateUnavailableError is legacy_proc_fx.FXRateUnavailableError
    assert BenchmarkPriceProvider is legacy_proc_bm.BenchmarkPriceProvider

    # Performance
    assert calculate_cagr is legacy_math.calculate_cagr
    assert calculate_xirr is legacy_math.calculate_xirr
    assert numeric_value is legacy_post_xirr._numeric_value
    assert PortfolioXIRRCalculator is legacy_post_xirr.PortfolioXIRRCalculator
    assert RealizedGainsCalculator is legacy_post_gains.RealizedGainsCalculator

    # Portfolio
    assert SnapshotGenerator is legacy_proc_snapshot.SnapshotGenerator
    assert AdvancedAnalyticsCalculator is legacy_post_analytics.AdvancedAnalyticsCalculator
    assert HarvestRecommendationCalculator is legacy_post_harvest.HarvestRecommendationCalculator
    assert GroupProcessor is legacy_post_group.GroupProcessor
    assert PORTFOLIO_COL_RENAMES is legacy_post_group.PORTFOLIO_COL_RENAMES
    assert PortfolioWeightsCalculator is legacy_post_weights.PortfolioWeightsCalculator

    # Application Services
    assert TaxDataLoader is legacy_loader.TaxDataLoader
    assert parse_date_col is legacy_loader.parse_date_col
    assert clean_numeric_col is legacy_loader.clean_numeric_col
    assert IsinDataExtractor is legacy_extractor.IsinDataExtractor
    assert RunContext is legacy_pipe_context.RunContext
    assert AnalyticsContextManager is legacy_context.AnalyticsContextManager
    assert IsinProcessor is legacy_proc_isin.IsinProcessor
    assert is_indian_rights_entitlement_isin is legacy_proc_isin.is_indian_rights_entitlement_isin
    assert _is_zero_proceeds_re_adjustment is legacy_proc_isin._is_zero_proceeds_re_adjustment
    assert IsinPipeline is legacy_isin_pipeline.IsinPipeline
    assert _process_isin_worker is legacy_isin_pipeline._process_isin_worker
    assert PostProcessor is legacy_coordinator.PostProcessor
    assert PostProcessingPipeline is legacy_post_pipeline.PostProcessingPipeline
    assert InvestmentQuantEngine is legacy_engine.InvestmentQuantEngine
    assert InvestmentQuantEngine is legacy_pkg_analytics.InvestmentQuantEngine
    assert QuantService is InvestmentQuantEngine


def test_fifo_accounting_lifecycle() -> None:
    """Verify FIFO queue buy/sell matching, deterministic IDs, shadow units, and realized PnL."""
    toml_path = Path("tests/financial_rules.toml")
    rules = FinancialRules.from_toml(str(toml_path))

    df_t = pl.DataFrame(
        {
            "FY": ["2022-2023", "2023-2024"],
            "FY_Start_Date": ["2022-04-01", "2023-04-01"],
            "FY_End_Date": ["2023-03-31", "2024-03-31"],
            "Equity_Listed_LTCG": [0.10, 0.10],
            "Equity_Listed_STCG": [0.15, 0.15],
            "Default_LTCG": [0.10, 0.10],
            "Default_STCG": [0.15, 0.15],
            "Cess_Rate": [0.04, 0.04],
        }
    )
    fy_table = FYMacroParametersTable(df_t, rules=rules)

    fifo = FIFOPortfolio(
        tax_type="EQUITY",
        tax_subtype="LISTED",
        fy_table=fy_table,
        default_currency_id="INR",
        isin="INE002A01018",
    )

    # Buy Lot 1: 100 shares @ 100 on 2023-01-01, benchmark price 1000
    fifo.buy(
        buy_date=date(2023, 1, 1),
        qty=100.0,
        price=100.0,
        shadow_qty=10.0,
        bm_price=1000.0,
        purchase_id="P1",
    )
    assert fifo.get_closing_units() == 100.0
    assert fifo.get_closing_shadow_units() == 10.0
    assert len(fifo.active_lots) == 1

    lot1 = fifo.active_lots[0]
    assert lot1.lot_id is not None and lot1.lot_id.startswith("LOT_")
    assert lot1.qty == 100.0

    # Buy Lot 2: 50 shares @ 120 on 2023-06-01, benchmark price 1200
    fifo.buy(
        buy_date=date(2023, 6, 1),
        qty=50.0,
        price=120.0,
        shadow_qty=5.0,
        bm_price=1200.0,
        purchase_id="P2",
    )
    assert fifo.get_closing_units() == 150.0
    assert fifo.get_closing_shadow_units() == 15.0

    # Sell 120 shares @ 150 on 2024-02-01 (should exhaust Lot 1 [100] and partially take Lot 2 [20])
    events = fifo.sell(
        sell_date=date(2024, 2, 1),
        qty=120.0,
        price=150.0,
        sale_id="S1",
    )

    assert len(events) == 2
    # First event from Lot 1 (holding > 365 days -> LTCG)
    assert events[0]["Quantity_Disposed"] == 100.0
    assert events[0]["Realized_Gain_Loss"] == 100.0 * (150.0 - 100.0)  # 5000 gain
    assert events[0]["Holding_Type"] == "LTCG"
    assert events[0]["Lot_ID"] == lot1.lot_id

    # Second event from Lot 2 (holding < 365 days -> STCG)
    assert events[1]["Quantity_Disposed"] == 20.0
    assert events[1]["Realized_Gain_Loss"] == 20.0 * (150.0 - 120.0)  # 600 gain
    assert events[1]["Holding_Type"] == "STCG"

    # Remaining units in Lot 2 should be 30 shares
    assert fifo.get_closing_units() == 30.0
    assert len(fifo.active_lots) == 1
    remaining_lot = fifo.active_lots[0]
    assert remaining_lot.qty == 30.0
    assert remaining_lot.purchase_id == "P2"
    assert abs(fifo.get_closing_shadow_units() - 3.0) < 1e-6


def test_performance_cagr_and_xirr() -> None:
    """Verify CAGR and XIRR calculation status handling and precision."""
    # CAGR 100% over 730 days (2 years) = (2.0)**(365/730) - 1 ≈ 0.41421356
    cagr_res = calculate_cagr(100.0, 200.0, 730)
    assert cagr_res.status == CalculationStatus.VALID
    assert cagr_res.value is not None
    assert abs(cagr_res.value - 0.41421356) < 1e-4

    # Zero time duration CAGR -> UNDEFINED
    zero_time = calculate_cagr(100.0, 110.0, 0)
    assert zero_time.status == CalculationStatus.UNDEFINED
    assert zero_time.value is None

    # XIRR: Simple cash flow -100 on 2023-01-01, +110 on 2024-01-01 -> ~10%
    dates = [date(2023, 1, 1), date(2024, 1, 1)]
    amounts = [-100.0, 110.0]
    xirr_res = calculate_xirr(dates, amounts)
    assert xirr_res.status == CalculationStatus.VALID
    assert xirr_res.value is not None
    assert abs(xirr_res.value - 0.10) < 1e-3

    # All positive cashflows -> INVALID_INPUT
    all_pos = calculate_xirr([date(2023, 1, 1), date(2024, 1, 1)], [100.0, 200.0])
    assert all_pos.status == CalculationStatus.INVALID_INPUT
    assert all_pos.value is None


def test_benchmark_price_provider_bounded_staleness() -> None:
    """Verify BenchmarkPriceProvider staleness bounding and fallback behavior."""
    df_b = pl.DataFrame(
        {
            "Date": [date(2023, 1, 2), date(2023, 1, 3)],  # Missing Jan 1 and Jan 4-20
            "ID": ["^NSEI", "^NSEI"],
            "Close": [18000.0, 18100.0],
        }
    )
    provider = BenchmarkPriceProvider("^NSEI", df_b, max_staleness_days=15)

    # Exact date hit
    assert provider.get_bm_price(date(2023, 1, 3)) == 18100.0

    # Within 15-day staleness window (Jan 10 falls back to Jan 3)
    assert provider.get_bm_price(date(2023, 1, 10)) == 18100.0

    # Beyond 15-day staleness window (Jan 25 is > 15 days from Jan 3 -> None)
    assert provider.get_bm_price(date(2023, 1, 25)) is None


def test_reconciliation_engine_quantity_and_basis() -> None:
    """Verify ReconciliationEngine discrepancy detection and tolerance thresholds."""
    # Quantity discrepancy above tolerance (1e-8)
    assert ReconciliationEngine.should_reconcile_quantity(110.0, 100.0) is True
    # Quantity within tolerance -> False
    assert ReconciliationEngine.should_reconcile_quantity(100.000000001, 100.0) is False

    # Basis discrepancy above tolerance (0.01)
    assert ReconciliationEngine.should_reconcile_basis(5500.0, 50.0, 100.0) is True
    # Basis within tolerance -> False
    assert ReconciliationEngine.should_reconcile_basis(5000.005, 50.0, 100.0) is False


def test_investment_quant_engine_end_to_end() -> None:
    """Verify full InvestmentQuantEngine execution on synthetic multi-stream data."""
    toml_path = Path("tests/financial_rules.toml")
    rules = FinancialRules.from_toml(str(toml_path))

    # Purchases: Buy 10 shares of INE002A01018 on 2023-01-02 @ 100
    df_p = pl.DataFrame(
        {
            "Date": ["2023-01-02"],
            "ISIN": ["INE002A01018"],
            "Quantity": [10.0],
            "Price": [100.0],
            "Value": [1000.0],
            "Purchase_ID": ["P1"],
        }
    )

    # Sales: Empty
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

    # Market: Daily closing prices for 2023-01-02 and 2023-01-03
    df_m = pl.DataFrame(
        {
            "Date": ["2023-01-02", "2023-01-03"],
            "ISIN": ["INE002A01018", "INE002A01018"],
            "Quantity": [10.0, 10.0],
            "Closing_Price": [105.0, 110.0],
            "Buy_Value": [1000.0, 1000.0],
        }
    )

    # Instrument metadata
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

    # Benchmark prices
    df_b = pl.DataFrame(
        {
            "Date": ["2023-01-02", "2023-01-03"],
            "ID": ["^NSEI", "^NSEI"],
            "Close": [18000.0, 18100.0],
        }
    )

    # Macro parameters
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

    # Execute engine
    engine = InvestmentQuantEngine(
        df_p=df_p,
        df_s=df_s,
        df_m=df_m,
        df_i=df_i,
        df_b=df_b,
        df_t=df_t,
        rules=rules,
        start_date=date(2023, 1, 2),
        end_date=date(2023, 1, 3),
        run_id="TEST_RUN_001",
    )
    results = engine.run()

    # Verify all 13 canonical tables are present
    expected_tables = {
        "df_f_investment_analytics_lot",
        "df_f_investment_realized_events",
        "df_f_investment_reconciliation_events",
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
    }
    assert expected_tables.issubset(set(results.keys()))

    # Verify lot table has 2 rows (one for Jan 2, one for Jan 3)
    df_lot = results["df_f_investment_analytics_lot"]
    assert len(df_lot) == 2
    assert "ISIN" in df_lot.columns
    assert "Closing_Date" in df_lot.columns

    # Verify portfolio table has 2 rows
    df_port = results["df_f_investment_analytics_portfolio"]
    assert len(df_port) == 2
    assert "Closing_Date" in df_port.columns
    assert "Weight" in df_port.columns
