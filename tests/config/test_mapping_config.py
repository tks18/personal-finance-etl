"""Tests for source-to-canonical column mapping and bounded normalization models.

Owns
----
- Unit tests for ColumnMapping instantiation and whitespace trimming validation.
- Unit tests for dictionary-to-mapping conversion helpers.
- Unit tests for all 8 bounded NormalizationRule models (Cast, ParseDate, Trim, etc.).
- Unit tests for SourceDatasetConfig mapping dictionary coercion and discriminated union parsing.
- Serialization and round-trip tests to and from TOML format.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from personal_finance_etl.config.sources.loader import SourceConfiguration
from personal_finance_etl.config.sources.mapping import (
    ColumnMapping,
    dict_to_mapping_list,
    mapping_list_to_dict,
)
from personal_finance_etl.config.sources.model import SourceConfig, SourceDatasetConfig
from personal_finance_etl.config.sources.normalization import (
    CastRule,
    ConstantRule,
    DefaultRule,
    MapValuesRule,
    NormalizeCaseRule,
    NormalizeNullRule,
    ParseDateRule,
    TrimRule,
)
from personal_finance_etl.config.sources.selectors import SqliteSelector
from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import ProviderType, SourceId


def test_column_mapping_valid() -> None:
    """Verify ColumnMapping instantiates correctly with trimmed field names."""
    m = ColumnMapping(source_field="  ZNAME  ", canonical_field="  category_name  ")
    assert m.source_field == "ZNAME"
    assert m.canonical_field == "category_name"


def test_column_mapping_empty_fails() -> None:
    """Verify ColumnMapping rejects empty or whitespace-only field names."""
    with pytest.raises(ValidationError, match="cannot be empty"):
        ColumnMapping(source_field="", canonical_field="target")

    with pytest.raises(ValidationError, match="cannot be empty"):
        ColumnMapping(source_field="source", canonical_field="   ")


def test_dict_to_mapping_helpers_round_trip() -> None:
    """Verify dict_to_mapping_list and mapping_list_to_dict convert bidirectionally."""
    raw = {"Z_PK": "UID", "ZNAME": "category_name", "ZTYPE": "category_type"}
    mappings = dict_to_mapping_list(raw)
    assert len(mappings) == 3
    assert mappings[0].source_field == "Z_PK"
    assert mappings[0].canonical_field == "UID"

    reconstructed = mapping_list_to_dict(mappings)
    assert reconstructed == raw


def test_normalization_rules_instantiation() -> None:
    """Verify all 8 normalization rules instantiate correctly with valid parameters."""
    cast_rule = CastRule(field="amount", target_type="float64")
    assert cast_rule.rule == "cast"
    assert cast_rule.target_type == "float64"

    date_rule = ParseDateRule(field="date_str", format="%d-%m-%Y", strict=True)
    assert date_rule.rule == "parse_date"
    assert date_rule.format == "%d-%m-%Y"
    assert date_rule.strict is True

    trim_rule = TrimRule(field="name", mode="both")
    assert trim_rule.rule == "trim"
    assert trim_rule.mode == "both"

    case_rule = NormalizeCaseRule(field="symbol", case="upper")
    assert case_rule.rule == "normalize_case"
    assert case_rule.case == "upper"

    const_rule = ConstantRule(field="country", value="IN")
    assert const_rule.rule == "constant"
    assert const_rule.value == "IN"

    default_rule = DefaultRule(field="is_del", value="0")
    assert default_rule.rule == "default"
    assert default_rule.value == "0"

    null_rule = NormalizeNullRule(field="notes", null_values=["N/A", "null"])
    assert null_rule.rule == "normalize_null"
    assert null_rule.null_values == ["N/A", "null"]

    map_rule = MapValuesRule(field="type", mapping={"0": "INCOME", "1": "EXPENSE"}, default="OTHER")
    assert map_rule.rule == "map_values"
    assert map_rule.mapping == {"0": "INCOME", "1": "EXPENSE"}
    assert map_rule.default == "OTHER"


def test_normalization_rules_invalid_options() -> None:
    """Verify normalization rules reject invalid options and dtypes."""
    with pytest.raises(ValidationError):
        # Invalid target_type
        CastRule(field="col", target_type="invalid_type")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        # Invalid case
        NormalizeCaseRule(field="col", case="camel")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        # Invalid trim mode
        TrimRule(field="col", mode="middle")  # type: ignore[arg-type]


def test_source_dataset_config_dict_coercion() -> None:
    """Verify SourceDatasetConfig coerces mapping dictionary into ColumnMapping list."""
    ds = SourceDatasetConfig(
        source_id=SourceId("src_db"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=SqliteSelector(table_name="ZCATEGORY"),
        mapping={"Z_PK": "UID", "ZNAME": "CATEGORY_NAME"},  # type: ignore[arg-type]
    )
    assert len(ds.mapping) == 2
    assert ds.mapping[0].source_field == "Z_PK"
    assert ds.mapping[0].canonical_field == "UID"
    assert ds.mapping[1].source_field == "ZNAME"
    assert ds.mapping[1].canonical_field == "CATEGORY_NAME"


def test_source_dataset_config_normalization_parsing() -> None:
    """Verify SourceDatasetConfig parses discriminated normalization rules."""
    raw_rules = [
        {"rule": "trim", "field": "CATEGORY_NAME", "mode": "both"},
        {"rule": "normalize_case", "field": "CATEGORY_NAME", "case": "upper"},
        {"rule": "map_values", "field": "TYPE", "mapping": {"0": "INCOME", "1": "EXPENSE"}},
    ]
    ds = SourceDatasetConfig(
        source_id=SourceId("src_db"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=SqliteSelector(table_name="ZCATEGORY"),
        normalization=raw_rules,  # type: ignore[arg-type]
    )
    assert len(ds.normalization) == 3
    assert isinstance(ds.normalization[0], TrimRule)
    assert isinstance(ds.normalization[1], NormalizeCaseRule)
    assert isinstance(ds.normalization[2], MapValuesRule)


def test_source_configuration_toml_round_trip_with_mappings(tmp_path: Path) -> None:
    """Verify SourceConfiguration serializes to TOML and deserializes back with mappings and rules."""
    source = SourceConfig(
        source_id=SourceId("household_db"),
        provider_type=ProviderType.SQLITE,
        location="inputs/DB.sqlite",
    )
    dataset = SourceDatasetConfig(
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        selector=SqliteSelector(table_name="ZCATEGORY"),
        mapping=[
            ColumnMapping(source_field="Z_PK", canonical_field="UID"),
            ColumnMapping(source_field="ZNAME", canonical_field="CATEGORY_NAME"),
        ],
        normalization=[
            TrimRule(field="CATEGORY_NAME", mode="both"),
            NormalizeCaseRule(field="CATEGORY_NAME", case="upper"),
            ConstantRule(field="ORDER_NUM", value=1),
        ],
    )
    config = SourceConfiguration(sources=(source,), datasets=(dataset,))

    toml_file = tmp_path / "sources_with_mappings.toml"
    config.to_toml(str(toml_file))

    loaded = SourceConfiguration.from_toml(str(toml_file))
    loaded_ds = loaded.get_dataset_binding(DatasetId.HOUSEHOLD_ZCATEGORY)
    assert loaded_ds is not None
    assert len(loaded_ds.mapping) == 2
    assert loaded_ds.mapping[0].source_field == "Z_PK"
    assert loaded_ds.mapping[0].canonical_field == "UID"
    assert len(loaded_ds.normalization) == 3
    assert isinstance(loaded_ds.normalization[0], TrimRule)
    assert isinstance(loaded_ds.normalization[1], NormalizeCaseRule)
    assert isinstance(loaded_ds.normalization[2], ConstantRule)
    assert loaded_ds.normalization[2].value == 1
