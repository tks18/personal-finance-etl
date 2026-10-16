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

    category_ids: list[str] = Field(default_factory=list)
    sub_category_ids: list[str] = Field(default_factory=list)


class PortfolioManagementRules(BaseModel):
    """Portfolio management drift thresholds and rebalancing triggers."""

    rebalance_tolerance_pct_points: float = Field(
        default=5.0,
        description="Threshold (in percentage points) for triggering a rebalance requirement.",
    )
