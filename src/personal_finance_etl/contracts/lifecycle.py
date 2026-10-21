"""Operational lifecycle and failure contracts.

Owns
----
- Explicit cross-database transaction commit states (CommitState).
- Machine-readable operational failure classifications (FailureDomain).
- Deterministic failure domain classification logic (classify_failure_domain).

Does not own
-------------
- Workflow orchestration policies (owned by application.pipeline).
- Database transaction management (owned by infrastructure.warehouse/control_plane).
"""

from enum import StrEnum
from typing import TypedDict

__all__ = ["CommitState", "FailureDomain", "SyncSummaryRecord", "classify_failure_domain"]


class SyncSummaryRecord(TypedDict, total=False):
    """Authoritative file-sync summary metrics for pipeline runs."""

    run_id: str
    actionable_count: int
    synced_count: int
    healed_count: int
    failed_count: int
    deferred_count: int
    sync_status: str
    created_at: str


class CommitState(StrEnum):
    """Explicit cross-database transaction commit state."""

    NOT_STARTED = "NOT_STARTED"
    STARTED = "STARTED"
    ROLLED_BACK = "ROLLED_BACK"
    DUCKDB_COMMITTED = "DUCKDB_COMMITTED"
    FULLY_COMMITTED = "FULLY_COMMITTED"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    CONVERGED = "CONVERGED"
    DUCKDB_COMMITTED_SQLITE_FAILED = "RECOVERY_REQUIRED"
    COMMIT_STATE_UNKNOWN = "COMMIT_STATE_UNKNOWN"


class FailureDomain(StrEnum):
    """Machine-readable failure classification taxonomy."""

    CONFIGURATION = "CONFIGURATION"
    SOURCE_DISCOVERY = "SOURCE_DISCOVERY"
    SOURCE_VALIDATION = "SOURCE_VALIDATION"
    EXTERNAL_PROVIDER = "EXTERNAL_PROVIDER"
    BRONZE_SYNC = "BRONZE_SYNC"
    TRANSFORMATION = "TRANSFORMATION"
    FINANCIAL_INVARIANT = "FINANCIAL_INVARIANT"
    PUBLICATION = "PUBLICATION"
    DUCKDB_COMMIT = "DUCKDB_COMMIT"
    SQLITE_COMMIT = "SQLITE_COMMIT"
    RECOVERY = "RECOVERY"
    SNAPSHOT = "SNAPSHOT"
    RESTORE = "RESTORE"
    WORKER = "WORKER"
    UNKNOWN = "UNKNOWN"


_ERROR_MATCH_RULES: tuple[tuple[tuple[str, ...], FailureDomain], ...] = (
    (("FinancialSourceValidationError",), FailureDomain.SOURCE_VALIDATION),
    (("ExtractionCompletenessError",), FailureDomain.EXTERNAL_PROVIDER),
    (("DataContract", "DATA_CONTRACT_REGISTRY"), FailureDomain.FINANCIAL_INVARIANT),
    (("DuckDB Commit Failed",), FailureDomain.DUCKDB_COMMIT),
    (("SQLite Commit Failed",), FailureDomain.SQLITE_COMMIT),
    (("ISIN_FAILURE", "BrokenProcessPool", "Process-boundary"), FailureDomain.WORKER),
)

_STAGE_MATCH_RULES: tuple[tuple[tuple[str, ...], FailureDomain], ...] = (
    (("DISCOVERY",), FailureDomain.SOURCE_DISCOVERY),
    (("VALIDATION",), FailureDomain.SOURCE_VALIDATION),
    (("PROVIDER", "CURRENCY", "US_MARKET", "BENCHMARK"), FailureDomain.EXTERNAL_PROVIDER),
    (("BRONZE", "SYNC"), FailureDomain.BRONZE_SYNC),
    (("TRANSFORM", "ANALYTICS", "TAX", "PRESENTATION"), FailureDomain.TRANSFORMATION),
    (("PUBLICATION", "LOAD", "METADATA", "SILVER", "GOLD"), FailureDomain.PUBLICATION),
    (("DUCKDB_COMMIT",), FailureDomain.DUCKDB_COMMIT),
    (("SQLITE_COMMIT",), FailureDomain.SQLITE_COMMIT),
    (("RECOVERY", "CONVERGENCE"), FailureDomain.RECOVERY),
    (("SNAPSHOT",), FailureDomain.SNAPSHOT),
    (("RESTORE",), FailureDomain.RESTORE),
    (("CONFIG",), FailureDomain.CONFIGURATION),
    (("WORKER",), FailureDomain.WORKER),
)


def _match_error_domain(err_type: str, err_str: str) -> FailureDomain | None:
    """Match error type and message against known error patterns."""
    for patterns, domain in _ERROR_MATCH_RULES:
        if any(p in err_type or p in err_str for p in patterns):
            return domain
    if "Timeout" in err_type and "pipeline.lock" in err_str:
        return FailureDomain.CONFIGURATION
    return None


def _match_stage_domain(stage: str, err_str: str) -> FailureDomain:
    """Match stage name and error message against known stage patterns."""
    stg = stage.strip().upper()
    for patterns, domain in _STAGE_MATCH_RULES:
        if any(p in stg for p in patterns):
            return domain
    if "COMMIT" in stg:
        return (
            FailureDomain.DUCKDB_COMMIT
            if "DUCKDB" in err_str.upper()
            else FailureDomain.SQLITE_COMMIT
        )
    return FailureDomain.UNKNOWN


def classify_failure_domain(
    stage: str | None = None,
    error: BaseException | str | None = None,
) -> FailureDomain:
    """Classify failure deterministically into a standard FailureDomain.

    Parameters
    ----------
    stage : str | None
        Name of the pipeline stage where the error occurred.
    error : BaseException | str | None
        The exception or error object raised during execution.

    Returns
    -------
    FailureDomain
        The categorical failure domain representing the root cause.
    """
    err_str = str(error) if error is not None else ""
    err_type = type(error).__name__ if isinstance(error, BaseException) else ""

    err_domain = _match_error_domain(err_type, err_str)
    if err_domain is not None:
        return err_domain

    if stage:
        return _match_stage_domain(stage, err_str)

    return FailureDomain.UNKNOWN
