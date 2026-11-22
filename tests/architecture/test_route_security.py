"""Architecture and security verification for canonical route interpretation.

Owns
----
- Verification that route configuration and execution strictly reject arbitrary Python code, eval, exec, SQL, or callbacks.
- Verification that only the closed, approved set of PredicateOperator enums is accepted.
- Verification that Pydantic models forbid unknown extra fields.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from personal_finance_etl.config.sources.binding_model import CanonicalRouteConfig
from personal_finance_etl.config.sources.semantics import (
    ExcludeWhen,
    IncludeWhen,
    PredicateOperator,
    SemanticConstantRule,
    SemanticMapRule,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import CanonicalRouteId


def test_route_models_forbid_extra_fields() -> None:
    """Verify that semantic route models forbid extra arbitrary configuration fields."""
    with pytest.raises(ValidationError):
        IncludeWhen(
            field="action",
            operator=PredicateOperator.EQUALS,
            value="BUY",
            arbitrary_code="import os; os.system('echo bad')",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        ExcludeWhen(
            field="IS_DEL",
            operator=PredicateOperator.EQUALS,
            value="1",
            custom_filter=lambda x: True,  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        SemanticMapRule(
            field="action",
            mapping={"BUY": "PURCHASE"},
            python_callback="eval",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        SemanticConstantRule(
            field="CURRENCY",
            value="INR",
            sql_clause="WHERE 1=1",  # type: ignore[call-arg]
        )


def test_route_config_rejects_arbitrary_callables() -> None:
    """Verify that route predicates and semantics reject non-serializable callables."""
    with pytest.raises(ValidationError):
        CanonicalRouteConfig(
            route_id=CanonicalRouteId("direct"),
            target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
            predicates=[lambda row: True],  # type: ignore[list-item]
        )


def test_predicate_operators_are_closed_enum() -> None:
    """Verify that only the approved 8 operators exist in PredicateOperator."""
    approved_operators = {
        "equals",
        "not_equals",
        "is_in",
        "not_in",
        "is_null",
        "is_not_null",
        "is_empty",
        "is_not_empty",
    }
    actual_operators = {op.value for op in PredicateOperator}
    assert actual_operators == approved_operators

    with pytest.raises(ValueError):
        IncludeWhen(
            field="Action",
            operator="eval_regex",  # type: ignore[arg-type]
            value=".*",
        )


def test_route_source_code_has_no_eval_or_exec() -> None:
    """Verify that route compiler, executor, and models contain zero eval or exec calls."""
    target_files = [
        Path("src/personal_finance_etl/config/sources/semantics.py"),
        Path("src/personal_finance_etl/application/ingestion/route_compiler.py"),
        Path("src/personal_finance_etl/application/ingestion/route_executor.py"),
    ]

    for f_path in target_files:
        assert f_path.is_file(), f"Target file missing: {f_path}"
        tree = ast.parse(f_path.read_text(encoding="utf-8"), filename=str(f_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("eval", "exec", "compile"), (
                    f"Forbidden execution call '{node.func.id}' found in {f_path} at line {node.lineno}!"
                )
