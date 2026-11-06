"""Pre-Bronze warehouse persistence and transaction boundary test suite.

Owns
----
- Verification of additive pre_bronze DuckDB schema creation and idempotency.
- Invariant tests for PreBronzeDataContract and PRE_BRONZE_CONTRACT_REGISTRY integrity.
- Tests for PFETL-controlled physical table naming and SQL injection prevention.
- Full table replacement persistence and retrieval tests.
- Artifact-keyed incremental replacement persistence tests with multi-artifact isolation.
- Idempotent re-ingestion tests proving zero duplicate rows for unchanged artifacts.
- Artifact identity migration tests verifying rename handling without data re-extraction.
- ACID transaction proof asserting rollback reverts uncommitted Pre-Bronze mutations.
- AST architectural guard proving PreBronzeLayer contains zero independent commits.
- Schema evolution tests verifying dynamic addition of new source columns.
- Source-filtering and provenance column stripping in read APIs.

Does not own
-------------
- Production pipeline execution (owned by tests.application.test_forensic_pipeline).
- SQLite Control Plane artifact vaulting (owned by tests.infrastructure.test_provenance_resolution).
- Higher warehouse layers (owned by tests.infrastructure.test_warehouse_and_cp).
"""

from __future__ import annotations

import ast
from pathlib import Path

import polars as pl
import pytest

from personal_finance_etl.config.sources.change_detection import SyncStrategy
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    PRE_BRONZE_ARTIFACT_ID,
    PRE_BRONZE_CONTRACT_REGISTRY,
    PRE_BRONZE_DATASET_ID,
    PRE_BRONZE_PROVENANCE_COLUMNS,
    PRE_BRONZE_SOURCE_ID,
    PreBronzeDataContract,
)
from personal_finance_etl.infrastructure.warehouse.pre_bronze import (
    PreBronzeLayer,
    get_pre_bronze_table_name,
    sanitize_physical_identifier,
)
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_pre_bronze_contract_by_dataset_id,
    get_pre_bronze_contract_by_table,
    validate_registry,
)


def test_pre_bronze_schema_initialization_idempotent(
    isolated_duckdb_manager: DuckDBManager,
) -> None:
    """Verify that pre_bronze schema is created additively and idempotently."""
    isolated_duckdb_manager.open()
    # Call ensure_schemas multiple times to guarantee idempotency
    isolated_duckdb_manager.ensure_schemas()
    isolated_duckdb_manager.ensure_schemas()

    schemas = {
        str(row[0])
        for row in isolated_duckdb_manager.conn.execute(
            "SELECT schema_name FROM information_schema.schemata"
        ).fetchall()
    }
    assert {"pre_bronze", "bronze", "silver", "gold", "meta"}.issubset(schemas)


def test_pre_bronze_contract_registry_validation() -> None:
    """Verify structural validity and lookup of registered Pre-Bronze contracts."""
    # Ensure validate_registry passes without diagnostics
    validate_registry()

    assert len(PRE_BRONZE_CONTRACT_REGISTRY) > 0

    # Test lookup by DatasetId enum and string
    contract = get_pre_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert contract is not None
    assert contract.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY
    assert contract.physical_table == "pre_bronze.pb_household_zcategory"
    assert contract.sync_strategy == SyncStrategy.FULL_REPLACE
    assert contract.provenance_required is True

    contract_by_str = get_pre_bronze_contract_by_dataset_id("household_zcategory")
    assert contract_by_str == contract

    # Test lookup by physical table
    contract_by_table = get_pre_bronze_contract_by_table("pre_bronze.pb_household_zcategory")
    assert contract_by_table == contract

    # Case-insensitive lookup
    contract_case = get_pre_bronze_contract_by_table("PRE_BRONZE.PB_HOUSEHOLD_ZCATEGORY")
    assert contract_case == contract

    # Unknown returns None
    assert get_pre_bronze_contract_by_dataset_id("unknown_dataset_xyz") is None
    assert get_pre_bronze_contract_by_table("pre_bronze.pb_nonexistent") is None


