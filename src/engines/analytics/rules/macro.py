"""
Macro Parameters Rules Module.
Defines holding period thresholds and FY-specific rate lookups (tax, inflation, risk-free).
"""

from collections.abc import Callable
from datetime import date
from typing import Any, TypedDict

import polars as pl

from src.config.financial_rules import FinancialRules
from src.utils.helpers import to_date_obj

_DEFAULT_DEBT_MF_CUTOFF = date(2023, 4, 1)


class FYMapEntry(TypedDict):
    start: date
    end: date
    debt_cutoff: date
    raw: dict[str, float | str | date | None]


def get_ltcg_threshold(tax_type: str, tax_subtype: str, rules: FinancialRules | None) -> int:
    """Return holding period threshold for LTCG in days based on declarative rules."""
    tt = tax_type.strip().lower()
    tst = tax_subtype.strip().lower()

    thresholds = (
        rules.assumptions.tax.ltcg_thresholds if rules and hasattr(rules, "assumptions") else {}
    )

    key = f"{tt}_{tst}"
    if key in thresholds:
        return thresholds[key]
    key_base = f"{tt}_"
    if key_base in thresholds:
        return thresholds[key_base]

    return 730


class FYMacroParametersTable:
    """Loads and queries Financial Year macro parameters."""

    _COL_MAP = {
        ("equity", "listed"): ("Equity_Listed_LTCG", "Equity_Listed_STCG"),
        ("equity", "unlisted"): ("Equity_Unlisted_LTCG", "Equity_Unlisted_STCG"),
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
                start_d = to_date_obj(row.get("FY_Start_Date"))
                end_d = to_date_obj(row.get("FY_End_Date"))

                raw_cutoff = str(row.get("Debt_MF_Cutoff_Date", "")).strip()

                default_cutoff = (
                    to_date_obj(self.rules.assumptions.tax.debt_mf_cutoff_date)
                    if self.rules and hasattr(self.rules, "assumptions")
                    else _DEFAULT_DEBT_MF_CUTOFF
                )

                cutoff_d = (
                    to_date_obj(raw_cutoff)
                    if raw_cutoff and raw_cutoff != "None"
                    else default_cutoff
                )

                if start_d and end_d:
                    self.fy_map.append(
                        {
                            "start": start_d,
                            "end": end_d,
                            "debt_cutoff": cutoff_d or default_cutoff or _DEFAULT_DEBT_MF_CUTOFF,
                            "raw": row,
                        }
                    )
            except Exception as e:
                print(f"Macro Parameters parsing error on row: {row}")
                print(f"Error details: {e}")

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
        "equity": lambda tst, _: ("equity", "unlisted" if tst == "unlisted" else "listed"),
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

    def get_debt_mf_cutoff(self, ref_date: date) -> date:
        entry = self._find_entry(ref_date)
        return entry["debt_cutoff"] if entry else _DEFAULT_DEBT_MF_CUTOFF

    def get_tax_rates(
        self, tax_type: str, tax_subtype: str, lot_buy_date: date, ref_date: date
    ) -> tuple[float, float]:
        entry = self._find_entry(ref_date)
        cutoff = entry["debt_cutoff"] if entry else _DEFAULT_DEBT_MF_CUTOFF
        key = self._classify(tax_type, tax_subtype, lot_buy_date, cutoff)

        if entry is None:
            raise ValueError(f"No Tax Rate defined for FY encompassing date: {ref_date}")

        ltcg_col, stcg_col = self._COL_MAP.get(key, ("Default_LTCG", "Default_STCG"))
        raw = entry["raw"]
        try:
            return float(str(raw[ltcg_col])), float(str(raw[stcg_col]))
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
        try:
            val = raw.get("Equity_LTCG_Exemption")
            return float(str(val)) if val is not None and str(val).strip() != "" else fallback
        except (ValueError, TypeError):
            return fallback

    def get_holding_type(
        self, age_days: int, tax_type: str, tax_subtype: str, lot_buy_date: date, ref_date: date
    ) -> str:
        tt = tax_type.strip().lower()
        tst = tax_subtype.strip().lower()
        cutoff = self.get_debt_mf_cutoff(ref_date)
        if tt == "debt" and tst in ("mf", "mutual_fund", "debt_mf") and lot_buy_date >= cutoff:
            return "STCG"
        return (
            "LTCG" if age_days > get_ltcg_threshold(tax_type, tax_subtype, self.rules) else "STCG"
        )

    def get_risk_free_rate(self, ref_date: date) -> float:
        fallback = (
            self.rules.assumptions.macro.fallback_risk_free_rate
            if self.rules and hasattr(self.rules, "assumptions")
            else 0.05
        )
        entry = self._find_entry(ref_date)
        if entry is None:
            return fallback
        raw = entry["raw"]
        try:
            val = raw.get("Risk_Free_Rate")
            return float(str(val)) if val is not None and str(val).strip() != "" else fallback
        except (ValueError, TypeError):
            return fallback

    def get_inflation_rate(self, ref_date: date) -> float:
        fallback = (
            self.rules.assumptions.macro.fallback_inflation_rate
            if self.rules and hasattr(self.rules, "assumptions")
            else 0.05
        )
        entry = self._find_entry(ref_date)
        if entry is None:
            return fallback
        raw = entry["raw"]
        try:
            val = raw.get("Inflation_Rate")
            return float(str(val)) if val is not None and str(val).strip() != "" else fallback
        except (ValueError, TypeError):
            return fallback
