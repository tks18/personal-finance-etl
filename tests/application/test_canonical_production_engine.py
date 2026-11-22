"""Authoritative tests for the Canonical Production Engine.

Owns
----
- Verification of SOURCE (DIRECT, UNION), PROVIDER, and DERIVED production execution.
- Verification of target schema alignment (required vs optional columns).
- Verification of post-assembly row identity application.
- Verification of strict duplicate/grain enforcement (conflicting vs identical evidence).
- Verification of generic cardinalities (1->1, 1->N, N->1, N->M).
"""

from __future__ import annotations

from collections.abc import Mapping

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.canonical_production import (
    CanonicalProductionEngine,
)
from personal_finance_etl.application.ingestion.canonical_recipes import (
    CanonicalRecipeRegistry,
)
from personal_finance_etl.application.ingestion.route_executor import (
    MaterializedCanonicalFragment,
)
from personal_finance_etl.contracts.canonical_plans import (
    CanonicalDatasetPlan,
    CanonicalFragment,
    CanonicalProducerKind,
    SourceAssemblyMode,
)
from personal_finance_etl.contracts.canonical_recipes import (
    CanonicalProductionError,
    CanonicalRecipeDescriptor,
    ConflictingDuplicateIdentityError,
    IdenticalEvidenceCollisionError,
    IncompatibleFragmentSchemaError,
    MissingRequiredColumnError,
    UndeclaredUnionRouteError,
    UnresolvedRecipeError,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import (
    CanonicalRouteId,
    CanonicalRouteRef,
    SourceBindingId,
)


def _make_fragment(
    binding_id: str,
    route_id: str,
    dataset_id: DatasetId,
    df: pl.DataFrame,
) -> MaterializedCanonicalFragment:
    """Helper creating a MaterializedCanonicalFragment."""
    b_id = SourceBindingId(binding_id)
    r_id = CanonicalRouteId(route_id)
    descriptor = CanonicalFragment(
        fragment_id=f"frag_{binding_id}_{route_id}",
        binding_id=b_id,
        route_id=r_id,
        target_dataset_id=dataset_id,
        row_count=df.height,
    )
    return MaterializedCanonicalFragment(fragment=descriptor, frame=df)


def test_direct_production_single_fragment() -> None:
    """Verify that DIRECT assembly succeeds with 1 fragment, and rejects 0 or >1 fragments."""
    engine = CanonicalProductionEngine()
    plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
    )

    df_frag = pl.DataFrame(
        {
            "UID": ["INR", "USD"],
            "ISO": ["INR", "USD"],
            "SYMBOL": ["₹", "$"],
            "CURRENCY_NAME": ["Indian Rupee", "US Dollar"],
            "S_NO": [1, 2],
            "IS_DEL": [0, 0],
            "MODIFY_DATE": [1700000000, 1700000000],
        }
    )
    frag1 = _make_fragment("curr_binding", "curr_route", DatasetId.HOUSEHOLD_CURRENCY, df_frag)

    # 1. Exactly 1 fragment -> Success
    res_df, res_meta = engine.produce(plan, [frag1])
    assert res_df.height == 2
    assert res_meta.row_count == 2
    assert res_meta.fragment_count == 1
    assert res_meta.validation_passed is True

    # 2. Zero fragments -> Error
    with pytest.raises(CanonicalProductionError) as exc_0:
        engine.produce(plan, [])
    assert "received 0 fragments" in str(exc_0.value)

    # 3. Two fragments -> Error
    with pytest.raises(CanonicalProductionError) as exc_2:
        engine.produce(plan, [frag1, frag1])
    assert "received 2 fragments" in str(exc_2.value)