def test_pre_bronze_physical_table_naming_and_sanitization() -> None:
    """Verify deterministic physical table naming and rejection of SQL injection."""
    # Normal naming without source_id
    table_name = get_pre_bronze_table_name(DatasetId.INVESTMENT_STOCK_ORDERS)
    assert table_name == "pre_bronze.pb_investment_stock_orders"

    # With source_id
    table_with_src = get_pre_bronze_table_name(
        DatasetId.INVESTMENT_STOCK_ORDERS, source_id=SourceId("zerodha")
    )
    assert table_with_src == "pre_bronze.pb_zerodha_investment_stock_orders"

    # Sanitization of safe separators (hyphens and periods)
    assert sanitize_physical_identifier("my-source.data") == "my_source_data"

    # Rejection of dangerous injection characters
    injection_candidates = [
        "'; DROP TABLE pre_bronze.pb_test; --",
        "source'name",
        '"quoted_table"',
        "source--comment",
        "table with space",
        "path/to/table",
        "path\\to\\table",
        "",
        "   ",
    ]
    for candidate in injection_candidates:
        with pytest.raises(ValueError, match="Unsafe physical identifier|cannot be empty"):
            sanitize_physical_identifier(candidate)

    # Rejection of invalid types
    with pytest.raises(TypeError, match="Identifier must be a str"):
        sanitize_physical_identifier(123)


def test_pre_bronze_full_replace_persistence(isolated_pre_bronze_layer: PreBronzeLayer) -> None:
    """Verify full table replacement creates, attaches provenance, and replaces table rows."""
    contract = PreBronzeDataContract(
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        physical_table="pre_bronze.pb_household_zcategory",
        sync_strategy=SyncStrategy.FULL_REPLACE,
    )

    # 1. First full write: 3 rows
    df_initial = pl.DataFrame(
        {
            "Category_ID": [1, 2, 3],
            "Category_Name": ["Salary", "Investments", "Groceries"],
            "Type": ["Income", "Asset", "Expense"],
        }
    )
    rows_written = isolated_pre_bronze_layer.write_full_replace(
        contract,
        df_initial,
        artifact_id="art_hash_001",
        source_id=SourceId("household_sqlite"),
    )
    assert rows_written == 3
    assert isolated_pre_bronze_layer.table_exists(contract)

    # Read with provenance
    read_df = isolated_pre_bronze_layer.read(contract.dataset_id, include_provenance=True)
    assert read_df.height == 3
    assert set(PRE_BRONZE_PROVENANCE_COLUMNS).issubset(set(read_df.columns))
    assert read_df[PRE_BRONZE_ARTIFACT_ID].to_list() == ["art_hash_001"] * 3
    assert read_df[PRE_BRONZE_SOURCE_ID].to_list() == ["household_sqlite"] * 3
    assert read_df[PRE_BRONZE_DATASET_ID].to_list() == [DatasetId.HOUSEHOLD_ZCATEGORY.value] * 3

    # Read without provenance returns clean source-shaped frame
    read_clean = isolated_pre_bronze_layer.read(contract.dataset_id, include_provenance=False)
    assert read_clean.columns == ["Category_ID", "Category_Name", "Type"]

    # 2. Second full write: replaces entire table with 2 completely different rows
    df_replacement = pl.DataFrame(
        {
            "Category_ID": [10, 20],
            "Category_Name": ["Consulting", "Dividends"],
            "Type": ["Income", "Income"],
        }
    )
    rows_written_2 = isolated_pre_bronze_layer.write(
        contract,
        df_replacement,
        artifact_id="art_hash_002",
        source_id=SourceId("household_sqlite"),
    )
    assert rows_written_2 == 2

    # Assert old rows are completely replaced
    read_replaced = isolated_pre_bronze_layer.read(contract.dataset_id, include_provenance=True)
    assert read_replaced.height == 2
    assert read_replaced["Category_ID"].to_list() == [10, 20]
    assert read_replaced[PRE_BRONZE_ARTIFACT_ID].to_list() == ["art_hash_002"] * 2


