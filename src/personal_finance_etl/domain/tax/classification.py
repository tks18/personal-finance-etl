"""Tax income head, sub-head, and credit classification domain rules.

Owns
----
- TaxClassifier: Maps instrument metadata and ledger subcategories to statutory tax sub-heads.
- Validation of tax credit UIDs and subcategory dimension keys.
- Determination of pre/post-cutoff debt mutual fund classifications.

Does not own
-------------
- Tax rate resolution or monetary estimation (owned by domain.tax.estimates).
- TaxEvent construction or ID generation (owned by domain.tax.events).
- Gold aggregation tables (owned by domain.tax.reconciliation).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules, TaxHeadConfig
from personal_finance_etl.domain.common.dates import to_date_obj
from personal_finance_etl.domain.investments.contracts import RealizedEventDict

__all__ = ["TaxClassifier"]


_EQUITY_PREFIX_MAP: dict[str, str] = {
    "listed": "Equity_Listed",
    "direct": "Equity_Listed",
    "direct_equity": "Equity_Listed",
    "": "Equity_Listed",
    "unlisted": "Equity_Unlisted",
    "foreign": "Default",
    "us_listed": "Default",
    "us_stocks": "Default",
    "us_equity": "Default",
    "international": "Default",
}

_DIRECT_TYPE_PREFIX_MAP: dict[str, str] = {
    "reit": "REIT",
    "gold": "Gold",
    "sgb": "SGB",
}


class TaxClassifier:
    """Classifies income transactions, tax credits, and investment gains into tax heads."""

    @staticmethod
    def _parse_acquisition_date(acquisition_date: object) -> date | None:
        """Extract date object from date, datetime, or date string."""
        if isinstance(acquisition_date, datetime):
            return acquisition_date.date()
        if isinstance(acquisition_date, str):
            try:
                return to_date_obj(acquisition_date, strict=True)
            except ValueError:
                return None
        if isinstance(acquisition_date, date):
            return acquisition_date
        return None

    @classmethod
    def _resolve_debt_mf_prefix(
        cls,
        row: RealizedEventDict | Mapping[str, object],
        debt_mf_cutoff_date: str | date | None,
    ) -> str | None:
        """Determine pre or post cutoff tax prefix for debt mutual funds."""
        acq_date = cls._parse_acquisition_date(row.get("Acquisition_Date"))
        cutoff = (
            to_date_obj(debt_mf_cutoff_date, strict=False)
            if debt_mf_cutoff_date is not None
            else None
        )
        if acq_date is None or cutoff is None:
            return None
        return "Debt_MF_Pre_Cutoff" if acq_date < cutoff else "Debt_MF_Post_Cutoff"

    @classmethod
    def _resolve_debt_prefix(
        cls,
        row: RealizedEventDict | Mapping[str, object],
        subtype: str,
        debt_mf_cutoff_date: str | date | None,
    ) -> str | None:
        """Resolve statutory tax prefix for debt holdings against optional MF cutoff date."""
        if subtype == "mf_pre":
            return "Debt_MF_Pre_Cutoff"
        if subtype == "mf_post":
            return "Debt_MF_Post_Cutoff"
        if subtype in {"bond", "debenture", "other_debt", "direct_debt"}:
            return "Other_Debt"
        if subtype in {"mf", "mutual_fund", "debt_mf"}:
            return cls._resolve_debt_mf_prefix(row, debt_mf_cutoff_date)
        return None

    @classmethod
    def _resolve_instrument_prefix(
        cls,
        row: RealizedEventDict | Mapping[str, object],
        tax_type: str,
        subtype: str,
        debt_mf_cutoff_date: str | date | None,
    ) -> str | None:
        """Lookup or resolve statutory tax prefix based on asset type."""
        if tax_type == "equity":
            return _EQUITY_PREFIX_MAP.get(subtype)
        if tax_type == "debt":
            return cls._resolve_debt_prefix(row, subtype, debt_mf_cutoff_date)
        return _DIRECT_TYPE_PREFIX_MAP.get(tax_type)

    @classmethod
    def map_quant_sub_head(
        cls,
        row: RealizedEventDict | Mapping[str, object],
        debt_mf_cutoff_date: str | date | None = None,
    ) -> tuple[str, bool]:
        """Map Quant instrument/holding metadata to the configured evidence sub-head.

        Parameters
        ----------
        row : RealizedEventDict | Mapping[str, object]
            Realized event record dictionary.
        debt_mf_cutoff_date : str | date | None, optional
            Configured statutory cutoff date for debt mutual funds.

        Returns
        -------
        tuple[str, bool]
            Tuple of (tax_sub_head, classification_known).
        """
        tax_type = str(row.get("Tax_Type") or row.get("tax_type") or "").strip().lower()
        subtype = str(row.get("Tax_Subtype") or row.get("tax_subtype") or "").strip().lower()
        holding_raw = str(row.get("Holding_Type") or row.get("gain_type") or "").strip().upper()
        holding = {"STCG": "ST", "LTCG": "LT", "ST": "ST", "LT": "LT"}.get(holding_raw)
        if holding is None:
            return "CHECK_REQUIRED", False

        prefix = cls._resolve_instrument_prefix(row, tax_type, subtype, debt_mf_cutoff_date)
        if prefix is None:
            return "CHECK_REQUIRED", False

        return f"{prefix}_{holding}CG", True

    @staticmethod
    def build_tax_credit_subhead_map(rules: FinancialRules) -> dict[str, str]:
        """Map configured tax-credit subcategory UIDs to their declared tax sub-head."""
        mapping: dict[str, str] = {}
        all_heads: list[tuple[str, TaxHeadConfig]] = []
        all_heads.extend(rules.assumptions.tax.heads_of_income.items())
        all_heads.extend(rules.assumptions.tax.exempt_income.items())
        all_heads.extend(rules.assumptions.tax.residual_income.items())
        for head_name, head_config in all_heads:
            for sub_head, config in head_config.sub_heads.items():
                for uid in config.tax_credit_sub_cat_ids:
                    if uid in mapping:
                        raise ValueError(
                            f"Tax-credit subcategory UID {uid!r} is configured more than once."
                        )
                    mapping[uid] = config.sub_head_display_name or sub_head or head_name
        return mapping

    @staticmethod
    def validate_tax_credit_uids(
        df_subcategory: pl.DataFrame,
        credit_subheads: dict[str, str],
    ) -> None:
        """Validate that all configured tax credit UIDs exist in the subcategory dimension."""
        available = {
            str(uid).strip()
            for uid in df_subcategory.get_column("UID").drop_nulls().to_list()
            if str(uid).strip()
        }
        unknown = sorted(set(credit_subheads) - available)
        if unknown:
            raise ValueError(
                "Configured tax-credit subcategory UID(s) do not exist in "
                f"silver.d_Income_Subcategory: {unknown}"
            )

    @staticmethod
    def validate_subcategory_dimension(df_subcategory: pl.DataFrame) -> None:
        """Reject ambiguous subcategory dimension keys before building lookups."""
        if "UID" not in df_subcategory.columns:
            raise ValueError("Income subcategory dimension must contain UID.")
        uids = [
            str(uid).strip()
            for uid in df_subcategory.get_column("UID").drop_nulls().to_list()
            if str(uid).strip()
        ]
        seen: set[str] = set()
        duplicates: set[str] = set()
        for uid in uids:
            if uid in seen:
                duplicates.add(uid)
            seen.add(uid)
        if duplicates:
            raise ValueError(
                f"Income subcategory dimension contains duplicate UID(s): {sorted(duplicates)}"
            )