def test_union_production_explicit_routes_and_order_invariance() -> None:
    """Verify that UNION requires declared routes, rejects undeclared routes, and is order-invariant."""
    engine = CanonicalProductionEngine()
    r1 = CanonicalRouteRef(binding_id=SourceBindingId("b1"), route_id=CanonicalRouteId("r1"))
    r2 = CanonicalRouteRef(binding_id=SourceBindingId("b2"), route_id=CanonicalRouteId("r2"))

    plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.UNION,
        is_required=True,
        is_enabled=True,
        route_refs=(r1, r2),
    )

    df_b1 = pl.DataFrame(
        {
            "UID": ["EUR"],
            "ISO": ["EUR"],
            "SYMBOL": ["€"],
            "CURRENCY_NAME": ["Euro"],
            "S_NO": [3],
            "IS_DEL": [0],
            "MODIFY_DATE": [1700000000],
        }
    )
    df_b2 = pl.DataFrame(
        {
            "UID": ["GBP"],
            "ISO": ["GBP"],
            "SYMBOL": ["£"],
            "CURRENCY_NAME": ["British Pound"],
            "S_NO": [4],
            "IS_DEL": [0],
            "MODIFY_DATE": [1700000000],
        }
    )

    frag1 = _make_fragment("b1", "r1", DatasetId.HOUSEHOLD_CURRENCY, df_b1)
    frag2 = _make_fragment("b2", "r2", DatasetId.HOUSEHOLD_CURRENCY, df_b2)

    # Assembly in order [frag1, frag2]
    res1, _ = engine.produce(plan, [frag1, frag2])
    # Assembly in inverted order [frag2, frag1]
    res2, _ = engine.produce(plan, [frag2, frag1])

    # Resulting order must be deterministic and identical regardless of input sequence
    assert res1.select("ISO").to_series().to_list() == res2.select("ISO").to_series().to_list()
    assert sorted(res1["ISO"].to_list()) == ["EUR", "GBP"]

    # Encountering undeclared route -> Rejection
    frag_unknown = _make_fragment("b3", "r_unregistered", DatasetId.HOUSEHOLD_CURRENCY, df_b1)
    with pytest.raises(UndeclaredUnionRouteError) as exc_info:
        engine.produce(plan, [frag1, frag_unknown])
    assert "r_unregistered" in exc_info.value.undeclared_routes


def test_schema_alignment_required_and_optional_columns() -> None:
    """Verify that required columns must be present and missing optional columns are padded with typed nulls."""
    engine = CanonicalProductionEngine()
    plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
    )

    # 1. Missing required column 'CURRENCY_NAME'
    df_missing_req = pl.DataFrame(
        {
            "UID": ["INR"],
            "ISO": ["INR"],
        }
    )
    frag_missing = _make_fragment("b1", "r1", DatasetId.HOUSEHOLD_CURRENCY, df_missing_req)
    with pytest.raises(MissingRequiredColumnError) as exc_missing:
        engine.produce(plan, [frag_missing])
    assert "CURRENCY_NAME" in exc_missing.value.missing_columns

    # 2. Has all required columns, but missing optional columns (SYMBOL, S_NO, IS_DEL, MODIFY_DATE)
    df_valid_min = pl.DataFrame(
        {
            "UID": ["INR"],
            "ISO": ["INR"],
            "CURRENCY_NAME": ["Rupee"],
        }
    )
    frag_valid = _make_fragment("b1", "r1", DatasetId.HOUSEHOLD_CURRENCY, df_valid_min)
    res_df, _ = engine.produce(plan, [frag_valid])
    assert "SYMBOL" in res_df.columns
    assert "S_NO" in res_df.columns
    assert res_df["SYMBOL"].null_count() == 1
    assert res_df["S_NO"].null_count() == 1

    # 3. Incompatible column type: non-numeric string in S_NO (Int64)
    df_incompat = pl.DataFrame(
        {
            "UID": ["INR"],
            "ISO": ["INR"],
            "CURRENCY_NAME": ["Rupee"],
            "S_NO": ["NOT_A_NUMBER"],
        }
    )
    frag_incompat = _make_fragment("b1", "r1", DatasetId.HOUSEHOLD_CURRENCY, df_incompat)
    with pytest.raises(IncompatibleFragmentSchemaError) as exc_incompat:
        engine.produce(plan, [frag_incompat])
    assert exc_incompat.value.field_name == "S_NO"


def test_conflicting_duplicate_identity_fails() -> None:
    """Verify that duplicate identity keys with conflicting payload values raise ConflictingDuplicateIdentityError."""
    engine = CanonicalProductionEngine()
    plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
    )

    # Two rows with identical UID='INR' but conflicting CURRENCY_NAME
    df_conflict = pl.DataFrame(
        {
            "UID": ["INR", "INR"],
            "ISO": ["INR", "INR"],
            "CURRENCY_NAME": ["Indian Rupee", "Conflicting Rupee Name"],
        }
    )
    frag = _make_fragment("b1", "r1", DatasetId.HOUSEHOLD_CURRENCY, df_conflict)

    with pytest.raises(ConflictingDuplicateIdentityError) as exc_info:
        engine.produce(plan, [frag])

    assert exc_info.value.duplicate_count == 1
    assert exc_info.value.sample_conflicts[0]["key"] == "INR"


