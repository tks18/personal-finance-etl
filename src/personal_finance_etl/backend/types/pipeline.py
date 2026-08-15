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
    class_cf: dict[str, list[dict[str, Any]]]
    class_pt: dict[str, dict[date, dict[str, float]]]
    class_re: dict[str, list[dict[str, Any]]]
    subtype_cf: dict[str, list[dict[str, Any]]]
    subtype_pt: dict[str, dict[date, dict[str, float]]]
    subtype_re: dict[str, list[dict[str, Any]]]
