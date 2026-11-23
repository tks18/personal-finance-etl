"""Investment and portfolio policy models.

Owns
----
- Investment instrument category and subcategory filtering rules.
- Portfolio management thresholds (e.g., rebalance tolerance percentage points).

Does not own
-------------
- Asset liquidity and conduit definitions (owned by config.financial_rules.household).
- Statutory capital gains tax rates (owned by config.financial_rules.tax).
- Macroeconomic and FIRE forecasting assumptions (owned by config.financial_rules.fire).
"""

from pydantic import BaseModel, Field


class InvestmentInstrumentRules(BaseModel):
    """Category and subcategory identifiers for marketable investment instruments."""

    category_ids: list[str] = Field(
        default_factory=list,
        description="Category IDs classifying this investment instrument.",
        json_schema_extra={"ui_widget": "id_list"},
    )
    sub_category_ids: list[str] = Field(
        default_factory=list,
        description="Subcategory UIDs classifying this investment instrument.",
        json_schema_extra={"ui_widget": "id_list"},
    )


class PortfolioManagementRules(BaseModel):
    """Portfolio management drift thresholds and rebalancing triggers."""

    rebalance_tolerance_pct_points: float = Field(
        default=5.0,
        description="Threshold (in percentage points) for triggering a rebalance requirement.",
        json_schema_extra={"min": 0.1, "max": 50.0, "step": 0.5, "unit": "pts"},
    )
    cost_basis_tolerance: float = Field(
        default=0.01,
        ge=0.0,
        description="Discrepancy tolerance threshold for cost basis unit validation.",
        json_schema_extra={"min": 0.0001, "max": 1.0, "step": 0.005, "unit": "INR"},
    )
