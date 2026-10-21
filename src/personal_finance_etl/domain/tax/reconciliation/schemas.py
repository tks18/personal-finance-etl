"""Schemas and aggregation expression builders for tax reconciliation marts.

Owns
----
- Schemas for tax gold marts (Tax_Year_Summary, Tax_Income_Breakdown, Tax_Reconciliation).
- Aggregation expressions and completeness calculation builders.

Does not own
-------------
- Mart formatting orchestration (owned by domain.tax.reconciliation.reconciler).
- Tax event normalization (owned by domain.tax.events).
"""

from __future__ import annotations

import polars as pl

__all__ = [
    "RECON_NUMERIC_ZERO_DEFAULTS",
    "TAX_INCOME_BREAKDOWN_SCHEMA",
    "TAX_RECONCILIATION_SCHEMA",
    "TAX_YEAR_SUMMARY_SCHEMA",
    "build_fy_agg_expressions",
    "build_fy_completeness_columns",
    "build_income_breakdown_agg",
    "build_income_breakdown_columns",
    "build_recon_agg_expressions",
    "build_recon_completeness_columns",
]

TAX_YEAR_SUMMARY_SCHEMA = pl.Schema(
    {
        "FY": pl.String,
        "Total_Ledger_Income": pl.Float64,
        "Total_Investment_Gain_Loss": pl.Float64,
        "Total_Tax_Credits": pl.Float64,
        "Total_Estimated_Investment_Tax": pl.Float64,
        "Investment_Tax_Estimate_Count": pl.Int64,
        "Investment_Tax_Estimate_Missing_Count": pl.Int64,
        "Investment_Tax_Estimate_Complete": pl.Boolean,
        "Total_Estimated_Ledger_Tax": pl.Float64,
        "Ledger_Tax_Estimate_Count": pl.Int64,
        "Ledger_Tax_Estimate_Missing_Count": pl.Int64,
        "Ledger_Tax_Estimate_Complete": pl.Boolean,
        "Total_Event_Count": pl.Int64,
        "Ready_Count": pl.Int64,
        "Check_Required_Count": pl.Int64,
    }
)

TAX_INCOME_BREAKDOWN_SCHEMA = pl.Schema(
    {
        "FY": pl.String,
        "Income_Head": pl.String,
        "Tax_Sub_Head": pl.String,
        "Source_Type": pl.String,
        "Event_Amount_INR": pl.Float64,
        "Estimated_Tax_INR": pl.Float64,
        "Estimated_Tax_Event_Count": pl.Int64,
        "Estimated_Tax_Missing_Count": pl.Int64,
        "Estimated_Tax_Complete": pl.Boolean,
        "Event_Count": pl.Int64,
        "Ready_Count": pl.Int64,
        "Check_Required_Count": pl.Int64,
    }
)

TAX_RECONCILIATION_SCHEMA = pl.Schema(
    {
        "FY": pl.String,
        "Tax_Sub_Head": pl.String,
        "Ledger_Tax_Event_Amount": pl.Float64,
        "Excluded_Non_Taxable_Amount": pl.Float64,
        "Excluded_Non_Taxable_Event_Count": pl.Int64,
        "Excluded_Investment_Ledger_Amount": pl.Float64,
        "Excluded_Investment_Ledger_Event_Count": pl.Int64,
        "Quant_Realized_Gain_Loss": pl.Float64,
        "Estimated_Investment_Tax": pl.Float64,
        "Estimated_Tax_Event_Count": pl.Int64,
        "Estimated_Tax_Missing_Count": pl.Int64,
        "Estimated_Investment_Tax_Complete": pl.Boolean,
        "Estimated_Ledger_Tax": pl.Float64,
        "Ledger_Tax_Estimate_Count": pl.Int64,
        "Ledger_Tax_Estimate_Missing_Count": pl.Int64,
        "Estimated_Ledger_Tax_Complete": pl.Boolean,
        "Tax_Credit_Amount": pl.Float64,
        "Tax_Event_Amount": pl.Float64,
        "Investment_Source_Difference_INR": pl.Float64,
        "Ledger_Event_Count": pl.Int64,
        "Quant_Event_Count": pl.Int64,
        "Tax_Credit_Event_Count": pl.Int64,
        "Check_Required_Count": pl.Int64,
    }
)

RECON_NUMERIC_ZERO_DEFAULTS = [
    "Ledger_Tax_Event_Amount",
    "Excluded_Non_Taxable_Amount",
    "Excluded_Non_Taxable_Event_Count",
    "Excluded_Investment_Ledger_Amount",
    "Excluded_Investment_Ledger_Event_Count",
    "Quant_Realized_Gain_Loss",
    "Tax_Credit_Amount",
    "Tax_Event_Amount",
    "Ledger_Event_Count",
    "Estimated_Tax_Event_Count",
    "Estimated_Tax_Missing_Count",
    "Ledger_Tax_Estimate_Count",
    "Ledger_Tax_Estimate_Missing_Count",
    "Quant_Event_Count",
    "Tax_Credit_Event_Count",
    "Check_Required_Count",
]


