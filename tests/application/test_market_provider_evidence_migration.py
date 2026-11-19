"""Comprehensive verification test suite for Phase 034 market provider evidence migration.

Owns
----
- Verification of MarketProviderSelector model, defaults, and discriminated union resolution.
- Verification of dynamic SourcePlanner synthesis of ProviderDatasetPlan and ProviderSourcePlan.
- Verification of capability-aware request gating (FOREIGN_ASSET_ENRICHMENT and BENCHMARK_ENRICHMENT).
- Verification of Gate 1 / Gate 2 validation on provider response frames and canonical Bronze schemas.
- Verification of Pre-Bronze persistence, table existence, and operational provenance columns.
- Verification of failure isolation: validation errors halt publication before Bronze modification.
- Verification of caching preservation and skip events on disabled capabilities.
- Verification of downstream transformation stability across Currency, Benchmark, and US Market.

Does not own
------------
- File-based evidence admission (owned by tests.application.test_generalized_vertical_slice).
- Low-level Yahoo Finance HTTP network mocks (owned by tests.infrastructure.test_providers).
- Architectural layer boundaries (owned by tests.architecture.test_boundaries).
"""

from __future__ import annotations

import tempfile
from datetime import date
from unittest.mock import MagicMock

import polars as pl
import pytest
from pydantic import TypeAdapter

from personal_finance_etl.application.ingestion.market_sync import (
    upsert_market_delta_and_register,
)
from personal_finance_etl.application.pipeline.planner import CapabilityPlanner
from personal_finance_etl.application.pipeline.source_planner import (
    CompiledSourcePlan,
    SourcePlanner,
)
from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.selectors import (
    DatasetSelector,
    MarketProviderSelector,
)
from personal_finance_etl.contracts.capabilities import CapabilityId
from personal_finance_etl.contracts.datasets import (
    PROVIDER_GENERATED_DATASETS,
    DatasetId,
    DatasetOrigin,
)
from personal_finance_etl.contracts.event_transport import EventQueue
from personal_finance_etl.contracts.observability import (
    PresentationKind,
)
from personal_finance_etl.contracts.sources import ProviderType, SourceId
from personal_finance_etl.contracts.validation import ValidationError
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.control_plane.hashing import generate_file_id
from personal_finance_etl.infrastructure.observability import ObservabilityEmitter
from personal_finance_etl.infrastructure.validation.canonical_schemas import (
    CANONICAL_BRONZE_MARKET_BENCHMARK_HISTORY_SCHEMA,
    CANONICAL_BRONZE_MARKET_CURRENCY_FX_RATES_SCHEMA,
    CANONICAL_BRONZE_MARKET_US_STOCK_PRICES_SCHEMA,
    get_canonical_bronze_schema,
    has_canonical_bronze_schema,
)
from personal_finance_etl.infrastructure.warehouse.bronze import (
    BronzeLayer,
)
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
    PRE_BRONZE_ARTIFACT_ID,
    PRE_BRONZE_DATASET_ID,
    PRE_BRONZE_SOURCE_ID,
)
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer
from personal_finance_etl.infrastructure.warehouse.pre_bronze import PreBronzeLayer
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_pre_bronze_contract_by_dataset_id,
)


def test_market_provider_selector_contract() -> None:
    """Verify MarketProviderSelector initialization, serialization, and discriminator resolution."""
    selector = MarketProviderSelector()
    assert selector.provider_type == ProviderType.MARKET_DATA
    assert selector.feed_name == "yahoo_finance"

    # Discriminated union round-trip
    adapter: TypeAdapter[DatasetSelector] = TypeAdapter(DatasetSelector)
    raw_dict: dict[str, object] = {"provider_type": "market_data", "feed_name": "alpha_vantage"}
    parsed = adapter.validate_python(raw_dict)
    assert isinstance(parsed, MarketProviderSelector)
    assert parsed.provider_type == ProviderType.MARKET_DATA
    assert parsed.feed_name == "alpha_vantage"


