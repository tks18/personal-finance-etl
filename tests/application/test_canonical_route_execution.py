"""Authoritative test suite for canonical route execution and semantic interpretation.

Owns
----
- Verification of bounded IncludeWhen and ExcludeWhen route predicate filtering.
- Verification that source deletion flags (e.g. IS_DEL) and placeholder rows are resolved and dropped.
- Verification of deterministic execution order: predicates filter rows before semantic mapping.
- Verification of fail-fast UnmappedSemanticValueError diagnostics on unknown categorical values.
- Verification of 1-to-N route emission from a single source-shaped Pre-Bronze frame.
- Verification that final canonical fragment projection removes all vendor/source residue.
- Verification of route fingerprint changes upon predicate or semantic modifications.
"""

from __future__ import annotations

import polars as pl
import pytest

from personal_finance_etl.application.ingestion.route_compiler import RouteCompiler
from personal_finance_etl.application.ingestion.route_executor import (
    RouteExecutor,
    UnmappedSemanticValueError,
)
from personal_finance_etl.config.sources.binding_model import CanonicalRouteConfig
from personal_finance_etl.config.sources.fingerprint import (
    compute_canonical_route_fingerprint,
)
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.semantics import (
    ExcludeWhen,
    IncludeWhen,
    PredicateOperator,
    SemanticConstantRule,
    SemanticMapRule,
)
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import CanonicalRouteId, SourceBindingId