def build_fy_agg_expressions() -> list[pl.Expr]:
    """Aggregate event counts, sums, and estimate coverage by FY."""
    return [
        pl.col("Amount_INR")
        .filter(pl.col("Source_Type") == "LEDGER")
        .sum()
        .alias("Total_Ledger_Income"),
        pl.col("Amount_INR")
        .filter(pl.col("Source_Type") == "QUANT")
        .sum()
        .alias("Total_Investment_Gain_Loss"),
        pl.col("Amount_INR")
        .filter(pl.col("Source_Type") == "TAX_CREDIT")
        .sum()
        .alias("Total_Tax_Credits"),
        pl.col("Estimated_Tax")
        .filter(pl.col("Source_Type") == "QUANT")
        .sum()
        .alias("_Investment_Tax_Sum"),
        (pl.col("Source_Type").eq("QUANT") & pl.col("Estimated_Tax").is_not_null())
        .sum()
        .cast(pl.Int64)
        .alias("Investment_Tax_Estimate_Count"),
        (pl.col("Source_Type").eq("QUANT") & pl.col("Estimated_Tax").is_null())
        .sum()
        .cast(pl.Int64)
        .alias("Investment_Tax_Estimate_Missing_Count"),
        pl.col("Estimated_Tax")
        .filter(pl.col("Source_Type") == "LEDGER")
        .sum()
        .alias("_Ledger_Tax_Sum"),
        (pl.col("Source_Type").eq("LEDGER") & pl.col("Estimated_Tax").is_not_null())
        .sum()
        .cast(pl.Int64)
        .alias("Ledger_Tax_Estimate_Count"),
        (pl.col("Source_Type").eq("LEDGER") & pl.col("Estimated_Tax").is_null())
        .sum()
        .cast(pl.Int64)
        .alias("Ledger_Tax_Estimate_Missing_Count"),
        pl.len().cast(pl.Int64).alias("Total_Event_Count"),
        (pl.col("Tax_Status") == "READY").sum().cast(pl.Int64).alias("Ready_Count"),
        (pl.col("Tax_Status") == "CHECK_REQUIRED")
        .sum()
        .cast(pl.Int64)
        .alias("Check_Required_Count"),
    ]


def build_fy_completeness_columns() -> list[pl.Expr]:
    """Derive explicit completeness and total estimated tax flags by FY."""
    return [
        pl.when(pl.col("Investment_Tax_Estimate_Count") > 0)
        .then(pl.col("_Investment_Tax_Sum"))
        .otherwise(pl.lit(None, dtype=pl.Float64))
        .alias("Total_Estimated_Investment_Tax"),
        pl.when(pl.col("Ledger_Tax_Estimate_Count") > 0)
        .then(pl.col("_Ledger_Tax_Sum"))
        .otherwise(pl.lit(None, dtype=pl.Float64))
        .alias("Total_Estimated_Ledger_Tax"),
        pl.when(
            (
                pl.col("Investment_Tax_Estimate_Count")
                + pl.col("Investment_Tax_Estimate_Missing_Count")
            )
            > 0
        )
        .then(
            (pl.col("Investment_Tax_Estimate_Count") > 0)
            & (pl.col("Investment_Tax_Estimate_Missing_Count") == 0)
        )
        .otherwise(pl.lit(None, dtype=pl.Boolean))
        .alias("Investment_Tax_Estimate_Complete"),
        pl.when(
            (pl.col("Ledger_Tax_Estimate_Count") + pl.col("Ledger_Tax_Estimate_Missing_Count")) > 0
        )
        .then(
            (pl.col("Ledger_Tax_Estimate_Count") > 0)
            & (pl.col("Ledger_Tax_Estimate_Missing_Count") == 0)
        )
        .otherwise(pl.lit(None, dtype=pl.Boolean))
        .alias("Ledger_Tax_Estimate_Complete"),
    ]


def build_income_breakdown_agg() -> list[pl.Expr]:
    """Aggregate event counts, sums, and estimate coverage by income head and sub-head."""
    return [
        pl.col("Amount_INR").sum().alias("Event_Amount_INR"),
        pl.col("Estimated_Tax").sum().alias("_Estimated_Tax_Sum"),
        (pl.col("Source_Type").is_in(["LEDGER", "QUANT"]) & pl.col("Estimated_Tax").is_not_null())
        .sum()
        .cast(pl.Int64)
        .alias("Estimated_Tax_Event_Count"),
        (pl.col("Source_Type").is_in(["LEDGER", "QUANT"]) & pl.col("Estimated_Tax").is_null())
        .sum()
        .cast(pl.Int64)
        .alias("Estimated_Tax_Missing_Count"),
        pl.len().cast(pl.Int64).alias("Event_Count"),
        (pl.col("Tax_Status") == "READY").sum().cast(pl.Int64).alias("Ready_Count"),
        (pl.col("Tax_Status") == "CHECK_REQUIRED")
        .sum()
        .cast(pl.Int64)
        .alias("Check_Required_Count"),
    ]


