"""Investment and quantitative decision-support domain.

Owns
----
- Deterministic lot accounting, FIFO disposal, and cost-basis tracking.
- Market valuation, benchmark counterfactuals, and FX valuation.
- Performance analytics: XIRR, CAGR, returns, and attribution.
- Broker vs. reconstructed portfolio reconciliation.
- Portfolio snapshots, weights, and aggregation.

Does not own
-------------
- Multiprocessing worker execution (owned by application.investments).
- Warehouse persistence (owned by infrastructure.warehouse).
- Presentation rendering (owned by presentation).
"""

from personal_finance_etl.domain.investments.classification import (
    DEFAULT_DOMESTIC_COUNTRY,
    DEFAULT_DOMESTIC_CURRENCY,
    filter_us_market_trades,
    is_foreign_currency_trade_expr,
    is_us_market_instrument_expr,
    is_us_market_trade_expr,
    resolve_us_market_active_isins,
)
from personal_finance_etl.domain.investments.contracts import (
    AcquisitionLot,
    CashflowDict,
    CashflowRecord,
    InstrumentMetricsRecord,
    IsinMasterRecord,
    ISINProcessResult,
    ISINTags,
    ISINTaskPayload,
    LotAction,
    MarketSpineRecord,
    PipelineExecutionResult,
    PortfolioResult,
    Purchase,
    RealizedEvent,
    RealizedEventDict,
    RealizedEventRecord,
    ReconciliationAdjustmentType,
    ReconciliationEvent,
    ReconciliationEventDict,
    ReconciliationEventRecord,
    Sale,
    SnapshotRecord,
    TaxLot,
    TerminalValueDict,
    TerminalValueRecord,
    TradeRecord,
)

__all__ = [
    "AcquisitionLot",
    "CashflowDict",
    "CashflowRecord",
    "ISINProcessResult",
    "ISINTags",
    "ISINTaskPayload",
    "InstrumentMetricsRecord",
    "IsinMasterRecord",
    "LotAction",
    "MarketSpineRecord",
    "PipelineExecutionResult",
    "PortfolioResult",
    "Purchase",
    "RealizedEvent",
    "RealizedEventDict",
    "RealizedEventRecord",
    "ReconciliationAdjustmentType",
    "ReconciliationEvent",
    "ReconciliationEventDict",
    "ReconciliationEventRecord",
    "Sale",
    "SnapshotRecord",
    "TaxLot",
    "TerminalValueDict",
    "TerminalValueRecord",
    "TradeRecord",
    "DEFAULT_DOMESTIC_COUNTRY",
    "DEFAULT_DOMESTIC_CURRENCY",
    "filter_us_market_trades",
    "is_foreign_currency_trade_expr",
    "is_us_market_instrument_expr",
    "is_us_market_trade_expr",
    "resolve_us_market_active_isins",
]
