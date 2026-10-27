"""Quant FIFO realized events normalization to canonical TaxEvents.

Owns
----
- normalize_quant_realized_events: Normalize authoritative Quant FIFO realized gains/losses.
- build_quant_tax_event: Transform single FIFO realized disposal event into typed TaxEventDict.
- resolve_quant_rates: Validate applied tax rate and estimated tax bounds.
- check_quant_status_reasons: Audit status and warning reasons for manual tax review.

Does not own
-------------
- Ledger income normalization (owned by domain.tax.events.builder).
- Statutory tax classification rules (owned by domain.tax.classification).
- Tax event identifier batch generation (owned by domain.tax.events.hashing).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date, datetime

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.dates import get_fy_string
from personal_finance_etl.domain.investments.contracts import RealizedEventDict
from personal_finance_etl.domain.tax.classification import TaxClassifier
from personal_finance_etl.domain.tax.estimates import TaxEstimator
from personal_finance_etl.domain.tax.events.schema import TaxEventDict

__all__ = [
    "build_quant_tax_event",
    "check_quant_status_reasons",
    "normalize_quant_realized_events",
    "quant_sub_head",
    "resolve_quant_rates",
]


def _clean_text(value: object) -> str | None:
    """Trim whitespace and normalize empty strings to None.

    Parameters
    ----------
    value : object
        Input string or object to sanitize.

    Returns
    -------
    str | None
        Stripped string, or None if the value is null or empty.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_id(value: object, field_name: str) -> str:
    """Validate and extract a non-empty identity string.

    Parameters
    ----------
    value : object
        Candidate identity value.
    field_name : str
        Field label for descriptive error messaging.

    Returns
    -------
    str
        Stripped identity string.

    Raises
    ------
    ValueError
        If the value is null or whitespace-only.
    """
    if value is None or not str(value).strip():
        raise ValueError(f"Required identity field {field_name} is missing.")
    return str(value).strip()


def _required_amount(value: object, field_name: str, source_id: object) -> float:
    """Validate and convert an input value into a finite float amount.

    Parameters
    ----------
    value : object
        Candidate numeric or string amount value.
    field_name : str
        Field label for error attribution.
    source_id : object
        Source transaction ID for diagnostic logging.

    Returns
    -------
    float
        Finite floating-point amount.

    Raises
    ------
    ValueError
        If value is boolean, non-numeric, null, or non-finite.
    """
    if value is None:
        raise ValueError(f"Required amount {field_name} is null for source {source_id!r}.")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(
            f"Required amount {field_name} is invalid for source {source_id!r}: {value!r}"
        )
    try:
        amount = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Required amount {field_name} is invalid for source {source_id!r}: {value!r}"
        ) from exc

    if not math.isfinite(amount):
        raise ValueError(f"Required amount {field_name} must be finite for source {source_id!r}.")
    return amount


def _as_date(value: object, field_name: str, source_id: object) -> date:
    """Parse and validate an arbitrary date representation into a Python date object.

    Parameters
    ----------
    value : object
        Candidate date object, datetime, or date string.
    field_name : str
        Field label for diagnostic context.
    source_id : object
        Source ID for error attribution.

    Returns
    -------
    date
        Validated date instance.

    Raises
    ------
    ValueError
        If value is null or cannot be cast into a valid date.
    """
    if value is None:
        raise ValueError(f"Required date {field_name} is null for source {source_id!r}.")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        parsed = pl.Series([value]).cast(pl.Date, strict=True).item()
    except Exception as exc:
        raise ValueError(
            f"Required date {field_name} is invalid for source {source_id!r}: {value!r}"
        ) from exc
    if not isinstance(parsed, date):
        raise ValueError(f"Required date {field_name} is null for source {source_id!r}.")
    return parsed


def resolve_quant_rates(
    row: Mapping[str, object],
    is_reconciliation: bool,
) -> tuple[float | None, float | None, bool]:
    """Extract and bound applied rate and estimated tax from Quant realized event.

    Parameters
    ----------
    row : Mapping[str, object]
        Quant realized event record.
    is_reconciliation : bool
        Whether lot originates from reconciliation.

    Returns
    -------
    tuple[float | None, float | None, bool]
        Tuple of (applied rate, estimated tax, whether rates are valid).
    """
    applied_rate = TaxEstimator.clean_optional_finite_number(row.get("Applied_Rate"))
    estimated_tax = TaxEstimator.clean_optional_finite_number(row.get("Estimated_Tax"))
    if applied_rate is not None and not 0.0 <= applied_rate <= 1.0:
        applied_rate = None
    if estimated_tax is not None and estimated_tax < 0:
        estimated_tax = None

    rates_valid = applied_rate is not None and estimated_tax is not None
    if is_reconciliation or not rates_valid:
        return None, None, rates_valid
    return applied_rate, estimated_tax, rates_valid


