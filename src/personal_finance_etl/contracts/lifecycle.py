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

    # Exception-type or exact message classification
    if "FinancialSourceValidationError" in err_type or "FinancialSourceValidationError" in err_str:
        return FailureDomain.SOURCE_VALIDATION

    if "ExtractionCompletenessError" in err_type or "ExtractionCompletenessError" in err_str:
        return FailureDomain.EXTERNAL_PROVIDER

    if "DataContract" in err_str or "DATA_CONTRACT_REGISTRY" in err_str:
        return FailureDomain.FINANCIAL_INVARIANT

    if "DuckDB Commit Failed" in err_str or "DUCKDB_COMMIT" in str(stage).upper():
        return FailureDomain.DUCKDB_COMMIT

    if "SQLite Commit Failed" in err_str or "SQLITE_COMMIT" in str(stage).upper():
        return FailureDomain.SQLITE_COMMIT

    if "ISIN_FAILURE" in err_str or "BrokenProcessPool" in err_str or "Process-boundary" in err_str:
        return FailureDomain.WORKER

    if "Timeout" in err_type and "pipeline.lock" in err_str:
        return FailureDomain.CONFIGURATION

    # Stage-based classification
    if stage:
        stg = stage.strip().upper()
        if "DISCOVERY" in stg:
            return FailureDomain.SOURCE_DISCOVERY
        if "VALIDATION" in stg:
            return FailureDomain.SOURCE_VALIDATION
        if "PROVIDER" in stg or "CURRENCY" in stg or "US_MARKET" in stg or "BENCHMARK" in stg:
            return FailureDomain.EXTERNAL_PROVIDER
        if "BRONZE" in stg or "SYNC" in stg:
            return FailureDomain.BRONZE_SYNC
        if "TRANSFORM" in stg or "ANALYTICS" in stg or "TAX" in stg or "PRESENTATION" in stg:
            return FailureDomain.TRANSFORMATION
        if (
            "PUBLICATION" in stg
            or "LOAD" in stg
            or "METADATA" in stg
            or "SILVER" in stg
            or "GOLD" in stg
        ):
            return FailureDomain.PUBLICATION
        if "DUCKDB_COMMIT" in stg:
            return FailureDomain.DUCKDB_COMMIT
        if "SQLITE_COMMIT" in stg:
            return FailureDomain.SQLITE_COMMIT
        if "COMMIT" in stg:
            return (
                FailureDomain.DUCKDB_COMMIT
                if "DUCKDB" in err_str.upper()
                else FailureDomain.SQLITE_COMMIT
            )
        if "RECOVERY" in stg or "CONVERGENCE" in stg:
            return FailureDomain.RECOVERY
        if "SNAPSHOT" in stg:
            return FailureDomain.SNAPSHOT
        if "RESTORE" in stg:
            return FailureDomain.RESTORE
        if "CONFIG" in stg:
            return FailureDomain.CONFIGURATION
        if "WORKER" in stg:
            return FailureDomain.WORKER

    return FailureDomain.UNKNOWN
