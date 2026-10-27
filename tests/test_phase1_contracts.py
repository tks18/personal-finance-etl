# pylint: skip-file
# flake8: noqa
"""Tests for Phase 1 typed contracts across operational, application, and domain boundaries.

Owns
----
- Unit tests validating contract instantiation, invariant checking, alias mapping,
  and behavioral semantics for contracts/ and domain/investments/contracts.py.
"""

from datetime import date

import polars as pl
import pytest

from personal_finance_etl.contracts.application import (
    EngineExecutionResult,
    EngineStage,
)
from personal_finance_etl.contracts.extraction import (
    ExtractionBatchResult,
    ExtractionCompletenessError,
    ExtractorEntityResult,
    ExtractorEntityStatus,
)
from personal_finance_etl.contracts.lifecycle import (
    CommitState,
    FailureDomain,
    classify_failure_domain,
)
from personal_finance_etl.contracts.observability import DiagnosticSeverity
from personal_finance_etl.contracts.recovery import (
    RestoreOutcome,
    RestoreResult,
    SnapshotOutcome,
    SnapshotResult,
)
from personal_finance_etl.domain.common.calculation import (
    CagrResult,
    CalculationStatus,
    CpiResult,
    XirrResult,
)
from personal_finance_etl.domain.common.validation import (
    FinancialSourceValidationError,
)
from personal_finance_etl.domain.investments.contracts import (
    CashflowRecord,
    ISINProcessResult,
    ISINTags,
    RealizedEventRecord,
    ReconciliationEventRecord,
    TaxLot,
    TerminalValueRecord,
)
from personal_finance_etl.domain.market.fx import FXObservation

# ---------------------------------------------------------------------------
# Operational Contracts Tests
# ---------------------------------------------------------------------------


def test_commit_state_enum():
    assert CommitState.NOT_STARTED == "NOT_STARTED"
    assert CommitState.FULLY_COMMITTED == "FULLY_COMMITTED"
    assert CommitState.RECOVERY_REQUIRED == "RECOVERY_REQUIRED"


def test_classify_failure_domain():
    # Exception type checks
    val_err = FinancialSourceValidationError("Malformed date", source="Zerodha")
    assert classify_failure_domain("TRANSFORM", val_err) == FailureDomain.SOURCE_VALIDATION

    comp_err = ExtractionCompletenessError("Missing ticker", failed_entities={"INFY.NS": "error"})
    assert classify_failure_domain("EXTRACTION", comp_err) == FailureDomain.EXTERNAL_PROVIDER

    # Stage checks
    assert (
        classify_failure_domain("DUCKDB_COMMIT", Exception("Write error"))
        == FailureDomain.DUCKDB_COMMIT
    )
    assert (
        classify_failure_domain("SQLITE_COMMIT", Exception("Lock error"))
        == FailureDomain.SQLITE_COMMIT
    )
    assert classify_failure_domain("DISCOVERY") == FailureDomain.SOURCE_DISCOVERY
    assert classify_failure_domain("BRONZE_SYNC") == FailureDomain.BRONZE_SYNC
    assert classify_failure_domain("RECOVERY_STAGE") == FailureDomain.RECOVERY
    assert classify_failure_domain("SNAPSHOT_STAGE") == FailureDomain.SNAPSHOT
    assert classify_failure_domain("UNKNOWN_STAGE") == FailureDomain.UNKNOWN


def test_extraction_batch_result_contract():
    df1 = pl.DataFrame({"a": [1, 2]})
    df2 = pl.DataFrame({"a": [3, 4]})

    res1 = ExtractorEntityResult(
        entity="USD", status=ExtractorEntityStatus.SUCCESS, message="OK", df=df1
    )
    res2 = ExtractorEntityResult(
        entity="EUR", status=ExtractorEntityStatus.CACHED, message="Cached", df=df2
    )

    batch = ExtractionBatchResult(
        requested_entities=["USD", "EUR"],
        successful_entities=["USD"],
        cached_entities=["EUR"],
        frames=[df1, df2],
        entity_results=[res1, res2],
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )

    assert batch.is_complete is True
    assert batch.combined_frame.shape == (4, 1)

    # Legacy tuple unpacking support
    df_combined, injected = batch
    assert isinstance(df_combined, pl.DataFrame)
    assert isinstance(injected, list)
    assert df_combined.shape == (4, 1)
    assert injected == []

    # Completeness failure
    failed_batch = ExtractionBatchResult(
        failed_entities={"GBP": "API timeout"},
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 31),
    )
    assert failed_batch.is_complete is False
    with pytest.raises(ExtractionCompletenessError) as exc_info:
        failed_batch.assert_complete("CurrencyExtractor")
    assert "GBP" in str(exc_info.value)


def test_recovery_results():
    snap = SnapshotResult(
        outcome=SnapshotOutcome.SNAPSHOT_PUBLISHED,
        archive_path=None,
        files_archived=["raw.sqlite", "duckdb.db"],
        archive_size_bytes=1024,
    )
    assert snap.is_success is True

    restore = RestoreResult(
        outcome=RestoreOutcome.RESTORE_SUCCEEDED,
        source_archive=None,  # type: ignore[arg-type]
        files_restored=["duckdb.db"],
    )
    assert restore.is_success is True