def test_source_planner_synthesizes_provider_datasets(
    source_config: SourceConfiguration,
) -> None:
    """Verify SourcePlanner synthesizes typed provider plans without user file sources."""
    execution_plan = CapabilityPlanner().create_plan()
    planner = SourcePlanner(source_config, execution_plan)
    compiled = planner.compile_plan()

    assert isinstance(compiled, CompiledSourcePlan)

    # 1. Check all 3 provider datasets have compiled plans
    for provider_ds_id in PROVIDER_GENERATED_DATASETS:
        dp = compiled.get_dataset_plan(provider_ds_id)
        assert dp is not None, f"Missing DatasetPlan for provider dataset {provider_ds_id}"
        assert dp.origin == DatasetOrigin.PROVIDER_GENERATED
        assert dp.provider_type == ProviderType.MARKET_DATA
        assert dp.source_id == SourceId("provider_market_data")
        assert dp.location == "provider://market_data"
        assert isinstance(dp.selector, MarketProviderSelector)
        assert dp.is_required is True
        assert dp.is_enabled is True
        assert compiled.is_dataset_enabled(provider_ds_id) is True

    # 2. Check synthesized provider SourcePlan
    sp = compiled.get_source_plan("provider_market_data")
    assert sp is not None
    assert sp.provider_type == ProviderType.MARKET_DATA
    assert sp.enabled is True
    assert len(sp.dataset_plans) == 3


def test_source_planner_capability_gating(
    source_config: SourceConfiguration,
) -> None:
    """Verify omitting enrichment capabilities propagates is_enabled=False to provider datasets."""
    # 1. Disable FOREIGN_ASSET_ENRICHMENT
    caps_no_fx = [c for c in CapabilityId if c != CapabilityId.FOREIGN_ASSET_ENRICHMENT]
    plan_no_fx = CapabilityPlanner().create_plan(requested_capabilities=caps_no_fx)
    compiled_no_fx = SourcePlanner(source_config, plan_no_fx).compile_plan()

    dp_fx = compiled_no_fx.get_dataset_plan(DatasetId.MARKET_CURRENCY_FX_RATES)
    assert dp_fx is not None
    assert dp_fx.is_required is False
    assert dp_fx.is_enabled is False

    dp_us = compiled_no_fx.get_dataset_plan(DatasetId.MARKET_US_STOCK_PRICES)
    assert dp_us is not None
    assert dp_us.is_required is False
    assert dp_us.is_enabled is False

    # Benchmark remains enabled
    dp_bm = compiled_no_fx.get_dataset_plan(DatasetId.MARKET_BENCHMARK_HISTORY)
    assert dp_bm is not None
    assert dp_bm.is_required is True
    assert dp_bm.is_enabled is True

    # 2. Disable BENCHMARK_ENRICHMENT
    caps_no_bm = [c for c in CapabilityId if c != CapabilityId.BENCHMARK_ENRICHMENT]
    plan_no_bm = CapabilityPlanner().create_plan(requested_capabilities=caps_no_bm)
    compiled_no_bm = SourcePlanner(source_config, plan_no_bm).compile_plan()

    dp_bm2 = compiled_no_bm.get_dataset_plan(DatasetId.MARKET_BENCHMARK_HISTORY)
    assert dp_bm2 is not None
    assert dp_bm2.is_required is False
    assert dp_bm2.is_enabled is False

    dp_fx2 = compiled_no_bm.get_dataset_plan(DatasetId.MARKET_CURRENCY_FX_RATES)
    assert dp_fx2 is not None
    assert dp_fx2.is_required is True
    assert dp_fx2.is_enabled is True


