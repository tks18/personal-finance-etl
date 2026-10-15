"""Investment application services.

Owns
----
- Ingestion adaptation from warehouse tables into typed ISIN inputs.
- Orchestrating per-ISIN processing tasks across worker boundaries.
- Post-ISIN portfolio aggregation and performance attribution coordination.
- End-to-end investment quantitative pipeline execution.

Does not own
-------------
- FIFO lot accounting or tax lot state (owned by domain.investments.lots).
- Pure mathematical formulas for XIRR/CAGR (owned by domain.investments.performance).
- Physical warehouse tables (owned by infrastructure.warehouse).
"""

from personal_finance_etl.application.investments.aggregation_service import (
    PostProcessingPipeline,
    PostProcessor,
)
from personal_finance_etl.application.investments.context import (
    AnalyticsContextManager,
    RunContext,
)
from personal_finance_etl.application.investments.input_adapter import (
    IsinDataExtractor,
    TaxDataLoader,
)
from personal_finance_etl.application.investments.isin_service import (
    IsinPipeline,
    IsinProcessor,
)
from personal_finance_etl.application.investments.quant_service import (
    InvestmentQuantEngine,
    QuantService,
)

__all__ = [
    "AnalyticsContextManager",
    "InvestmentQuantEngine",
    "IsinDataExtractor",
    "IsinPipeline",
    "IsinProcessor",
    "PostProcessingPipeline",
    "PostProcessor",
    "QuantService",
    "RunContext",
    "TaxDataLoader",
]
