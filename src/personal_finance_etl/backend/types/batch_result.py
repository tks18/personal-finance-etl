from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import polars as pl


class ExtractionCompletenessError(RuntimeError):
    """Raised when required market evidence extraction fails to meet completeness policy."""

    def __init__(
        self,
        message: str,
        *,
        failed_entities: dict[str, str],
        requested_interval: tuple[date, date] | None = None,
        provider: str = "Yahoo Finance",
    ) -> None:
        super().__init__(
            f"{message} [failed={failed_entities}, interval={requested_interval}, provider={provider}]"
        )
        self.failed_entities = failed_entities
        self.requested_interval = requested_interval
        self.provider = provider


@dataclass
class ExtractionBatchResult:
    """Structured extraction outcome across concurrent entity workers."""

    requested_entities: list[str] = field(default_factory=lambda: list[str]())
    successful_entities: list[str] = field(default_factory=lambda: list[str]())
    cached_entities: list[str] = field(default_factory=lambda: list[str]())
    no_new_data_entities: list[str] = field(default_factory=lambda: list[str]())
    failed_entities: dict[str, str] = field(default_factory=lambda: dict[str, str]())
    frames: list[pl.DataFrame] = field(default_factory=lambda: list[pl.DataFrame]())
    injected_files: list[str] = field(default_factory=lambda: list[str]())
    provider: str = "Yahoo Finance"
    start_date: date | None = None
    end_date: date | None = None

    @property
    def is_complete(self) -> bool:
        """True if every requested entity succeeded, was cached, or returned valid empty data."""
        return len(self.failed_entities) == 0

    @property
    def combined_frame(self) -> pl.DataFrame:
        if not self.frames:
            return pl.DataFrame()
        return pl.concat(self.frames, how="diagonal_relaxed")

    def assert_complete(self, extractor_name: str = "Extractor") -> None:
        """Raise ExtractionCompletenessError if any entity failed."""
        if not self.is_complete:
            interval = (self.start_date, self.end_date) if self.start_date and self.end_date else None
            raise ExtractionCompletenessError(
                f"{extractor_name} batch extraction failed completeness policy: "
                f"{len(self.failed_entities)} required entity/entities failed",
                failed_entities=self.failed_entities,
                requested_interval=interval,
                provider=self.provider,
            )

    def __iter__(self) -> Iterator[Any]:
        """Support legacy tuple unpacking: (combined_df, injected_files) = batch_result."""
        return iter((self.combined_frame, self.injected_files))