def build_income_breakdown_columns() -> list[pl.Expr]:
    """Derive breakdown estimated tax and completeness flags."""
    return [
        pl.when(
            pl.col("Source_Type").is_in(["LEDGER", "QUANT"])
            & (pl.col("Estimated_Tax_Event_Count") > 0)
        )
        .then(pl.col("_Estimated_Tax_Sum"))
        .otherwise(pl.lit(None, dtype=pl.Float64))
        .alias("Estimated_Tax_INR"),
        pl.when(pl.col("Source_Type").is_in(["LEDGER", "QUANT"]))
        .then(
            (pl.col("Estimated_Tax_Event_Count") > 0) & (pl.col("Estimated_Tax_Missing_Count") == 0)
        )
        .otherwise(pl.lit(None, dtype=pl.Boolean))
        .alias("Estimated_Tax_Complete"),
    ]


def build_recon_agg_expressions() -> list[pl.Expr]:
    """Aggregate event reconciliation metrics by FY and Tax_Sub_Head."""
    return [
        pl.col("Amount_INR")
        .filter(pl.col("Source_Type") == "LEDGER")
        .sum()
        .alias("Ledger_Tax_Event_Amount"),
        pl.col("Amount_INR")
        .filter(pl.col("Source_Type") == "QUANT")
        .sum()
        .alias("Quant_Realized_Gain_Loss"),
        pl.col("Estimated_Tax")
        .filter(pl.col("Source_Type") == "QUANT")
        .sum()
        .alias("_Investment_Tax_Sum"),
        (pl.col("Source_Type").eq("QUANT") & pl.col("Estimated_Tax").is_not_null())
        .sum()
        .cast(pl.Int64)
        .alias("Estimated_Tax_Event_Count"),
        (pl.col("Source_Type").eq("QUANT") & pl.col("Estimated_Tax").is_null())
        .sum()
        .cast(pl.Int64)
        .alias("Estimated_Tax_Missing_Count"),
        pl.col("Estimated_Tax")
        .filter(pl.col("Source_Type") == "LEDGER")
        .sum()
        .alias("_Ledger_Tax_Sum"),
        (pl.col("Source_Type").eq("LEDGER") & pl.col("Estimated_Tax").is_not_null())
        .sum()
        .cast(pl.Int64)
        .alias("Ledger_Tax_Estimate_Count"),
        (pl.col("Source_Type").eq("LEDGER") & pl.col("Estimated_Tax").is_null())
        .sum()
        .cast(pl.Int64)
        .alias("Ledger_Tax_Estimate_Missing_Count"),
        pl.col("Amount_INR")
        .filter(pl.col("Source_Type") == "TAX_CREDIT")
        .sum()
        .alias("Tax_Credit_Amount"),
        (pl.col("Source_Type") == "LEDGER").sum().cast(pl.Int64).alias("Ledger_Event_Count"),
        (pl.col("Source_Type") == "QUANT").sum().cast(pl.Int64).alias("Quant_Event_Count"),
        (pl.col("Source_Type") == "TAX_CREDIT")
        .sum()
        .cast(pl.Int64)
        .alias("Tax_Credit_Event_Count"),
        (pl.col("Tax_Status") == "CHECK_REQUIRED")
        .sum()
        .cast(pl.Int64)
        .alias("Check_Required_Count"),
    ]


def build_recon_completeness_columns() -> list[pl.Expr]:
    """Derive completeness and total tax event amounts for reconciliation."""
    return [
        pl.when(pl.col("Estimated_Tax_Event_Count") > 0)
        .then(pl.col("_Investment_Tax_Sum"))
        .otherwise(pl.lit(None, dtype=pl.Float64))
        .alias("Estimated_Investment_Tax"),
        pl.when(pl.col("Ledger_Tax_Estimate_Count") > 0)
        .then(pl.col("_Ledger_Tax_Sum"))
        .otherwise(pl.lit(None, dtype=pl.Float64))
        .alias("Estimated_Ledger_Tax"),
        pl.when(pl.col("Quant_Event_Count") > 0)
        .then(
            (pl.col("Estimated_Tax_Event_Count") > 0) & (pl.col("Estimated_Tax_Missing_Count") == 0)
        )
        .otherwise(pl.lit(None, dtype=pl.Boolean))
        .alias("Estimated_Investment_Tax_Complete"),
        pl.when(pl.col("Ledger_Event_Count") > 0)
        .then(
            (pl.col("Ledger_Tax_Estimate_Count") > 0)
            & (pl.col("Ledger_Tax_Estimate_Missing_Count") == 0)
        )
        .otherwise(pl.lit(None, dtype=pl.Boolean))
        .alias("Estimated_Ledger_Tax_Complete"),
        (
            pl.col("Ledger_Tax_Event_Amount").fill_null(0.0)
            + pl.col("Quant_Realized_Gain_Loss").fill_null(0.0)
        ).alias("Tax_Event_Amount"),
    ]
