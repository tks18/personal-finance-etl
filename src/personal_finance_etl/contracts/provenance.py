"""Authoritative canonical provenance and artifact metadata contracts.

Owns
----
- ProvenanceRef: Compact immutable cross-boundary reference linking records to artifacts.
- ArtifactMetadata: Descriptive artifact operational metadata resolved via Control Plane.

Does not own
------------
- Physical hashing or path normalization (owned by infrastructure.control_plane.hashing).
- SQLite artifact vaulting or persistence (owned by infrastructure.control_plane.artifact_repository).
- Ingestion orchestration (owned by application.ingestion.coordinator).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.sources import SourceId

__all__ = ["ArtifactMetadata", "ProvenanceRef"]


@dataclass(frozen=True, slots=True)
class ProvenanceRef:
    """Immutable cross-boundary reference linking canonical rows to originating artifacts.

    Parameters
    ----------
    artifact_id : str
        Hexadecimal SHA-256 identifier of the source artifact in the Control Plane.
    source_id : SourceId | str | None, default=None
        Authoritative source identifier when resolved via source topology.
    dataset_id : DatasetId | str | None, default=None
        Canonical logical dataset identifier.
    source_record_key : str | None, default=None
        Optional record-level discriminator for multi-row artifacts where required.

    Raises
    ------
    TypeError
        If artifact_id is not a string, or optional IDs are of invalid types.
    ValueError
        If artifact_id is empty or whitespace-only.
    """

    artifact_id: str
    source_id: SourceId | str | None = None
    dataset_id: DatasetId | str | None = None
    source_record_key: str | None = None

    def __post_init__(self) -> None:
        """Validate provenance reference fields and enforce immutability invariants."""
        # pylint: disable=unidiomatic-typecheck
        if type(self.artifact_id) is not str:
            raise TypeError(f"artifact_id must be a string, got {type(self.artifact_id).__name__}")
        cleaned_id = self.artifact_id.strip()
        if not cleaned_id:
            raise ValueError("artifact_id cannot be empty or whitespace.")
        object.__setattr__(self, "artifact_id", cleaned_id)

        if self.source_id is not None and type(self.source_id) is not str:
            raise TypeError(
                f"source_id must be a string or SourceId, got {type(self.source_id).__name__}"
            )

        if self.dataset_id is not None:
            if type(self.dataset_id) is not str and type(self.dataset_id) is not DatasetId:
                raise TypeError(
                    f"dataset_id must be a DatasetId or str, got {type(self.dataset_id).__name__}"
                )
            cleaned_ds = str(self.dataset_id).strip()
            if not cleaned_ds:
                raise ValueError("dataset_id cannot be empty or whitespace if provided.")
            if type(self.dataset_id) is str:
                object.__setattr__(self, "dataset_id", cleaned_ds)

        if self.source_record_key is not None:
            if type(self.source_record_key) is not str:
                raise TypeError(
                    f"source_record_key must be a str, got {type(self.source_record_key).__name__}"
                )
            cleaned_key = self.source_record_key.strip()
            if not cleaned_key:
                raise ValueError("source_record_key cannot be empty or whitespace if provided.")
            object.__setattr__(self, "source_record_key", cleaned_key)

    def to_dict(self) -> dict[str, str | None]:
        """Serialize provenance reference to a dictionary of string values.

        Returns
        -------
        dict[str, str | None]
            String-keyed dictionary representing the provenance reference.
        """
        return {
            "artifact_id": self.artifact_id,
            "source_id": str(self.source_id) if self.source_id is not None else None,
            "dataset_id": (
                self.dataset_id.value
                if isinstance(self.dataset_id, DatasetId)
                else (str(self.dataset_id) if self.dataset_id is not None else None)
            ),
            "source_record_key": self.source_record_key,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> ProvenanceRef:
        """Construct a ProvenanceRef instance from a dictionary.

        Parameters
        ----------
        data : Mapping[str, object]
            Key-value mapping containing provenance fields.

        Returns
        -------
        ProvenanceRef
            Validated provenance reference instance.

        Raises
        ------
        KeyError
            If artifact_id is missing from data.
        TypeError
            If artifact_id is not a string.
        """
        if "artifact_id" not in data:
            raise KeyError("data dictionary must contain 'artifact_id' key.")

        raw_artifact_id = data["artifact_id"]
        if not isinstance(raw_artifact_id, str):
            raise TypeError(f"artifact_id must be a string, got {type(raw_artifact_id).__name__}")

        raw_source_id = data.get("source_id")
        source_id: SourceId | str | None = None
        if raw_source_id is not None:
            source_id = SourceId(str(raw_source_id))

        raw_dataset_id = data.get("dataset_id")
        dataset_id: DatasetId | str | None = None
        if raw_dataset_id is not None:
            ds_str = str(raw_dataset_id)
            try:
                dataset_id = DatasetId(ds_str)
            except ValueError:
                dataset_id = ds_str

        raw_key = data.get("source_record_key")
        source_record_key: str | None = str(raw_key) if raw_key is not None else None

        return cls(
            artifact_id=raw_artifact_id,
            source_id=source_id,
            dataset_id=dataset_id,
            source_record_key=source_record_key,
        )


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    """Authoritative descriptive metadata for a control plane artifact.

    Parameters
    ----------
    artifact_id : str
        Hexadecimal SHA-256 identifier of the artifact.
    file_name : str
        Base file name of the artifact.
    relative_path : str
        Normalized relative path of the artifact.
    file_category : str
        Category classification in the control plane.
    file_type : str | None, default=None
        Storage format classification (e.g. 'csv', 'excel', 'sqlite', 'parquet').
    file_hash : str, default=""
        SHA-256 content digest of the artifact payload.
    sync_status : str | None, default=None
        Current synchronization status (e.g. 'SYNCED', 'PENDING_BRONZE', 'REMOVED').

    Raises
    ------
    TypeError
        If any required string parameter is not a string.
    ValueError
        If required identifier fields are empty or whitespace.
    """

    artifact_id: str
    file_name: str
    relative_path: str
    file_category: str
    file_type: str | None = None
    file_hash: str = ""
    sync_status: str | None = None

    def __post_init__(self) -> None:
        """Validate artifact metadata fields and enforce invariants."""
        # pylint: disable=unidiomatic-typecheck
        fields: tuple[tuple[str, object], ...] = (
            ("artifact_id", self.artifact_id),
            ("file_name", self.file_name),
            ("relative_path", self.relative_path),
            ("file_category", self.file_category),
        )
        for field_name, value in fields:
            if type(value) is not str:
                raise TypeError(f"{field_name} must be a string, got {type(value).__name__}")
            if not value.strip():
                raise ValueError(f"{field_name} cannot be empty or whitespace.")
