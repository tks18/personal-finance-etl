"""Tests for NormalizationCompiler non-I/O execution planning and validation.

Owns
----
- Unit tests verifying canonical target field validation against CANONICAL_BRONZE_FIELDS.
- Negative tests for InvalidCanonicalTargetError with candidate field suggestions.
- Negative tests for DuplicateMappingError on source and canonical collisions.
- Negative tests for MissingSourceFieldError when incoming source schema lacks mapped columns.
- Deterministic rule ordering tests proving stable compilation regardless of configuration order.
- Expected output fields and provenance fields assembly tests.
"""

from __future__ import annotations

import pytest

from personal_finance_etl.application.normalization.compiler import (
    NormalizationCompiler,
)
from personal_finance_etl.application.normalization.errors import (
    DuplicateMappingError,
    InvalidCanonicalTargetError,
    MissingSourceFieldError,
)
from personal_finance_etl.config.sources.mapping import ColumnMapping
from personal_finance_etl.config.sources.model import SourceDatasetConfig
from personal_finance_etl.config.sources.normalization import (
    CastRule,
    ConstantRule,
    DefaultRule,
    NormalizationRule,
    NormalizeCaseRule,
    NormalizeNullRule,
    ParseDateRule,
    TrimRule,
)
from personal_finance_etl.config.sources.selectors import SqliteSelector
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId


def test_compiler_valid_dataset_plan() -> None:
    """Verify compiler produces a valid NormalizationPlan for valid mappings and rules."""
    config = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
        selector=SqliteSelector(table_name="ASSETGROUP"),
        mapping=[
            ColumnMapping(source_field="Z_PK", canonical_field="UID"),
            ColumnMapping(source_field="ZNAME", canonical_field="ASSET_GROUP"),
        ],
        normalization=[
            TrimRule(field="ZNAME", mode="both"),
            NormalizeCaseRule(field="ASSET_GROUP", case="upper"),
            ConstantRule(field="IS_DEL", value="0"),
        ],
    )

    compiler = NormalizationCompiler()
    plan = compiler.compile(config)

    assert plan.dataset_id == DatasetId.HOUSEHOLD_ASSET_GROUP
    assert plan.source_id == SourceId("household_db")
    assert plan.column_mapping == {"Z_PK": "UID", "ZNAME": "ASSET_GROUP"}
    assert len(plan.pre_rename_rules) == 1
    assert isinstance(plan.pre_rename_rules[0], TrimRule)
    assert len(plan.post_rename_rules) == 2
    assert "UID" in plan.expected_output_fields
    assert "ASSET_GROUP" in plan.expected_output_fields
    assert "IS_DEL" in plan.expected_output_fields
    assert "artifact_id" in plan.provenance_fields


def test_compiler_invalid_canonical_target_raises() -> None:
    """Verify compiler raises InvalidCanonicalTargetError when target field is unknown."""
    config = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
        selector=SqliteSelector(table_name="ASSETGROUP"),
        mapping=[
            ColumnMapping(source_field="Z_PK", canonical_field="UNKNOWN_TARGET_COLUMN"),
        ],
    )

    compiler = NormalizationCompiler()
    with pytest.raises(InvalidCanonicalTargetError) as exc_info:
        compiler.compile(config)

    err = exc_info.value
    assert err.target_field == "UNKNOWN_TARGET_COLUMN"
    assert "ASSET_GROUP" in err.permitted_fields
    assert err.dataset_id == str(DatasetId.HOUSEHOLD_ASSET_GROUP)


def test_compiler_duplicate_source_field_raises() -> None:
    """Verify compiler raises DuplicateMappingError when source column is mapped twice."""
    config = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
        selector=SqliteSelector(table_name="ASSETGROUP"),
        mapping=[
            ColumnMapping(source_field="Z_PK", canonical_field="UID"),
            ColumnMapping(source_field="Z_PK", canonical_field="ORDER_NUM"),
        ],
    )

    compiler = NormalizationCompiler()
    with pytest.raises(DuplicateMappingError) as exc_info:
        compiler.compile(config)

    err = exc_info.value
    assert err.duplicate_field == "Z_PK"
    assert err.is_source_field is True


def test_compiler_duplicate_canonical_target_raises() -> None:
    """Verify compiler raises DuplicateMappingError when canonical column is targeted twice."""
    config = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
        selector=SqliteSelector(table_name="ASSETGROUP"),
        mapping=[
            ColumnMapping(source_field="Z_PK", canonical_field="UID"),
            ColumnMapping(source_field="Z_OTHER", canonical_field="UID"),
        ],
    )

    compiler = NormalizationCompiler()
    with pytest.raises(DuplicateMappingError) as exc_info:
        compiler.compile(config)

    err = exc_info.value
    assert err.duplicate_field == "UID"
    assert err.is_source_field is False


def test_compiler_missing_source_field_raises() -> None:
    """Verify compiler raises MissingSourceFieldError when available columns lack mapped source."""
    config = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ASSET_GROUP,
        selector=SqliteSelector(table_name="ASSETGROUP"),
        mapping=[
            ColumnMapping(source_field="Z_PK", canonical_field="UID"),
            ColumnMapping(source_field="ZNAME", canonical_field="ASSET_GROUP"),
        ],
    )

    compiler = NormalizationCompiler()
    with pytest.raises(MissingSourceFieldError) as exc_info:
        compiler.compile(config, available_source_columns=["Z_PK", "SOME_OTHER_COL"])

    err = exc_info.value
    assert err.missing_field == "ZNAME"
    assert "Z_PK" in err.available_fields


def test_compiler_deterministic_rule_ordering() -> None:
    """Verify compiler enforces deterministic operation ordering regardless of authoring order."""
    # Authored in reverse or shuffled order
    shuffled_rules: list[NormalizationRule] = [
        ConstantRule(field="IS_DEL", value="0"),
        ParseDateRule(field="TRANSACTION_DATE", format="%Y-%m-%d"),
        TrimRule(field="ZNAME", mode="both"),
        NormalizeCaseRule(field="CONTENT", case="upper"),
        DefaultRule(field="MEMO", value=""),
        NormalizeNullRule(field="ZCONTENT", null_values=["", "null"]),
        CastRule(field="AMOUNT", target_type="float64"),
    ]

    config = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_INOUTCOME,
        selector=SqliteSelector(table_name="INOUTCOME"),
        mapping=[
            ColumnMapping(source_field="ZNAME", canonical_field="CONTENT"),
            ColumnMapping(source_field="ZCONTENT", canonical_field="MEMO"),
        ],
        normalization=shuffled_rules,
    )

    compiler = NormalizationCompiler()
    plan = compiler.compile(config)

    # Pre-rename rules: Trim (ZNAME) should precede NormalizeNull (ZCONTENT)
    assert len(plan.pre_rename_rules) == 2
    assert isinstance(plan.pre_rename_rules[0], TrimRule)
    assert isinstance(plan.pre_rename_rules[1], NormalizeNullRule)

    # Post-rename rules: ParseDate -> Cast -> NormalizeCase -> Default -> Constant
    post_types = [type(r) for r in plan.post_rename_rules]
    expected_order = [ParseDateRule, CastRule, NormalizeCaseRule, DefaultRule, ConstantRule]
    assert post_types == expected_order