def test_identical_evidence_collapse_policy() -> None:
    """Verify that identical evidence duplicates fail by default, but collapse when enabled."""
    engine = CanonicalProductionEngine()
    plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
    )

    # Two rows with identical UID and identical payload columns
    df_identical = pl.DataFrame(
        {
            "UID": ["INR", "INR"],
            "ISO": ["INR", "INR"],
            "CURRENCY_NAME": ["Indian Rupee", "Indian Rupee"],
        }
    )
    frag = _make_fragment("b1", "r1", DatasetId.HOUSEHOLD_CURRENCY, df_identical)

    # 1. allow_identical_collapse=False (default) -> Fails
    with pytest.raises(IdenticalEvidenceCollisionError) as exc_info:
        engine.produce(plan, [frag], allow_identical_collapse=False)
    assert "INR" in exc_info.value.sample_keys

    # 2. allow_identical_collapse=True -> Deduplicates safely
    res_df, _ = engine.produce(plan, [frag], allow_identical_collapse=True)
    assert res_df.height == 1
    assert res_df["ISO"].to_list() == ["INR"]


def test_derived_recipe_execution() -> None:
    """Verify that DERIVED producer executes registered recipe and rejects unregistered names."""
    registry = CanonicalRecipeRegistry()

    def dummy_recipe(inputs: Mapping[DatasetId, pl.DataFrame]) -> pl.DataFrame:
        in_df = inputs[DatasetId.HOUSEHOLD_ASSETS]
        return in_df.select(["UID", "ISO", "CURRENCY_NAME"])

    desc = CanonicalRecipeDescriptor(
        recipe_id="synthesize_currencies",
        version="1.0.0",
        target_dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
        dependencies=(DatasetId.HOUSEHOLD_ASSETS,),
        description="Synthesizes currencies from assets.",
    )
    registry.register(desc, dummy_recipe)

    engine = CanonicalProductionEngine(recipe_registry=registry)
    plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
        producer_kind=CanonicalProducerKind.DERIVED,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
        recipe_name="synthesize_currencies",
    )

    dep_df = pl.DataFrame(
        {
            "UID": ["USD"],
            "ISO": ["USD"],
            "CURRENCY_NAME": ["US Dollar"],
        }
    )
    res_df, res_meta = engine.produce(
        plan,
        dependent_datasets={DatasetId.HOUSEHOLD_ASSETS: dep_df},
    )
    assert res_df.height == 1
    assert res_meta.producer_kind == CanonicalProducerKind.DERIVED

    # Unregistered recipe name -> Error
    unreg_plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
        producer_kind=CanonicalProducerKind.DERIVED,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
        recipe_name="unknown_recipe",
    )
    with pytest.raises(UnresolvedRecipeError):
        engine.produce(unreg_plan)


def test_provider_production() -> None:
    """Verify that PROVIDER producer accepts provider evidence and executes target alignment."""
    engine = CanonicalProductionEngine()
    plan = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
        producer_kind=CanonicalProducerKind.PROVIDER,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
    )

    provider_df = pl.DataFrame(
        {
            "UID": ["JPY"],
            "ISO": ["JPY"],
            "CURRENCY_NAME": ["Japanese Yen"],
        }
    )
    res_df, res_meta = engine.produce(plan, provider_data=provider_df)
    assert res_df.height == 1
    assert res_df["ISO"][0] == "JPY"
    assert res_meta.producer_kind == CanonicalProducerKind.PROVIDER


def test_generic_cardinality_matrix() -> None:
    """Verify generic 1->1, 1->N, N->1, and N->M production without domain branching."""
    engine = CanonicalProductionEngine()

    # 1. 1->1: 1 binding emits 1 fragment to 1 dataset
    plan_1_1 = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.DIRECT,
        is_required=True,
        is_enabled=True,
    )
    f1 = _make_fragment(
        "b1",
        "r1",
        DatasetId.HOUSEHOLD_CURRENCY,
        pl.DataFrame({"UID": ["c1"], "ISO": ["c1"], "CURRENCY_NAME": ["Currency 1"]}),
    )
    out_1_1, _ = engine.produce(plan_1_1, [f1])
    assert out_1_1.height == 1

    # 2. N->1: 2 bindings emit 2 fragments to 1 dataset via UNION
    r1 = CanonicalRouteRef(binding_id=SourceBindingId("b1"), route_id=CanonicalRouteId("r1"))
    r2 = CanonicalRouteRef(binding_id=SourceBindingId("b2"), route_id=CanonicalRouteId("r2"))
    plan_n_1 = CanonicalDatasetPlan(
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
        producer_kind=CanonicalProducerKind.SOURCE,
        assembly_mode=SourceAssemblyMode.UNION,
        is_required=True,
        is_enabled=True,
        route_refs=(r1, r2),
    )
    f2 = _make_fragment(
        "b2",
        "r2",
        DatasetId.HOUSEHOLD_CURRENCY,
        pl.DataFrame({"UID": ["c2"], "ISO": ["c2"], "CURRENCY_NAME": ["Currency 2"]}),
    )
    out_n_1, _ = engine.produce(plan_n_1, [f1, f2])
    assert out_n_1.height == 2
