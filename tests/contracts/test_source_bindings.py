"""Tests for canonical contract and source-binding foundation vocabulary.

Owns
----
- Unit tests for SourceBindingId, CanonicalRouteId, and CanonicalRouteRef.
- Unit tests for HouseholdCategoryKind, HouseholdTransactionKind, and InvestmentAction.
- Negative tests proving canonical enums reject numeric and vendor-specific codes.
- Immutability and structural tests for CanonicalFragment, SourceBindingPlan,
  CanonicalDatasetPlan, and CanonicalProductionPlan.
- Invariant tests for candidate canonical Bronze DatasetIds.

Does not own
------------
- Pydantic configuration model tests (owned by tests.config.test_source_bindings_config).
- Runtime pipeline execution (owned by tests.application).
"""

from __future__ import annotations

import pytest

from personal_finance_etl.config.sources.change_detection import ChangeDetectionPolicy
from personal_finance_etl.config.sources.selectors import CsvSelector
from personal_finance_etl.contracts.canonical_plans import (
    CanonicalDatasetPlan,
    CanonicalFragment,
    CanonicalProducerKind,
    CanonicalProductionPlan,
    SourceAssemblyMode,
    SourceBindingPlan,
)
from personal_finance_etl.contracts.canonical_semantics import (
    HouseholdCategoryKind,
    HouseholdTransactionKind,
    InvestmentAction,
)
from personal_finance_etl.contracts.datasets import (
    BRONZE_DATASET_ORIGIN_MAP,
    CANDIDATE_BRONZE_DATASETS,
    DatasetId,
)
from personal_finance_etl.contracts.sources import (
    CanonicalRouteId,
    CanonicalRouteRef,
    ProviderType,
    SourceBindingId,
    SourceId,
    validate_canonical_route_id,
    validate_source_binding_id,
)


def test_source_binding_id_validation_and_equality() -> None:
    """Verify validate_source_binding_id accepts clean IDs and rejects invalid values."""
    valid_id = validate_source_binding_id("household_sqlite_categories")
    assert valid_id == "household_sqlite_categories"
    assert isinstance(valid_id, str)

    # Rejection of empty or whitespace
    with pytest.raises(ValueError, match="empty or whitespace"):
        validate_source_binding_id("")
    with pytest.raises(ValueError, match="empty or whitespace"):
        validate_source_binding_id("   ")

    # Rejection of path separators
    with pytest.raises(ValueError, match="path separators"):
        validate_source_binding_id("data/binding_1")
    with pytest.raises(ValueError, match="path separators"):
        validate_source_binding_id("data\\binding_1")

    # Rejection of non-string
    with pytest.raises(TypeError, match="must be a string"):
        validate_source_binding_id(123)


def test_canonical_route_id_validation_and_equality() -> None:
    """Verify validate_canonical_route_id accepts clean IDs and rejects invalid values."""
    valid_id = validate_canonical_route_id("route_categories")
    assert valid_id == "route_categories"
    assert isinstance(valid_id, str)

    # Rejection of empty or whitespace
    with pytest.raises(ValueError, match="empty or whitespace"):
        validate_canonical_route_id("")
    with pytest.raises(ValueError, match="empty or whitespace"):
        validate_canonical_route_id("   ")

    # Rejection of path separators
    with pytest.raises(ValueError, match="path separators"):
        validate_canonical_route_id("routes/category")
    with pytest.raises(ValueError, match="path separators"):
        validate_canonical_route_id("routes\\category")

    # Rejection of non-string
    with pytest.raises(TypeError, match="must be a string"):
        validate_canonical_route_id(456)


def test_canonical_route_ref_formatting_and_parsing() -> None:
    """Verify CanonicalRouteRef format round-tripping and error handling."""
    binding_id = SourceBindingId("bind_orders")
    route_id = CanonicalRouteId("route_buy")

    ref = CanonicalRouteRef(binding_id=binding_id, route_id=route_id)
    assert ref.to_string() == "bind_orders:route_buy"

    # from_string round trip
    parsed = CanonicalRouteRef.from_string("bind_orders:route_buy")
    assert parsed == ref
    assert parsed.binding_id == binding_id
    assert parsed.route_id == route_id

    # Malformed strings
    with pytest.raises(ValueError, match="Expected 'binding_id:route_id'"):
        CanonicalRouteRef.from_string("no_colon")
    with pytest.raises(ValueError, match="Expected 'binding_id:route_id'"):
        CanonicalRouteRef.from_string(":empty_binding")
    with pytest.raises(ValueError, match="Expected 'binding_id:route_id'"):
        CanonicalRouteRef.from_string("empty_route:")
    with pytest.raises(TypeError, match="must be a str"):
        CanonicalRouteRef.from_string(999)


def test_household_category_kind_values_and_rejections() -> None:
    """Verify HouseholdCategoryKind contains canonical values and rejects aliases."""
    assert HouseholdCategoryKind.INCOME.value == "income"
    assert HouseholdCategoryKind.EXPENSE.value == "expense"
    assert len(HouseholdCategoryKind) == 2

    # Rejection of numeric source codes
    with pytest.raises(ValueError):
        HouseholdCategoryKind(0)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        HouseholdCategoryKind(1)  # type: ignore[arg-type]
    # Rejection of non-canonical strings
    with pytest.raises(ValueError):
        HouseholdCategoryKind("INCOME")
    with pytest.raises(ValueError):
        HouseholdCategoryKind("ZCATEGORY")