def test_pre_bronze_incremental_artifact_keyed_write(
    isolated_pre_bronze_layer: PreBronzeLayer,
) -> None:
    """Verify artifact-keyed incremental write replaces changed artifacts and preserves siblings."""
    contract = PreBronzeDataContract(
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        physical_table="pre_bronze.pb_investment_stock_orders",
        sync_strategy=SyncStrategy.INCREMENTAL,
    )

    # 1. Ingest Artifact A (3 rows)
    df_art_a = pl.DataFrame(
        {
            "order_id": ["A1", "A2", "A3"],
            "symbol": ["INFY", "TCS", "RELIANCE"],
            "qty": [10, 20, 30],
        }
    )
    isolated_pre_bronze_layer.write_incremental(
        contract,
        df_art_a,
        artifact_id="artifact_a_sha",
        source_id=SourceId("broker_zerodha"),
    )
    assert isolated_pre_bronze_layer.read(contract.dataset_id).height == 3

    # 2. Ingest Artifact B (2 rows) into the same table
    df_art_b = pl.DataFrame(
        {
            "order_id": ["B1", "B2"],
            "symbol": ["HDFCBANK", "ICICIBANK"],
            "qty": [50, 100],
        }
    )
    isolated_pre_bronze_layer.write_incremental(
        contract,
        df_art_b,
        artifact_id="artifact_b_sha",
        source_id=SourceId("broker_groww"),
    )
    assert isolated_pre_bronze_layer.read(contract.dataset_id).height == 5

    # 3. Update Artifact A with 4 modified rows (A1, A2, A3, A4)
    df_art_a_updated = pl.DataFrame(
        {
            "order_id": ["A1", "A2", "A3", "A4"],
            "symbol": ["INFY", "TCS", "RELIANCE", "WIPRO"],
            "qty": [15, 25, 35, 45],
        }
    )
    isolated_pre_bronze_layer.write(
        contract,
        df_art_a_updated,
        artifact_id="artifact_a_sha",
        source_id=SourceId("broker_zerodha"),
    )

    # Total rows must now be 6 (4 updated rows from A + 2 unchanged rows from B)
    combined = isolated_pre_bronze_layer.read(contract.dataset_id, include_provenance=True)
    assert combined.height == 6

    # Verify Artifact B rows were preserved exactly
    b_rows = combined.filter(pl.col(PRE_BRONZE_ARTIFACT_ID) == "artifact_b_sha")
    assert b_rows.height == 2
    assert set(b_rows["order_id"].to_list()) == {"B1", "B2"}

    # Verify Artifact A rows reflect the updated data
    a_rows = combined.filter(pl.col(PRE_BRONZE_ARTIFACT_ID) == "artifact_a_sha")
    assert a_rows.height == 4
    assert set(a_rows["order_id"].to_list()) == {"A1", "A2", "A3", "A4"}


def test_pre_bronze_unchanged_artifact_no_duplication(
    isolated_pre_bronze_layer: PreBronzeLayer,
) -> None:
    """Verify that re-ingesting an unchanged artifact replaces rows idempotently without duplication."""
    contract = PreBronzeDataContract(
        dataset_id=DatasetId.MARKET_MF_HOLDINGS,
        physical_table="pre_bronze.pb_market_mf_holdings",
        sync_strategy=SyncStrategy.INCREMENTAL,
    )
    df = pl.DataFrame(
        {
            "folio": ["123", "456"],
            "scheme": ["HDFC Top 100", "Parag Parikh Flexi Cap"],
            "units": [100.5, 200.75],
        }
    )

    isolated_pre_bronze_layer.write_incremental(contract, df, artifact_id="holdings_sha_001")
    assert isolated_pre_bronze_layer.read(contract.dataset_id).height == 2

    # Re-write the same artifact
    isolated_pre_bronze_layer.write_incremental(contract, df, artifact_id="holdings_sha_001")
    assert isolated_pre_bronze_layer.read(contract.dataset_id).height == 2


