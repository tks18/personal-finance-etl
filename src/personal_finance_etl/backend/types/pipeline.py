from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict


class ISINTaskPayload(BaseModel):
    """Payload representing a single ISIN processing task in the multiprocessing queue."""

    model_config = ConfigDict(arbitrary_types_allowed=True, strict=True)

    isin: str
    p_inst: list[dict[str, Any]]
    s_inst: list[dict[str, Any]]
    m_inst: list[dict[str, Any]]
    master_row: dict[str, Any]
    bm_map: dict[str, Any]


class PipelineExecutionResult(BaseModel):
    """Aggregate result from the entire pipeline execution."""

    model_config = ConfigDict(arbitrary_types_allowed=True, strict=True)

    has_data: bool
    global_cf: list[dict[str, Any]]
    global_pt: dict[date, dict[str, float]]
    global_re: list[dict[str, Any]]
    global_recon_events: list[dict[str, Any]]
    # Per-ISIN cashflows and terminal paths allow non-additive metrics to be
    # recomputed at ISIN grain instead of taking the first lot's XIRR.
    isin_cf: dict[str, list[dict[str, Any]]]
    isin_pt: dict[str, dict[date, dict[str, Any]]]
    class_cf: dict[str, list[dict[str, Any]]]
    class_pt: dict[str, dict[date, dict[str, float]]]
    class_re: dict[str, list[dict[str, Any]]]
    subtype_cf: dict[str, list[dict[str, Any]]]
    subtype_pt: dict[str, dict[date, dict[str, float]]]
    subtype_re: dict[str, list[dict[str, Any]]]
    instrument_type_cf: dict[str, list[dict[str, Any]]]
    instrument_type_pt: dict[str, dict[date, dict[str, float]]]
    sector_cf: dict[str, list[dict[str, Any]]]
    sector_pt: dict[str, dict[date, dict[str, float]]]
    industry_cf: dict[str, list[dict[str, Any]]]
    industry_pt: dict[str, dict[date, dict[str, float]]]
    geo_cf: dict[str, list[dict[str, Any]]]
    geo_pt: dict[str, dict[date, dict[str, float]]]
    country_cf: dict[str, list[dict[str, Any]]]
    country_pt: dict[str, dict[date, dict[str, float]]]
    currency_cf: dict[str, list[dict[str, Any]]]
    currency_pt: dict[str, dict[date, dict[str, float]]]
    currency_re: dict[str, list[dict[str, Any]]]
