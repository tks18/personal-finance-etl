from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules, TaxHeadConfig
from personal_finance_etl.backend.engines.analytics.rules.macro import FYMacroParametersTable
from personal_finance_etl.backend.utils.identity import generate_deterministic_id

TAX_EVENT_SCHEMA: dict[str, pl.DataType] = {
    "Tax_Event_ID": pl.String(),
    "FY": pl.String(),
    "Event_Date": pl.Date(),
    "Source_Type": pl.String(),
    "Source_ID": pl.String(),
    "Income_Head": pl.String(),
    "Tax_Sub_Head": pl.String(),
    "Amount_INR": pl.Float64(),
    "Applied_Rate": pl.Float64(),
    "Estimated_Tax": pl.Float64(),
    "CURRENCY_ID": pl.String(),
    "Tax_Status": pl.String(),
    "Tax_Status_Reason": pl.String(),
    "ISIN": pl.String(),
    "Lot_ID": pl.String(),
}


def _batch_compute_tax_event_ids(s: pl.Series) -> pl.Series:
    source_types = s.struct.field("Source_Type")
    source_ids = s.struct.field("Source_ID")
    sub_heads = s.struct.field("Tax_Sub_Head")
    ids = [
        generate_deterministic_id(
            "TAX",
            {
                "Source_Type": st,
                "Source_ID": sid,
                "Tax_Sub_Head": tsh,
            },
        )
        for st, sid, tsh in zip(source_types, source_ids, sub_heads, strict=False)
    ]
    return pl.Series(ids, dtype=pl.String)


