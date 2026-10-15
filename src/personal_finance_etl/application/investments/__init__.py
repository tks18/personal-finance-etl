"""Investment application services.

Owns
----
- Ingestion adaptation from warehouse tables into typed ISIN inputs.
- Orchestrating per-ISIN processing tasks across worker boundaries.
- Post-ISIN portfolio aggregation and performance attribution coordination.

Does not own
-------------
- FIFO lot accounting or tax lot state (owned by domain.investments.lots).
- Pure mathematical formulas for XIRR/CAGR (owned by domain.investments.performance).
- Physical warehouse tables (owned by infrastructure.warehouse).
"""