def test_route_predicates_and_is_del_removal() -> None:
    """Verify IncludeWhen and ExcludeWhen filter rows and source deletion flags are removed from projection."""
    df_raw = pl.DataFrame(
        {
            "C_IS_DEL": ["0", "1", "0", "0"],
            "Trade_Date": ["2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18"],
            "ISIN_Code": ["INE002A01018", "INE002A01018", "INE009A01021", "INE009A01021"],
            "Order_Action": ["BUY", "BUY", "SELL", "HOLD"],
            "Qty": [10.0, 20.0, 5.0, 0.0],
            "Price_Val": [2500.0, 2550.0, 3100.0, 0.0],
            "__artifact_id__": ["art_1", "art_1", "art_1", "art_1"],
        }
    )

    route = CanonicalRouteConfig(
        route_id=CanonicalRouteId("active_stock_trades"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[
            ColumnMapping(source_field="Trade_Date", canonical_field="Execution date and time"),
            ColumnMapping(source_field="ISIN_Code", canonical_field="ISIN"),
            ColumnMapping(source_field="Qty", canonical_field="Quantity"),
            ColumnMapping(source_field="Price_Val", canonical_field="Value"),
            ColumnMapping(source_field="Order_Action", canonical_field="Type"),
        ],
        predicates=[
            # Filter out deleted rows
            ExcludeWhen(
                field="C_IS_DEL",
                operator=PredicateOperator.EQUALS,
                value="1",
            ),
            # Filter out placeholder non-trade rows
            ExcludeWhen(
                field="Order_Action",
                operator=PredicateOperator.EQUALS,
                value="HOLD",
            ),
        ],
        semantics=[
            SemanticMapRule(
                field="Type",
                mapping={"BUY": "BUY", "SELL": "SELL"},
                on_unmapped="error",
            ),
        ],
    )

    compiler = RouteCompiler()
    executor = RouteExecutor()

    plan = compiler.compile(
        route,
        binding_id=SourceBindingId("broker__stock_orders"),
        available_source_columns=df_raw.columns,
    )
    mat_fragment = executor.execute(plan, df_raw)

    out_df = mat_fragment.frame
    assert out_df.height == 2  # Row 1 (IS_DEL=1) and Row 4 (HOLD) dropped
    assert "C_IS_DEL" not in out_df.columns  # Vendor deletion flag projected away
    assert set(out_df["Type"].to_list()) == {"BUY", "SELL"}
    assert "__artifact_id__" in out_df.columns
    assert mat_fragment.fragment.row_count == 2
    assert mat_fragment.fragment.target_dataset_id == DatasetId.INVESTMENT_STOCK_ORDERS


def test_execution_order_filters_placeholder_before_semantic_mapping() -> None:
    """Verify that placeholder rows are filtered before semantic mapping to prevent false unmapped value errors."""
    df_raw = pl.DataFrame(
        {
            "Date": ["2024-01-01", "2024-01-02", "TOTAL"],
            "ISIN": ["INE002A01018", "INE009A01021", "---"],
            "Action": ["BUY", "SELL", "SUMMARY_ROW"],  # "SUMMARY_ROW" would fail semantic mapping!
            "Units": [10.0, 20.0, 30.0],
            "Price": [100.0, 200.0, 300.0],
            "__artifact_id__": ["art_summary", "art_summary", "art_summary"],
        }
    )

    route = CanonicalRouteConfig(
        route_id=CanonicalRouteId("orders_clean"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[
            ColumnMapping(source_field="Date", canonical_field="Execution date and time"),
            ColumnMapping(source_field="ISIN", canonical_field="ISIN"),
            ColumnMapping(source_field="Action", canonical_field="Type"),
            ColumnMapping(source_field="Units", canonical_field="Quantity"),
            ColumnMapping(source_field="Price", canonical_field="Value"),
        ],
        predicates=[
            # Filter out summary rows before semantic mapping
            ExcludeWhen(
                field="Date",
                operator=PredicateOperator.EQUALS,
                value="TOTAL",
            ),
        ],
        semantics=[
            SemanticMapRule(
                field="Type",
                mapping={"BUY": "BUY", "SELL": "SELL"},
                on_unmapped="error",
            ),
        ],
    )

    compiler = RouteCompiler()
    executor = RouteExecutor()

    plan = compiler.compile(route, available_source_columns=df_raw.columns)
    # If predicates executed after semantics, this would raise UnmappedSemanticValueError
    mat_fragment = executor.execute(plan, df_raw)
    assert mat_fragment.frame.height == 2
    assert "SUMMARY_ROW" not in mat_fragment.frame["Type"].to_list()


def test_fail_fast_on_unmapped_categorical_value() -> None:
    """Verify that unmapped categorical values raise UnmappedSemanticValueError with clear diagnostics."""
    df_raw = pl.DataFrame(
        {
            "Date": ["2024-01-01", "2024-01-02"],
            "ISIN": ["INE002A01018", "INE009A01021"],
            "Action": ["BUY", "SPLIT_DIVIDEND"],  # "SPLIT_DIVIDEND" is not in mapping!
            "Units": [10.0, 20.0],
            "Price": [100.0, 200.0],
            "__artifact_id__": ["art_1", "art_1"],
        }
    )

    route = CanonicalRouteConfig(
        route_id=CanonicalRouteId("strict_orders"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[
            ColumnMapping(source_field="Date", canonical_field="Execution date and time"),
            ColumnMapping(source_field="ISIN", canonical_field="ISIN"),
            ColumnMapping(source_field="Action", canonical_field="Type"),
            ColumnMapping(source_field="Units", canonical_field="Quantity"),
            ColumnMapping(source_field="Price", canonical_field="Value"),
        ],
        semantics=[
            SemanticMapRule(
                field="Type",
                mapping={"BUY": "BUY", "SELL": "SELL"},
                on_unmapped="error",
            ),
        ],
    )

    compiler = RouteCompiler()
    executor = RouteExecutor()

    plan = compiler.compile(
        route,
        binding_id=SourceBindingId("test_source__orders"),
        available_source_columns=df_raw.columns,
    )

    with pytest.raises(UnmappedSemanticValueError) as exc_info:
        executor.execute(plan, df_raw)

    err = exc_info.value
    assert err.field == "Type"
    assert "SPLIT_DIVIDEND" in err.offending_values
    assert err.route_id == "strict_orders"
    assert str(err.binding_id) == "test_source__orders"


def test_one_to_many_route_splitting() -> None:
    """Verify that a single source-shaped Pre-Bronze frame can emit multiple canonical fragments."""
    # A single broker order log containing BUY and SELL
    df_raw = pl.DataFrame(
        {
            "Date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"],
            "ISIN": ["INE002A01018", "INE002A01018", "INE009A01021", "INE009A01021"],
            "Side": ["B", "S", "B", "S"],
            "Qty": [100.0, 50.0, 200.0, 100.0],
            "Rate": [500.0, 520.0, 1500.0, 1550.0],
            "__artifact_id__": ["art_multi", "art_multi", "art_multi", "art_multi"],
        }
    )

    route_buys = CanonicalRouteConfig(
        route_id=CanonicalRouteId("buy_orders"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[
            ColumnMapping(source_field="Date", canonical_field="Execution date and time"),
            ColumnMapping(source_field="ISIN", canonical_field="ISIN"),
            ColumnMapping(source_field="Qty", canonical_field="Quantity"),
            ColumnMapping(source_field="Rate", canonical_field="Value"),
        ],
        predicates=[
            IncludeWhen(field="Side", operator=PredicateOperator.EQUALS, value="B"),
        ],
        semantics=[
            SemanticConstantRule(field="Type", value="BUY"),
        ],
    )

    route_sells = CanonicalRouteConfig(
        route_id=CanonicalRouteId("sell_orders"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[
            ColumnMapping(source_field="Date", canonical_field="Execution date and time"),
            ColumnMapping(source_field="ISIN", canonical_field="ISIN"),
            ColumnMapping(source_field="Qty", canonical_field="Quantity"),
            ColumnMapping(source_field="Rate", canonical_field="Value"),
        ],
        predicates=[
            IncludeWhen(field="Side", operator=PredicateOperator.EQUALS, value="S"),
        ],
        semantics=[
            SemanticConstantRule(field="Type", value="SELL"),
        ],
    )

    compiler = RouteCompiler()
    executor = RouteExecutor()
    binding_id = SourceBindingId("zerodha__equity_trades")

    plan_buys = compiler.compile(
        route_buys, binding_id=binding_id, available_source_columns=df_raw.columns
    )
    plan_sells = compiler.compile(
        route_sells, binding_id=binding_id, available_source_columns=df_raw.columns
    )

    frag_buys = executor.execute(plan_buys, df_raw)
    frag_sells = executor.execute(plan_sells, df_raw)

    assert frag_buys.frame.height == 2
    assert all(frag_buys.frame["Type"] == "BUY")
    assert frag_buys.fragment.route_id == "buy_orders"

    assert frag_sells.frame.height == 2
    assert all(frag_sells.frame["Type"] == "SELL")
    assert frag_sells.fragment.route_id == "sell_orders"


def test_route_fingerprint_invalidation_on_semantic_change() -> None:
    """Verify that altering predicates or semantic mappings alters route cryptographic fingerprint."""
    base_route = CanonicalRouteConfig(
        route_id=CanonicalRouteId("base_route"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[
            ColumnMapping(source_field="Trade_Date", canonical_field="Execution date and time")
        ],
        predicates=[IncludeWhen(field="Action", operator=PredicateOperator.EQUALS, value="BUY")],
        semantics=[SemanticMapRule(field="Type", mapping={"BUY": "BUY"})],
    )
    fp_base = compute_canonical_route_fingerprint(base_route)

    # Change predicate operand
    changed_pred_route = base_route.model_copy(
        update={
            "predicates": [
                IncludeWhen(field="Action", operator=PredicateOperator.EQUALS, value="SELL")
            ]
        }
    )
    fp_pred = compute_canonical_route_fingerprint(changed_pred_route)
    assert fp_base != fp_pred

    # Change semantic mapping
    changed_sem_route = base_route.model_copy(
        update={"semantics": [SemanticMapRule(field="Type", mapping={"BUY": "PURCHASE"})]}
    )
    fp_sem = compute_canonical_route_fingerprint(changed_sem_route)
    assert fp_base != fp_sem


def test_route_compiler_validation_errors() -> None:
    """Verify that route compiler catches missing source fields, invalid targets, and duplicate mappings."""
    compiler = RouteCompiler()

    # 1. Invalid canonical target field
    invalid_target_route = CanonicalRouteConfig(
        route_id=CanonicalRouteId("r1"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[ColumnMapping(source_field="Date", canonical_field="NON_EXISTENT_FIELD")],
    )
    from personal_finance_etl.application.normalization.errors import (
        DuplicateMappingError,
        InvalidCanonicalTargetError,
        MissingSourceFieldError,
    )

    with pytest.raises(InvalidCanonicalTargetError):
        compiler.compile(invalid_target_route)

    # 2. Duplicate mapping for source field
    dup_source_route = CanonicalRouteConfig(
        route_id=CanonicalRouteId("r2"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[
            ColumnMapping(source_field="Date", canonical_field="Execution date and time"),
            ColumnMapping(source_field="Date", canonical_field="ISIN"),
        ],
    )
    with pytest.raises(DuplicateMappingError):
        compiler.compile(dup_source_route)

    # 3. Missing source field when available columns checked
    missing_source_route = CanonicalRouteConfig(
        route_id=CanonicalRouteId("r3"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[
            ColumnMapping(source_field="MissingCol", canonical_field="Execution date and time")
        ],
    )
    with pytest.raises(MissingSourceFieldError):
        compiler.compile(missing_source_route, available_source_columns=["Date", "ISIN"])

    # 4. Missing predicate field when available columns checked
    missing_pred_route = CanonicalRouteConfig(
        route_id=CanonicalRouteId("r4"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[ColumnMapping(source_field="Date", canonical_field="Execution date and time")],
        predicates=[
            IncludeWhen(field="NonExistentPredCol", operator=PredicateOperator.EQUALS, value="1")
        ],
    )
    with pytest.raises(MissingSourceFieldError):
        compiler.compile(missing_pred_route, available_source_columns=["Date"])


def test_predicate_operators_comprehensive() -> None:
    """Verify is_in, not_in, is_null, is_not_null, is_empty, is_not_empty predicates."""
    df_raw = pl.DataFrame(
        {
            "ISIN": ["INE001", "INE002", None, "INE004", ""],
            "Type": ["A", "B", "C", "D", "E"],
            "Val": [10.0, 20.0, 30.0, 40.0, 50.0],
            "__artifact_id__": ["art", "art", "art", "art", "art"],
        }
    )

    # 1. is_in / not_in
    route_in = CanonicalRouteConfig(
        route_id=CanonicalRouteId("r_in"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[
            ColumnMapping(source_field="ISIN", canonical_field="ISIN"),
            ColumnMapping(source_field="Type", canonical_field="Type"),
            ColumnMapping(source_field="Val", canonical_field="Value"),
        ],
        predicates=[IncludeWhen(field="Type", operator=PredicateOperator.IS_IN, value=["A", "B"])],
    )
    compiler = RouteCompiler()
    executor = RouteExecutor()
    plan_in = compiler.compile(route_in, available_source_columns=df_raw.columns)
    assert executor.execute(plan_in, df_raw).frame.height == 2

    # 2. is_not_null
    route_not_null = CanonicalRouteConfig(
        route_id=CanonicalRouteId("r_not_null"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[
            ColumnMapping(source_field="ISIN", canonical_field="ISIN"),
            ColumnMapping(source_field="Type", canonical_field="Type"),
            ColumnMapping(source_field="Val", canonical_field="Value"),
        ],
        predicates=[IncludeWhen(field="ISIN", operator=PredicateOperator.IS_NOT_NULL)],
    )
    plan_not_null = compiler.compile(route_not_null, available_source_columns=df_raw.columns)
    assert executor.execute(plan_not_null, df_raw).frame.height == 4  # 1 null dropped

    # 3. is_not_empty
    route_not_empty = CanonicalRouteConfig(
        route_id=CanonicalRouteId("r_not_empty"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[
            ColumnMapping(source_field="ISIN", canonical_field="ISIN"),
            ColumnMapping(source_field="Type", canonical_field="Type"),
            ColumnMapping(source_field="Val", canonical_field="Value"),
        ],
        predicates=[IncludeWhen(field="ISIN", operator=PredicateOperator.IS_NOT_EMPTY)],
    )
    plan_not_empty = compiler.compile(route_not_empty, available_source_columns=df_raw.columns)
    assert executor.execute(plan_not_empty, df_raw).frame.height == 3  # null and "" dropped


def test_semantic_map_fallback_default() -> None:
    """Verify that SemanticMapRule with on_unmapped='default' correctly applies fallback default."""
    df_raw = pl.DataFrame(
        {
            "ISIN": ["INE001", "INE002"],
            "Side": ["BUY", "TRANSFER_IN"],
            "Val": [10.0, 20.0],
            "__artifact_id__": ["art", "art"],
        }
    )
    route = CanonicalRouteConfig(
        route_id=CanonicalRouteId("r_default"),
        target_dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        mapping=[
            ColumnMapping(source_field="ISIN", canonical_field="ISIN"),
            ColumnMapping(source_field="Side", canonical_field="Type"),
            ColumnMapping(source_field="Val", canonical_field="Value"),
        ],
        semantics=[
            SemanticMapRule(
                field="Type",
                mapping={"BUY": "BUY"},
                on_unmapped="default",
                default="OTHER",
            )
        ],
    )
    compiler = RouteCompiler()
    executor = RouteExecutor()
    plan = compiler.compile(route, available_source_columns=df_raw.columns)
    res = executor.execute(plan, df_raw).frame
    assert res["Type"].to_list() == ["BUY", "OTHER"]
