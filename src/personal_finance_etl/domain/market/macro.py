"""Macro parameters, holding period rules, and FY-specific rate lookups.

Owns
----
- FYMapEntry typing definition.
- Calendar-aware month addition with end-of-month clamping (add_months).
- Holding period calculation for LTCG/STCG threshold months.
- FYMacroParametersTable query interface for tax rates, exemptions, inflation, and risk-free rates.

Does not own
-------------
- Raw CSV extraction of macro parameters (owned by infrastructure.providers).
- Physical table insertion (owned by infrastructure.warehouse).
"""

import calendar
import logging
from collections.abc import Callable
from datetime import date
from typing import Any, TypedDict

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.common.dates import to_date_obj

logger = logging.getLogger(__name__)

_DEFAULT_DEBT_MF_CUTOFF = date(2023, 4, 1)


class FYMapEntry(TypedDict):
    """Structure for an indexed financial year entry."""

    start: date
    end: date
    debt_cutoff: date
    raw: dict[str, float | str | date | None]


def add_months(d: date, months: int) -> date:
    """Add months with end-of-month clamping.

    Parameters
    ----------
    d : date
        Base date.
    months : int
        Number of calendar months to add.

    Returns
    -------
    date
        Adjusted date with month-end boundary respected.
    """
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def get_ltcg_threshold_months(tax_type: str, tax_subtype: str, rules: FinancialRules | None) -> int:
    """Return holding period threshold for LTCG in calendar months based on declarative rules.

    Parameters
    ----------
    tax_type : str
        Tax classification type (e.g. "equity", "debt", "reit").
    tax_subtype : str
        Tax classification subtype (e.g. "listed", "unlisted", "foreign").
    rules : FinancialRules | None
        Authoritative financial rules configuration.

    Returns
    -------
    int
        Holding period threshold in months.
    """
    tt = tax_type.strip().lower()
    tst = tax_subtype.strip().lower()

    if tt == "equity" and tst in ("us_listed", "us_stocks", "foreign"):
        tst = "unlisted"

    thresholds = (
        rules.assumptions.tax.ltcg_threshold_months
        if rules and hasattr(rules, "assumptions")
        else {}
    )

    key = f"{tt}_{tst}"
    if key in thresholds:
        return thresholds[key]
    key_base = f"{tt}_"
    if key_base in thresholds:
        return thresholds[key_base]

    return 24  # Default 24 months