def test_application_execution_result():
    assert EngineStage.TRANSFORMING.value == "TRANSFORMING"
    assert DiagnosticSeverity.INFO.value == "INFO"
    res = EngineExecutionResult(
        is_success=True,
        run_id="run_123",
        commit_state=CommitState.FULLY_COMMITTED,
        duration_seconds=12.5,
    )
    assert res.is_success is True
    assert res.commit_state == CommitState.FULLY_COMMITTED


# ---------------------------------------------------------------------------
# Domain Common Contracts Tests
# ---------------------------------------------------------------------------


def test_calculation_results():
    xirr_ok = XirrResult(value=0.15, status=CalculationStatus.VALID)
    assert xirr_ok.is_valid is True
    assert xirr_ok.as_float() == 0.15

    xirr_fail = XirrResult(value=None, status=CalculationStatus.NON_CONVERGENT)
    assert xirr_fail.is_valid is False
    assert xirr_fail.as_float(fallback=-1.0) == -1.0

    cagr_ok = CagrResult(value=0.12, status=CalculationStatus.VALID)
    assert cagr_ok.is_valid is True
    assert cagr_ok.as_float() == 0.12

    cpi_ok = CpiResult(value=180.5, status=CalculationStatus.VALID)
    assert cpi_ok.is_valid is True


def test_financial_source_validation_error():
    err = FinancialSourceValidationError(
        "Invalid number format",
        source="Excel_Bank",
        sheet="Accounts",
        field_name="Balance",
        raw_value="12,34.56.78",
        row_identifier=42,
    )
    msg = str(err)
    assert "Invalid number format" in msg
    assert "source=Excel_Bank" in msg
    assert "sheet=Accounts" in msg
    assert "field=Balance" in msg
    assert "row=42" in msg


def test_fx_observation():
    obs = FXObservation(rate=83.5, currency="USD", observation_date=date(2025, 1, 15))
    assert obs.is_missing is False
    assert obs.as_float() == 83.5

    obs_none = FXObservation(rate=None, currency="EUR", observation_date=date(2025, 1, 15))
    assert obs_none.is_missing is True
    assert obs_none.as_float(fallback=1.0) == 1.0


# ---------------------------------------------------------------------------
# Investment Domain Contracts Tests
# ---------------------------------------------------------------------------


def test_tax_lot_slots_and_immutability():
    lot = TaxLot(
        date=date(2024, 1, 10),
        qty=100.0,
        price=150.0,
        bm_buy=145.0,
        shadow_qty=100.0,
        currency_id="INR_INR",
        lot_id="LOT_123",
    )
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        lot.qty = 200.0  # type: ignore[misc]


def test_realized_event_record_aliases():
    # Test constructing from dictionary with established Polars/FIFO field names
    data = {
        "Realized_Event_ID": "REALIZED_abc123",
        "Sale_ID": "SALE_456",
        "Lot_ID": "LOT_789",
        "ISIN": "INE002A01018",
        "Disposal_Date": date(2024, 6, 1),
        "FY": "2024-2025",
        "Quantity_Disposed": 50.0,
        "Acquisition_Price": 100.0,
        "Disposed_Cost_Basis": 5000.0,
        "Sale_Price": 120.0,
        "Sale_Proceeds": 6000.0,
        "Realized_Gain_Loss": 1000.0,
        "Holding_Type": "LTCG",
        "Tax_Type": "equity",
        "Tax_Subtype": "listed_equity",
        "Applied_Rate": 0.125,
        "Estimated_Tax": 125.0,
    }
    event = RealizedEventRecord.model_validate(data)
    assert event.realized_event_id == "REALIZED_abc123"
    assert event.isin == "INE002A01018"
    assert event.realized_gain_loss == 1000.0
    assert event.holding_type == "LTCG"


def test_reconciliation_event_record_aliases():
    data = {
        "Reconciliation_Event_ID": "RECON_001",
        "Reconciliation_Group_ID": "GROUP_001",
        "ISIN": "INF209K01157",
        "Reconciliation_Date": date(2024, 12, 31),
        "Adjustment_Type": "QUANTITY_SURPLUS",
        "Reconstructed_Quantity": 100.0,
        "Observed_Quantity": 105.0,
        "Delta_Quantity": 5.0,
    }
    recon = ReconciliationEventRecord.model_validate(data)
    assert recon.recon_event_id == "RECON_001"
    assert recon.delta_qty == 5.0


def test_isin_process_result_and_pipeline_result():
    tags = ISINTags.model_validate(
        {
            "class": "Equity",
            "subtype": "Mutual Fund",
            "country": "India",
            "currency": "INR",
        }
    )
    cf = CashflowRecord(date=date(2024, 1, 1), amount=-1000.0)
    tv = TerminalValueRecord(val=1200.0)

    isin_res = ISINProcessResult(
        cashflows=[cf],
        terminals={date(2024, 12, 31): tv},
        realized_events=[],
        tags=tags,
    )
    assert len(isin_res.cashflows) == 1
    assert isin_res.tags.subtype == "Mutual Fund"
