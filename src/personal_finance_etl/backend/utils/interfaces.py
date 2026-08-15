from typing import Protocol

import polars as pl

from personal_finance_etl.backend.utils.models import EngineStatus


class ILogger(Protocol):
    """Protocol for logging engine statuses."""

    def put(
        self, status: EngineStatus, block: bool = True, timeout: float | None = None
    ) -> None: ...


class IDatabaseLoader(Protocol):
    """Protocol for loading DataFrames into a database."""

    def run(self, dfs: dict[str, pl.DataFrame]) -> None: ...
