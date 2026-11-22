"""Authoritative unit and integration tests for canonical household route interpretation and production.

Owns
----
- Unit tests verifying declarative route configuration for all six household datasets.
- Vectorized execution tests proving deletion filtering, categorical enum mapping, and column projection.
- Error tests proving unknown categorical types fail fast with UnmappedSemanticValueError.
- End-to-end production tests through CanonicalProductionEngine with Gate-2 Pandera validation.
"""

from __future__ import annotations

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.canonical_production import (
    CanonicalProductionEngine,
)
from personal_finance_etl.application.ingestion.route_compiler import RouteCompiler
from personal_finance_etl.application.ingestion.route_executor import (
    RouteExecutor,
    UnmappedSemanticValueError,
)
from personal_finance_etl.config.sources.household_routes import (
    CANONICAL_HOUSEHOLD_ROUTE_ID,
    build_household_canonical_production,
    build_household_canonical_route,
    is_household_transitional_dataset,
)
from personal_finance_etl.contracts.canonical_plans import (
    CanonicalDatasetPlan,
    CanonicalProducerKind,
    SourceAssemblyMode,
)
from personal_finance_etl.contracts.canonical_semantics import (
    HouseholdCategoryKind,
    HouseholdTransactionKind,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceBindingId
from personal_finance_etl.infrastructure.warehouse.registry import (
    get_bronze_contract_by_dataset_id,
)


def test_is_household_transitional_dataset() -> None:
    """Verify inspection predicate identifies exactly the six legacy household datasets."""
    expected = {
        DatasetId.HOUSEHOLD_ZCATEGORY,
        DatasetId.HOUSEHOLD_ASSET_GROUP,
        DatasetId.HOUSEHOLD_ASSETS,
        DatasetId.HOUSEHOLD_CURRENCY,
        DatasetId.HOUSEHOLD_INOUTCOME,
        DatasetId.HOUSEHOLD_OPENING_BALANCES,
    }
    for ds in expected:
        assert is_household_transitional_dataset(ds) is True
    assert is_household_transitional_dataset(DatasetId.INVESTMENT_MF_ORDERS) is False
    assert is_household_transitional_dataset(DatasetId.HOUSEHOLD_CATEGORIES) is False


def test_household_categories_route_execution() -> None:
    """Verify categories route filters deleted rows, maps TYPE, normalizes parent, and passes Gate 2."""
    route = build_household_canonical_route(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert route is not None
    assert route.target_dataset_id == DatasetId.HOUSEHOLD_CATEGORIES
    assert route.route_id == CANONICAL_HOUSEHOLD_ROUTE_ID

    compiler = RouteCompiler()
    executor = RouteExecutor()
    engine = CanonicalProductionEngine()

    raw_data = pl.DataFrame(
        {
            "uid": ["cat_1", "cat_2", "cat_del"],
            "NAME": ["Salary", "Groceries", "Old Deleted"],
            "TYPE": [0, 1, 1],
            "pUid": ["", "cat_parent", ""],
            "C_IS_DEL": [0, 0, 1],
            "ID": [1, 2, 3],
            "artifact_id": ["art_1", "art_1", "art_1"],
        }
    )

    plan = compiler.compile(route, available_source_columns=raw_data.columns)
    fragment = executor.execute(plan, raw_data)

    assert fragment.frame.height == 2
    assert "C_IS_DEL" not in fragment.frame.columns
    assert "ID" not in fragment.frame.columns
    assert fragment.frame["category_id"].to_list() == ["cat_1", "cat_2"]
    assert fragment.frame["category_kind"].to_list() == [
        HouseholdCategoryKind.INCOME.value,
        HouseholdCategoryKind.EXPENSE.value,
    ]
    assert fragment.frame["parent_category_id"].to_list() == [None, "cat_parent"]

    # Production & Gate 2 Pandera validation
    contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_CATEGORIES)
    assert contract is not None
    ds_plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_CATEGORIES,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
    )
    admitted_df, prod_res = engine.produce(ds_plan, [fragment], contract=contract)
    assert admitted_df.height == 2
    assert prod_res.validation_passed is True
    assert prod_res.applied_identity is True