def test_pre_bronze_artifact_rename_migration(isolated_pre_bronze_layer: PreBronzeLayer) -> None:
    """Verify artifact identity migration across file renames without re-extracting data."""
    contract = PreBronzeDataContract(
        dataset_id=DatasetId.INVESTMENT_MF_ORDERS,
        physical_table="pre_bronze.pb_investment_mf_orders",
        sync_strategy=SyncStrategy.INCREMENTAL,
    )
    df = pl.DataFrame(
        {
            "order_num": ["ORD_1", "ORD_2"],
            "scheme": ["Axis Bluechip", "Mirae Large Cap"],
        }
    )

    isolated_pre_bronze_layer.write_incremental(contract, df, artifact_id="old_file_sha_123")
    assert isolated_pre_bronze_layer.read(contract.dataset_id).height == 2

    # Migrate identity to new artifact ID
    updated_rows = isolated_pre_bronze_layer.migrate_artifact_identity(
        old_artifact_id="old_file_sha_123",
        new_artifact_id="new_file_sha_456",
        contract_or_table=contract,
    )
    assert updated_rows == 2

    # Verify table now reflects the new artifact ID
    migrated_df = isolated_pre_bronze_layer.read(contract.dataset_id, include_provenance=True)
    assert migrated_df.height == 2
    assert migrated_df[PRE_BRONZE_ARTIFACT_ID].to_list() == ["new_file_sha_456"] * 2


def test_pre_bronze_delete_artifact(isolated_pre_bronze_layer: PreBronzeLayer) -> None:
    """Verify parameterized deletion of an artifact's rows from Pre-Bronze."""
    contract = PreBronzeDataContract(
        dataset_id=DatasetId.INVESTMENT_US_STOCK_TRANSACTIONS,
        physical_table="pre_bronze.pb_investment_us_stock_transactions",
        sync_strategy=SyncStrategy.INCREMENTAL,
    )
    df_a = pl.DataFrame({"symbol": ["AAPL", "GOOGL"], "shares": [10, 5]})
    df_b = pl.DataFrame({"symbol": ["MSFT"], "shares": [8]})

    isolated_pre_bronze_layer.write_incremental(contract, df_a, artifact_id="art_us_1")
    isolated_pre_bronze_layer.write_incremental(contract, df_b, artifact_id="art_us_2")
    assert isolated_pre_bronze_layer.read(contract.dataset_id).height == 3

    # Delete art_us_1
    deleted_count = isolated_pre_bronze_layer.delete_artifact("art_us_1", contract)
    assert deleted_count == 2

    # Verify only art_us_2 remains
    remaining = isolated_pre_bronze_layer.read(contract.dataset_id, include_provenance=True)
    assert remaining.height == 1
    assert remaining[PRE_BRONZE_ARTIFACT_ID].to_list() == ["art_us_2"]


def test_pre_bronze_schema_evolution_on_incremental_write(
    isolated_pre_bronze_layer: PreBronzeLayer,
) -> None:
    """Verify that incremental writes dynamically evolve table schema when new columns appear."""
    contract = PreBronzeDataContract(
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        physical_table="pre_bronze.pb_investment_stock_orders",
        sync_strategy=SyncStrategy.INCREMENTAL,
    )

    # 1. Initial write with 2 columns
    df_v1 = pl.DataFrame({"order_id": ["ORD_1"], "symbol": ["TCS"]})
    isolated_pre_bronze_layer.write_incremental(contract, df_v1, artifact_id="art_v1")

    # 2. Subsequent write with an additional column 'exchange' and 'trade_date'
    df_v2 = pl.DataFrame(
        {
            "order_id": ["ORD_2"],
            "symbol": ["INFY"],
            "exchange": ["NSE"],
            "trade_date": ["2026-03-01"],
        }
    )
    isolated_pre_bronze_layer.write_incremental(contract, df_v2, artifact_id="art_v2")

    # Read combined table
    evolved_df = isolated_pre_bronze_layer.read(contract.dataset_id, include_provenance=False)
    assert evolved_df.height == 2
    assert "exchange" in evolved_df.columns
    assert "trade_date" in evolved_df.columns

    # First row should have null for the newly evolved columns
    row_1 = evolved_df.filter(pl.col("order_id") == "ORD_1")
    assert row_1["exchange"][0] is None
    assert row_1["trade_date"][0] is None

    # Second row should have populated values
    row_2 = evolved_df.filter(pl.col("order_id") == "ORD_2")
    assert row_2["exchange"][0] == "NSE"
    assert row_2["trade_date"][0] == "2026-03-01"


