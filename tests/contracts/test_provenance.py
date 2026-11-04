"""Authoritative canonical provenance contract test suite.

Owns
----
- Invariant verification for ProvenanceRef construction, validation, and immutability.
- Strict rejection tests for malformed or empty artifact identifiers.
- Deterministic hashing, equality, and dictionary serialization round-trip tests.
- Invariant tests for ArtifactMetadata operational record contracts.

Does not own
------------
- Physical SQLite database testing (owned by tests.infrastructure.test_provenance_resolution).
- Ingestion extraction execution (owned by tests.application.test_ingestion).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.provenance import (
    ArtifactMetadata,
    ProvenanceRef,
)
from personal_finance_etl.contracts.sources import SourceId


def test_provenance_ref_valid_construction() -> None:
    """Verify that ProvenanceRef accepts valid inputs and preserves attributes."""
    ref = ProvenanceRef(
        artifact_id="a1b2c3d4e5f6",
        source_id=SourceId("household_db"),
        dataset_id=DatasetId.HOUSEHOLD_ZCATEGORY,
        source_record_key="rec_001",
    )
    assert ref.artifact_id == "a1b2c3d4e5f6"
    assert ref.source_id == "household_db"
    assert ref.dataset_id == DatasetId.HOUSEHOLD_ZCATEGORY
    assert ref.source_record_key == "rec_001"

    # Minimal construction with required artifact_id only
    ref_minimal = ProvenanceRef(artifact_id="f1e2d3c4b5a6")
    assert ref_minimal.artifact_id == "f1e2d3c4b5a6"
    assert ref_minimal.source_id is None
    assert ref_minimal.dataset_id is None
    assert ref_minimal.source_record_key is None


def test_provenance_ref_rejection_invariants() -> None:
    """Verify that invalid inputs to ProvenanceRef are strictly rejected."""
    # Empty artifact_id
    with pytest.raises(ValueError, match="artifact_id cannot be empty or whitespace"):
        ProvenanceRef(artifact_id="")

    # Whitespace-only artifact_id
    with pytest.raises(ValueError, match="artifact_id cannot be empty or whitespace"):
        ProvenanceRef(artifact_id="   ")

    # Non-string artifact_id
    with pytest.raises(TypeError, match="artifact_id must be a string"):
        ProvenanceRef(artifact_id=12345)  # type: ignore[arg-type]

    # Non-string source_id
    with pytest.raises(TypeError, match="source_id must be a string or SourceId"):
        ProvenanceRef(artifact_id="valid_id", source_id=999)  # type: ignore[arg-type]

    # Invalid dataset_id type
    with pytest.raises(TypeError, match="dataset_id must be a DatasetId or str"):
        ProvenanceRef(artifact_id="valid_id", dataset_id=456)  # type: ignore[arg-type]

    # Empty string dataset_id
    with pytest.raises(ValueError, match="dataset_id cannot be empty or whitespace"):
        ProvenanceRef(artifact_id="valid_id", dataset_id="   ")

    # Invalid source_record_key type
    with pytest.raises(TypeError, match="source_record_key must be a str"):
        ProvenanceRef(artifact_id="valid_id", source_record_key=789)  # type: ignore[arg-type]

    # Empty string source_record_key
    with pytest.raises(ValueError, match="source_record_key cannot be empty or whitespace"):
        ProvenanceRef(artifact_id="valid_id", source_record_key="   ")


def test_provenance_ref_immutability() -> None:
    """Verify that ProvenanceRef is an immutable frozen dataclass."""
    ref = ProvenanceRef(artifact_id="abc123")
    with pytest.raises(FrozenInstanceError):
        ref.artifact_id = "new_id"  # type: ignore[misc]


def test_provenance_ref_equality_and_hashing() -> None:
    """Verify that ProvenanceRef instances support deterministic equality and hashing."""
    ref1 = ProvenanceRef(
        artifact_id="hash_1",
        source_id="src_1",
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
    )
    ref2 = ProvenanceRef(
        artifact_id="hash_1",
        source_id="src_1",
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
    )
    ref3 = ProvenanceRef(
        artifact_id="hash_2",
        source_id="src_1",
        dataset_id=DatasetId.HOUSEHOLD_CURRENCY,
    )

    assert ref1 == ref2
    assert ref1 != ref3
    assert hash(ref1) == hash(ref2)
    assert hash(ref1) != hash(ref3)

    # Set membership
    ref_set = {ref1, ref2, ref3}
    assert len(ref_set) == 2


def test_provenance_ref_serialization_round_trip() -> None:
    """Verify dictionary serialization and deserialization round-trip."""
    ref = ProvenanceRef(
        artifact_id="art_999",
        source_id="portfolio_src",
        dataset_id=DatasetId.INVESTMENT_STOCK_ORDERS,
        source_record_key="row_42",
    )
    serialized = ref.to_dict()
    assert serialized == {
        "artifact_id": "art_999",
        "source_id": "portfolio_src",
        "dataset_id": "investment_stock_orders",
        "source_record_key": "row_42",
    }

    reconstituted = ProvenanceRef.from_dict(serialized)
    assert reconstituted == ref
    assert reconstituted.dataset_id == DatasetId.INVESTMENT_STOCK_ORDERS


def test_provenance_ref_from_dict_validation() -> None:
    """Verify that from_dict strictly validates the incoming payload."""
    with pytest.raises(KeyError, match="must contain 'artifact_id' key"):
        ProvenanceRef.from_dict({"source_id": "src"})

    with pytest.raises(TypeError, match="artifact_id must be a string"):
        ProvenanceRef.from_dict({"artifact_id": 12345})


def test_artifact_metadata_valid_and_immutability() -> None:
    """Verify ArtifactMetadata valid construction and frozen immutability."""
    meta = ArtifactMetadata(
        artifact_id="64_char_hash",
        file_name="statement.xlsx",
        relative_path="Statements/statement.xlsx",
        file_category="mf_holdings",
        file_type="excel",
        file_hash="content_sha256",
        sync_status="SYNCED",
    )
    assert meta.artifact_id == "64_char_hash"
    assert meta.file_name == "statement.xlsx"
    assert meta.file_type == "excel"

    with pytest.raises(FrozenInstanceError):
        meta.file_name = "other.xlsx"  # type: ignore[misc]


def test_artifact_metadata_rejection_invariants() -> None:
    """Verify that invalid inputs to ArtifactMetadata are rejected."""
    with pytest.raises(ValueError, match="file_name cannot be empty or whitespace"):
        ArtifactMetadata(
            artifact_id="hash",
            file_name="   ",
            relative_path="path",
            file_category="cat",
        )

    with pytest.raises(TypeError, match="artifact_id must be a string"):
        ArtifactMetadata(
            artifact_id=123,  # type: ignore[arg-type]
            file_name="file.csv",
            relative_path="path.csv",
            file_category="cat",
        )