def test_household_asset_categories_route_execution() -> None:
    """Verify asset categories route filters deleted rows and projects canonical fields."""
    route = build_household_canonical_route(DatasetId.HOUSEHOLD_ASSET_GROUP)
    assert route is not None
    assert route.target_dataset_id == DatasetId.HOUSEHOLD_ASSET_CATEGORIES

    compiler = RouteCompiler()
    executor = RouteExecutor()
    engine = CanonicalProductionEngine()

    raw_data = pl.DataFrame(
        {
            "uid": ["ag_1", "ag_2", "ag_del"],
            "ACC_GROUP_NAME": ["Bank Accounts", "Credit Cards", "Deleted Group"],
            "IS_DEL": [0, 0, 1],
            "DEVICE_ID": [10, 10, 10],
            "artifact_id": ["art_1", "art_1", "art_1"],
        }
    )

    plan = compiler.compile(route, available_source_columns=raw_data.columns)
    fragment = executor.execute(plan, raw_data)

    assert fragment.frame.height == 2
    assert fragment.frame["asset_category_id"].to_list() == ["ag_1", "ag_2"]
    assert fragment.frame["asset_category_name"].to_list() == ["Bank Accounts", "Credit Cards"]

    contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ASSET_CATEGORIES)
    assert contract is not None
    ds_plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_ASSET_CATEGORIES,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
    )
    admitted_df, prod_res = engine.produce(ds_plan, [fragment], contract=contract)
    assert admitted_df.height == 2
    assert prod_res.validation_passed is True
    assert prod_res.applied_identity is True


def test_household_accounts_route_execution() -> None:
    """Verify accounts route filters deleted rows, projects canonical fields, and drops vendor metadata."""
    route = build_household_canonical_route(DatasetId.HOUSEHOLD_ASSETS)
    assert route is not None
    assert route.target_dataset_id == DatasetId.HOUSEHOLD_ACCOUNTS

    compiler = RouteCompiler()
    executor = RouteExecutor()
    engine = CanonicalProductionEngine()

    raw_data = pl.DataFrame(
        {
            "uid": ["acc_1", "acc_2", "acc_del"],
            "NIC_NAME": ["Checking", "Savings", "Closed"],
            "groupUid": ["ag_1", "ag_1", "ag_1"],
            "currencyUid": ["curr_1", "curr_1", "curr_1"],
            "ZDATA1": ["Main Bank", "High Yield", ""],
            "ZDATA2": ["", "Emergency Fund", "Gone"],
            "ZDATA": ["0", "0", "1"],
            "APP_PACKAGE": ["com.bank", "com.bank", "com.bank"],
            "SMS_TEL": ["123", "456", "789"],
            "artifact_id": ["art_1", "art_1", "art_1"],
        }
    )

    plan = compiler.compile(route, available_source_columns=raw_data.columns)
    fragment = executor.execute(plan, raw_data)

    assert fragment.frame.height == 2
    assert "APP_PACKAGE" not in fragment.frame.columns
    assert "SMS_TEL" not in fragment.frame.columns
    assert fragment.frame["asset_id"].to_list() == ["acc_1", "acc_2"]
    assert fragment.frame["description"].to_list() == ["Main Bank", "High Yield"]
    assert fragment.frame["notes"].to_list() == [None, "Emergency Fund"]

    contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ACCOUNTS)
    assert contract is not None
    ds_plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_ACCOUNTS,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
    )
    admitted_df, prod_res = engine.produce(ds_plan, [fragment], contract=contract)
    assert admitted_df.height == 2
    assert prod_res.validation_passed is True
    assert prod_res.applied_identity is True