def test_canonical_bronze_schemas_exist_and_validate() -> None:
    """Verify canonical Bronze Pandera schemas exist and validate well-formed provider frames."""
    assert has_canonical_bronze_schema(DatasetId.MARKET_CURRENCY_FX_RATES)
    assert has_canonical_bronze_schema(DatasetId.MARKET_BENCHMARK_HISTORY)
    assert has_canonical_bronze_schema(DatasetId.MARKET_US_STOCK_PRICES)

    # 1. Currency FX Schema Validation (with nullable closure gap)
    df_currency = pl.DataFrame(
        {
            "Date": [date(2026, 1, 1), date(2026, 1, 2)],
            "Currency_ID": ["USD", "USD"],
            "Currency_Name": ["US Dollar", "US Dollar"],
            "Currency_Code": ["USD", "USD"],
            "Target_Currency_Code": ["INR", "INR"],
            "yF_Ticker": ["USDINR=X", "USDINR=X"],
            "FX_Rate": [83.5, None],
            "Data_Provider": ["Yahoo Finance", "Yahoo Finance"],
            "Extraction_Time": ["2026-01-02T10:00:00", "2026-01-02T10:00:00"],
            "Requested_Start": [date(2026, 1, 1), date(2026, 1, 1)],
            "Requested_End": [date(2026, 1, 2), date(2026, 1, 2)],
            "Is_Closure_Gap": [False, True],
        }
    )
    schema_fx = get_canonical_bronze_schema(DatasetId.MARKET_CURRENCY_FX_RATES)
    assert schema_fx is CANONICAL_BRONZE_MARKET_CURRENCY_FX_RATES_SCHEMA
    validated_fx = schema_fx.validate(df_currency)
    assert validated_fx.height == 2

    # 2. Benchmark Schema Validation
    df_bm = pl.DataFrame(
        {
            "Date": [date(2026, 1, 1)],
            "ID": ["NIFTY_50"],
            "Benchmark_Name": ["Nifty 50"],
            "yF_Ticker": ["^NSEI"],
            "CURRENCY_ID": ["INR"],
            "Close": [24500.0],
            "Data_Provider": ["Yahoo Finance"],
            "Extraction_Time": ["2026-01-02T10:00:00"],
            "Requested_Start": [date(2026, 1, 1)],
            "Requested_End": [date(2026, 1, 1)],
            "Is_Closure_Gap": [False],
        }
    )
    schema_bm = get_canonical_bronze_schema(DatasetId.MARKET_BENCHMARK_HISTORY)
    assert schema_bm is CANONICAL_BRONZE_MARKET_BENCHMARK_HISTORY_SCHEMA
    validated_bm = schema_bm.validate(df_bm)
    assert validated_bm.height == 1

    # 3. US Market Schema Validation
    df_us = pl.DataFrame(
        {
            "Date": [date(2026, 1, 1)],
            "ISIN": ["US0378331005"],
            "yF_Ticker": ["AAPL"],
            "Closing_Price_Local": [225.5],
            "Data_Provider": ["Yahoo Finance"],
            "Extraction_Time": ["2026-01-02T10:00:00"],
            "Requested_Start": [date(2026, 1, 1)],
            "Requested_End": [date(2026, 1, 1)],
            "Is_Closure_Gap": [False],
        }
    )
    schema_us = get_canonical_bronze_schema(DatasetId.MARKET_US_STOCK_PRICES)
    assert schema_us is CANONICAL_BRONZE_MARKET_US_STOCK_PRICES_SCHEMA
    validated_us = schema_us.validate(df_us)
    assert validated_us.height == 1


