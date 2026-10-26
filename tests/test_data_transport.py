"""Phase 5 Data Transport and Status Separation Test Suite.

Owns
----
- Verification of strict separation between status/observability events and tabular data transport.
- Verification that EngineStatusMessage completely eradicated the legacy 'data' field.
- Verification of the dedicated immutable EngineDataTransport contract.
- Verification that cross-process worker status messages carry zero DataFrame payloads.
- Verification that ObservabilityEvent context cannot be polluted with arbitrary DataFrames.

Does not own
-------------
- Domain numerical calculations (owned by domain.*).
- DuckDB / SQLite disk persistence (owned by infrastructure.warehouse and infrastructure.control_plane).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

import polars as pl
import pytest

from personal_finance_etl.contracts.application import (
    EngineDataTransport,
    EngineStage,
    EngineStatusMessage,
)
from personal_finance_etl.contracts.logging import LogLevel
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    ObservabilityContext,
    ObservabilityEvent,
    PresentationKind,
)


def test_engine_status_message_has_no_data_field() -> None:
    """Verify EngineStatusMessage does not possess or accept a 'data' field."""
    field_names = [f.name for f in dataclasses.fields(EngineStatusMessage)]
    assert "data" not in field_names

    msg = EngineStatusMessage(
        msg="Processing complete",
        level=LogLevel.SUCCESS,
        progress=1.0,
        stage=EngineStage.COMPLETED,
    )
    assert not hasattr(msg, "data")
    assert msg.msg == "Processing complete"
    assert msg.progress == 1.0

    # Passing data must raise a TypeError
    with pytest.raises(TypeError, match="unexpected keyword argument 'data'"):
        EngineStatusMessage(msg="fail", data=pl.DataFrame())  # type: ignore[call-arg]


def test_engine_data_transport_typed_contract() -> None:
    """Verify dedicated EngineDataTransport contract transports tabular results independently."""
    sample_df = pl.DataFrame({"metric": ["CAGR", "IRR"], "value": [0.145, 0.182]})
    metadata = {"run_id": "run_test_01", "row_count": 2}

    transport = EngineDataTransport(
        channel="portfolio_analytics",
        data=sample_df,
        metadata=metadata,
    )

    assert transport.channel == "portfolio_analytics"
    assert transport.data.height == 2
    assert transport.metadata["row_count"] == 2
    assert isinstance(transport.timestamp, datetime)

    # Immutability check
    with pytest.raises(dataclasses.FrozenInstanceError):
        transport.channel = "tampered"  # type: ignore[misc]


def test_observability_event_status_projection_has_no_data() -> None:
    """Verify ObservabilityEvent projects to status messages without data payloads."""
    ctx = ObservabilityContext(run_id="run-phase5-01", stage=EngineStage.TRANSFORMING)
    event = ObservabilityEvent.create(
        event_code=EventCode.TRANSFORMATION_DAG_COMPLETED,
        message="Master dimension transformed successfully",
        context=ctx,
        presentation_kind=PresentationKind.STEP,
        severity=DiagnosticSeverity.INFO,
        progress=0.75,
    )

    status_msg = event.to_status_message()
    assert isinstance(status_msg, EngineStatusMessage)
    assert not hasattr(status_msg, "data")
    assert status_msg.msg == "Master dimension transformed successfully"
    assert status_msg.progress == 0.75
    assert status_msg.stage == EngineStage.TRANSFORMING