def test_common_currencies_route_execution() -> None:
    """Verify currencies route filters deleted rows and standardizes common currency master."""
    route = build_household_canonical_route(DatasetId.HOUSEHOLD_CURRENCY)
    assert route is not None
    assert route.target_dataset_id == DatasetId.COMMON_CURRENCIES

    compiler = RouteCompiler()
    executor = RouteExecutor()
    engine = CanonicalProductionEngine()

    raw_data = pl.DataFrame(
        {
            "uid": ["inr", "usd", "del_curr"],
            "NAME": ["Indian Rupee", "US Dollar", "Dead Coin"],
            "ISO": ["INR", "USD", "DEAD"],
            "SYMBOL": ["₹", "$", ""],
            "IS_DEL": [0, 0, 1],
            "IS_MAIN_CURRENCY": [1, 0, 0],
            "artifact_id": ["art_1", "art_1", "art_1"],
        }
    )

    plan = compiler.compile(route, available_source_columns=raw_data.columns)
    fragment = executor.execute(plan, raw_data)

    assert fragment.frame.height == 2
    assert "IS_MAIN_CURRENCY" not in fragment.frame.columns
    assert fragment.frame["currency_id"].to_list() == ["inr", "usd"]
    assert fragment.frame["iso_code"].to_list() == ["INR", "USD"]
    assert fragment.frame["symbol"].to_list() == ["₹", "$"]

    contract = get_bronze_contract_by_dataset_id(DatasetId.COMMON_CURRENCIES)
    assert contract is not None
    ds_plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.COMMON_CURRENCIES,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
    )
    admitted_df, prod_res = engine.produce(ds_plan, [fragment], contract=contract)
    assert admitted_df.height == 2
    assert prod_res.validation_passed is True
    assert prod_res.applied_identity is True


def test_household_transactions_route_execution() -> None:
    """Verify transactions route maps transaction codes, casts numerics, and validates Gate 2."""
    route = build_household_canonical_route(DatasetId.HOUSEHOLD_INOUTCOME)
    assert route is not None
    assert route.target_dataset_id == DatasetId.HOUSEHOLD_TRANSACTIONS

    compiler = RouteCompiler()
    executor = RouteExecutor()
    engine = CanonicalProductionEngine()

    raw_data = pl.DataFrame(
        {
            "uid": ["tx_1", "tx_2", "tx_3", "tx_4", "tx_del"],
            "WDATE": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
            "wtime": ["10:00:00", "11:00:00", "", "14:00:00", "15:00:00"],
            "assetUid": ["acc_1", "acc_1", "acc_1", "acc_2", "acc_1"],
            "toAssetUid": ["", "", "acc_2", "", ""],
            "ctgUid": ["cat_salary", "cat_food", "", "", "cat_food"],
            "currencyUid": ["inr", "inr", "inr", "inr", "inr"],
            "ZMONEY": ["50000.0", "1200.5", "5000.0", "5000.0", "999.0"],
            "IN_ZMONEY": ["50000.0", "1200.5", "5000.0", "5000.0", "999.0"],
            "AMOUNT_ACCOUNT": ["50000.0", "1200.5", "5000.0", "5000.0", "999.0"],
            "ZCONTENT": ["Monthly pay", "Dinner", "Transfer", "Transfer in", "Old"],
            "txUidTrans": ["", "", "tx_3_pair", "tx_3_pair", ""],
            "DO_TYPE": ["0", "1", "3", "4", "1"],
            "IS_DEL": [0, 0, 0, 0, 1],
            "lat": [12.34, 12.34, 12.34, 12.34, 12.34],
            "lng": [56.78, 56.78, 56.78, 56.78, 56.78],
            "artifact_id": ["art_1"] * 5,
        }
    )

    plan = compiler.compile(route, available_source_columns=raw_data.columns)
    fragment = executor.execute(plan, raw_data)

    assert fragment.frame.height == 4
    assert "lat" not in fragment.frame.columns
    assert "lng" not in fragment.frame.columns
    assert fragment.frame["transaction_kind"].to_list() == [
        HouseholdTransactionKind.INCOME.value,
        HouseholdTransactionKind.EXPENSE.value,
        HouseholdTransactionKind.TRANSFER_OUT.value,
        HouseholdTransactionKind.TRANSFER_IN.value,
    ]
    assert fragment.frame["base_amount"].to_list() == [50000.0, 1200.5, 5000.0, 5000.0]
    assert fragment.frame["transaction_time"].to_list() == [
        "10:00:00",
        "11:00:00",
        None,
        "14:00:00",
    ]

    contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_TRANSACTIONS)
    assert contract is not None
    ds_plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_TRANSACTIONS,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
    )
    admitted_df, prod_res = engine.produce(ds_plan, [fragment], contract=contract)
    assert admitted_df.height == 4
    assert prod_res.validation_passed is True
    assert prod_res.applied_identity is True


