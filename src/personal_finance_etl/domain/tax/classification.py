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

from datetime import date, datetime
from typing import Any

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules, TaxHeadConfig
from personal_finance_etl.domain.common.dates import to_date_obj

__all__ = ["TaxClassifier"]


class TaxClassifier:
    """Classifies income transactions, tax credits, and investment gains into tax heads."""

    @staticmethod
    def map_quant_sub_head(
        row: dict[str, Any],
        debt_mf_cutoff_date: str | date | None = None,
    ) -> tuple[str, bool]:
        """Map Quant instrument/holding metadata to the configured evidence sub-head.

        Parameters
        ----------
        row : dict[str, Any]
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

        if tax_type == "equity" and subtype in {"listed", "direct", "direct_equity", ""}:
            prefix = "Equity_Listed"
        elif tax_type == "equity" and subtype == "unlisted":
            prefix = "Equity_Unlisted"
        elif tax_type == "equity" and subtype in {
            "foreign",
            "us_listed",
            "us_stocks",
            "us_equity",
            "international",
        }:
            prefix = "Default"
        elif tax_type == "debt":
            if subtype == "mf_pre":
                prefix = "Debt_MF_Pre_Cutoff"
            elif subtype == "mf_post":
                prefix = "Debt_MF_Post_Cutoff"
            elif subtype in {"mf", "mutual_fund", "debt_mf"}:
                acquisition_date = row.get("Acquisition_Date")
                if isinstance(acquisition_date, datetime):
                    acquisition_date = acquisition_date.date()
                elif acquisition_date is not None and not isinstance(acquisition_date, date):
                    try:
                        acquisition_date = to_date_obj(acquisition_date, strict=True)
                    except ValueError:
                        acquisition_date = None

                cutoff = (
                    to_date_obj(debt_mf_cutoff_date, strict=False)
                    if debt_mf_cutoff_date is not None
                    else None
                )
                if acquisition_date is None or cutoff is None:
                    return "CHECK_REQUIRED", False
                prefix = (
                    "Debt_MF_Pre_Cutoff" if acquisition_date < cutoff else "Debt_MF_Post_Cutoff"
                )
            elif subtype in {"bond", "debenture", "other_debt", "direct_debt"}:
                prefix = "Other_Debt"
            else:
                return "CHECK_REQUIRED", False
        elif tax_type == "reit":
            prefix = "REIT"
        elif tax_type == "gold":
            prefix = "Gold"
        elif tax_type == "sgb":
            prefix = "SGB"
        else:
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
