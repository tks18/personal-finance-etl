"""Frozen migration matrix asserting 1:1 compatibility compilation for all baseline datasets.

Owns
----
- Verification of the complete migration matrix for all 17 baseline physical evidence datasets:
  legacy dataset config -> SourceBindingId -> CanonicalRouteId -> transitional DatasetId -> DIRECT production.
- Serves as the immutable input contract for physical planning migration in Phase 048.

Removal Owner
-------------
- Phase 055 (when legacy SourceDatasetConfig is decommissioned).
"""

from __future__ import annotations

from personal_finance_etl.config.sources.compiler import (
    DEFAULT_COMPATIBILITY_ROUTE_ID,
    derive_source_binding_id,
)
from personal_finance_etl.config.sources.loader import get_shan_baseline_source_configuration
from personal_finance_etl.contracts.canonical_plans import (
    CanonicalProducerKind,
    SourceAssemblyMode,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import CanonicalRouteId, SourceBindingId, SourceId

# Authoritative 17-element migration contract for Phase 048
EXPECTED_BASELINE_MIGRATION_MATRIX: tuple[tuple[str, str, str], ...] = (
    ("household_db", "household_zcategory", "household_db__household_zcategory"),
    ("household_db", "household_asset_group", "household_db__household_asset_group"),
    ("household_db", "household_assets", "household_db__household_assets"),
    ("household_db", "household_currency", "household_db__household_currency"),
    ("household_db", "household_inoutcome", "household_db__household_inoutcome"),
    ("mf_isin_csv", "investment_mf_isin_mapping", "mf_isin_csv__investment_mf_isin_mapping"),
    (
        "benchmark_mapping_csv",
        "investment_benchmark_mapping",
        "benchmark_mapping_csv__investment_benchmark_mapping",
    ),
    (
        "opening_balance_csv",
        "household_opening_balances",
        "opening_balance_csv__household_opening_balances",
    ),
    (
        "benchmark_master_csv",
        "investment_benchmark_master",
        "benchmark_master_csv__investment_benchmark_master",
    ),
    (
        "macro_parameters_csv",
        "investment_macro_parameters",
        "macro_parameters_csv__investment_macro_parameters",
    ),
    (
        "currency_mapping_csv",
        "market_currency_mapping",
        "currency_mapping_csv__market_currency_mapping",
    ),
    ("column_master_csv", "common_column_master", "column_master_csv__common_column_master"),
    ("mf_holdings_excel", "market_mf_holdings", "mf_holdings_excel__market_mf_holdings"),
    ("mf_orders_excel", "investment_mf_orders", "mf_orders_excel__investment_mf_orders"),
    ("stock_pl_excel", "market_stock_holdings", "stock_pl_excel__market_stock_holdings"),
    (
        "stock_orders_excel",
        "investment_stock_orders",
        "stock_orders_excel__investment_stock_orders",
    ),
    (
        "us_stock_transactions",
        "investment_us_stock_transactions",
        "us_stock_transactions__investment_us_stock_transactions",
    ),
)


def test_migration_matrix_completeness_and_exact_count() -> None:
    """Verify that exactly 17 dataset bindings exist in the baseline migration matrix."""
    assert len(EXPECTED_BASELINE_MIGRATION_MATRIX) == 17
    distinct_bindings = {entry[2] for entry in EXPECTED_BASELINE_MIGRATION_MATRIX}
    assert len(distinct_bindings) == 17


def test_compiled_baseline_matches_migration_matrix_contract() -> None:
    """Verify that compiling baseline configuration matches the exact frozen migration matrix."""
    config = get_shan_baseline_source_configuration()
    topology = config.compile_binding_topology()

    assert len(topology.bindings) == 17
    assert len(topology.productions) == 17

    for source_id_str, dataset_id_str, expected_b_id_str in EXPECTED_BASELINE_MIGRATION_MATRIX:
        target_dataset_id = DatasetId(dataset_id_str)
        expected_b_id = SourceBindingId(expected_b_id_str)

        # 1. Verify derive_source_binding_id produces the exact expected ID
        derived_id = derive_source_binding_id(SourceId(source_id_str), target_dataset_id)
        assert derived_id == expected_b_id

        # 2. Verify compiled binding exists with matching attributes
        binding = topology.get_binding(expected_b_id)
        assert binding is not None, f"Binding '{expected_b_id}' not found in compiled topology"
        assert str(binding.source_id) == source_id_str
        expected_enabled = dataset_id_str != "common_column_master"
        assert binding.enabled is expected_enabled

        # 3. Verify single DIRECT route
        assert len(binding.routes) == 1
        route = binding.routes[0]
        assert route.route_id == DEFAULT_COMPATIBILITY_ROUTE_ID
        assert route.route_id == CanonicalRouteId("direct")
        assert route.target_dataset_id == target_dataset_id
        assert route.enabled is expected_enabled

        # 4. Verify DIRECT production rule targeting same transitional DatasetId
        prod = topology.get_production(target_dataset_id)
        assert prod is not None, f"Production rule for '{target_dataset_id}' not found"
        assert prod.dataset_id == target_dataset_id
        assert prod.producer_kind == CanonicalProducerKind.SOURCE
        assert prod.assembly_mode == SourceAssemblyMode.DIRECT
        assert prod.enabled is expected_enabled
        assert len(prod.source_routes) == 1
        assert prod.source_routes[0].binding_id == expected_b_id
        assert prod.source_routes[0].route_id == CanonicalRouteId("direct")
        assert prod.source_routes[0].to_string() == f"{expected_b_id_str}:direct"