def test_pre_bronze_read_api_filtering_and_lazy(
    isolated_pre_bronze_layer: PreBronzeLayer,
) -> None:
    """Verify read filtering by source_id and lazy frame evaluation."""
    contract = PreBronzeDataContract(
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        physical_table="pre_bronze.pb_investment_stock_orders",
        sync_strategy=SyncStrategy.INCREMENTAL,
    )
    df_zerodha = pl.DataFrame({"order_id": ["Z1", "Z2"], "symbol": ["INFY", "TCS"]})
    df_groww = pl.DataFrame({"order_id": ["G1"], "symbol": ["WIPRO"]})

    isolated_pre_bronze_layer.write_incremental(
        contract, df_zerodha, artifact_id="art_z", source_id=SourceId("zerodha")
    )
    isolated_pre_bronze_layer.write_incremental(
        contract, df_groww, artifact_id="art_g", source_id=SourceId("groww")
    )

    # Filter by source_id
    res_z = isolated_pre_bronze_layer.read(contract.dataset_id, source_id="zerodha")
    assert res_z.height == 2
    assert res_z["order_id"].to_list() == ["Z1", "Z2"]

    res_g = isolated_pre_bronze_layer.read(contract.dataset_id, source_id="groww")
    assert res_g.height == 1
    assert res_g["order_id"].to_list() == ["G1"]

    # Test read_lazy returns pl.LazyFrame
    lazy_res = isolated_pre_bronze_layer.read_lazy(contract.dataset_id, source_id="groww")
    assert isinstance(lazy_res, pl.LazyFrame)
    assert lazy_res.collect().height == 1

    # Query nonexistent dataset returns empty DataFrame
    assert isolated_pre_bronze_layer.read("nonexistent_dataset").height == 0


def test_pre_bronze_transaction_boundary_and_rollback(
    isolated_duckdb_manager: DuckDBManager,
) -> None:
    """Verify ACID transaction proof: rollback reverts all uncommitted Pre-Bronze mutations."""
    isolated_duckdb_manager.open()
    isolated_duckdb_manager.ensure_schemas()
    layer = PreBronzeLayer(isolated_duckdb_manager)

    contract = PreBronzeDataContract(
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        physical_table="pre_bronze.pb_household_zcategory",
        sync_strategy=SyncStrategy.FULL_REPLACE,
    )
    df = pl.DataFrame({"Category_ID": [1, 2], "Category_Name": ["A", "B"]})

    # Start explicit transaction
    isolated_duckdb_manager.conn.execute("BEGIN TRANSACTION")

    # Perform write inside transaction
    layer.write_full_replace(contract, df, artifact_id="art_tx_test")
    assert layer.read(contract.dataset_id).height == 2

    # Deliberate rollback
    isolated_duckdb_manager.conn.execute("ROLLBACK")

    # Table must not exist or be empty after rollback
    assert not layer.table_exists(contract)
    assert layer.read(contract.dataset_id).height == 0


def test_pre_bronze_no_independent_commit_invariant() -> None:
    """AST guard: PreBronzeLayer must not invoke COMMIT or BEGIN TRANSACTION."""
    src_file = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "personal_finance_etl"
        / "infrastructure"
        / "warehouse"
        / "pre_bronze.py"
    )
    assert src_file.is_file(), f"PreBronzeLayer source file not found: {src_file}"

    tree = ast.parse(src_file.read_text(encoding="utf-8"), filename=str(src_file))

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check for .commit() method calls
            if isinstance(node.func, ast.Attribute) and node.func.attr == "commit":
                pytest.fail(
                    f"PreBronzeLayer contains prohibited .commit() call at line {node.lineno}"
                )
            # Check for conn.execute("COMMIT") or "BEGIN TRANSACTION"
            if isinstance(node.func, ast.Attribute) and node.func.attr == "execute":
                if node.args and isinstance(node.args[0], ast.Constant):
                    sql_str = str(node.args[0].value).strip().upper()
                    if "COMMIT" in sql_str or "BEGIN TRANSACTION" in sql_str:
                        pytest.fail(
                            f"PreBronzeLayer contains prohibited transaction control SQL at line {node.lineno}: {sql_str}"
                        )
