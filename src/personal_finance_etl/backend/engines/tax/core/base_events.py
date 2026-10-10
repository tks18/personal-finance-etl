from typing import Any

import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules
from personal_finance_etl.backend.engines.tax.utils.date_utils import add_fy_if_missing
from personal_finance_etl.backend.utils.identity import generate_deterministic_id

# Fallback investment CG sub-head set — used only when capital_gains_groups is not
# configured in the TOML.  Prefer configuring capital_gains_groups so new asset
# classes can be added without code changes.
_INVESTMENT_SUB_HEADS: frozenset[str] = frozenset(
    {
        "Equity_Listed_STCG",
        "Equity_Listed_LTCG",
        "Equity_Unlisted_STCG",
        "Equity_Unlisted_LTCG",
        "Debt_MF_Pre_Cutoff_STCG",
        "Debt_MF_Pre_Cutoff_LTCG",
        "Debt_MF_Post_Cutoff_STCG",
        "Debt_MF_Post_Cutoff_LTCG",
        "Other_Debt_STCG",
        "Other_Debt_LTCG",
        "REIT_STCG",
        "REIT_LTCG",
        "Gold_STCG",
        "Gold_LTCG",
        "SGB_STCG",
        "SGB_LTCG",
        "Default_STCG",
        "Default_LTCG",
    }
)


