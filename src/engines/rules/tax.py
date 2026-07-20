"""
Tax Rules Module.
Defines all holding period thresholds and FY-specific rate lookups.
"""

from datetime import date
import polars as pl
from src.utils.helpers import to_date_obj

_DEFAULT_DEBT_MF_CUTOFF = date(2023, 4, 1)


def get_ltcg_threshold(tax_type: str, tax_subtype: str) -> int:
    """Return holding period threshold for LTCG in days."""
    tt = tax_type.strip().lower()
    tst = tax_subtype.strip().lower()

    if tt == "equity":
        return 365 if tst == "listed" else 730
    elif tt == "debt":
        return 1095
    elif tt == "gold" or tt == "sgb":
        return 730 if tst == "mf" else 365
    elif tt == "silver":
        return 730 if tst == "mf" else 365
    return 730


class FYTaxRateTable:
    """Loads and queries Financial Year tax rates."""

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

    def __init__(self, df: pl.DataFrame):
        self.fy_map: list[dict] = []
        if df.is_empty():
            raise ValueError("Tax Rates DataFrame cannot be empty.")

        for row in df.to_dicts():
            try:
                start_d = to_date_obj(row.get("FY_Start_Date"))
                end_d = to_date_obj(row.get("FY_End_Date"))

                raw_cutoff = str(row.get("Debt_MF_Cutoff_Date", "")).strip()
                cutoff_d = to_date_obj(
                    raw_cutoff) if raw_cutoff and raw_cutoff != "None" else _DEFAULT_DEBT_MF_CUTOFF

                if start_d and end_d:
                    self.fy_map.append({
                        "start": start_d, "end": end_d,
                        "debt_cutoff": cutoff_d or _DEFAULT_DEBT_MF_CUTOFF, "raw": row
                    })
            except Exception as e:
                print(f"Tax Rates parsing error on row: {row}")
                print(f"Error details: {e}")

        self.fy_map.sort(key=lambda x: x["start"])

    def _find_entry(self, ref_date: date) -> dict | None:
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

    def _classify(self, tax_type: str, tax_subtype: str, lot_buy_date: date, debt_cutoff: date) -> tuple[str, str]:
        tt = tax_type.strip().lower()
        tst = tax_subtype.strip().lower()
        if tt in ("equity", "reit", "invit"):
            return (tt, "listed" if tst != "unlisted" else "unlisted")
        if tt in ("gold", "sgb"):
            return (tt, "")
        if tt == "debt":
            if tst in ("mf", "mutual_fund", "debt_mf"):
                return ("debt", "mf_post" if lot_buy_date >= debt_cutoff else "mf_pre")
            return ("debt", "other")
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
            raise ValueError(
                f"No Tax Rate defined for FY encompassing date: {ref_date}")

        ltcg_col, stcg_col = self._COL_MAP.get(
            key, ("Default_LTCG", "Default_STCG"))
        raw = entry["raw"]
        try:
            return float(raw[ltcg_col]), float(raw[stcg_col])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                f"Missing or invalid tax rate data for columns: {ltcg_col}, {stcg_col}")

    def get_equity_ltcg_exemption(self, ref_date: date) -> float:
        """Returns the annual LTCG exemption limit specifically for equity."""
        entry = self._find_entry(ref_date)
        if entry is None:
            return 125_000.0
        raw = entry["raw"]
        try:
            val = raw.get("Equity_LTCG_Exemption")
            return float(val) if val is not None and str(val).strip() != "" else 125_000.0
        except (ValueError, TypeError):
            return 125_000.0

    def get_holding_type(
        self, age_days: int, tax_type: str, tax_subtype: str, lot_buy_date: date, ref_date: date
    ) -> str:
        tt = tax_type.strip().lower()
        tst = tax_subtype.strip().lower()
        cutoff = self.get_debt_mf_cutoff(ref_date)
        if tt == "debt" and tst in ("mf", "mutual_fund", "debt_mf") and lot_buy_date >= cutoff:
            return "STCG"
        return "LTCG" if age_days > get_ltcg_threshold(tax_type, tax_subtype) else "STCG"
