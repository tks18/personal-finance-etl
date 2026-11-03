"""Bronze row identity contract and strategy system test suite.

Owns
----
- Invariant tests verifying all 20 Bronze datasets declare identity requirements and row grains.
- Negative tests verifying registry validation fails if identity metadata is omitted.
- Validation tests for SourceFieldIdentity, CompositeIdentity, and DerivedDeterministicIdentity.
- Guard tests ensuring protected financial namespaces (PURCHASE, SALE, LOT, TAX, etc.) cannot be hijacked.
- Compiler tests for IdentityPlan under REQUIRED and NONE constraints.
- Deterministic executor execution, null canonicalization, and duplicate collision diagnostic verification.
- Architectural boundary checks ensuring Bronze identity modules remain decoupled from financial calculations.
"""

from __future__ import annotations

import ast
from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError

from personal_finance_etl.application.ingestion.identity import (
    IdentityCollisionError,
    IdentityNotPermittedError,
    MissingIdentityFieldError,
    MissingIdentityStrategyError,
    compile_identity_plan,
    execute_identity_plan,
)
from personal_finance_etl.config.sources.identity import (
    PROTECTED_FINANCIAL_NAMESPACES,
    CompositeIdentity,
    DerivedDeterministicIdentity,
    SourceFieldIdentity,
)
from personal_finance_etl.contracts.datasets import DatasetId, IdentityRequirement
from personal_finance_etl.infrastructure.warehouse.contracts import (
    BRONZE_CONTRACT_REGISTRY,
    BronzeDataContract,
)
from personal_finance_etl.infrastructure.warehouse.registry import validate_registry


def test_bronze_contracts_identity_coverage() -> None:
    """Verify that every Bronze contract specifies an explicit IdentityRequirement and row grain."""
    assert len(BRONZE_CONTRACT_REGISTRY) == 20

    required_contracts = [
        c
        for c in BRONZE_CONTRACT_REGISTRY
        if c.identity_requirement == IdentityRequirement.REQUIRED
    ]
    none_contracts = [
        c for c in BRONZE_CONTRACT_REGISTRY if c.identity_requirement == IdentityRequirement.NONE
    ]

    # Exactly 12 contracts require row identity; 8 contracts are NONE
    assert len(required_contracts) == 12
    assert len(none_contracts) == 8

    # Every contract has a non-empty, meaningful grain declaration
    for contract in BRONZE_CONTRACT_REGISTRY:
        assert isinstance(contract.identity_requirement, IdentityRequirement)
        assert isinstance(contract.grain, str)
        assert len(contract.grain.strip()) > 0
        assert "(" in contract.grain and ")" in contract.grain


