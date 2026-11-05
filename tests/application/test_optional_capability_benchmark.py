# pyright: reportPrivateUsage=false
"""Enterprise test suite proving optional capability execution for Benchmark Enrichment.

Owns
----
- Verification of Benchmark Enrichment enabled vs disabled execution paths.
- Verification that disabled benchmark enrichment skips BenchmarkPipeline and provider calls.
- Verification that TransformationDAG omits df_d_benchmark_master when inactive.
- Verification that plan-scoped completeness passes with 44 tables on disabled path.
- Verification that unexpected benchmark tables raise RuntimeError on disabled path.
- Verification that active core financial outputs (lots, sales, realized events) are invariant.
- Verification of distinct cryptographic plan fingerprints between enabled and disabled plans.

Does not own
-------------
- Capability graph topological cycle checks (owned by test_capabilities.py).
- CapabilityPlanner resolution algorithms (owned by test_capability_planner.py).
- Control Plane plan snapshot persistence (owned by test_plan_scoped_completeness.py).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from personal_finance_etl.application.investments.context import (
    QuantDataFrames,
    QuantRunOptions,
)
from personal_finance_etl.application.investments.quant_service import (
    InvestmentQuantEngine,
)
from personal_finance_etl.application.pipeline.execution import PipelineExecutor
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.transformer import TransformationDAG
from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.event_transport import NullEventQueue
from personal_finance_etl.contracts.extraction import ExtractionResult
from personal_finance_etl.contracts.observability import PresentationKind
from personal_finance_etl.infrastructure.control_plane import ControlPlane
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    DATA_CONTRACT_REGISTRY,
)


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    """Fixture providing initialized Settings pointing to temporary directory."""
    return Settings(
        TARGET_DB_BASE_PATH=str(tmp_path),
        TARGET_DB_NAME="test_warehouse.duckdb",
        RAW_DOCUMENT_STORE_NAME="test_cp.sqlite",
        STATEMENTS_FOLDER=str(tmp_path / "statements"),
    )


def test_benchmark_capability_omission_scoping() -> None:
    """Verify omitting BENCHMARK_ENRICHMENT produces a 44-table plan with distinct fingerprint."""
    planner = CapabilityPlanner()
    full_plan = planner.create_plan()
    assert full_plan.is_capability_active(CapabilityId.BENCHMARK_ENRICHMENT)
    assert full_plan.active_analytical_dataset_count == 46

    # Omit BENCHMARK_ENRICHMENT from requested capabilities
    all_except_benchmark = [c for c in CapabilityId if c != CapabilityId.BENCHMARK_ENRICHMENT]
    disabled_plan = planner.create_plan(requested_capabilities=all_except_benchmark)

    assert not disabled_plan.is_capability_active(CapabilityId.BENCHMARK_ENRICHMENT)
    assert disabled_plan.active_analytical_dataset_count == 44
    assert DatasetId.INVESTMENT_BENCHMARK_MASTER_DIM not in disabled_plan.active_analytical_datasets
    assert DatasetId.INVESTMENT_BENCHMARK_DATA not in disabled_plan.active_analytical_datasets
    assert disabled_plan.plan_fingerprint != full_plan.plan_fingerprint


def test_disabled_benchmark_skips_process_benchmark(test_settings: Settings) -> None:
    """Verify process_benchmark skips provider creation and emits SKIP event when inactive."""
    db_manager = DuckDBManager(test_settings.TARGET_DB_BASE_PATH, test_settings.TARGET_DB_NAME)
    queue = NullEventQueue()
    emitter = MagicMock(spec=ObservabilityEmitter)

    all_except_benchmark = [c for c in CapabilityId if c != CapabilityId.BENCHMARK_ENRICHMENT]
    disabled_plan = CapabilityPlanner().create_plan(requested_capabilities=all_except_benchmark)

    executor = PipelineExecutor(
        test_settings, queue, db_manager, emitter=emitter, plan=disabled_plan
    )

    cp = MagicMock(spec=ControlPlane)
    bronze = MagicMock(spec=BronzeLayer)

    with patch(
        "personal_finance_etl.application.pipeline.execution.BenchmarkPipeline"
    ) as mock_pipeline:
        executor.process_benchmark(cp, bronze)
        # Assert BenchmarkPipeline was NEVER instantiated
        mock_pipeline.assert_not_called()

    # Assert SKIP event was emitted
    emitter.emit_event.assert_called_once()
    call_kwargs = emitter.emit_event.call_args.kwargs
    assert call_kwargs["presentation_kind"] == PresentationKind.SKIP
    assert "benchmark_enrichment" in call_kwargs["message"]
    assert "df_f_investment_benchmark_data" not in executor.dfs


def test_enabled_benchmark_executes_process_benchmark(test_settings: Settings) -> None:
    """Verify process_benchmark instantiates BenchmarkPipeline and runs process when active."""
    db_manager = DuckDBManager(test_settings.TARGET_DB_BASE_PATH, test_settings.TARGET_DB_NAME)
    queue = NullEventQueue()
    planner = CapabilityPlanner()
    full_plan = planner.create_plan()

    executor = PipelineExecutor(test_settings, queue, db_manager, plan=full_plan)
    executor.dfs["df_d_benchmark_master"] = pl.DataFrame({"ID": ["NIFTY50"]})

    cp = MagicMock(spec=ControlPlane)
    bronze = MagicMock(spec=BronzeLayer)

    mock_result = pl.DataFrame({"ID": ["NIFTY50"], "Close": [20000.0]})
    with patch(
        "personal_finance_etl.application.pipeline.execution.BenchmarkPipeline"
    ) as mock_pipeline_cls:
        mock_pipeline_inst = MagicMock()
        mock_pipeline_inst.process.return_value = mock_result
        mock_pipeline_cls.return_value = mock_pipeline_inst

        executor.process_benchmark(cp, bronze)

        mock_pipeline_cls.assert_called_once_with(cp, bronze, queue, emitter=executor.emitter)
        mock_pipeline_inst.process.assert_called_once()
        assert "df_f_investment_benchmark_data" in executor.dfs
        assert executor.dfs["df_f_investment_benchmark_data"].equals(mock_result)


@patch(
    "personal_finance_etl.application.pipeline.transformer.transform_d_income_category",
    return_value=pl.DataFrame().lazy(),
)
@patch(
    "personal_finance_etl.application.pipeline.transformer.transform_d_income_subcategory",
    return_value=pl.DataFrame().lazy(),
)
@patch(
    "personal_finance_etl.application.pipeline.transformer.transform_d_expense_category",
    return_value=pl.DataFrame().lazy(),
)
@patch(
    "personal_finance_etl.application.pipeline.transformer.transform_d_expense_subcategory",
    return_value=pl.DataFrame().lazy(),
)
@patch(
    "personal_finance_etl.application.pipeline.transformer.transform_d_asset_category",
    return_value=pl.DataFrame().lazy(),
)
@patch(
    "personal_finance_etl.application.pipeline.transformer.transform_d_asset_subcategory",
    return_value=pl.DataFrame().lazy(),
)
@patch(
    "personal_finance_etl.application.pipeline.transformer.transform_d_currency",
    return_value=pl.DataFrame().lazy(),
)
@patch(
    "personal_finance_etl.application.pipeline.transformer.transform_d_macro_parameters",
    return_value=pl.DataFrame().lazy(),
)
@patch(
    "personal_finance_etl.application.pipeline.transformer.transform_d_investment_benchmark_master",
    return_value=pl.DataFrame().lazy(),
)
def test_transformation_dag_respects_disabled_benchmark_plan(
    mock_bm: MagicMock,
    mock_macro: MagicMock,
    mock_curr: MagicMock,
    mock_asub: MagicMock,
    mock_acat: MagicMock,
    mock_esub: MagicMock,
    mock_ecat: MagicMock,
    mock_isub: MagicMock,
    mock_icat: MagicMock,
    test_settings: Settings,
    rules: FinancialRules,
) -> None:
    """Verify TransformationDAG omits df_d_benchmark_master when capability is inactive."""
    queue = NullEventQueue()
    emitter = MagicMock(spec=ObservabilityEmitter)

    all_except_benchmark = [c for c in CapabilityId if c != CapabilityId.BENCHMARK_ENRICHMENT]
    disabled_plan = CapabilityPlanner().create_plan(requested_capabilities=all_except_benchmark)

    transformer = TransformationDAG(
        test_settings, queue, rules, emitter=emitter, plan=disabled_plan
    )

    lf = pl.DataFrame().lazy()
    extracted = ExtractionResult(
        zcategory=lf,
        assetgroup=lf,
        assets=lf,
        currency=lf,
        inoutcome=lf,
        mappings={
            "category": {},
            "asset_group": {},
            "assets": {},
            "currency": {},
        },
        stg_mf_isin_mapping=lf,
        stg_benchmark_mapping=lf,
        mf_market_data_raw=lf,
        mf_transactions_raw=lf,
        stock_market_data_raw=lf,
        stock_transactions_raw=lf,
        raw_opening_balances=lf,
        raw_benchmark_master=lf,
        raw_macro_parameters=lf,
        column_master=pl.DataFrame(),
        us_stock_transactions_raw=lf,
        currency_mapping_raw=lf,
    )

    dims = transformer._transform_dimensions(extracted)
    assert "df_d_benchmark_master" not in dims
    mock_bm.assert_not_called()

    # Enabled path verification
    full_plan = CapabilityPlanner().create_plan()
    enabled_transformer = TransformationDAG(
        test_settings, queue, rules, emitter=emitter, plan=full_plan
    )
    enabled_dims = enabled_transformer._transform_dimensions(extracted)
    assert "df_d_benchmark_master" in enabled_dims
    mock_bm.assert_called_once()


def test_plan_scoped_completeness_disabled_benchmark_success(test_settings: Settings) -> None:
    """Verify _run_analytics_phase passes with exactly 44 tables when benchmark is disabled."""
    db_manager = DuckDBManager(test_settings.TARGET_DB_BASE_PATH, test_settings.TARGET_DB_NAME)
    queue = NullEventQueue()

    all_except_benchmark = [c for c in CapabilityId if c != CapabilityId.BENCHMARK_ENRICHMENT]
    disabled_plan = CapabilityPlanner().create_plan(requested_capabilities=all_except_benchmark)

    executor = PipelineExecutor(test_settings, queue, db_manager, plan=disabled_plan)
    executor.run_engines = MagicMock()  # type: ignore[method-assign]

    # Populate dfs with all contracts EXCEPT the 2 benchmark contracts
    benchmark_datasets = {
        DatasetId.INVESTMENT_BENCHMARK_MASTER_DIM,
        DatasetId.INVESTMENT_BENCHMARK_DATA,
    }

    for contract in DATA_CONTRACT_REGISTRY:
        if contract.dataset_id not in benchmark_datasets:
            executor.dfs[contract.contract_id] = pl.DataFrame({"id": [1]})

    cp = MagicMock(spec=ControlPlane)
    # Must succeed cleanly with exactly 44 analytical tables
    executor._run_analytics_phase(cp, "run_disabled_bm_001")
    assert len(executor.dfs) == 44


def test_plan_scoped_completeness_disabled_benchmark_rejects_spurious_output(
    test_settings: Settings,
) -> None:
    """Verify _run_analytics_phase fails if benchmark table appears when disabled in plan."""
    db_manager = DuckDBManager(test_settings.TARGET_DB_BASE_PATH, test_settings.TARGET_DB_NAME)
    queue = NullEventQueue()

    all_except_benchmark = [c for c in CapabilityId if c != CapabilityId.BENCHMARK_ENRICHMENT]
    disabled_plan = CapabilityPlanner().create_plan(requested_capabilities=all_except_benchmark)

    executor = PipelineExecutor(test_settings, queue, db_manager, plan=disabled_plan)
    executor.run_engines = MagicMock()  # type: ignore[method-assign]

    # Populate 44 active tables
    benchmark_datasets = {
        DatasetId.INVESTMENT_BENCHMARK_MASTER_DIM,
        DatasetId.INVESTMENT_BENCHMARK_DATA,
    }
    for contract in DATA_CONTRACT_REGISTRY:
        if contract.dataset_id not in benchmark_datasets:
            executor.dfs[contract.contract_id] = pl.DataFrame({"id": [1]})

    # Erroneously inject df_d_benchmark_master
    bm_contract = next(
        c
        for c in DATA_CONTRACT_REGISTRY
        if c.dataset_id == DatasetId.INVESTMENT_BENCHMARK_MASTER_DIM
    )
    executor.dfs[bm_contract.contract_id] = pl.DataFrame({"id": [1]})

    cp = MagicMock(spec=ControlPlane)
    with pytest.raises(RuntimeError) as exc_info:
        executor._run_analytics_phase(cp, "run_disabled_bm_002")

    msg = str(exc_info.value)
    assert f"unexpected analytical table '{bm_contract.contract_id}'" in msg
    assert f"dataset_id='{bm_contract.dataset_id.value}'" in msg
    assert disabled_plan.plan_fingerprint in msg


def test_quant_engine_active_outputs_invariant_to_benchmark_presence(
    rules: FinancialRules,
) -> None:
    """Verify core investment outputs (lots, realized PnL, reconciliation) are identical with or without benchmark."""
    # Synthetic trades matching InvestmentQuantEngine canonical schema
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

    df_s = pl.DataFrame(
        {
            "Date": ["2023-01-03"],
            "ISIN": ["INE002A01018"],
            "Quantity": [5.0],
            "Sell_Price": [120.0],
            "Sell_Value": [600.0],
            "Sale_ID": ["S1"],
        }
    )

    df_m = pl.DataFrame(
        {
            "Date": ["2023-01-02", "2023-01-03"],
            "ISIN": ["INE002A01018", "INE002A01018"],
            "Quantity": [10.0, 5.0],
            "Closing_Price": [105.0, 110.0],
            "Buy_Value": [1000.0, 500.0],
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

    options = QuantRunOptions(
        rules=rules,
        start_date=date(2023, 1, 2),
        end_date=date(2023, 1, 3),
        run_id="INV_TEST_RUN",
    )

    # 1. Run with benchmark enabled (df_b provided)
    engine_enabled = InvestmentQuantEngine(
        data=QuantDataFrames(
            df_p=df_p,
            df_s=df_s,
            df_m=df_m,
            df_i=df_i,
            df_b=df_b,
            df_t=df_t,
        ),
        options=options,
    )
    res_enabled = engine_enabled.run()

    # 2. Run with benchmark disabled (df_b=None)
    engine_disabled = InvestmentQuantEngine(
        data=QuantDataFrames(
            df_p=df_p,
            df_s=df_s,
            df_m=df_m,
            df_i=df_i,
            df_b=None,
            df_t=df_t,
        ),
        options=options,
    )
    res_disabled = engine_disabled.run()

    # Invariance assertions: FIFO lots core accounting, realized gains, and reconciliation events must be strictly identical
    lot_enabled = res_enabled["df_f_investment_analytics_lot"]
    lot_disabled = res_disabled["df_f_investment_analytics_lot"]

    bm_cols = {
        c
        for c in lot_enabled.columns
        if "BM_" in c
        or "Benchmark" in c
        or "Alpha" in c
        or "Outperforming" in c
        or "Active_Return" in c
    }
    core_cols = [c for c in lot_enabled.columns if c not in bm_cols]

    # Core 73 accounting columns (cost basis, market value, unrealized gain, tax estimates, holding periods)
    assert lot_enabled.select(core_cols).equals(lot_disabled.select(core_cols))

    # Benchmark-enriched columns reflect presence/absence cleanly
    assert lot_enabled["BM_Buy_Price"].null_count() == 0
    assert lot_disabled["BM_Buy_Price"].null_count() == len(lot_disabled)

    # Realized gains and reconciliation are 100% byte-identical
    realized_enabled = res_enabled["df_f_investment_realized_events"]
    realized_disabled = res_disabled["df_f_investment_realized_events"]
    assert realized_enabled.equals(realized_disabled)

    recon_enabled = res_enabled["df_f_investment_reconciliation_events"]
    recon_disabled = res_disabled["df_f_investment_reconciliation_events"]
    assert recon_enabled.equals(recon_disabled)