def test_upsert_market_delta_persists_pre_bronze_and_bronze() -> None:
    """Verify upsert_market_delta_and_register persists Pre-Bronze with provenance and canonical Bronze."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_mgr = DuckDBManager(temp_dir, "Personal_Finance_DB.duckdb")
        db_mgr.open()
        db_mgr.ensure_schemas()

        cp = ControlPlane(temp_dir, "Raw_Documents.sqlite")
        cp.open()
        cp.ensure_schema()

        try:
            meta_layer = MetaLayer(db_mgr, MagicMock(), MagicMock())
            bronze = BronzeLayer(db_mgr, cp, meta_layer)

            # Build valid Currency FX delta
            v_path = cp.artifacts.inject_virtual_file(
                filename="currency_delta_2026_test.parquet",
                category="currency_history",
                raw_bytes=b"dummy_parquet_content",
            )
            artifact_id = generate_file_id(v_path)

            df_delta = pl.DataFrame(
                {
                    "Date": [date(2026, 1, 1), date(2026, 1, 2)],
                    "Currency_ID": ["USD", "USD"],
                    "Currency_Name": ["US Dollar", "US Dollar"],
                    "Currency_Code": ["USD", "USD"],
                    "Target_Currency_Code": ["INR", "INR"],
                    "yF_Ticker": ["USDINR=X", "USDINR=X"],
                    "FX_Rate": [83.5, 83.6],
                    "Data_Provider": ["Yahoo Finance", "Yahoo Finance"],
                    "Extraction_Time": ["2026-01-02T10:00:00", "2026-01-02T10:00:00"],
                    "Requested_Start": [date(2026, 1, 1), date(2026, 1, 1)],
                    "Requested_End": [date(2026, 1, 2), date(2026, 1, 2)],
                    "Is_Closure_Gap": [False, False],
                    "artifact_id": [artifact_id, artifact_id],
                }
            )

            upsert_market_delta_and_register(
                bronze=bronze,
                df_delta=df_delta,
                table_name="bronze.r_Currency_FX_Data",
                new_files=[v_path],
                meta_file_type="currency_history",
                dataset_id=DatasetId.MARKET_CURRENCY_FX_RATES,
                frames=[df_delta],
            )

            # 1. Assert Pre-Bronze table exists and contains provenance
            pb_contract = get_pre_bronze_contract_by_dataset_id(DatasetId.MARKET_CURRENCY_FX_RATES)
            assert pb_contract is not None
            pb_layer = PreBronzeLayer(db_mgr)
            assert pb_layer.table_exists(pb_contract)

            pb_rows = db_mgr.conn.execute(f"SELECT * FROM {pb_contract.physical_table}").pl()
            assert pb_rows.height == 2
            assert PRE_BRONZE_ARTIFACT_ID in pb_rows.columns
            assert PRE_BRONZE_SOURCE_ID in pb_rows.columns
            assert PRE_BRONZE_DATASET_ID in pb_rows.columns
            assert pb_rows[PRE_BRONZE_ARTIFACT_ID][0] == artifact_id
            assert pb_rows[PRE_BRONZE_SOURCE_ID][0] == "market_data"
            assert pb_rows[PRE_BRONZE_DATASET_ID][0] == "market_currency_fx_rates"

            # 2. Assert Bronze table exists and contains admitted rows
            bronze_table = bronze.get_table("r_Currency_FX_Data")
            assert bronze_table.height == 2
            assert "FX_Rate" in bronze_table.columns
            assert "yF_Ticker" in bronze_table.columns

            # 3. Assert artifact is marked SYNCED in Control Plane
            reg = cp.artifacts.get_registry_with_status()
            assert v_path in reg
            assert reg[v_path][2] == "SYNCED"
        finally:
            db_mgr.close()
            cp.close()


def test_upsert_market_delta_validation_failure_blocks_bronze() -> None:
    """Verify validation error in provider frame halts execution before Bronze table modification."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_mgr = DuckDBManager(temp_dir, "Personal_Finance_DB.duckdb")
        db_mgr.open()
        db_mgr.ensure_schemas()

        cp = ControlPlane(temp_dir, "Raw_Documents.sqlite")
        cp.open()
        cp.ensure_schema()

        try:
            meta_layer = MetaLayer(db_mgr, MagicMock(), MagicMock())
            bronze = BronzeLayer(db_mgr, cp, meta_layer)

            v_path = cp.artifacts.inject_virtual_file(
                filename="invalid_bm.parquet",
                category="benchmark_history",
                raw_bytes=b"dummy",
            )

            # Invalid frame: Date is a string instead of Date, Close is invalid type
            df_invalid = pl.DataFrame(
                {
                    "Date": ["not-a-date"],
                    "ID": ["NIFTY"],
                    "Benchmark_Name": ["Nifty 50"],
                    "yF_Ticker": ["^NSEI"],
                    "CURRENCY_ID": ["INR"],
                    "Close": ["not-a-number"],
                    "Data_Provider": ["Yahoo Finance"],
                    "Extraction_Time": ["2026-01-01T00:00:00"],
                    "Requested_Start": ["invalid"],
                    "Requested_End": ["invalid"],
                    "Is_Closure_Gap": [False],
                }
            )

            with pytest.raises(ValidationError):
                upsert_market_delta_and_register(
                    bronze=bronze,
                    df_delta=df_invalid,
                    table_name="bronze.r_Benchmark_Data",
                    new_files=[v_path],
                    meta_file_type="benchmark_history",
                    dataset_id=DatasetId.MARKET_BENCHMARK_HISTORY,
                )

            # Verify Bronze table was NOT created or modified
            df_bronze = bronze.get_table("r_Benchmark_Data")
            assert df_bronze.is_empty()
        finally:
            db_mgr.close()
            cp.close()