def test_household_transaction_kind_values_and_rejections() -> None:
    """Verify HouseholdTransactionKind contains canonical values and rejects source codes."""
    assert HouseholdTransactionKind.INCOME.value == "income"
    assert HouseholdTransactionKind.EXPENSE.value == "expense"
    assert HouseholdTransactionKind.TRANSFER_OUT.value == "transfer_out"
    assert HouseholdTransactionKind.TRANSFER_IN.value == "transfer_in"
    assert HouseholdTransactionKind.TRANSFER.value == "transfer"
    assert len(HouseholdTransactionKind) == 5

    # Rejection of numeric source transaction type codes (0=income, 1=expense, 3=transfer_out, 4=transfer_in)
    for code in (0, 1, 3, 4):
        with pytest.raises(ValueError):
            HouseholdTransactionKind(code)  # type: ignore[arg-type]
    # Rejection of vendor table name
    with pytest.raises(ValueError):
        HouseholdTransactionKind("INOUTCOME")


def test_investment_action_values_and_rejections() -> None:
    """Verify InvestmentAction contains canonical values and rejects broker strings."""
    assert InvestmentAction.BUY.value == "buy"
    assert InvestmentAction.SELL.value == "sell"
    assert InvestmentAction.SPLIT.value == "split"
    assert InvestmentAction.BONUS.value == "bonus"
    assert InvestmentAction.DIVIDEND_REINVEST.value == "dividend_reinvest"
    assert InvestmentAction.RECONCILIATION.value == "reconciliation"
    assert len(InvestmentAction) == 6

    # Rejection of uppercase broker / vendor strings
    with pytest.raises(ValueError):
        InvestmentAction("BUY")
    with pytest.raises(ValueError):
        InvestmentAction("PURCHASE")
    with pytest.raises(ValueError):
        InvestmentAction("REDEEM")
    with pytest.raises(ValueError):
        InvestmentAction("SELL_STOCK")


def test_canonical_plans_immutability_and_slots() -> None:
    """Verify planning contracts are immutable slotted dataclasses."""
    frag = CanonicalFragment(
        fragment_id="frag_1",
        binding_id=SourceBindingId("b1"),
        route_id=CanonicalRouteId("r1"),
        target_dataset_id=DatasetId.HOUSEHOLD_TRANSACTIONS,
        row_count=100,
    )
    assert frag.fragment_id == "frag_1"
    assert frag.row_count == 100

    # Frozen invariant
    with pytest.raises(AttributeError):
        frag.row_count = 200  # type: ignore[misc]

    binding_plan = SourceBindingPlan(
        binding_id=SourceBindingId("b1"),
        source_id=SourceId("s1"),
        provider_type=ProviderType.CSV,
        location="data/orders.csv",
        selector=CsvSelector(file_pattern="orders.csv"),
        change_detection=ChangeDetectionPolicy(),
        enabled=True,
        route_ids=(CanonicalRouteId("r1"),),
    )
    assert binding_plan.enabled is True
    with pytest.raises(AttributeError):
        binding_plan.enabled = False  # type: ignore[misc]

    ds_plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.INVESTMENT_TRANSACTIONS,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.UNION,
        is_required=True,
        is_enabled=True,
        route_refs=(CanonicalRouteRef(SourceBindingId("b1"), CanonicalRouteId("r1")),),
    )
    assert ds_plan.assembly_mode == SourceAssemblyMode.UNION
    with pytest.raises(AttributeError):
        ds_plan.is_required = False  # type: ignore[misc]

    prod_plan = CanonicalProductionPlan(
        dataset_plans=(ds_plan,),
        binding_plans=(binding_plan,),
    )
    assert prod_plan.get_dataset_plan(DatasetId.INVESTMENT_TRANSACTIONS) is ds_plan
    assert prod_plan.get_dataset_plan("investment_transactions") is ds_plan
    assert prod_plan.get_dataset_plan("unknown_dataset") is None

    assert prod_plan.get_binding_plan(SourceBindingId("b1")) is binding_plan
    assert prod_plan.get_binding_plan("b1") is binding_plan
    assert prod_plan.get_binding_plan("unknown_binding") is None


def test_candidate_canonical_bronze_dataset_ids_registration() -> None:
    """Verify candidate Bronze DatasetIds are registered in DatasetId and CANDIDATE_BRONZE_DATASETS."""
    expected_candidates = {
        DatasetId.HOUSEHOLD_CATEGORIES,
        DatasetId.HOUSEHOLD_ASSET_CATEGORIES,
        DatasetId.HOUSEHOLD_ACCOUNTS,
        DatasetId.HOUSEHOLD_ACCOUNT_BALANCES,
        DatasetId.HOUSEHOLD_TRANSACTIONS,
        DatasetId.INVESTMENT_TRANSACTIONS,
        DatasetId.INVESTMENT_HOLDINGS,
        DatasetId.INVESTMENT_INSTRUMENTS,
        DatasetId.INVESTMENT_BENCHMARKS,
        DatasetId.INVESTMENT_INSTRUMENT_BENCHMARK_ASSIGNMENTS,
        DatasetId.MARKET_PROVIDER_SYMBOL_MAPPINGS,
        DatasetId.MARKET_FX_RATES,
        DatasetId.MARKET_BENCHMARK_PRICES,
        DatasetId.MARKET_INSTRUMENT_PRICES,
        DatasetId.COMMON_CURRENCIES,
    }

    assert CANDIDATE_BRONZE_DATASETS == expected_candidates
    # Candidate datasets are not yet in BRONZE_DATASET_ORIGIN_MAP
    for cand in expected_candidates:
        assert cand not in BRONZE_DATASET_ORIGIN_MAP
    # Exactly 20 active Bronze datasets in BRONZE_DATASET_ORIGIN_MAP
    assert len(BRONZE_DATASET_ORIGIN_MAP) == 20