def test_household_transactions_unmapped_code_fails_fast() -> None:
    """Verify route execution raises UnmappedSemanticValueError on unknown TRANSACTION_TYPE code."""
    route = build_household_canonical_route(DatasetId.HOUSEHOLD_INOUTCOME)
    assert route is not None

    compiler = RouteCompiler()
    executor = RouteExecutor()

    raw_data = pl.DataFrame(
        {
            "uid": ["tx_alien"],
            "WDATE": ["2026-01-01"],
            "wtime": ["10:00:00"],
            "assetUid": ["acc_1"],
            "toAssetUid": [""],
            "ctgUid": ["cat_1"],
            "currencyUid": ["inr"],
            "ZMONEY": ["100.0"],
            "IN_ZMONEY": ["100.0"],
            "AMOUNT_ACCOUNT": ["100.0"],
            "ZCONTENT": ["Alien"],
            "txUidTrans": [""],
            "DO_TYPE": ["999"],  # Unknown alien transaction code
            "IS_DEL": [0],
            "artifact_id": ["art_1"],
        }
    )

    plan = compiler.compile(route, available_source_columns=raw_data.columns)
    with pytest.raises(UnmappedSemanticValueError) as exc_info:
        executor.execute(plan, raw_data)

    assert "999" in str(exc_info.value)
    assert exc_info.value.field == "transaction_kind"


def test_household_opening_balances_route_execution() -> None:
    """Verify opening balances route standardizes CoreData CSV into canonical schema."""
    route = build_household_canonical_route(DatasetId.HOUSEHOLD_OPENING_BALANCES)
    assert route is not None
    assert route.target_dataset_id == DatasetId.HOUSEHOLD_ACCOUNT_BALANCES

    compiler = RouteCompiler()
    executor = RouteExecutor()
    engine = CanonicalProductionEngine()

    raw_data = pl.DataFrame(
        {
            "Z_PK": [1, 2],
            "ZTXDATESTR": ["2026-01-01 00:00:00", "2026-01-01 00:00:00"],
            "ZASSETUID": ["acc_1", "acc_2"],
            "ZCURRENCYUID": ["inr", "usd"],
            "ZAMOUNT": [100000.0, 5000.0],
            "ZAMOUNTACCOUNT": [100000.0, 5000.0],
            "Z_ENT": [1, 1],
            "Z_OPT": [1, 1],
            "ZISDEL": [0, 0],
            "artifact_id": ["art_1", "art_1"],
        }
    )

    plan = compiler.compile(route, available_source_columns=raw_data.columns)
    fragment = executor.execute(plan, raw_data)

    assert fragment.frame.height == 2
    assert "Z_ENT" not in fragment.frame.columns
    assert fragment.frame["opening_balance_id"].to_list() == ["1", "2"]
    assert fragment.frame["balance_date"].to_list() == [
        "2026-01-01 00:00:00",
        "2026-01-01 00:00:00",
    ]
    assert fragment.frame["asset_id"].to_list() == ["acc_1", "acc_2"]
    assert fragment.frame["opening_amount"].to_list() == [100000.0, 5000.0]

    contract = get_bronze_contract_by_dataset_id(DatasetId.HOUSEHOLD_ACCOUNT_BALANCES)
    assert contract is not None
    ds_plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_ACCOUNT_BALANCES,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
    )
    admitted_df, prod_res = engine.produce(ds_plan, [fragment], contract=contract)
    assert admitted_df.height == 2
    assert prod_res.validation_passed is True
    assert prod_res.applied_identity is True


def test_build_household_canonical_production() -> None:
    """Verify production declarations connect to parent bindings and canonical route IDs."""
    b_id = SourceBindingId("household_db__household_zcategory")
    prod = build_household_canonical_production(b_id, DatasetId.HOUSEHOLD_ZCATEGORY)
    assert prod is not None
    assert prod.dataset_id == DatasetId.HOUSEHOLD_CATEGORIES
    assert prod.producer_kind == CanonicalProducerKind.SOURCE
    assert prod.assembly_mode == SourceAssemblyMode.DIRECT
    assert len(prod.source_routes) == 1
    assert prod.source_routes[0].binding_id == b_id
    assert prod.source_routes[0].route_id == CANONICAL_HOUSEHOLD_ROUTE_ID
