"""Realized and reconciliation event lazy DataFrame construction.

Owns
----
- build_realized_events: Materialize realized gain/loss tax event records into typed LazyFrame.
- build_reconciliation_events: Assign deterministic event IDs and assemble reconciliation LazyFrame.

Does not own
-------------
- Portfolio XIRR and metrics calculation (owned by application.investments.aggregation_service).
- Post-processing pipeline scanning (owned by application.investments.aggregation_pipeline).
"""

from __future__ import annotations

import polars as pl

from personal_finance_etl.domain.common.identity import generate_deterministic_id
from personal_finance_etl.domain.investments.contracts import PipelineExecutionResult

__all__ = ["build_realized_events", "build_reconciliation_events"]


def build_realized_events(pipeline_res: PipelineExecutionResult) -> pl.LazyFrame:
    """Build standardized LazyFrame of realized gain/loss transactions.

    Parameters
    ----------
    pipeline_res : PipelineExecutionResult
        Aggregated results container from worker pool.

    Returns
    -------
    pl.LazyFrame
        Typed LazyFrame containing realized disposal event records.
    """
    re_schema = {
        "Realized_Event_ID": pl.String,
        "Sale_ID": pl.String,
        "Lot_ID": pl.String,
        "Purchase_ID": pl.String,
        "ISIN": pl.String,
        "Acquisition_Date": pl.Date,
        "Disposal_Date": pl.Date,
        "FY": pl.String,
        "Quantity_Disposed": pl.Float64,
        "Acquisition_Price": pl.Float64,
        "Disposed_Cost_Basis": pl.Float64,
        "Sale_Price": pl.Float64,
        "Sale_Proceeds": pl.Float64,
        "Realized_Gain_Loss": pl.Float64,
        "Holding_Type": pl.String,
        "Tax_Type": pl.String,
        "Tax_Subtype": pl.String,
        "Lot_Source_Type": pl.String,
        "Currency_ID": pl.String,
        "Asset_PnL_Local": pl.Float64,
        "Asset_PnL": pl.Float64,
        "Forex_PnL": pl.Float64,
        "Applied_Rate": pl.Float64,
        "Estimated_Tax": pl.Float64,
    }

    if not pipeline_res.global_re:
        return pl.LazyFrame(schema=re_schema)

    return (
        pl.LazyFrame(pipeline_res.global_re, schema_overrides=re_schema)
        .select(list(re_schema.keys()))
        .with_columns(
            pl.when(
                pl.col("Lot_Source_Type").cast(pl.String).str.to_uppercase() == "RECONCILIATION"
            )
            .then(pl.lit(None, dtype=pl.Float64))
            .otherwise(pl.col("Applied_Rate"))
            .alias("Applied_Rate"),
            pl.when(
                pl.col("Lot_Source_Type").cast(pl.String).str.to_uppercase() == "RECONCILIATION"
            )
            .then(pl.lit(None, dtype=pl.Float64))
            .otherwise(pl.col("Estimated_Tax"))
            .alias("Estimated_Tax"),
        )
    )


def build_reconciliation_events(
    pipeline_res: PipelineExecutionResult,
    run_id: str,
) -> pl.LazyFrame:
    """Assign deterministic group/event IDs and build reconciliation LazyFrame.

    Parameters
    ----------
    pipeline_res : PipelineExecutionResult
        Aggregated results container from worker pool.
    run_id : str
        Unique identifier for the current pipeline execution.

    Returns
    -------
    pl.LazyFrame
        Typed LazyFrame containing broker-to-reconstructed reconciliation adjustments.
    """
    for re_event in pipeline_res.global_recon_events:
        re_event["Run_ID"] = run_id
        re_event["Reconciliation_Group_ID"] = generate_deterministic_id(
            "RECON_GROUP",
            {
                "ISIN": re_event.get("ISIN"),
                "Reconciliation_Date": re_event.get("Reconciliation_Date"),
                "Adjustment_Type": re_event.get("Adjustment_Type"),
                "Broker_Quantity": re_event.get("Broker_Quantity"),
                "Reconstructed_Quantity": re_event.get("Reconstructed_Quantity"),
                "Broker_Cost_Basis": re_event.get("Broker_Cost_Basis"),
                "Reconstructed_Cost_Basis": re_event.get("Reconstructed_Cost_Basis"),
            },
        )
        re_event["Reconciliation_Event_ID"] = generate_deterministic_id(
            "RECON_EVENT",
            {
                "Reconciliation_Group_ID": re_event["Reconciliation_Group_ID"],
                "Lot_ID": re_event.get("Lot_ID"),
                "Adjustment_Type": re_event.get("Adjustment_Type"),
            },
        )

    if pipeline_res.global_recon_events:
        return pl.LazyFrame(pipeline_res.global_recon_events)

    return pl.LazyFrame(
        schema={
            "Reconciliation_Group_ID": pl.String,
            "Reconciliation_Event_ID": pl.String,
            "Run_ID": pl.String,
            "ISIN": pl.String,
            "Reconciliation_Date": pl.Date,
            "Lot_ID": pl.String,
            "Purchase_ID": pl.String,
            "Adjustment_Type": pl.String,
            "Reason": pl.String,
            "Broker_Quantity": pl.Float64,
            "Reconstructed_Quantity": pl.Float64,
            "Quantity_Adjustment": pl.Float64,
            "Broker_Cost_Basis": pl.Float64,
            "Reconstructed_Cost_Basis": pl.Float64,
            "Cost_Basis_Adjustment": pl.Float64,
            "Original_Unit_Cost": pl.Float64,
            "Adjusted_Unit_Cost": pl.Float64,
        }
    )
