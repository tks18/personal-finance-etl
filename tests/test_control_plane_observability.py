# pyright: reportPrivateUsage=false
"""Control Plane Projection and Run Evidence Certification Test Suite.

Owns
----
- Verification of operational milestone transitions and commit state tracking in cp_runs.
- Verification of failure classification and domain persistence in cp_run_failures.
- Verification of zlib compression ratio and lossless trace decompression round-trip.
- Verification of non-fatal degradation during trace archival failures.
- Architectural assertion guaranteeing zero legacy bracket prefixes in control plane.

Does not own
-------------
- In-memory event fan-out or span timing (owned by tests/test_observability_emitter.py).
- UI narrative widget rendering (owned by tests/test_presentation_narrative.py).
"""

from __future__ import annotations

import re
from collections.abc import Generator
from pathlib import Path

import pytest

from personal_finance_etl.contracts.lifecycle import CommitState, FailureDomain
from personal_finance_etl.infrastructure.control_plane.connection import SQLiteManager
from personal_finance_etl.infrastructure.control_plane.facade import ControlPlane
from personal_finance_etl.infrastructure.control_plane.run_repository import RunRepository
from personal_finance_etl.infrastructure.observability.archival import (
    DEFAULT_COMPRESSION_LEVEL,
    archive_run_trace,
    compress_bytes,
    decompress_bytes,
    retrieve_run_trace,
)


@pytest.fixture
def sqlite_db(tmp_path: Path) -> Generator[SQLiteManager, None, None]:
    """Create a temporary initialized Control Plane SQLite database."""
    manager = SQLiteManager(str(tmp_path), db_name="test_cp.sqlite")
    manager.open()
    manager.ensure_schema()
    yield manager
    manager.close()


@pytest.fixture
def control_plane(tmp_path: Path) -> Generator[ControlPlane, None, None]:
    """Create a temporary initialized ControlPlane facade."""
    cp = ControlPlane(str(tmp_path), db_name="test_cp_facade.sqlite")
    cp.open()
    cp.ensure_schema()
    yield cp
    cp.close()


def test_milestone_persistence_and_status(sqlite_db: SQLiteManager) -> None:
    """Verify run lifecycle milestone state transitions in cp_runs."""
    repo = RunRepository(sqlite_db)
    run_id = repo.start_run(cfg_json='{"app": "test"}', rules_json='{"tax": "india"}')

    assert run_id is not None
    status_initial = repo.get_run_status(run_id)
    assert status_initial is not None
    assert status_initial["run_id"] == run_id
    assert status_initial["status"] == "STARTED"
    assert status_initial["commit_state"] == "STARTED"
    assert status_initial["has_execution_log"] is False

    # Transition commit state
    repo.update_commit_state(run_id, CommitState.DUCKDB_COMMITTED)
    assert repo.get_run_status(run_id)["commit_state"] == "DUCKDB_COMMITTED"  # type: ignore[index]

    # Finalize run
    repo.finish_run(run_id, "SUCCESS", commit_state=CommitState.FULLY_COMMITTED)
    status_final = repo.get_run_status(run_id)
    assert status_final is not None
    assert status_final["status"] == "SUCCESS"
    assert status_final["commit_state"] == "FULLY_COMMITTED"
    assert status_final["finished_at"] is not None


def test_failure_logging_and_domain_capture(sqlite_db: SQLiteManager) -> None:
    """Verify error telemetry and failure domain classification persistence."""
    repo = RunRepository(sqlite_db)
    run_id = repo.start_run()

    repo.log_run_failure(
        run_id=run_id,
        failed_isin="INE002A01018",
        stage="InvestmentQuantEngine",
        error_type="FinancialInvariantError",
        error_message="Corporate action ratio must be strictly positive",
        traceback_log="Traceback (most recent call last):\n  File ...",
        failure_domain=FailureDomain.FINANCIAL_INVARIANT,
    )

    rows = sqlite_db.conn.execute(
        "SELECT run_id, failed_isin, stage, error_type, failure_domain FROM cp_run_failures WHERE run_id = ?",
        (run_id,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == run_id
    assert rows[0][1] == "INE002A01018"
    assert rows[0][2] == "InvestmentQuantEngine"
    assert rows[0][3] == "FinancialInvariantError"
    assert rows[0][4] == "FINANCIAL_INVARIANT"


def test_compression_policy_and_round_trip() -> None:
    """Verify zlib compression achieves high compression ratio and lossless recovery."""
    # Construct realistic synthetic log payload
    sample_log = (
        b"2026-10-22T21:00:00Z [INFO] Step 1: Processing ISIN INE002A01018 - 150 quotes\n"
        b"2026-10-22T21:00:01Z [INFO] Step 2: FIFO Lot matching complete, 42 lots mapped\n"
        b"2026-10-22T21:00:02Z [DEBUG] Cache hit on USDINR=X currency series\n"
    ) * 200

    compressed = compress_bytes(sample_log, level=DEFAULT_COMPRESSION_LEVEL)
    assert len(compressed) < len(sample_log) * 0.15, "Expected at least 85% compression ratio"

    decompressed = decompress_bytes(compressed)
    assert decompressed == sample_log


def test_trace_archival_and_retrieval(control_plane: ControlPlane, tmp_path: Path) -> None:
    """Verify end-to-end trace archival into Control Plane and retrieval."""
    run_id = control_plane.runs.start_run()
    trace_file = tmp_path / "run_execution.log"
    trace_content = b"2026-10-22 21:00:00 [INFO] Full pipeline run completed successfully.\n" * 50
    trace_file.write_bytes(trace_content)

    success = archive_run_trace(control_plane, run_id, str(trace_file))
    assert success is True

    # Retrieve and verify decompressed content
    retrieved = retrieve_run_trace(control_plane, run_id, decompress=True)
    assert retrieved == trace_content

    # Retrieve raw compressed bytes
    raw_blob = retrieve_run_trace(control_plane, run_id, decompress=False)
    assert raw_blob is not None
    assert len(raw_blob) < len(trace_content)

    # Verify status reflects execution log presence
    status = control_plane.runs.get_run_status(run_id)
    assert status is not None
    assert status["has_execution_log"] is True


def test_archival_non_fatal_on_missing_file(control_plane: ControlPlane) -> None:
    """Verify archive_run_trace degrades gracefully when file is missing."""
    run_id = control_plane.runs.start_run()
    success = archive_run_trace(control_plane, run_id, "non_existent_file.log")
    assert success is False


def test_archival_non_fatal_on_database_error(control_plane: ControlPlane, tmp_path: Path) -> None:
    """Verify archive_run_trace never raises exceptions if SQLite write fails."""
    run_id = control_plane.runs.start_run()
    trace_file = tmp_path / "valid.log"
    trace_file.write_bytes(b"sample log line")

    # Intentionally close connection to induce error
    control_plane.close()

    success = archive_run_trace(control_plane, run_id, str(trace_file))
    assert success is False


def test_zero_bracket_prefixes_in_control_plane() -> None:
    """Certify zero legacy bracket prefixes in control plane codebase."""
    bracket_regex = re.compile(r"\[(?:CONTROL_PLANE|PIPELINE|EXTRACT|PHASE).*?\]")
    base_dir = Path("src/personal_finance_etl/infrastructure/control_plane")

    violations: list[str] = []
    for py_path in base_dir.rglob("*.py"):
        content = py_path.read_text(encoding="utf-8")
        matches = bracket_regex.findall(content)
        if matches:
            violations.append(f"{py_path.name}: {matches}")

    assert not violations, f"Found legacy bracket prefixes in control_plane: {violations}"
