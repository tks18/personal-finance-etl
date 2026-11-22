"""Phase 5 Data Transport and Status Separation Test Suite.

Owns
----
- Verification of strict separation between status/observability events and tabular data transport.
- Verification that EngineStatusMessage was completely eradicated from contracts.
- Verification of the dedicated immutable EngineDataTransport contract.
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

import personal_finance_etl.contracts as contracts
import personal_finance_etl.contracts.application as app_contracts
from personal_finance_etl.contracts.application import (
    EngineDataTransport,
    EngineStage,
)
from personal_finance_etl.contracts.observability import (
    DiagnosticSeverity,
    EventCode,
    ObservabilityContext,
    ObservabilityEvent,
    PresentationKind,
)


def test_engine_status_message_completely_eradicated() -> None:
    """Verify EngineStatusMessage is eradicated and cannot be accessed from contracts."""
    assert not hasattr(contracts, "EngineStatusMessage")
    assert not hasattr(app_contracts, "EngineStatusMessage")


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


def test_observability_event_has_no_data_payload() -> None:
    """Verify ObservabilityEvent possesses zero data fields and rejects data kwargs."""
    ctx = ObservabilityContext(run_id="run-phase5-01", stage=EngineStage.TRANSFORMING)
    event = ObservabilityEvent.create(
        event_code=EventCode.TRANSFORMATION_DAG_COMPLETED,
        message="Master dimension transformed successfully",
        context=ctx,
        presentation_kind=PresentationKind.STEP,
        severity=DiagnosticSeverity.INFO,
        progress=0.75,
    )

    assert not hasattr(event, "data")
    assert not hasattr(event.context, "data")
    assert event.message == "Master dimension transformed successfully"
    assert event.progress == 0.75

    with pytest.raises(TypeError, match="unexpected keyword argument 'data'"):
        create_fn = getattr(ObservabilityEvent, "create")
        create_fn(
            event_code=EventCode.TRANSFORMATION_DAG_COMPLETED,
            message="failure",
            data=pl.DataFrame(),
        )