def check_quant_status_reasons(
    row: Mapping[str, object],
    is_reconciliation: bool,
    classification_known: bool,
    clean_curr: str | None,
    rates_valid: bool,
) -> list[str]:
    """Compile status warnings for Quant tax events requiring manual review.

    Parameters
    ----------
    row : Mapping[str, object]
        Raw realized event record.
    is_reconciliation : bool
        Flag indicating synthetic reconciliation lot.
    classification_known : bool
        Flag indicating standard tax classification matched.
    clean_curr : str | None
        Normalized currency string.
    rates_valid : bool
        Whether tax rate and estimate are valid.

    Returns
    -------
    list[str]
        List of warning reason strings.
    """
    status_reasons: list[str] = []
    if is_reconciliation:
        status_reasons.append("Reconciliation lot: original acquisition evidence requires review.")
    if not classification_known:
        status_reasons.append("Investment tax classification is unmapped or invalid.")
    if not _clean_text(row.get("ISIN")):
        status_reasons.append("ISIN is missing.")
    if not _clean_text(row.get("Lot_ID")):
        status_reasons.append("Lot_ID is missing.")
    if not clean_curr:
        status_reasons.append("Currency_ID is missing.")
    if not is_reconciliation and not rates_valid:
        status_reasons.append("Applied tax rate or estimated tax is unavailable or invalid.")
    return status_reasons


def quant_sub_head(
    row: RealizedEventDict | Mapping[str, object],
    rules: FinancialRules | None,
) -> tuple[str, bool]:
    """Map Quant instrument/holding metadata to configured evidence sub-head.

    Parameters
    ----------
    row : RealizedEventDict | Mapping[str, object]
        Realized event row.
    rules : FinancialRules | None
        Active financial rules configuration.

    Returns
    -------
    tuple[str, bool]
        Tuple of (sub-head category, whether classification is known).
    """
    cutoff = rules.assumptions.tax.debt_mf_cutoff_date if rules else None
    return TaxClassifier.map_quant_sub_head(row, debt_mf_cutoff_date=cutoff)


def build_quant_tax_event(
    row: Mapping[str, object],
    has_currency_id: bool,
    rules: FinancialRules | None,
) -> TaxEventDict:
    """Construct a strongly typed TaxEventDict from a Quant FIFO realized event row.

    Parameters
    ----------
    row : Mapping[str, object]
        Source Quant FIFO disposal event.
    has_currency_id : bool
        Whether Currency_ID column exists.
    rules : FinancialRules | None
        Active financial rules.

    Returns
    -------
    TaxEventDict
        Normalized canonical TaxEvent dictionary.
    """
    source_id = _required_id(row.get("Realized_Event_ID"), "Realized_Event_ID")
    event_date = _as_date(row.get("Disposal_Date"), "Quant Disposal_Date", source_id)
    amount = _required_amount(row.get("Realized_Gain_Loss"), "Realized_Gain_Loss", source_id)
    sub_head, classification_known = quant_sub_head(row, rules)
    is_reconciliation = str(row.get("Lot_Source_Type") or "").upper() == "RECONCILIATION"

    currency_val = row.get("Currency_ID") if has_currency_id else row.get("CURRENCY_ID")
    clean_curr = _clean_text(currency_val)

    applied_rate, estimated_tax, rates_valid = resolve_quant_rates(row, is_reconciliation)
    status_reasons = check_quant_status_reasons(
        row, is_reconciliation, classification_known, clean_curr, rates_valid
    )

    return {
        "FY": get_fy_string(event_date),
        "Event_Date": event_date,
        "Source_Type": "QUANT",
        "Source_ID": source_id,
        "Income_Head": "Capital Gains",
        "Tax_Sub_Head": sub_head,
        "Amount_INR": amount,
        "Applied_Rate": applied_rate,
        "Estimated_Tax": estimated_tax,
        "CURRENCY_ID": clean_curr,
        "Tax_Status": "CHECK_REQUIRED" if status_reasons else "READY",
        "Tax_Status_Reason": " ".join(status_reasons) or None,
        "ISIN": _clean_text(row.get("ISIN")),
        "Lot_ID": _clean_text(row.get("Lot_ID")),
    }


def normalize_quant_realized_events(
    df_realized_events: pl.DataFrame,
    rules: FinancialRules | None,
) -> list[TaxEventDict]:
    """Normalize authoritative Quant FIFO realized gains/losses into canonical TaxEvents.

    Parameters
    ----------
    df_realized_events : pl.DataFrame
        DataFrame of Quant realized disposal events.
    rules : FinancialRules | None
        Active financial rules configuration.

    Returns
    -------
    list[TaxEventDict]
        List of normalized TaxEvent dictionaries.
    """
    if df_realized_events.is_empty():
        return []
    required = {"Realized_Event_ID", "Disposal_Date", "Realized_Gain_Loss"}
    missing = sorted(required - set(df_realized_events.columns))
    if missing:
        raise ValueError(f"Quant realized events missing required columns: {missing}")

    has_currency_id = "Currency_ID" in df_realized_events.columns
    return [
        build_quant_tax_event(row, has_currency_id, rules) for row in df_realized_events.to_dicts()
    ]