class FYMacroParametersTable:
    """Loads and queries Financial Year macro parameters."""

    _COL_MAP = {
        ("equity", "listed"): ("Equity_Listed_LTCG", "Equity_Listed_STCG"),
        ("equity", "unlisted"): ("Equity_Unlisted_LTCG", "Equity_Unlisted_STCG"),
        # Foreign listed equity (US stocks via LRS) — post-Budget 2024 treatment:
        #   LTCG (> 24 months): 12.5% concessional rate  → reuses Default_LTCG
        #   STCG (≤ 24 months): investor's income-tax slab rate → reuses Default_STCG
        # No dedicated CSV columns needed; Default_LTCG/STCG already carry these values.
        ("equity", "foreign"): ("Default_LTCG", "Default_STCG"),
        ("debt", "mf_pre"): ("Debt_MF_Pre_Cutoff_LTCG", "Debt_MF_Pre_Cutoff_STCG"),
        ("debt", "mf_post"): ("Debt_MF_Post_Cutoff_LTCG", "Debt_MF_Post_Cutoff_STCG"),
        ("debt", "other"): ("Other_Debt_LTCG", "Other_Debt_STCG"),
        ("reit", "listed"): ("REIT_LTCG", "REIT_STCG"),
        ("gold", ""): ("Gold_LTCG", "Gold_STCG"),
        ("sgb", ""): ("SGB_LTCG", "SGB_STCG"),
        ("default", ""): ("Default_LTCG", "Default_STCG"),
    }

    def __init__(self, df: pl.DataFrame, rules: FinancialRules):
        self.rules = rules
        self.fy_map: list[FYMapEntry] = []
        if df.is_empty():
            raise ValueError("Macro Parameters DataFrame cannot be empty.")

        for row in df.to_dicts():
            try:
                start_d = to_date_obj(row.get("FY_Start_Date"), strict=True)
                end_d = to_date_obj(row.get("FY_End_Date"), strict=True)
                if not start_d or not end_d:
                    raise ValueError(
                        f"FY_Start_Date and FY_End_Date are required for Financial Year row: {row}"
                    )

                raw_cutoff = str(row.get("Debt_MF_Cutoff_Date", "")).strip()

                default_cutoff = (
                    to_date_obj(self.rules.assumptions.tax.debt_mf_cutoff_date, strict=False)
                    if self.rules and hasattr(self.rules, "assumptions")
                    else _DEFAULT_DEBT_MF_CUTOFF
                )

                cutoff_d = (
                    to_date_obj(raw_cutoff, strict=True)
                    if raw_cutoff and raw_cutoff != "None"
                    else default_cutoff
                )

                self.fy_map.append(
                    {
                        "start": start_d,
                        "end": end_d,
                        "debt_cutoff": cutoff_d or default_cutoff or _DEFAULT_DEBT_MF_CUTOFF,
                        "raw": row,
                    }
                )
            except Exception as e:
                logger.error(f"Macro Parameters parsing error on row: {row}")
                logger.error(f"Error details: {e}")
                raise ValueError(
                    f"Malformed financial year parameters in row: {row}. Details: {e}"
                ) from e

        self.fy_map.sort(key=lambda x: x["start"])

    def _find_entry(self, ref_date: date) -> FYMapEntry | None:
        # Exact match
        for entry in reversed(self.fy_map):
            if entry["start"] <= ref_date <= entry["end"]:
                return entry
        # Nearest past entry
        for entry in reversed(self.fy_map):
            if entry["start"] <= ref_date:
                return entry
        # Nearest future entry (if date is before all defined FYs)
        if self.fy_map:
            return self.fy_map[0]
        return None

    _CLASSIFICATION_RULES: dict[str, Callable[[str, dict[str, Any]], tuple[str, str]]] = {
        "equity": lambda tst, _: (
            "equity",
            # Foreign equity subtypes get their own classification so they can be taxed
            # at slab rates via the dedicated Foreign_Equity_LTCG/STCG macro columns.
            # Domestically unlisted equity retains the "unlisted" classification.
            "foreign"
            if tst in ("us_listed", "us_stocks", "foreign", "us_equity")
            else "unlisted"
            if tst == "unlisted"
            else "listed",
        ),
        "reit": lambda tst, _: ("reit", "unlisted" if tst == "unlisted" else "listed"),
        "invit": lambda tst, _: ("invit", "unlisted" if tst == "unlisted" else "listed"),
        "gold": lambda tst, _: ("gold", ""),
        "sgb": lambda tst, _: ("sgb", ""),
        "debt": lambda tst, kwargs: (
            "debt",
            ("mf_post" if kwargs["lot_buy_date"] >= kwargs["debt_cutoff"] else "mf_pre")
            if tst in ("mf", "mutual_fund", "debt_mf")
            else "other",
        ),
    }

    def _classify(
        self, tax_type: str, tax_subtype: str, lot_buy_date: date, debt_cutoff: date
    ) -> tuple[str, str]:
        tt = tax_type.strip().lower()
        tst = tax_subtype.strip().lower()

        rule = self._CLASSIFICATION_RULES.get(tt)
        if rule:
            return rule(tst, {"lot_buy_date": lot_buy_date, "debt_cutoff": debt_cutoff})

        return ("default", "")

    def get_fy_string(self, ref_date: date) -> str:
        """Get the financial year string (e.g. '2023-24') for `ref_date`."""
        entry = self._find_entry(ref_date)
        return str(entry["raw"].get("FY", "UNKNOWN")) if entry else "UNKNOWN"

    def get_debt_mf_cutoff(self, ref_date: date) -> date:
        """Get the debt mutual fund taxation cutoff date applicable at `ref_date`."""
        entry = self._find_entry(ref_date)
        return entry["debt_cutoff"] if entry else _DEFAULT_DEBT_MF_CUTOFF

    def get_tax_rates(
        self, tax_type: str, tax_subtype: str, lot_buy_date: date, ref_date: date
    ) -> tuple[float, float]:
        """Get (LTCG_rate, STCG_rate) for the given asset and dates."""
        entry = self._find_entry(ref_date)
        cutoff = entry["debt_cutoff"] if entry else _DEFAULT_DEBT_MF_CUTOFF
        key = self._classify(tax_type, tax_subtype, lot_buy_date, cutoff)

        if entry is None:
            raise ValueError(f"No Tax Rate defined for FY encompassing date: {ref_date}")

        ltcg_col, stcg_col = self._COL_MAP.get(key, ("Default_LTCG", "Default_STCG"))
        raw = entry["raw"]
        try:
            ltcg_val = float(str(raw[ltcg_col]))
            stcg_val = float(str(raw[stcg_col]))
            return ltcg_val, stcg_val
        except (KeyError, TypeError, ValueError) as e:
            raise ValueError(
                f"Missing or invalid tax rate data for columns: {ltcg_col}, {stcg_col}"
            ) from e

    def get_equity_ltcg_exemption(self, ref_date: date) -> float:
        """Returns the annual LTCG exemption limit specifically for equity."""
        fallback = (
            self.rules.assumptions.tax.fallback_equity_ltcg_exemption
            if self.rules and hasattr(self.rules, "assumptions")
            else 125000.0
        )
        entry = self._find_entry(ref_date)
        if entry is None:
            return fallback
        raw = entry["raw"]
        val = raw.get("Equity_LTCG_Exemption")
        if val is None or str(val).strip() == "" or str(val).strip().lower() in ("none", "null"):
            return fallback
        try:
            return float(str(val).replace(",", "").strip())
        except (ValueError, TypeError) as err:
            logger.warning(
                "[MACRO] Unparseable Equity_LTCG_Exemption %r for date %s; using fallback %s: %s",
                val,
                ref_date,
                fallback,
                err,
            )
            return fallback

    def get_holding_type(
        self, tax_type: str, tax_subtype: str, lot_buy_date: date, ref_date: date
    ) -> str:
        """Determines whether a holding period qualifies as 'LTCG' or 'STCG'."""
        tt = tax_type.strip().lower()
        tst = tax_subtype.strip().lower()
        cutoff = self.get_debt_mf_cutoff(ref_date)
        if tt == "debt" and tst in ("mf", "mutual_fund", "debt_mf") and lot_buy_date >= cutoff:
            return "STCG"

        threshold_months = get_ltcg_threshold_months(tax_type, tax_subtype, self.rules)
        boundary_date = add_months(lot_buy_date, threshold_months)

        return "LTCG" if ref_date > boundary_date else "STCG"

    def get_risk_free_rate(self, ref_date: date) -> float:
        """Get the annualized risk-free interest rate for `ref_date`."""
        fallback = (
            self.rules.assumptions.macro.fallback_risk_free_rate
            if self.rules and hasattr(self.rules, "assumptions")
            else 0.05
        )
        entry = self._find_entry(ref_date)
        if entry is None:
            return fallback
        raw = entry["raw"]
        val = raw.get("Risk_Free_Rate")
        if val is None or str(val).strip() == "" or str(val).strip().lower() in ("none", "null"):
            return fallback
        try:
            return float(str(val).replace(",", "").strip())
        except (ValueError, TypeError) as err:
            logger.warning(
                "[MACRO] Unparseable Risk_Free_Rate %r for date %s; using fallback %s: %s",
                val,
                ref_date,
                fallback,
                err,
            )
            return fallback

    def get_inflation_rate(self, ref_date: date) -> float:
        """Get the annual inflation rate for `ref_date`."""
        fallback = (
            self.rules.assumptions.macro.fallback_inflation_rate
            if self.rules and hasattr(self.rules, "assumptions")
            else 0.05
        )
        entry = self._find_entry(ref_date)
        if entry is None:
            return fallback
        raw = entry["raw"]
        val = raw.get("Inflation_Rate")
        if val is None or str(val).strip() == "" or str(val).strip().lower() in ("none", "null"):
            return fallback
        try:
            return float(str(val).replace(",", "").strip())
        except (ValueError, TypeError) as err:
            logger.warning(
                "[MACRO] Unparseable Inflation_Rate %r for date %s; using fallback %s: %s",
                val,
                ref_date,
                fallback,
                err,
            )
            return fallback

    def get_ordinary_income_rate(self, ref_date: date) -> float:
        """Get the estimated ordinary income tax rate for `ref_date`."""
        fallback = (
            self.rules.assumptions.macro.fallback_ordinary_income_rate
            if self.rules and hasattr(self.rules, "assumptions")
            else 0.30
        )
        entry = self._find_entry(ref_date)
        if entry is None:
            return fallback
        raw = entry["raw"]
        val = raw.get("Estimated_Ordinary_Income_Tax_Rate")
        if val is None or str(val).strip() == "" or str(val).strip().lower() in ("none", "null"):
            return fallback
        try:
            return float(str(val).replace(",", "").strip())
        except (ValueError, TypeError) as err:
            logger.warning(
                "[MACRO] Unparseable Estimated_Ordinary_Income_Tax_Rate %r for date %s; using fallback %s: %s",
                val,
                ref_date,
                fallback,
                err,
            )
            return fallback
