"""Canonical TaxEvent schema definition and evidence normalization builder.

Owns
----
- BaseEventsBuilder / TaxEventNormalizer: Normalizes ledger income, tax credits, and Quant FIFO events.
- Evidence validation across sources and dimension tables.

Does not own
-------------
- TAX_EVENT_SCHEMA and TaxEventDict definitions (owned by domain.tax.events.schema).
- Batch computation of deterministic Tax_Event_IDs (owned by domain.tax.events.hashing).
- Statutory income head and sub-head classification rules (owned by domain.tax.classification).
- Ordinary tax rate lookup and rate bounding (owned by domain.tax.estimates).
- Presentation aggregations and reconciliation marts (owned by domain.tax.reconciliation).
"""

from __future__ import annotations

from datetime import date

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules
from personal_finance_etl.domain.market.macro import FYMacroParametersTable
from personal_finance_etl.domain.tax.classification import TaxClassifier
from personal_finance_etl.domain.tax.estimates import TaxEstimator
from personal_finance_etl.domain.tax.events.hashing import _batch_compute_tax_event_ids
from personal_finance_etl.domain.tax.events.quant import (
    normalize_quant_realized_events,
)
from personal_finance_etl.domain.tax.events.schema import TAX_EVENT_SCHEMA, TaxEventDict

__all__ = [
    "TAX_EVENT_SCHEMA",
    "BaseEventsBuilder",
    "TaxEventDict",
    "TaxEventNormalizer",
    "_batch_compute_tax_event_ids",
]