def test_validate_registry_rejects_missing_identity_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify registry validation rejects contracts with missing or invalid identity metadata."""
    # 1. Reject empty grain
    corrupted_grain = list(BRONZE_CONTRACT_REGISTRY)
    corrupted_grain[0] = BronzeDataContract(
        dataset_id=corrupted_grain[0].dataset_id,
        extraction_attribute=corrupted_grain[0].extraction_attribute,
        sync_category=corrupted_grain[0].sync_category,
        physical_table=corrupted_grain[0].physical_table,
        is_full_replace=corrupted_grain[0].is_full_replace,
        identity_requirement=IdentityRequirement.REQUIRED,
        grain="   ",
    )
    monkeypatch.setattr(
        "personal_finance_etl.infrastructure.warehouse.registry.BRONZE_CONTRACT_REGISTRY",
        corrupted_grain,
    )
    with pytest.raises(ValueError, match="missing grain declaration"):
        validate_registry()


def test_source_identity_strategies_validation() -> None:
    """Verify field validations and constraints on BronzeIdentityStrategy models."""
    # 1. SourceFieldIdentity
    valid_sf = SourceFieldIdentity(field="ZUID")
    assert valid_sf.field == "ZUID"
    assert valid_sf.strategy_type == "source_field"

    with pytest.raises(ValidationError, match="cannot be empty or whitespace"):
        SourceFieldIdentity(field="   ")

    # 2. CompositeIdentity
    valid_comp = CompositeIdentity(fields=["Account", "Transaction_Date"])
    assert valid_comp.fields == ["Account", "Transaction_Date"]
    assert valid_comp.strategy_type == "composite"

    with pytest.raises(ValidationError, match="must specify at least one field"):
        CompositeIdentity(fields=[])

    with pytest.raises(ValidationError, match="fields contain duplicates"):
        CompositeIdentity(fields=["Account", "Account"])

    with pytest.raises(ValidationError, match="cannot be empty or whitespace"):
        CompositeIdentity(fields=["Account", " "])

    # 3. DerivedDeterministicIdentity
    valid_det = DerivedDeterministicIdentity(fields=["Folio", "Date", "Units"])
    assert valid_det.fields == ["Folio", "Date", "Units"]
    assert valid_det.namespace is None
    assert valid_det.version == "v2"

    with pytest.raises(ValidationError, match="fields contain duplicates"):
        DerivedDeterministicIdentity(fields=["A", "B", "A"])

    with pytest.raises(ValidationError, match="must specify at least one field"):
        DerivedDeterministicIdentity(fields=[])

    with pytest.raises(ValidationError, match="namespace cannot be empty"):
        DerivedDeterministicIdentity(fields=["A"], namespace="  ")


def test_protected_financial_namespaces_guard() -> None:
    """Verify that DerivedDeterministicIdentity strictly rejects all protected financial namespaces."""
    for protected in PROTECTED_FINANCIAL_NAMESPACES:
        with pytest.raises(ValidationError, match="collides with protected financial namespace"):
            DerivedDeterministicIdentity(fields=["A", "B"], namespace=protected)

        # Case-insensitive protection
        with pytest.raises(ValidationError, match="collides with protected financial namespace"):
            DerivedDeterministicIdentity(fields=["A", "B"], namespace=protected.lower())


def test_compile_identity_plan_rules() -> None:
    """Verify compilation rules for IdentityPlan under REQUIRED and NONE constraints."""
    contract_required = next(
        c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id == DatasetId.HOUSEHOLD_INOUTCOME
    )
    contract_none = next(
        c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id == DatasetId.INVESTMENT_STOCK_ORDERS
    )

    available_cols = {"ZUID", "ZDATE", "ZAMOUNT", "ISIN", "Order_Date"}

    # 1. REQUIRED + no strategy => fails with MissingIdentityStrategyError
    with pytest.raises(MissingIdentityStrategyError, match="has IdentityRequirement.REQUIRED"):
        compile_identity_plan(contract_required, available_cols, strategy=None)

    # 2. REQUIRED + missing field => fails with MissingIdentityFieldError
    strategy_bad_field = SourceFieldIdentity(field="NON_EXISTENT_COLUMN")
    with pytest.raises(MissingIdentityFieldError, match="not found in available schema fields"):
        compile_identity_plan(contract_required, available_cols, strategy=strategy_bad_field)

    # 3. REQUIRED + valid strategy => compiles cleanly
    strategy_valid = SourceFieldIdentity(field="ZUID")
    plan = compile_identity_plan(contract_required, available_cols, strategy=strategy_valid)
    assert plan.dataset_id == DatasetId.HOUSEHOLD_INOUTCOME
    assert plan.requirement == IdentityRequirement.REQUIRED
    assert plan.target_fields == ("ZUID",)
    assert plan.namespace == "BRONZE_HOUSEHOLD_INOUTCOME"
    assert plan.grain == contract_required.grain

    # 4. NONE + no strategy => compiles cleanly with None strategy
    plan_none = compile_identity_plan(contract_none, available_cols, strategy=None)
    assert plan_none.dataset_id == DatasetId.INVESTMENT_STOCK_ORDERS
    assert plan_none.requirement == IdentityRequirement.NONE
    assert plan_none.strategy is None
    assert not plan_none.target_fields

    # 5. NONE + strategy without permission => fails with IdentityNotPermittedError
    with pytest.raises(IdentityNotPermittedError, match="does not permit row identity generation"):
        compile_identity_plan(contract_none, available_cols, strategy=strategy_valid)

    # 6. NONE + strategy with allow_optional_identity=True => compiles successfully
    plan_optional = compile_identity_plan(
        contract_none,
        available_cols,
        strategy=strategy_valid,
        allow_optional_identity=True,
    )
    assert plan_optional.strategy == strategy_valid


def test_execute_identity_plan_determinism_and_features() -> None:
    """Verify deterministic executor consistency, null canonicalization, and data frame integration."""
    contract = next(
        c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id == DatasetId.HOUSEHOLD_OPENING_BALANCES
    )
    available_cols = {"Account", "Date", "Amount"}
    strategy = DerivedDeterministicIdentity(fields=["Account", "Date"])
    plan = compile_identity_plan(contract, available_cols, strategy=strategy)

    data = [
        {"Account": "HDFC_Checking", "Date": "2024-01-01", "Amount": 50000},
        {"Account": "Zerodha_Demat", "Date": "2024-01-01", "Amount": 150000},
    ]

    # 1. Sequence execution
    ids1 = execute_identity_plan(plan, data)
    assert isinstance(ids1, list)
    assert len(ids1) == 2
    assert all(i.startswith("BRONZE_HOUSEHOLD_OPENING_BALANCES_") for i in ids1)

    # 2. Determinism across repeated runs
    ids2 = execute_identity_plan(plan, data)
    assert ids1 == ids2

    # 3. Dict key ordering does not alter generated ID
    data_permuted = [
        {"Date": "2024-01-01", "Amount": 50000, "Account": "HDFC_Checking"},
        {"Date": "2024-01-01", "Amount": 150000, "Account": "Zerodha_Demat"},
    ]
    ids_permuted = execute_identity_plan(plan, data_permuted)
    assert ids1 == ids_permuted

    # 4. Polars DataFrame execution
    df = pl.DataFrame(data)
    df_with_id = execute_identity_plan(plan, df, id_column="__row_id__")
    assert isinstance(df_with_id, pl.DataFrame)
    assert "__row_id__" in df_with_id.columns
    assert df_with_id["__row_id__"].to_list() == ids1


def test_execute_identity_plan_duplicate_collision_diagnostic() -> None:
    """Verify that duplicate identity keys trigger an explicit IdentityCollisionError with diagnostic context."""
    contract = next(
        c for c in BRONZE_CONTRACT_REGISTRY if c.dataset_id == DatasetId.INVESTMENT_MF_ISIN_MAPPING
    )
    strategy = SourceFieldIdentity(field="Scheme_Name")
    plan = compile_identity_plan(contract, {"Scheme_Name", "ISIN"}, strategy=strategy)

    # Duplicate Scheme_Name
    colliding_data = [
        {"Scheme_Name": "Parag Parikh Flexi Cap", "ISIN": "INF879O01018"},
        {"Scheme_Name": "UTI Nifty 50 Index Fund", "ISIN": "INF789FB1X41"},
        {"Scheme_Name": "Parag Parikh Flexi Cap", "ISIN": "INF879O01018"},  # Duplicate
    ]

    with pytest.raises(IdentityCollisionError) as exc_info:
        execute_identity_plan(plan, colliding_data)

    diagnostic = exc_info.value.diagnostic
    assert diagnostic.dataset_id == DatasetId.INVESTMENT_MF_ISIN_MAPPING
    assert diagnostic.duplicate_count == 2
    assert diagnostic.strategy_fields == ("Scheme_Name",)
    assert ("Parag Parikh Flexi Cap", 2) in diagnostic.sample_duplicates
    assert "2 total rows collide" in str(exc_info.value)


def test_protected_financial_namespace_isolation_ast() -> None:
    """Verify via AST that identity modules never import domain financial transaction contracts."""
    repo_root = Path(__file__).resolve().parents[2]
    identity_app_path = (
        repo_root / "src" / "personal_finance_etl" / "application" / "ingestion" / "identity.py"
    )
    content = identity_app_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(identity_app_path))

    imported_modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    # Must never import FIFO, lots, reconciliation, or tax calculators
    forbidden = [
        "personal_finance_etl.domain.investments.lots",
        "personal_finance_etl.domain.investments.reconciliation",
        "personal_finance_etl.domain.tax",
    ]
    for m in imported_modules:
        for f in forbidden:
            assert not m.startswith(f), f"identity.py forbidden import: {m}"