def test_migrated_datasets_contains_all_19_active_evidence_streams() -> None:
    """Verify all 19 active Medallion Bronze evidence datasets are registered."""
    evidence_contracts = [
        c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id != DatasetId.COMMON_COLUMN_MASTER
    ]
    assert len(evidence_contracts) == 19
    for ds_id in (
        DatasetId.MARKET_CURRENCY_FX_RATES,
        DatasetId.MARKET_BENCHMARK_HISTORY,
        DatasetId.MARKET_US_STOCK_PRICES,
    ):
        assert any(c.dataset_id == ds_id for c in evidence_contracts)


def test_pipeline_executor_capability_skips() -> None:
    """Verify that PipelineExecutor skips market provider syncs when capabilities are inactive."""
    from personal_finance_etl.application.pipeline.execution import PipelineExecutor

    # Plan with FOREIGN_ASSET_ENRICHMENT and BENCHMARK_ENRICHMENT disabled
    active_caps = [
        c
        for c in CapabilityId
        if c not in (CapabilityId.FOREIGN_ASSET_ENRICHMENT, CapabilityId.BENCHMARK_ENRICHMENT)
    ]
    plan = CapabilityPlanner().create_plan(requested_capabilities=active_caps)

    mock_emitter = MagicMock(spec=ObservabilityEmitter)
    mock_db = MagicMock(spec=DuckDBManager)
    mock_cp = MagicMock(spec=ControlPlane)
    mock_bronze = MagicMock(spec=BronzeLayer)
    mock_queue = MagicMock(spec=EventQueue)

    executor = PipelineExecutor(
        cfg=MagicMock(),
        status_queue=mock_queue,
        db_manager=mock_db,
        plan=plan,
        emitter=mock_emitter,
    )

    # 1. Currency should skip
    executor.process_currency(mock_cp, mock_bronze)
    # 2. US Market should skip
    executor.process_us_market_data(mock_cp, mock_bronze)
    # 3. Benchmark should skip
    executor.process_benchmark(mock_cp, mock_bronze)

    # Verify skip events emitted
    skip_calls = [
        call
        for call in mock_emitter.emit_event.call_args_list
        if call.kwargs.get("presentation_kind") == PresentationKind.SKIP
    ]
    assert len(skip_calls) == 3