class BaseEventsBuilder:
    """Builds the base silver tax events by consolidating ledger and investment data."""

    def __init__(
        self,
        df_income: pl.DataFrame,
        df_realized_events: pl.DataFrame,
        df_subcategory: pl.DataFrame,
        rules: FinancialRules | None,
        rules_snapshot_id: str,
        df_macro: pl.DataFrame | None = None,
    ):
        self.df_income = df_income
        self.df_realized_events = df_realized_events
        self.df_subcategory = df_subcategory
        self.rules = rules
        self.rules_snapshot_id = rules_snapshot_id
        self.df_macro = df_macro if df_macro is not None else pl.DataFrame()

    def build(self) -> pl.LazyFrame:
        """Build the canonical silver tax events table."""
        if not self.rules:
            return pl.LazyFrame()

        fallback_ord = self.rules.assumptions.macro.fallback_ordinary_income_rate

        # Derive valid investment CG sub-heads from capital_gains_groups config if present;
        # fall back to the hardcoded registry for backward compatibility.
        if self.rules.assumptions.tax.capital_gains_groups:
            valid_inv_sub_heads: frozenset[str] = frozenset(
                code
                for group in self.rules.assumptions.tax.capital_gains_groups.values()
                for code in group.sub_head_codes
            )
        else:
            valid_inv_sub_heads = _INVESTMENT_SUB_HEADS

        # 1. LEDGER TAX EVENTS
        df_ledger = self.df_income.lazy().join(
            self.df_subcategory.lazy().select(
                ["UID", "Tax_Income_Head", "Tax_Sub_Head", "Taxability", "Tax_Method"]
            ),
            left_on="CATEGORY_ID",
            right_on="UID",
            how="left",
        )

        # Exclude non-taxable
        df_ledger = df_ledger.filter(pl.col("Taxability") != "non_taxable")

        # Exclude Investment-category ledger capital gains (keep only Default_STCG/LTCG)
        df_ledger = df_ledger.filter(
            ~(
                (pl.col("Tax_Method") == "capital_gains")
                & ~pl.col("Tax_Sub_Head").is_in(["Default_STCG", "Default_LTCG"])
            )
        )

        df_ledger = add_fy_if_missing(df_ledger, "DATE")

        # Map Ledger
        df_ledger_mapped = df_ledger.select(
            [
                pl.col("DATE").cast(pl.Date).alias("Event_Date"),
                pl.col("FY"),
                pl.lit("LEDGER").alias("Source_Type"),
                pl.col("UID").cast(pl.Utf8).alias("Source_ID"),
                pl.col("Tax_Income_Head").alias("Income_Head"),
                pl.col("Tax_Sub_Head"),
                pl.col("Taxability"),
                pl.col("Tax_Method"),
                pl.col("BASE_AMOUNT").cast(pl.Float64).alias("Gross_Amount"),
            ]
        ).with_columns(
            pl.col("Gross_Amount").alias("Taxable_Amount"),
            pl.when(pl.col("Tax_Sub_Head") == "Default_STCG")
            .then(pl.lit("ST"))
            .when(pl.col("Tax_Sub_Head") == "Default_LTCG")
            .then(pl.lit("LT"))
            .otherwise(pl.lit(None))
            .cast(pl.Utf8)
            .alias("Gain_Type"),
            pl.when(pl.col("Tax_Method") == "capital_gains")
            .then(pl.col("Gross_Amount"))
            .otherwise(pl.lit(None))
            .cast(pl.Float64)
            .alias("Realized_Gain_Loss"),
        )

        # 2. INVESTMENT REALIZED EVENTS
        df_inv = self.df_realized_events.lazy()
        schema_cols = df_inv.collect_schema().names()

        # NOTE: RECONCILIATION-lot disposals (Lot_Source_Type == "RECONCILIATION") are
        # intentionally NOT filtered out here.
        #
        # These events arise when a real broker sale disposes a synthetic lot created by
        # QUANTITY_ADD reconciliation.  The *sale* is real and authoritative — the
        # proceeds appear in the demat / bank statement.  Omitting them from the tax
        # pipeline would cause a silent mismatch during IT scrutiny.
        #
        # Instead they are classified as CHECK_REQUIRED (see below), Applied_Rate and
        # Estimated_Tax are nulled out, and Tax_Status is set to CHECK_REQUIRED.  This
        # forces a human to supply the original acquisition evidence before filing.
        # Only then will FIFO reprocess the lot as PURCHASE type and produce a READY event.

        date_col = "Disposal_Date" if "Disposal_Date" in schema_cols else "date"
        gain_col = "Realized_Gain_Loss" if "Realized_Gain_Loss" in schema_cols else "gain"
        proceeds_col = "Sale_Proceeds" if "Sale_Proceeds" in schema_cols else gain_col

        df_inv = add_fy_if_missing(df_inv, date_col)

        df_inv_mapped = df_inv.with_columns(
            pl.col(date_col).cast(pl.Date).alias("Event_Date"),
            pl.lit("INVESTMENT_REALIZED").alias("Source_Type"),
        )

        if "Realized_Event_ID" in schema_cols:
            df_inv_mapped = df_inv_mapped.with_columns(
                pl.col("Realized_Event_ID").alias("Source_ID")
            )
        else:
            df_inv_mapped = df_inv_mapped.with_columns(
                pl.concat_str(
                    [pl.lit("REALIZED_"), pl.col("sale_id"), pl.lit("_"), pl.col("lot_id")]
                ).alias("Source_ID")
            )

        df_inv_mapped = df_inv_mapped.with_columns(
            pl.lit("Capital_Gains").alias("Income_Head"),
            pl.lit("taxable").alias("Taxability"),
            pl.lit("capital_gains").alias("Tax_Method"),
        )

        type_col = "Tax_Type" if "Tax_Type" in schema_cols else "tax_type"
        subtype_col = "Tax_Subtype" if "Tax_Subtype" in schema_cols else "tax_subtype"
        holding_col = "Holding_Type" if "Holding_Type" in schema_cols else "gain_type"

        def _build_sub_head_raw(row: dict[str, Any]) -> str:
            tt = (row.get(type_col) or "").strip().lower()
            tst = (row.get(subtype_col) or "").strip().lower()
            ht = (row.get(holding_col) or "STCG").strip().upper()
            # Normalize holding type: strip CL suffix that may appear in older data
            ht_clean = ht.replace("CL", "").replace("CG", "")
            suffix = ht_clean + "CG"  # → "STCG" or "LTCG"
            # Determine column prefix from composite key
            if tt == "equity" and tst in ("listed", "direct", "direct_equity", ""):
                prefix = "Equity_Listed"
            elif tt == "equity" and tst == "unlisted":
                prefix = "Equity_Unlisted"
            elif tt == "equity" and tst in (
                "foreign",
                "us_listed",
                "us_stocks",
                "us_equity",
                "international",
            ):
                prefix = "Default"  # (equity, foreign) → reuses Default_LTCG/Default_STCG
            elif tt == "debt" and tst in ("mf_pre", "mf", "mutual_fund", "debt_mf"):
                prefix = "Debt_MF_Pre_Cutoff"  # pre-cutoff; post-cutoff lots become STCG at runtime
            elif tt == "debt" and tst == "mf_post":
                prefix = "Debt_MF_Post_Cutoff"
            elif tt == "debt":
                prefix = "Other_Debt"
            elif tt == "reit":
                prefix = "REIT"
            elif tt == "gold":
                prefix = "Gold"
            elif tt == "sgb":
                prefix = "SGB"
            else:
                prefix = "Default"
            return f"{prefix}_{suffix}"

        df_inv_mapped = df_inv_mapped.with_columns(
            pl.struct([type_col, subtype_col, holding_col])
            .map_elements(_build_sub_head_raw, return_dtype=pl.Utf8)
            .alias("Tax_Sub_Head_Raw"),
            pl.col(holding_col)
            .str.replace("CG", "", literal=True)
            .str.replace("CL", "", literal=True)
            .alias("Gain_Type"),
        )

        # Investment Engine owns the classification — validate against the code-owned
        # _INVESTMENT_SUB_HEADS set, NOT valid_sub_heads from TaxConfig/TOML.
        #
        # TaxConfig sub-heads (heads_of_income keys) are exclusively for LEDGER events.
        # _INVESTMENT_SUB_HEADS entries like "Equity_Listed_LTCG" are macro column-name
        # suffixes — a completely different namespace from TOML keys.
        #
        # CHECK_REQUIRED fires when:
        #   (a) the (Tax_Type, Tax_Subtype) combo produces an unknown prefix → unknown asset class
        #   (b) the lot is a RECONCILIATION synthetic lot (no acquisition evidence)
        #       The sale is real but cost basis is unknown — forces human resolution before filing.
        reconciliation_col = "Lot_Source_Type" if "Lot_Source_Type" in schema_cols else None

        is_unknown_sub_head = ~pl.col("Tax_Sub_Head_Raw").is_in(list(valid_inv_sub_heads))
        is_reconciliation_lot = (
            (pl.col(reconciliation_col) == pl.lit("RECONCILIATION"))
            if reconciliation_col
            else pl.lit(False)
        )

        df_inv_mapped = df_inv_mapped.with_columns(
            pl.when(is_unknown_sub_head | is_reconciliation_lot)
            .then(pl.lit("CHECK_REQUIRED"))
            .otherwise(pl.col("Tax_Sub_Head_Raw"))
            .alias("Tax_Sub_Head")
        ).drop("Tax_Sub_Head_Raw")

        # Ensure correct assignment: Proceeds -> Gross_Amount, Gain -> Taxable_Amount & Realized_Gain_Loss
        if proceeds_col in schema_cols:
            df_inv_mapped = df_inv_mapped.with_columns(
                pl.col(proceeds_col).cast(pl.Float64).alias("Gross_Amount")
            )
        else:
            df_inv_mapped = df_inv_mapped.with_columns(
                pl.lit(0.0).cast(pl.Float64).alias("Gross_Amount")
            )

        df_inv_mapped = df_inv_mapped.with_columns(
            pl.col(gain_col).cast(pl.Float64).alias("Taxable_Amount"),
            pl.col(gain_col).cast(pl.Float64).alias("Realized_Gain_Loss"),
        ).select(
            [
                "Event_Date",
                "FY",
                "Source_Type",
                "Source_ID",
                "Income_Head",
                "Tax_Sub_Head",
                "Taxability",
                "Tax_Method",
                "Gross_Amount",
                "Taxable_Amount",
                "Gain_Type",
                "Realized_Gain_Loss",
            ]
        )

        # 3. CONSOLIDATE
        df_tax_events = pl.concat([df_ledger_mapped, df_inv_mapped], how="vertical_relaxed")

        # 4. TAX ESTIMATION
        # Rate resolution: INVESTMENT_REALIZED events use FIFO's pre-computed rates; LEDGER events use macro CSV or TOML fallback.

        # Build a lookup: Source_ID → (Applied_Rate, Estimated_Tax) from realized events.
        # Only INVESTMENT_REALIZED rows have Source_IDs that exist in df_realized_events.
        _rate_cols_present = (
            "Applied_Rate" in self.df_realized_events.columns
            and "Estimated_Tax" in self.df_realized_events.columns
            and "Realized_Event_ID" in self.df_realized_events.columns
        )

        if _rate_cols_present and not self.df_realized_events.is_empty():
            lf_inv_rates = self.df_realized_events.lazy().select(
                [
                    pl.col("Realized_Event_ID").cast(pl.Utf8).alias("Source_ID"),
                    pl.col("Applied_Rate").cast(pl.Float64),
                    pl.col("Estimated_Tax").cast(pl.Float64),
                ]
            )
            # Left-join: INVESTMENT_REALIZED rows match on Source_ID; LEDGER rows get nulls
            df_tax_events = df_tax_events.join(lf_inv_rates, on="Source_ID", how="left")
        else:
            df_tax_events = df_tax_events.with_columns(
                pl.lit(None).cast(pl.Float64).alias("Applied_Rate"),
                pl.lit(None).cast(pl.Float64).alias("Estimated_Tax"),
            )

        # For LEDGER events: resolve ordinary income rate from macro CSV → TOML fallback
        _ord_col_in_macro: str | None = (
            "Estimated_Ordinary_Income_Tax_Rate"
            if not self.df_macro.is_empty()
            and "Estimated_Ordinary_Income_Tax_Rate" in self.df_macro.columns
            and "FY" in self.df_macro.columns
            else None
        )

        if _ord_col_in_macro:
            lf_ord_rates = self.df_macro.lazy().select(
                [
                    pl.col("FY").cast(pl.Utf8),
                    pl.col(_ord_col_in_macro).cast(pl.Float64).alias("_Ord_Rate_Macro"),
                ]
            )
            df_tax_events = df_tax_events.join(lf_ord_rates, on="FY", how="left")
        else:
            df_tax_events = df_tax_events.with_columns(
                pl.lit(None).cast(pl.Float64).alias("_Ord_Rate_Macro")
            )

        # Fill LEDGER capital gains and ordinary income rates (investment events already set)
        df_tax_events = (
            df_tax_events.with_columns(
                pl.when(pl.col("Source_Type") == "LEDGER")
                .then(
                    pl.when(pl.col("Tax_Method") == "ordinary_rate")
                    .then(
                        pl.when(pl.col("_Ord_Rate_Macro").is_not_null())
                        .then(pl.col("_Ord_Rate_Macro"))
                        .otherwise(pl.lit(fallback_ord))
                    )
                    .when(pl.col("Tax_Method") == "capital_gains")
                    .then(
                        # Default_LTCG/STCG from ledger use the ordinary income rate
                        # (non-investment property/other CG — slab rate applies)
                        pl.when(pl.col("_Ord_Rate_Macro").is_not_null())
                        .then(pl.col("_Ord_Rate_Macro"))
                        .otherwise(pl.lit(fallback_ord))
                    )
                    .otherwise(pl.lit(0.0))
                )
                .otherwise(pl.col("Applied_Rate"))  # INVESTMENT_REALIZED: use FIFO's rate as-is
                .alias("Applied_Rate_Resolved")
            )
            .with_columns(
                pl.when(pl.col("Source_Type") == "LEDGER")
                .then(
                    pl.when(pl.col("Taxable_Amount") > 0)
                    .then(pl.col("Taxable_Amount") * pl.col("Applied_Rate_Resolved"))
                    .otherwise(pl.lit(0.0))
                )
                .otherwise(pl.col("Estimated_Tax"))  # INVESTMENT_REALIZED: use FIFO's estimate
                .alias("Estimated_Tax_Resolved")
            )
            .with_columns(
                # Null out for CHECK_REQUIRED — no precise tax should be reported
                pl.when(pl.col("Tax_Sub_Head") == pl.lit("CHECK_REQUIRED"))
                .then(pl.lit(None).cast(pl.Float64))
                .otherwise(pl.col("Applied_Rate_Resolved"))
                .alias("Applied_Rate"),
                pl.when(pl.col("Tax_Sub_Head") == pl.lit("CHECK_REQUIRED"))
                .then(pl.lit(None).cast(pl.Float64))
                .otherwise(pl.col("Estimated_Tax_Resolved"))
                .alias("Estimated_Tax"),
            )
            .drop(["Applied_Rate_Resolved", "Estimated_Tax_Resolved", "_Ord_Rate_Macro"])
        )

        # Set Tax Status
        df_tax_events = df_tax_events.with_columns(
            pl.when(pl.col("Tax_Sub_Head") == "CHECK_REQUIRED")
            .then(pl.lit("CHECK_REQUIRED"))
            .otherwise(pl.lit("READY"))
            .alias("Tax_Status"),
            pl.when(pl.col("Tax_Sub_Head") == "CHECK_REQUIRED")
            .then(pl.lit("RECONCILIATION lot or unrecognized tax classification"))
            .otherwise(pl.lit(None))
            .cast(pl.Utf8)
            .alias("Tax_Status_Reason"),
            pl.lit(self.rules_snapshot_id).alias("Rules_Snapshot_ID"),
        )

        # 5. TAX EVENT IDENTITY
        # Use a deterministic hash so Tax_Event_ID is stable across re-runs.
        # Inputs: Source_Type + Source_ID + Tax_Sub_Head uniquely identify one tax event.
        df_tax_events = df_tax_events.with_columns(
            pl.struct(["Source_Type", "Source_ID", "Tax_Sub_Head"])
            .map_elements(
                lambda row: generate_deterministic_id(
                    "TAX",
                    {
                        "Source_Type": row["Source_Type"],
                        "Source_ID": row["Source_ID"],
                        "Tax_Sub_Head": row["Tax_Sub_Head"],
                    },
                ),
                return_dtype=pl.Utf8,
            )
            .alias("Tax_Event_ID")
        )

        return df_tax_events
