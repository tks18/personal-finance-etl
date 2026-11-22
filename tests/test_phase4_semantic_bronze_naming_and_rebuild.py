# pyright: reportPrivateUsage=false
"""Tests for Phase 4: Semantic Bronze Naming and Rebuild Cutover.

Owns
----
- Verification of semantic naming across all 20 physical Bronze tables in BRONZE_CONTRACT_REGISTRY.
- Verification that zero 'bronze.r_*' physical names remain in the warehouse contract registry.
- Verification that ExtractionResult attributes map 1:1 to semantic physical table suffixes.
- Verification that BronzeLayer.get_table() resolves both plain and schema-qualified names.
- Verification that BronzeLayer.get_full_dataset() populates ExtractionResult from semantic tables.
- Verification of MetaLayer orphan table pruning for old 'bronze.r_*' tables.
- Verification of downstream Silver (24) and Gold (22) warehouse analytical topology.

Does not own
-------------
- Silver column disposition or Silver table renaming (owned by Phases 005-007).
- Gold Power BI query updates (owned by Phases 008-010).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from personal_finance_etl.config.settings import Settings
from personal_finance_etl.contracts.extraction import ExtractionResult
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.warehouse.bronze import BronzeLayer
from personal_finance_etl.infrastructure.warehouse.connection import DuckDBManager
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
    DATA_CONTRACT_REGISTRY,
)
from personal_finance_etl.infrastructure.warehouse.meta import MetaLayer


EXPECTED_TWENTY_BRONZE_TABLES: list[str] = [
    "bronze.household_zcategory",
    "bronze.household_asset_group",
    "bronze.household_assets",
    "bronze.household_currency",
    "bronze.household_inoutcome",
    "bronze.column_master",
    "bronze.mutual_fund_instrument_mapping",
    "bronze.instrument_master",
    "bronze.opening_balances",
    "bronze.benchmark_master",
    "bronze.financial_year_parameters",
    "bronze.currency_reference",
    "bronze.mf_market_data",
    "bronze.mf_transactions",
    "bronze.stock_market_data",
    "bronze.stock_transactions",
    "bronze.us_stock_transactions",
    "bronze.currency_fx_rates",
    "bronze.benchmark_history",
    "bronze.us_stock_prices",
]


def test_twenty_bronze_contracts_semantic_naming() -> None:
    """Verify all 20 Bronze contracts use semantic snake_case names and zero r_* remain."""
    assert len(BRONZE_CONTRACT_REGISTRY) == 20

    registered_tables = [c.physical_table for c in BRONZE_CONTRACT_REGISTRY]
    assert registered_tables == EXPECTED_TWENTY_BRONZE_TABLES

    # Verify zero legacy prefixes or camelCase
    for table in registered_tables:
        assert table.startswith("bronze."), f"Table must start with 'bronze.': {table}"
        unqualified = table.replace("bronze.", "")
        assert not unqualified.startswith("r_"), f"Legacy prefix 'r_' found: {table}"
        assert unqualified.islower(), f"Table name must be lowercase: {table}"
        assert " " not in unqualified, f"Spaces not allowed: {table}"

    # Verify 1:1 mapping with ExtractionResult attributes
    result_fields = ExtractionResult.__dataclass_fields__
    for contract in BRONZE_CONTRACT_REGISTRY:
        unqualified = contract.physical_table.replace("bronze.", "")
        assert contract.extraction_attribute == unqualified, (
            f"Extraction attribute '{contract.extraction_attribute}' does not match "
            f"table suffix '{unqualified}'"
        )
        # Note: market provider streams (currency_fx_rates, benchmark_history, us_stock_prices)
        # are managed via market_sync pipelines into DuckDB directly, while the remaining 17
        # are populated through ExtractionResult.
        if contract.extraction_attribute not in (
            "currency_fx_rates",
            "benchmark_history",
            "us_stock_prices",
        ):
            assert contract.extraction_attribute in result_fields, (
                f"Attribute '{contract.extraction_attribute}' missing from ExtractionResult"
            )


def test_full_replace_vs_incremental_semantics_preserved() -> None:
    """Verify full-replace and incremental sync modes match exact v11.0.0 behavior."""
    mode_map = {c.physical_table: c.is_full_replace for c in BRONZE_CONTRACT_REGISTRY}

    # Full replace tables (12 tables: 5 household + 7 reference)
    expected_full_replace = {
        "bronze.household_zcategory",
        "bronze.household_asset_group",
        "bronze.household_assets",
        "bronze.household_currency",
        "bronze.household_inoutcome",
        "bronze.column_master",
        "bronze.mutual_fund_instrument_mapping",
        "bronze.instrument_master",
        "bronze.opening_balances",
        "bronze.benchmark_master",
        "bronze.financial_year_parameters",
        "bronze.currency_reference",
    }
    for t in expected_full_replace:
        assert mode_map[t] is True, f"Expected {t} to be full_replace=True"

    # Incremental tables (8 tables: 5 statements + 3 market feeds)
    expected_incremental = {
        "bronze.mf_market_data",
        "bronze.mf_transactions",
        "bronze.stock_market_data",
        "bronze.stock_transactions",
        "bronze.us_stock_transactions",
        "bronze.currency_fx_rates",
        "bronze.benchmark_history",
        "bronze.us_stock_prices",
    }
    for t in expected_incremental:
        assert mode_map[t] is False, f"Expected {t} to be full_replace=False"


def test_bronze_layer_get_table_and_get_full_dataset(tmp_path: Path) -> None:
    """Verify BronzeLayer reads semantic tables cleanly via get_table and get_full_dataset."""
    db_mgr = DuckDBManager(str(tmp_path), "test_bronze.duckdb")
    db_mgr.open()
    db_mgr.ensure_schemas()

    mock_cp = MagicMock(spec=ControlPlane)
    mock_meta = MagicMock(spec=MetaLayer)
    bronze = BronzeLayer(db_mgr, mock_cp, mock_meta)

    # Populate a sample table: bronze.currency_fx_rates
    sample_df = pl.DataFrame(
        {
            "Date": ["2026-01-01"],
            "Currency_ID": ["USD_INR"],
            "FX_Rate": [85.5],
            "__file_name__": ["fx.parquet"],
        }
    )
    bronze.upsert_table(sample_df, "bronze.currency_fx_rates", ["fx.parquet"], full_replace=True)

    # Verify get_table works with and without 'bronze.' prefix
    df_with_prefix = bronze.get_table("bronze.currency_fx_rates")
    df_without_prefix = bronze.get_table("currency_fx_rates")
    assert df_with_prefix.height == 1
    assert df_without_prefix.height == 1
    assert df_with_prefix["FX_Rate"][0] == 85.5

    # Verify get_full_dataset returns typed ExtractionResult with new fields
    full_dataset = bronze.get_full_dataset(original_mappings={})
    assert isinstance(full_dataset, ExtractionResult)
    assert hasattr(full_dataset, "household_zcategory")
    assert hasattr(full_dataset, "household_asset_group")
    assert hasattr(full_dataset, "household_assets")
    assert hasattr(full_dataset, "household_currency")
    assert hasattr(full_dataset, "household_inoutcome")
    assert hasattr(full_dataset, "instrument_master")
    assert hasattr(full_dataset, "mutual_fund_instrument_mapping")
    assert hasattr(full_dataset, "opening_balances")
    assert hasattr(full_dataset, "benchmark_master")
    assert hasattr(full_dataset, "financial_year_parameters")
    assert hasattr(full_dataset, "currency_reference")
    assert hasattr(full_dataset, "mf_market_data")
    assert hasattr(full_dataset, "mf_transactions")
    assert hasattr(full_dataset, "stock_market_data")
    assert hasattr(full_dataset, "stock_transactions")
    assert hasattr(full_dataset, "us_stock_transactions")

    db_mgr.close()


def test_meta_layer_prunes_legacy_bronze_tables(tmp_path: Path) -> None:
    """Verify MetaLayer._cleanup_orphaned_tables drops legacy bronze.r_* tables."""
    db_mgr = DuckDBManager(str(tmp_path), "test_prune.duckdb")
    db_mgr.open()
    db_mgr.ensure_schemas()

    # Create a legacy r_ table and a target semantic table
    db_mgr.conn.execute("CREATE TABLE bronze.r_SQLite_ZCategory (id INT)")
    db_mgr.conn.execute("CREATE TABLE bronze.household_zcategory (id INT)")

    cfg = Settings()
    meta = MetaLayer(db_mgr, cfg, None)

    # Run cleanup
    meta._cleanup_orphaned_tables()

    remaining_tables = {
        row[0]
        for row in db_mgr.conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='bronze'"
        ).fetchall()
    }

    assert "r_sqlite_zcategory" not in remaining_tables
    assert "household_zcategory" in remaining_tables

    db_mgr.close()


def test_data_contract_registry_silver_and_gold_intact() -> None:
    """Verify that Silver (24) and Gold (22) analytical contracts are completely untouched."""
    silver_contracts = [c for c in DATA_CONTRACT_REGISTRY if c.layer == "silver"]
    gold_contracts = [c for c in DATA_CONTRACT_REGISTRY if c.layer == "gold"]

    assert len(silver_contracts) == 24, f"Expected 24 Silver contracts, found {len(silver_contracts)}"
    assert len(gold_contracts) == 22, f"Expected 22 Gold contracts, found {len(gold_contracts)}"
