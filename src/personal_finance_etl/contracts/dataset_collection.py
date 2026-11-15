"""Typed dataset collection and runtime transport contracts.

Owns
----
- MissingDatasetError: Raised when a required dataset is absent from DatasetCollection.
- DatasetRuntimeMetadata: Bounded operational metadata describing a transported dataset.
- DatasetCollection: Immutable, typed container mapping canonical DatasetIds to Polars frames.

Does not own
------------
- Physical file reading or extraction (owned by infrastructure.providers).
- Warehouse persistence (owned by infrastructure.warehouse).
- Domain transformations (owned by domain).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass

import polars as pl

from personal_finance_etl.contracts.datasets import DatasetId
from personal_finance_etl.contracts.provenance import ProvenanceRef
from personal_finance_etl.contracts.sources import SourceId

__all__ = [
    "DatasetCollection",
    "DatasetRuntimeMetadata",
    "MissingDatasetError",
]


class MissingDatasetError(KeyError):
    """Raised when a required DatasetId is absent from a DatasetCollection.

    Parameters
    ----------
    dataset_id : DatasetId
        Canonical identifier of the missing dataset.
    message : str | None, default=None
        Custom error message. If None, a standard message is formatted.
    capability_context : str | None, default=None
        Optional capability or consumer identifier requesting the dataset.
    """

    def __init__(
        self,
        dataset_id: DatasetId,
        message: str | None = None,
        *,
        capability_context: str | None = None,
    ) -> None:
        msg = message or f"Required dataset '{dataset_id.value}' is not present in collection"
        if capability_context:
            msg += f" (required by capability: '{capability_context}')"
        super().__init__(msg)
        self.dataset_id = dataset_id
        self.capability_context = capability_context


@dataclass(frozen=True, slots=True)
class DatasetRuntimeMetadata:
    """Metadata describing a dataset transported within DatasetCollection.

    Parameters
    ----------
    dataset_id : DatasetId
        Authoritative canonical dataset identifier.
    source_id : SourceId | None, default=None
        Authoritative source identifier when externally sourced.
    provenance : tuple[ProvenanceRef, ...], default=()
        Tuple of provenance references identifying originating artifacts.
    config_fingerprint : str | None, default=None
        Optional configuration schema or topology fingerprint string.
    """

    dataset_id: DatasetId
    source_id: SourceId | None = None
    provenance: tuple[ProvenanceRef, ...] = ()
    config_fingerprint: str | None = None


class DatasetCollection:
    """Immutable, typed container mapping canonical DatasetIds to Polars frames.

    Parameters
    ----------
    frames : Mapping[DatasetId, pl.LazyFrame | pl.DataFrame] | None, default=None
        Initial mapping of DatasetId keys to Polars frames.
    metadata : Mapping[DatasetId, DatasetRuntimeMetadata] | None, default=None
        Optional mapping of DatasetId keys to runtime operational metadata.

    Raises
    ------
    TypeError
        If keys are not DatasetId instances or frames are not pl.LazyFrame/pl.DataFrame.
    ValueError
        If metadata keys do not correspond to existing frames or dataset IDs mismatch.
    """

    __slots__ = ("_frames", "_metadata")

    def __init__(
        self,
        frames: Mapping[DatasetId, pl.LazyFrame | pl.DataFrame] | None = None,
        metadata: Mapping[DatasetId, DatasetRuntimeMetadata] | None = None,
    ) -> None:
        validated_frames: dict[DatasetId, pl.LazyFrame | pl.DataFrame] = {}
        if frames is not None:
            for k, v in frames.items():
                if not isinstance(k, DatasetId):  # pyright: ignore[reportUnnecessaryIsInstance]
                    raise TypeError(
                        f"DatasetCollection keys must be DatasetId instances, got '{type(k).__name__}'"
                    )
                if not isinstance(v, (pl.LazyFrame, pl.DataFrame)):  # pyright: ignore[reportUnnecessaryIsInstance]
                    raise TypeError(
                        f"DatasetCollection frames must be Polars LazyFrame or DataFrame, got '{type(v).__name__}' for '{k.value}'"
                    )
                validated_frames[k] = v

        validated_metadata: dict[DatasetId, DatasetRuntimeMetadata] = {}
        if metadata is not None:
            for k, m in metadata.items():
                if not isinstance(k, DatasetId):  # pyright: ignore[reportUnnecessaryIsInstance]
                    raise TypeError(
                        f"DatasetCollection metadata keys must be DatasetId instances, got '{type(k).__name__}'"
                    )
                if not isinstance(m, DatasetRuntimeMetadata):  # pyright: ignore[reportUnnecessaryIsInstance]
                    raise TypeError(
                        f"DatasetCollection metadata values must be DatasetRuntimeMetadata, got '{type(m).__name__}'"
                    )
                if m.dataset_id != k:
                    raise ValueError(
                        f"Metadata dataset_id '{m.dataset_id.value}' does not match key '{k.value}'"
                    )
                if k not in validated_frames:
                    raise ValueError(
                        f"Metadata provided for dataset '{k.value}' which does not exist in frames"
                    )
                validated_metadata[k] = m

        self._frames: dict[DatasetId, pl.LazyFrame | pl.DataFrame] = validated_frames
        self._metadata: dict[DatasetId, DatasetRuntimeMetadata] = validated_metadata

    @classmethod
    def empty(cls) -> DatasetCollection:
        """Construct an empty DatasetCollection.

        Returns
        -------
        DatasetCollection
            Empty immutable dataset collection.
        """
        return cls()

    def require(
        self,
        dataset_id: DatasetId,
        capability_context: str | None = None,
    ) -> pl.LazyFrame | pl.DataFrame:
        """Retrieve a required dataset frame or raise MissingDatasetError.

        Parameters
        ----------
        dataset_id : DatasetId
            Target canonical dataset identifier.
        capability_context : str | None, default=None
            Optional identifier of the requesting capability/pipeline component.

        Returns
        -------
        pl.LazyFrame | pl.DataFrame
            Stored Polars frame.

        Raises
        ------
        MissingDatasetError
            If dataset_id is not present in this collection.
        """
        if dataset_id not in self._frames:
            raise MissingDatasetError(dataset_id, capability_context=capability_context)
        return self._frames[dataset_id]

    def require_lazy(
        self,
        dataset_id: DatasetId,
        capability_context: str | None = None,
    ) -> pl.LazyFrame:
        """Retrieve a required dataset as a pl.LazyFrame.

        If the underlying frame is a pl.DataFrame, `.lazy()` is invoked.

        Parameters
        ----------
        dataset_id : DatasetId
            Target canonical dataset identifier.
        capability_context : str | None, default=None
            Optional identifier of the requesting capability/pipeline component.

        Returns
        -------
        pl.LazyFrame
            Polars LazyFrame.

        Raises
        ------
        MissingDatasetError
            If dataset_id is not present in this collection.
        """
        frame = self.require(dataset_id, capability_context=capability_context)
        return frame if isinstance(frame, pl.LazyFrame) else frame.lazy()

    def get(
        self,
        dataset_id: DatasetId,
        default: pl.LazyFrame | pl.DataFrame | None = None,
    ) -> pl.LazyFrame | pl.DataFrame | None:
        """Retrieve an optional dataset frame or return default if absent.

        Parameters
        ----------
        dataset_id : DatasetId
            Target canonical dataset identifier.
        default : pl.LazyFrame | pl.DataFrame | None, default=None
            Fallback value returned if dataset_id is not present.

        Returns
        -------
        pl.LazyFrame | pl.DataFrame | None
            Stored Polars frame or default.
        """
        return self._frames.get(dataset_id, default)

    def get_lazy(
        self,
        dataset_id: DatasetId,
        default: pl.LazyFrame | None = None,
    ) -> pl.LazyFrame | None:
        """Retrieve an optional dataset frame as a pl.LazyFrame or return default if absent.

        Parameters
        ----------
        dataset_id : DatasetId
            Target canonical dataset identifier.
        default : pl.LazyFrame | None, default=None
            Fallback value returned if dataset_id is not present.

        Returns
        -------
        pl.LazyFrame | None
            Polars LazyFrame or default.
        """
        frame = self._frames.get(dataset_id)
        if frame is None:
            return default
        return frame if isinstance(frame, pl.LazyFrame) else frame.lazy()

    def get_metadata(self, dataset_id: DatasetId) -> DatasetRuntimeMetadata | None:
        """Retrieve operational metadata for a transported dataset.

        Parameters
        ----------
        dataset_id : DatasetId
            Target canonical dataset identifier.

        Returns
        -------
        DatasetRuntimeMetadata | None
            Operational metadata or None if no metadata was registered.
        """
        return self._metadata.get(dataset_id)

    def contains(self, dataset_id: DatasetId) -> bool:
        """Check whether a dataset is present in the collection.

        Parameters
        ----------
        dataset_id : DatasetId
            Target canonical dataset identifier.

        Returns
        -------
        bool
            True if present, False otherwise.
        """
        return dataset_id in self._frames

    def dataset_ids(self) -> tuple[DatasetId, ...]:
        """Return an immutable tuple of all DatasetIds present in the collection.

        Returns
        -------
        tuple[DatasetId, ...]
            All dataset identifiers present in this collection.
        """
        return tuple(self._frames.keys())

    def items(self) -> tuple[tuple[DatasetId, pl.LazyFrame | pl.DataFrame], ...]:
        """Return an immutable tuple of (DatasetId, frame) pairs.

        Returns
        -------
        tuple[tuple[DatasetId, pl.LazyFrame | pl.DataFrame], ...]
            Collection items.
        """
        return tuple(self._frames.items())

    def with_dataset(
        self,
        dataset_id: DatasetId,
        frame: pl.LazyFrame | pl.DataFrame,
        metadata: DatasetRuntimeMetadata | None = None,
    ) -> DatasetCollection:
        """Return a new DatasetCollection with an added or updated dataset.

        Parameters
        ----------
        dataset_id : DatasetId
            Target canonical dataset identifier.
        frame : pl.LazyFrame | pl.DataFrame
            Polars frame to add or replace.
        metadata : DatasetRuntimeMetadata | None, default=None
            Optional operational metadata for the dataset.

        Returns
        -------
        DatasetCollection
            New immutable collection containing the updated dataset.
        """
        new_frames = dict(self._frames)
        new_frames[dataset_id] = frame

        new_metadata = dict(self._metadata)
        if metadata is not None:
            new_metadata[dataset_id] = metadata
        elif dataset_id in new_metadata:
            # Drop old metadata if not provided for updated frame
            del new_metadata[dataset_id]

        return DatasetCollection(frames=new_frames, metadata=new_metadata)

    def merge(self, other: DatasetCollection) -> DatasetCollection:
        """Combine this collection with another, with the other collection taking precedence.

        Parameters
        ----------
        other : DatasetCollection
            Collection whose datasets and metadata take precedence on collision.

        Returns
        -------
        DatasetCollection
            Combined immutable DatasetCollection.
        """
        combined_frames = dict(self._frames)
        combined_frames.update(other._frames)

        combined_metadata = dict(self._metadata)
        combined_metadata.update(other._metadata)

        return DatasetCollection(frames=combined_frames, metadata=combined_metadata)

    def __getitem__(self, dataset_id: DatasetId) -> pl.LazyFrame | pl.DataFrame:
        """Key-based lookup delegating to require()."""
        return self.require(dataset_id)

    def __contains__(self, item: object) -> bool:
        """Support membership testing via `dataset_id in collection`."""
        return item in self._frames

    def __len__(self) -> int:
        """Return the number of datasets in the collection."""
        return len(self._frames)

    def __iter__(self) -> Iterator[DatasetId]:
        """Iterate over DatasetIds present in the collection."""
        return iter(self._frames)

    def __repr__(self) -> str:
        """Return human-readable diagnostic representation."""
        ds_names = [d.value for d in self._frames]
        return f"DatasetCollection(datasets={ds_names}, count={len(self._frames)})"