class BaseEventsBuilder:
    """Normalize ledger, tax-credit, and Quant FIFO evidence into canonical TaxEvents.

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
        """Return validated, deterministic TaxEvents as a LazyFrame.

        Returns
        -------
        pl.LazyFrame
            LazyFrame matching TAX_EVENT_SCHEMA.
        """
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
        base_schema = {k: v for k, v in TAX_EVENT_SCHEMA.items() if k != "Tax_Event_ID"}
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
        if self.rules is None:
            raise ValueError("FinancialRules are required to build tax credit subhead map.")
        return TaxClassifier.build_tax_credit_subhead_map(self.rules)

    def _validate_tax_credit_uids(self, credit_subheads: dict[str, str]) -> None:
        TaxClassifier.validate_tax_credit_uids(self.df_subcategory, credit_subheads)

    @staticmethod
    def _validate_ledger_amount(df: pl.DataFrame, source_label: str) -> pl.DataFrame:
        """Validate BASE_AMOUNT column is non-boolean, finite, and convert to Amount_INR."""
        amount_col = df.get_column("BASE_AMOUNT")
        if amount_col.dtype == pl.Boolean:
            bad_id = str(df.get_column("Source_ID")[0])
            label_prefix = f"{source_label} " if source_label else ""
            raise ValueError(
                f"Required amount {label_prefix}BASE_AMOUNT cannot be boolean for source {bad_id!r}."
            )
        try:
            df = df.with_columns(
                pl.col("BASE_AMOUNT").cast(pl.Float64, strict=True).alias("Amount_INR")
            )
        except Exception as exc:
            bad_id = str(df.get_column("Source_ID")[0])
            label_prefix = f"{source_label} " if source_label else ""
            raise ValueError(
                f"Required amount {label_prefix}BASE_AMOUNT is invalid for source {bad_id!r}: {exc}"
            ) from exc

        if df["Amount_INR"].is_nan().any() or df["Amount_INR"].is_infinite().any():
            bad_idx = (df["Amount_INR"].is_nan() | df["Amount_INR"].is_infinite()).arg_true()[0]
            bad_id = str(df.get_column("Source_ID")[bad_idx])
            label_prefix = f"{source_label} " if source_label else ""
            raise ValueError(
                f"Required amount {label_prefix}BASE_AMOUNT must be finite for source {bad_id!r}."
            )
        return df

    @staticmethod
    def _validate_ledger_date(df: pl.DataFrame, source_label: str) -> pl.DataFrame:
        """Validate DATE column is present, non-null, and convert to Date Event_Date."""
        if df["DATE"].is_null().any():
            bad_idx = df["DATE"].is_null().arg_true()[0]
            bad_id = str(df.get_column("Source_ID")[bad_idx])
            date_label = f"{source_label} DATE" if source_label else "income DATE"
            raise ValueError(f"Required date {date_label} is null for source {bad_id!r}.")

        if df["DATE"].dtype == pl.Datetime:
            return df.with_columns(pl.col("DATE").dt.date().alias("Event_Date"))
        if df["DATE"].dtype == pl.Date:
            return df.with_columns(pl.col("DATE").alias("Event_Date"))
        try:
            return df.with_columns(pl.col("DATE").cast(pl.Date, strict=True).alias("Event_Date"))
        except Exception as exc:
            bad_id = str(df.get_column("Source_ID")[0])
            date_label = f"{source_label} DATE" if source_label else "income DATE"
            raise ValueError(
                f"Required date {date_label} is invalid for source {bad_id!r}: {exc}"
            ) from exc

    @staticmethod
    def _add_fy_column(df: pl.DataFrame) -> pl.DataFrame:
        """Derive standard Indian Fiscal Year string from Event_Date."""
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
        return df.with_columns(fy_expr)

    @classmethod
    def _validate_and_prepare_ledger_frame(
        cls,
        df: pl.DataFrame,
        source_label: str,
    ) -> pl.DataFrame:
        """Validate BASE_AMOUNT and DATE columns, casting to finite Amount_INR, Event_Date, and FY."""
        if df.is_empty():
            return df
        df = cls._validate_ledger_amount(df, source_label)
        df = cls._validate_ledger_date(df, source_label)
        return cls._add_fy_column(df)

    def _prepare_subcategory_projection(self) -> pl.DataFrame:
        """Extract existing subcategory dimension tax metadata columns."""
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
        return self.df_subcategory.select(sub_cols)

    def _get_configured_exclusions(self) -> set[str]:
        """Collect subcategory UIDs configured as capital gains exclusions."""
        excluded: set[str] = set()
        if self.rules is not None:
            exclusions = self.rules.assumptions.tax.investment_exclusions
            excluded.update(exclusions.stcg_sub_cat_ids)
            excluded.update(exclusions.ltcg_sub_cat_ids)
        return excluded

    def _filter_taxable_ledger_records(
        self,
        df_joined: pl.DataFrame,
        excluded: set[str],
        credit_subheads: dict[str, str],
    ) -> pl.DataFrame:
        """Filter out exclusions, tax credits, and non-taxable entries."""
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

        return df_joined.filter(
            (~pl.col("_clean_cat_id").is_in(list(excluded)))
            & (~pl.col("_clean_cat_id").is_in(list(credit_subheads.keys())))
            & (~is_inv_excl)
            & (~is_tax_credit)
            & (taxability_clean != "non_taxable")
        )

    def _project_ledger_tax_events(
        self,
        df_filtered: pl.DataFrame,
    ) -> pl.DataFrame:
        """Project ledger columns to canonical TaxEvent schema attributes."""
        unique_dates = df_filtered["Event_Date"].unique().to_list()
        date_rate_map = {d: self._ordinary_income_rate(d) for d in unique_dates if d is not None}
        applied_rate_expr = pl.col("Event_Date").replace_strict(
            date_rate_map, default=None, return_dtype=pl.Float64
        )

        income_head_expr = pl.col("Tax_Income_Head").cast(pl.String).str.strip_chars()
        tax_sub_head_expr = pl.col("Tax_Sub_Head").cast(pl.String).str.strip_chars()
        taxability_clean = (
            pl.col("Taxability")
            .cast(pl.String)
            .str.strip_chars()
            .str.to_lowercase()
            .fill_null("review")
        )

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

        return df_filtered.select(
            pl.col("FY"),
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

    def _normalize_ledger_income(self, credit_subheads: dict[str, str]) -> pl.DataFrame:
        """Normalize taxable ledger income records into canonical TaxEvent schema."""
        required = {"UID", "DATE", "CATEGORY_ID", "BASE_AMOUNT"}
        missing = sorted(required - set(self.df_income.columns))
        if missing:
            raise ValueError(f"Income transactions missing required columns: {missing}")
        if self.df_income.is_empty():
            return pl.DataFrame(schema=TAX_EVENT_SCHEMA)

        df_sub = self._prepare_subcategory_projection()
        excluded = self._get_configured_exclusions()
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

        df_filtered = self._filter_taxable_ledger_records(df_joined, excluded, credit_subheads)
        if df_filtered.is_empty():
            return pl.DataFrame(schema=TAX_EVENT_SCHEMA)

        df_filtered = self._validate_and_prepare_ledger_frame(df_filtered, source_label="")
        return self._project_ledger_tax_events(df_filtered)

    def _ordinary_income_rate(self, event_date: date) -> float | None:
        """Resolve a configured ordinary-income estimate rate for the event date."""
        return TaxEstimator.resolve_ordinary_income_rate(self.macro_table, self.rules, event_date)

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

        df_credits = self._validate_and_prepare_ledger_frame(df_credits, source_label="tax-credit")

        currency_expr = (
            pl.col("CURRENCY_ID").cast(pl.String).str.strip_chars().alias("CURRENCY_ID")
            if "CURRENCY_ID" in df_credits.columns
            else pl.lit(None).cast(pl.String).alias("CURRENCY_ID")
        )

        return df_credits.select(
            pl.col("FY"),
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

    def _normalize_quant_realized_events(self) -> list[TaxEventDict]:
        """Normalize authoritative Quant FIFO realized gains/losses."""
        return normalize_quant_realized_events(self.df_realized_events, self.rules)

    def _validate_subcategory_dimension(self) -> None:
        """Reject ambiguous dimension keys before building the lookup map."""
        TaxClassifier.validate_subcategory_dimension(self.df_subcategory)

    def _validate_event_keys(self, df: pl.DataFrame) -> None:
        """Validate uniqueness of canonical TaxEvent natural keys."""
        key_columns = ["Source_Type", "Source_ID", "Tax_Sub_Head"]
        duplicates = df.group_by(key_columns).len().filter(pl.col("len") > 1)
        if not duplicates.is_empty():
            keys = duplicates.select(key_columns).to_dicts()
            raise ValueError(
                "Duplicate canonical TaxEvent natural key(s) detected "
                f"(Source_Type, Source_ID, Tax_Sub_Head): {keys[:10]}"
            )


TaxEventNormalizer = BaseEventsBuilder
