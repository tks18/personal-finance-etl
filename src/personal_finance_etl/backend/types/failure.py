"""
Machine-readable failure taxonomy for personal-finance-etl.
"""

from enum import StrEnum
from typing import Any


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
    error: Any = None,
) -> FailureDomain:
    """Classify failure deterministically into a standard FailureDomain."""
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
        if "PUBLICATION" in stg or "LOAD" in stg or "METADATA" in stg or "SILVER" in stg or "GOLD" in stg:
            return FailureDomain.PUBLICATION
        if "DUCKDB_COMMIT" in stg:
            return FailureDomain.DUCKDB_COMMIT
        if "SQLITE_COMMIT" in stg:
            return FailureDomain.SQLITE_COMMIT
        if "COMMIT" in stg:
            return FailureDomain.DUCKDB_COMMIT if "DUCKDB" in err_str.upper() else FailureDomain.SQLITE_COMMIT
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

