# pylint: skip-file
# flake8: noqa
"""Source identity and provider contracts test suite.

Owns
----
- Invariant tests for SourceId validation, path-independence, and string serialization.
- Tests for ProviderType closed vocabulary and case-insensitive resolution.
- Validation, default behavior, and round-trip serialization tests for SourceConfig.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from personal_finance_etl.config.sources.model import SourceConfig
from personal_finance_etl.contracts.sources import (
    ProviderType,
    SourceId,
    validate_source_id,
)


def test_source_id_valid_and_string_behavior() -> None:
    """Verify that validate_source_id creates a valid SourceId string."""
    sid = validate_source_id("household_db")
    assert isinstance(sid, str)
    assert sid == "household_db"
    assert len(sid) == 12

    # Strips whitespace
    sid_whitespace = validate_source_id("  household_db  ")
    assert sid_whitespace == "household_db"


def test_source_id_rejection_invariants() -> None:
    """Verify that invalid inputs to validate_source_id are strictly rejected."""
    # Empty string
    with pytest.raises(ValueError, match="SourceId cannot be empty or whitespace"):
        validate_source_id("")

    # Whitespace only
    with pytest.raises(ValueError, match="SourceId cannot be empty or whitespace"):
        validate_source_id("   ")

    # Non-string type
    with pytest.raises(TypeError, match="SourceId must be a string"):
        validate_source_id(12345)  # type: ignore[arg-type]

    # Path separators forbidden (both forward and backward slash)
    with pytest.raises(ValueError, match="SourceId cannot contain path separators"):
        validate_source_id("path/to/source")

    with pytest.raises(ValueError, match="SourceId cannot contain path separators"):
        validate_source_id(r"path\to\source")


def test_provider_type_closed_vocabulary() -> None:
    """Verify ProviderType enum members and case-insensitive resolution."""
    assert ProviderType.CSV == "csv"
    assert ProviderType.EXCEL == "excel"
    assert ProviderType.SQLITE == "sqlite"

    # Case-insensitive resolution via _missing_
    assert ProviderType("csv") == ProviderType.CSV
    assert ProviderType("CSV") == ProviderType.CSV
    assert ProviderType("Excel") == ProviderType.EXCEL
    assert ProviderType("EXCEL") == ProviderType.EXCEL
    assert ProviderType("sqlite") == ProviderType.SQLITE
    assert ProviderType("SQLITE") == ProviderType.SQLITE

    # Unsupported provider types rejected
    with pytest.raises(ValueError):
        ProviderType("parquet")

    with pytest.raises(ValueError):
        ProviderType("json")


def test_source_config_defaults_and_roundtrip() -> None:
    """Verify SourceConfig creation, default values, and serialization round-trip."""
    cfg = SourceConfig(
        source_id=SourceId("household_db"),
        provider_type=ProviderType.SQLITE,
        location="data/Personal_Finance.sqlite",
    )

    # Defaults
    assert cfg.enabled is True
    assert cfg.description is None
    assert cfg.source_id == "household_db"
    assert cfg.provider_type == ProviderType.SQLITE

    # Dict round-trip
    data_dict = cfg.model_dump()
    assert data_dict == {
        "source_id": "household_db",
        "provider_type": "sqlite",
        "location": "data/Personal_Finance.sqlite",
        "enabled": True,
        "description": None,
    }
    reconstructed_dict = SourceConfig.model_validate(data_dict)
    assert reconstructed_dict == cfg
    assert reconstructed_dict.source_id == "household_db"

    # JSON round-trip
    json_str = cfg.model_dump_json()
    reconstructed_json = SourceConfig.model_validate_json(json_str)
    assert reconstructed_json == cfg
    assert reconstructed_json.source_id == "household_db"


def test_source_config_source_id_validation_on_deserialization() -> None:
    """Verify that SourceConfig rejects invalid source_id values during deserialization."""
    with pytest.raises(ValidationError, match="SourceId cannot contain path separators"):
        SourceConfig.model_validate_json(
            '{"source_id": "path/to/source", "provider_type": "sqlite", "location": "data.db"}'
        )

    with pytest.raises(ValidationError, match="SourceId cannot be empty or whitespace"):
        SourceConfig.model_validate_json(
            '{"source_id": "   ", "provider_type": "sqlite", "location": "data.db"}'
        )


def test_source_config_location_validation() -> None:
    """Verify that enabled sources require non-empty locations, while disabled sources do not."""
    # Enabled source with empty location rejected
    with pytest.raises(
        ValidationError,
        match="Enabled source 'test_source' must specify a non-empty location",
    ):
        SourceConfig(
            source_id=SourceId("test_source"),
            provider_type=ProviderType.CSV,
            location="",
            enabled=True,
        )

    with pytest.raises(
        ValidationError,
        match="Enabled source 'test_source' must specify a non-empty location",
    ):
        SourceConfig(
            source_id=SourceId("test_source"),
            provider_type=ProviderType.CSV,
            location="   ",
            enabled=True,
        )

    # Disabled source with empty location permitted
    disabled_cfg = SourceConfig(
        source_id=SourceId("test_source"),
        provider_type=ProviderType.CSV,
        location="",
        enabled=False,
    )
    assert disabled_cfg.enabled is False
    assert disabled_cfg.location == ""


def test_multiple_sources_can_share_provider_type() -> None:
    """Verify that multiple SourceConfigs can share the same ProviderType with distinct SourceIds."""
    src1 = SourceConfig(
        source_id=SourceId("mf_holdings"),
        provider_type=ProviderType.EXCEL,
        location="statements/Mutual Funds - Holdings",
    )
    src2 = SourceConfig(
        source_id=SourceId("stock_pl"),
        provider_type=ProviderType.EXCEL,
        location="statements/Stock PL Statements",
    )

    assert src1.provider_type == src2.provider_type == ProviderType.EXCEL
    assert src1.source_id != src2.source_id
    assert src1.location != src2.location


def test_changing_location_does_not_change_source_id() -> None:
    """Verify that modifying location preserves source identity immutability."""
    orig = SourceConfig(
        source_id=SourceId("opening_balances"),
        provider_type=ProviderType.CSV,
        location="path/a.csv",
    )
    updated = orig.model_copy(update={"location": "path/b.csv"})

    assert updated.source_id == orig.source_id
    assert updated.source_id == "opening_balances"
    assert updated.location == "path/b.csv"