def test_upsert_market_delta_backfills_pre_bronze_when_delta_is_empty() -> None:
    """Verify that when delta is empty but Pre-Bronze is missing, cached CP chunks backfill Pre-Bronze."""
    import io

    with tempfile.TemporaryDirectory() as temp_dir:
        db_mgr = DuckDBManager(temp_dir, "Personal_Finance_DB.duckdb")
        db_mgr.open()
        db_mgr.ensure_schemas()

        cp = ControlPlane(temp_dir, "Raw_Documents.sqlite")
        cp.open()
        cp.ensure_schema()

        try:
            meta_layer = MetaLayer(db_mgr, MagicMock(), MagicMock())
            bronze = BronzeLayer(db_mgr, cp, meta_layer)

            # Create real parquet bytes in Control Plane
            chunk_df = pl.DataFrame(
                {
                    "Date": [date(2025, 1, 1), date(2025, 1, 2)],
                    "Currency_ID": ["USD", "USD"],
                    "Currency_Name": ["US Dollar", "US Dollar"],
                    "Currency_Code": ["USD", "USD"],
                    "Target_Currency_Code": ["INR", "INR"],
                    "yF_Ticker": ["USDINR=X", "USDINR=X"],
                    "FX_Rate": [83.0, 83.1],
                    "Data_Provider": ["Yahoo Finance", "Yahoo Finance"],
                    "Extraction_Time": ["2025-01-02T10:00:00", "2025-01-02T10:00:00"],
                    "Requested_Start": [date(2025, 1, 1), date(2025, 1, 1)],
                    "Requested_End": [date(2025, 1, 2), date(2025, 1, 2)],
                    "Is_Closure_Gap": [False, False],
                    "artifact_id": ["sha256_mock_curr_2025", "sha256_mock_curr_2025"],
                }
            )
            buf = io.BytesIO()
            chunk_df.write_parquet(buf)
            raw_bytes = buf.getvalue()

            v_path = cp.artifacts.inject_virtual_file(
                filename="currency_2025.parquet",
                category="currency_history",
                raw_bytes=raw_bytes,
            )

            # Ensure Pre-Bronze table does not exist initially
            pb_layer = PreBronzeLayer(db_mgr)
            pb_contract = get_pre_bronze_contract_by_dataset_id(DatasetId.MARKET_CURRENCY_FX_RATES)
            assert pb_contract is not None
            assert not pb_layer.table_exists(pb_contract)

            # Call upsert with empty df_delta (simulating 100% cached run)
            upsert_market_delta_and_register(
                bronze=bronze,
                df_delta=pl.DataFrame(),
                table_name="bronze.r_Currency_FX_Data",
                new_files=[],
                meta_file_type="currency_history",
                dataset_id=DatasetId.MARKET_CURRENCY_FX_RATES,
            )

            # Verify Pre-Bronze was automatically backfilled from Control Plane
            assert pb_layer.table_exists(pb_contract)
            df_pb = pb_layer.read(DatasetId.MARKET_CURRENCY_FX_RATES, include_provenance=True)
            assert df_pb.height == 2
            assert "__artifact_id__" in df_pb.columns
            assert df_pb.select(pl.col("__artifact_id__")).item(0, 0) == generate_file_id(v_path)
        finally:
            db_mgr.close()
            cp.close()


def test_market_provider_virtual_artifacts_file_type_is_parquet() -> None:
    """Verify market provider virtual artifacts receive 'parquet' file_type in CP and MetaLayer."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_mgr = DuckDBManager(temp_dir, "Personal_Finance_DB.duckdb")
        db_mgr.open()
        db_mgr.ensure_schemas()

        cp = ControlPlane(temp_dir, "Raw_Documents.sqlite")
        cp.open()
        cp.ensure_schema()

        try:
            meta_layer = MetaLayer(db_mgr, MagicMock(), MagicMock())

            # 1. Inject currency virtual file
            cur_path = cp.artifacts.inject_virtual_file(
                filename="currency_2026.parquet",
                category="currency_history",
                raw_bytes=b"dummy_bytes",
            )
            # 2. Inject us stock virtual file
            us_path = cp.artifacts.inject_virtual_file(
                filename="us_stock_2026.parquet",
                category="us_stock_market",
                raw_bytes=b"dummy_bytes",
            )

            # Assert Control Plane registry has file_type='parquet'
            cur_meta = cp.artifacts.get_artifact_metadata(generate_file_id(cur_path))
            assert cur_meta is not None
            assert cur_meta.file_type == "parquet"

            us_meta = cp.artifacts.get_artifact_metadata(generate_file_id(us_path))
            assert us_meta is not None
            assert us_meta.file_type == "parquet"

            # Register in MetaLayer
            meta_layer.register_file(cur_path, "currency_history", 100, cp)
            meta_layer.register_file(us_path, "us_stock_market", 50, cp)

            # Assert DuckDB meta.m_File_Registry has file_type='parquet'
            meta_cur = db_mgr.conn.execute(
                "SELECT file_type FROM meta.m_File_Registry WHERE relative_path = ?",
                [cur_path],
            ).fetchone()
            assert meta_cur is not None
            assert meta_cur[0] == "parquet"

            meta_us = db_mgr.conn.execute(
                "SELECT file_type FROM meta.m_File_Registry WHERE relative_path = ?",
                [us_path],
            ).fetchone()
            assert meta_us is not None
            assert meta_us[0] == "parquet"
        finally:
            db_mgr.close()
            cp.close()