class BaseEventsBuilder:
    """Normalize ledger, tax-credit and Quant FIFO evidence into canonical TaxEvents.

    The builder carries FIFO-provided investment estimates and calculates indicative
    ledger estimates using the configured ordinary-income rate. It does not calculate
    final statutory liability or apply annual set-off/credit rules.
    """

    def __init__(
        self,
        df_income: pl.DataFrame,
        df_realized_events: pl.DataFrame,
        df_subcategory: pl.DataFrame,
        rules: FinancialRules | None,
        df_macro_parameters: pl.DataFrame | None = None,
    ) -> None:
        self.df_income = df_income
        self.df_realized_events = df_realized_events
        self.df_subcategory = df_subcategory
        self.rules = rules
        self.macro_table = (
            FYMacroParametersTable(df_macro_parameters, rules=rules)
            if rules is not None
            and df_macro_parameters is not None
            and not df_macro_parameters.is_empty()
            else None
        )

    def build(self) -> pl.LazyFrame:
        """Return validated, deterministic TaxEvents as a LazyFrame."""
        if self.rules is None:
            raise ValueError("FinancialRules are required to build canonical TaxEvents.")

        self._validate_subcategory_dimension()
        self.rules.validate_investment_exclusion_uids(self.df_subcategory)
        credit_subheads = self._tax_credit_subhead_map()
        self._validate_tax_credit_uids(credit_subheads)
        configured_exclusions = set(
            self.rules.assumptions.tax.investment_exclusions.stcg_sub_cat_ids
            + self.rules.assumptions.tax.investment_exclusions.ltcg_sub_cat_ids
        )
        credit_overlap = sorted(configured_exclusions.intersection(credit_subheads))
        if credit_overlap:
            raise ValueError(
                "A subcategory UID cannot be both an investment-gain exclusion and a tax credit: "
                f"{credit_overlap}"
            )

        df_ledger = self._normalize_ledger_income(credit_subheads)
        df_credits = self._normalize_tax_credits(credit_subheads)
        quant_records = self._normalize_quant_realized_events()
        base_schema = {c: TAX_EVENT_SCHEMA[c] for c in TAX_EVENT_SCHEMA if c != "Tax_Event_ID"}
        df_quant = (
            pl.DataFrame(quant_records, schema=base_schema, strict=False)
            if quant_records
            else pl.DataFrame(schema=base_schema)
        )

        frames = [f for f in (df_ledger, df_credits, df_quant) if not f.is_empty()]
        if not frames:
            return pl.DataFrame(schema=TAX_EVENT_SCHEMA).lazy()

        df = pl.concat(frames, how="vertical_relaxed")
        df = df.with_columns(
            pl.struct(["Source_Type", "Source_ID", "Tax_Sub_Head"])
            .map_batches(_batch_compute_tax_event_ids, return_dtype=pl.String)
            .alias("Tax_Event_ID")
        )
        self._validate_event_keys(df)
        return (
            df.select(list(TAX_EVENT_SCHEMA.keys()))
            .sort(["FY", "Event_Date", "Source_Type", "Source_ID", "Tax_Sub_Head"])
            .lazy()
        )

    def _tax_credit_subhead_map(self) -> dict[str, str]:
        """Map configured tax-credit subcategory UIDs to their declared tax sub-head."""
        assert self.rules is not None
        mapping: dict[str, str] = {}
        all_heads: list[tuple[str, TaxHeadConfig]] = []
        all_heads.extend(self.rules.assumptions.tax.heads_of_income.items())
        all_heads.extend(self.rules.assumptions.tax.exempt_income.items())
        all_heads.extend(self.rules.assumptions.tax.residual_income.items())
        for head_name, head_config in all_heads:
            for sub_head, config in head_config.sub_heads.items():
                for uid in config.tax_credit_sub_cat_ids:
                    if uid in mapping:
                        raise ValueError(
                            f"Tax-credit subcategory UID {uid!r} is configured more than once."
                        )
                    mapping[uid] = config.sub_head_display_name or sub_head or head_name
        return mapping

    def _validate_tax_credit_uids(self, credit_subheads: dict[str, str]) -> None:
        available = {
            str(uid).strip()
            for uid in self.df_subcategory.get_column("UID").drop_nulls().to_list()
            if str(uid).strip()
        }
        unknown = sorted(set(credit_subheads) - available)
        if unknown:
            raise ValueError(
                "Configured tax-credit subcategory UID(s) do not exist in "
                f"silver.d_Income_Subcategory: {unknown}"
            )

    def _normalize_ledger_income(self, credit_subheads: dict[str, str]) -> pl.DataFrame:
        required = {"UID", "DATE", "CATEGORY_ID", "BASE_AMOUNT"}
        missing = sorted(required - set(self.df_income.columns))
        if missing:
            raise ValueError(f"Income transactions missing required columns: {missing}")
        if self.df_income.is_empty():
            return pl.DataFrame(schema=TAX_EVENT_SCHEMA)

        sub_cols = [
            c
            for c in (
                "UID",
                "Tax_Income_Head",
                "Tax_Sub_Head",
                "Taxability",
                "Tax_Method",
                "Is_Investment_Exclusion",
                "Is_Tax_Credits",
            )
            if c in self.df_subcategory.columns
        ]
        if "UID" not in sub_cols:
            raise ValueError("Income subcategory dimension must contain UID.")

        excluded: set[str] = set()
        if self.rules is not None:
            exclusions = self.rules.assumptions.tax.investment_exclusions
            excluded.update(exclusions.stcg_sub_cat_ids)
            excluded.update(exclusions.ltcg_sub_cat_ids)

        df_sub = self.df_subcategory.select(sub_cols)
        df_inc = self.df_income.with_columns(
            pl.col("CATEGORY_ID")
            .cast(pl.String)
            .str.strip_chars()
            .fill_null("")
            .alias("_clean_cat_id"),
            pl.col("UID").cast(pl.String).str.strip_chars().alias("Source_ID"),
        )
        if df_inc["Source_ID"].is_null().any() or (df_inc["Source_ID"] == "").any():
            raise ValueError("Required identifier income UID is null or empty.")

        df_joined = df_inc.join(
            df_sub.with_columns(pl.col("UID").cast(pl.String).str.strip_chars()),
            left_on="_clean_cat_id",
            right_on="UID",
            how="left",
        )

        is_inv_excl = (
            pl.col("Is_Investment_Exclusion").fill_null(False)
            if "Is_Investment_Exclusion" in df_joined.columns
            else pl.lit(False)
        )
        is_tax_credit = (
            pl.col("Is_Tax_Credits").fill_null(False)
            if "Is_Tax_Credits" in df_joined.columns
            else pl.lit(False)
        )
        taxability_clean = (
            pl.col("Taxability")
            .cast(pl.String)
            .str.strip_chars()
            .str.to_lowercase()
            .fill_null("review")
        )

        df_filtered = df_joined.filter(
            (~pl.col("_clean_cat_id").is_in(list(excluded)))
            & (~pl.col("_clean_cat_id").is_in(list(credit_subheads.keys())))
            & (~is_inv_excl)
            & (~is_tax_credit)
            & (taxability_clean != "non_taxable")
        )
        if df_filtered.is_empty():
            return pl.DataFrame(schema=TAX_EVENT_SCHEMA)

        amount_col = df_filtered.get_column("BASE_AMOUNT")
        if amount_col.dtype == pl.Boolean:
            bad_id = str(df_filtered.get_column("Source_ID")[0])
            raise ValueError(
                f"Required amount BASE_AMOUNT cannot be boolean for source {bad_id!r}."
            )
        try:
            df_filtered = df_filtered.with_columns(
                pl.col("BASE_AMOUNT").cast(pl.Float64, strict=True).alias("Amount_INR")
            )
        except Exception as exc:
            bad_id = str(df_filtered.get_column("Source_ID")[0])
            raise ValueError(
                f"Required amount BASE_AMOUNT is invalid for source {bad_id!r}: {exc}"
            ) from exc

        if (
            df_filtered["Amount_INR"].is_nan().any()
            or df_filtered["Amount_INR"].is_infinite().any()
        ):
            bad_idx = (
                df_filtered["Amount_INR"].is_nan() | df_filtered["Amount_INR"].is_infinite()
            ).arg_true()[0]
            bad_id = str(df_filtered.get_column("Source_ID")[bad_idx])
            raise ValueError(f"Required amount BASE_AMOUNT must be finite for source {bad_id!r}.")

        if df_filtered["DATE"].is_null().any():
            bad_idx = df_filtered["DATE"].is_null().arg_true()[0]
            bad_id = str(df_filtered.get_column("Source_ID")[bad_idx])
            raise ValueError(f"Required date income DATE is null for source {bad_id!r}.")

        if df_filtered["DATE"].dtype == pl.Datetime:
            df_filtered = df_filtered.with_columns(pl.col("DATE").dt.date().alias("Event_Date"))
        elif df_filtered["DATE"].dtype == pl.Date:
            df_filtered = df_filtered.with_columns(pl.col("DATE").alias("Event_Date"))
        else:
            try:
                df_filtered = df_filtered.with_columns(
                    pl.col("DATE").cast(pl.Date, strict=True).alias("Event_Date")
                )
            except Exception as exc:
                bad_id = str(df_filtered.get_column("Source_ID")[0])
                raise ValueError(
                    f"Required date income DATE is invalid for source {bad_id!r}: {exc}"
                ) from exc

        fy_expr = (
            pl.when(pl.col("Event_Date").dt.month() >= 4)
            .then(
                pl.col("Event_Date").dt.year().cast(pl.String)
                + "-"
                + ((pl.col("Event_Date").dt.year() + 1) % 100).cast(pl.String).str.zfill(2)
            )
            .otherwise(
                (pl.col("Event_Date").dt.year() - 1).cast(pl.String)
                + "-"
                + (pl.col("Event_Date").dt.year() % 100).cast(pl.String).str.zfill(2)
            )
            .alias("FY")
        )

        unique_dates = df_filtered["Event_Date"].unique().to_list()
        date_rate_map = {d: self._ordinary_income_rate(d) for d in unique_dates if d is not None}
        applied_rate_expr = pl.col("Event_Date").replace_strict(
            date_rate_map, default=None, return_dtype=pl.Float64
        )

        income_head_expr = pl.col("Tax_Income_Head").cast(pl.String).str.strip_chars()
        tax_sub_head_expr = pl.col("Tax_Sub_Head").cast(pl.String).str.strip_chars()

        is_incomplete = (
            income_head_expr.is_null()
            | (income_head_expr == "")
            | (income_head_expr == "CHECK_REQUIRED")
            | tax_sub_head_expr.is_null()
            | (tax_sub_head_expr == "")
            | (tax_sub_head_expr == "CHECK_REQUIRED")
            | (taxability_clean != "taxable")
            | applied_rate_expr.is_null()
        )

        estimated_tax_expr = (
            pl.when(~is_incomplete & (pl.col("Amount_INR") > 0.0))
            .then(pl.col("Amount_INR") * applied_rate_expr)
            .when(~is_incomplete)
            .then(0.0)
            .otherwise(None)
        )

        currency_expr = (
            pl.col("CURRENCY_ID").cast(pl.String).str.strip_chars().alias("CURRENCY_ID")
            if "CURRENCY_ID" in df_filtered.columns
            else pl.lit(None).cast(pl.String).alias("CURRENCY_ID")
        )

        df_result = df_filtered.select(
            fy_expr,
            pl.col("Event_Date"),
            pl.lit("LEDGER").alias("Source_Type"),
            pl.col("Source_ID"),
            pl.when(income_head_expr.is_not_null() & (income_head_expr != ""))
            .then(income_head_expr)
            .otherwise(pl.lit("CHECK_REQUIRED"))
            .alias("Income_Head"),
            pl.when(tax_sub_head_expr.is_not_null() & (tax_sub_head_expr != ""))
            .then(tax_sub_head_expr)
            .otherwise(pl.lit("CHECK_REQUIRED"))
            .alias("Tax_Sub_Head"),
            pl.col("Amount_INR"),
            pl.when(~is_incomplete).then(applied_rate_expr).otherwise(None).alias("Applied_Rate"),
            estimated_tax_expr.alias("Estimated_Tax"),
            currency_expr,
            pl.when(is_incomplete)
            .then(pl.lit("CHECK_REQUIRED"))
            .otherwise(pl.lit("READY"))
            .alias("Tax_Status"),
            pl.when(is_incomplete)
            .then(
                pl.lit(
                    "Income classification is missing, non-taxable/review-only, or the ordinary tax rate is invalid."
                )
            )
            .otherwise(None)
            .alias("Tax_Status_Reason"),
            pl.lit(None).cast(pl.String).alias("ISIN"),
            pl.lit(None).cast(pl.String).alias("Lot_ID"),
        )
        return df_result

    def _ordinary_income_rate(self, event_date: date) -> float | None:
        """Resolve a configured ordinary-income estimate rate for the event date."""
        if self.macro_table is not None:
            rate = self.macro_table.get_ordinary_income_rate(event_date)
        elif self.rules is not None:
            rate = self.rules.assumptions.macro.fallback_ordinary_income_rate
        else:
            return None
        try:
            rate = float(rate)
        except (TypeError, ValueError, OverflowError):
            return None
        return rate if math.isfinite(rate) and 0.0 <= rate <= 1.0 else None

    def _normalize_tax_credits(self, credit_subheads: dict[str, str]) -> pl.DataFrame:
        """Keep observed tax-credit transactions separate from taxable income."""
        if not credit_subheads or self.df_income.is_empty():
            return pl.DataFrame(schema=TAX_EVENT_SCHEMA)

        df_inc = self.df_income.with_columns(
            pl.col("CATEGORY_ID")
            .cast(pl.String)
            .str.strip_chars()
            .fill_null("")
            .alias("_clean_cat_id"),
            pl.col("UID").cast(pl.String).str.strip_chars().alias("Source_ID"),
        )
        df_credits = df_inc.filter(pl.col("_clean_cat_id").is_in(list(credit_subheads.keys())))
        if df_credits.is_empty():
            return pl.DataFrame(schema=TAX_EVENT_SCHEMA)

        if df_credits["Source_ID"].is_null().any() or (df_credits["Source_ID"] == "").any():
            raise ValueError("Required identifier tax-credit income UID is null or empty.")

        amount_col = df_credits.get_column("BASE_AMOUNT")
        if amount_col.dtype == pl.Boolean:
            bad_id = str(df_credits.get_column("Source_ID")[0])
            raise ValueError(
                f"Required amount tax-credit BASE_AMOUNT cannot be boolean for source {bad_id!r}."
            )
        try:
            df_credits = df_credits.with_columns(
                pl.col("BASE_AMOUNT").cast(pl.Float64, strict=True).alias("Amount_INR")
            )
        except Exception as exc:
            bad_id = str(df_credits.get_column("Source_ID")[0])
            raise ValueError(
                f"Required amount tax-credit BASE_AMOUNT is invalid for source {bad_id!r}: {exc}"
            ) from exc

        if df_credits["Amount_INR"].is_nan().any() or df_credits["Amount_INR"].is_infinite().any():
            bad_idx = (
                df_credits["Amount_INR"].is_nan() | df_credits["Amount_INR"].is_infinite()
            ).arg_true()[0]
            bad_id = str(df_credits.get_column("Source_ID")[bad_idx])
            raise ValueError(
                f"Required amount tax-credit BASE_AMOUNT must be finite for source {bad_id!r}."
            )

        if df_credits["DATE"].is_null().any():
            bad_idx = df_credits["DATE"].is_null().arg_true()[0]
            bad_id = str(df_credits.get_column("Source_ID")[bad_idx])
            raise ValueError(f"Required date tax-credit DATE is null for source {bad_id!r}.")

        if df_credits["DATE"].dtype == pl.Datetime:
            df_credits = df_credits.with_columns(pl.col("DATE").dt.date().alias("Event_Date"))
        elif df_credits["DATE"].dtype == pl.Date:
            df_credits = df_credits.with_columns(pl.col("DATE").alias("Event_Date"))
        else:
            try:
                df_credits = df_credits.with_columns(
                    pl.col("DATE").cast(pl.Date, strict=True).alias("Event_Date")
                )
            except Exception as exc:
                bad_id = str(df_credits.get_column("Source_ID")[0])
                raise ValueError(
                    f"Required date tax-credit DATE is invalid for source {bad_id!r}: {exc}"
                ) from exc

        fy_expr = (
            pl.when(pl.col("Event_Date").dt.month() >= 4)
            .then(
                pl.col("Event_Date").dt.year().cast(pl.String)
                + "-"
                + ((pl.col("Event_Date").dt.year() + 1) % 100).cast(pl.String).str.zfill(2)
            )
            .otherwise(
                (pl.col("Event_Date").dt.year() - 1).cast(pl.String)
                + "-"
                + (pl.col("Event_Date").dt.year() % 100).cast(pl.String).str.zfill(2)
            )
            .alias("FY")
        )

        currency_expr = (
            pl.col("CURRENCY_ID").cast(pl.String).str.strip_chars().alias("CURRENCY_ID")
            if "CURRENCY_ID" in df_credits.columns
            else pl.lit(None).cast(pl.String).alias("CURRENCY_ID")
        )

        df_result = df_credits.select(
            fy_expr,
            pl.col("Event_Date"),
            pl.lit("TAX_CREDIT").alias("Source_Type"),
            pl.col("Source_ID"),
            pl.lit("TAX_CREDIT").alias("Income_Head"),
            pl.col("_clean_cat_id")
            .replace_strict(credit_subheads, return_dtype=pl.String)
            .alias("Tax_Sub_Head"),
            pl.col("Amount_INR"),
            pl.lit(None).cast(pl.Float64).alias("Applied_Rate"),
            pl.lit(None).cast(pl.Float64).alias("Estimated_Tax"),
            currency_expr,
            pl.lit("READY").alias("Tax_Status"),
            pl.lit(None).cast(pl.String).alias("Tax_Status_Reason"),
            pl.lit(None).cast(pl.String).alias("ISIN"),
            pl.lit(None).cast(pl.String).alias("Lot_ID"),
        )
        return df_result

    @staticmethod
    def _optional_finite_number(value: Any) -> float | None:
        """Return a finite numeric value, preserving missing/invalid values as null."""
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return number if math.isfinite(number) else None

    def _normalize_quant_realized_events(self) -> list[dict[str, Any]]:
        """Normalize authoritative Quant FIFO realized gains/losses."""
        df = self.df_realized_events
        if df.is_empty():
            return []
        required = {"Realized_Event_ID", "Disposal_Date", "Realized_Gain_Loss"}
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(f"Quant realized events missing required columns: {missing}")

        records: list[dict[str, Any]] = []
        for row in df.to_dicts():
            source_id = self._required_id(row.get("Realized_Event_ID"), "Realized_Event_ID")
            event_date = self._as_date(row.get("Disposal_Date"), "Quant Disposal_Date", source_id)
            amount = self._required_amount(
                row.get("Realized_Gain_Loss"), "Realized_Gain_Loss", source_id
            )
            sub_head, classification_known = self._quant_sub_head(row)
            is_reconciliation = str(row.get("Lot_Source_Type") or "").upper() == "RECONCILIATION"
            status_reasons: list[str] = []
            if is_reconciliation:
                status_reasons.append(
                    "Reconciliation lot: original acquisition evidence requires review."
                )
            if not classification_known:
                status_reasons.append("Investment tax classification is unmapped or invalid.")
            if not self._clean_text(row.get("ISIN")):
                status_reasons.append("ISIN is missing.")
            if not self._clean_text(row.get("Lot_ID")):
                status_reasons.append("Lot_ID is missing.")
            if not self._clean_text(
                row.get("Currency_ID") if "Currency_ID" in df.columns else row.get("CURRENCY_ID")
            ):
                status_reasons.append("Currency_ID is missing.")

            applied_rate = self._optional_finite_number(row.get("Applied_Rate"))
            estimated_tax = self._optional_finite_number(row.get("Estimated_Tax"))
            if applied_rate is not None and not 0.0 <= applied_rate <= 1.0:
                applied_rate = None
            if estimated_tax is not None and estimated_tax < 0:
                estimated_tax = None
            if not is_reconciliation and (applied_rate is None or estimated_tax is None):
                status_reasons.append(
                    "Applied tax rate or estimated tax is unavailable or invalid."
                )
            # Missing identifiers/currency trigger review but do not erase an otherwise
            # valid FIFO tax estimate. Reconciliation lots and invalid calculations do.
            if is_reconciliation or applied_rate is None or estimated_tax is None:
                applied_rate = None
                estimated_tax = None

            records.append(
                {
                    "FY": self._financial_year(event_date),
                    "Event_Date": event_date,
                    "Source_Type": "QUANT",
                    "Source_ID": source_id,
                    "Income_Head": "Capital Gains",
                    "Tax_Sub_Head": sub_head,
                    "Amount_INR": amount,
                    "Applied_Rate": applied_rate,
                    "Estimated_Tax": estimated_tax,
                    "CURRENCY_ID": self._clean_text(
                        row.get("Currency_ID")
                        if "Currency_ID" in df.columns
                        else row.get("CURRENCY_ID")
                    ),
                    "Tax_Status": "CHECK_REQUIRED" if status_reasons else "READY",
                    "Tax_Status_Reason": " ".join(status_reasons) or None,
                    "ISIN": self._clean_text(row.get("ISIN")),
                    "Lot_ID": self._clean_text(row.get("Lot_ID")),
                }
            )
        return records

    def _quant_sub_head(self, row: dict[str, Any]) -> tuple[str, bool]:
        """Map Quant instrument/holding metadata to the configured evidence sub-head.

        This is classification only. It deliberately does not calculate tax rates or
        liability. Generic debt mutual-fund subtypes require acquisition-date evidence
        to determine which configured cutoff bucket applies.
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
                        acquisition_date = self._as_date(
                            acquisition_date, "Quant Acquisition_Date", row.get("Realized_Event_ID")
                        )
                    except ValueError:
                        acquisition_date = None
                try:
                    cutoff = (
                        self._as_date(
                            self.rules.assumptions.tax.debt_mf_cutoff_date,
                            "configured debt mutual-fund cutoff date",
                            "FinancialRules",
                        )
                        if self.rules
                        else None
                    )
                except ValueError:
                    cutoff = None
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

    def _validate_subcategory_dimension(self) -> None:
        """Reject ambiguous dimension keys before building the lookup map."""
        if "UID" not in self.df_subcategory.columns:
            raise ValueError("Income subcategory dimension must contain UID.")
        uids = [
            str(uid).strip()
            for uid in self.df_subcategory.get_column("UID").drop_nulls().to_list()
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

    def _validate_event_keys(self, df: pl.DataFrame) -> None:
        key_columns = ["Source_Type", "Source_ID", "Tax_Sub_Head"]
        duplicates = df.group_by(key_columns).len().filter(pl.col("len") > 1)
        if not duplicates.is_empty():
            keys = duplicates.select(key_columns).to_dicts()
            raise ValueError(
                "Duplicate canonical TaxEvent natural key(s) detected "
                f"(Source_Type, Source_ID, Tax_Sub_Head): {keys[:10]}"
            )

    @staticmethod
    def _required_id(value: Any, field_name: str) -> str:
        if value is None or not str(value).strip():
            raise ValueError(f"Required identity field {field_name} is missing.")
        return str(value).strip()

    @staticmethod
    def _required_amount(value: Any, field_name: str, source_id: Any) -> float:
        if value is None:
            raise ValueError(f"Required amount {field_name} is null for source {source_id!r}.")
        if isinstance(value, bool):
            raise ValueError(
                f"Required amount {field_name} cannot be boolean for source {source_id!r}."
            )
        try:
            amount = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Required amount {field_name} is invalid for source {source_id!r}: {value!r}"
            ) from exc

        if not math.isfinite(amount):
            raise ValueError(
                f"Required amount {field_name} must be finite for source {source_id!r}."
            )
        return amount

    @staticmethod
    def _as_date(value: Any, field_name: str, source_id: Any) -> date:
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
        if parsed is None:
            raise ValueError(f"Required date {field_name} is null for source {source_id!r}.")
        return parsed

    @staticmethod
    def _financial_year(event_date: date) -> str:
        start_year = event_date.year if event_date.month >= 4 else event_date.year - 1
        return f"{start_year}-{str(start_year + 1)[-2:]}"

    @staticmethod
    def _clean_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
