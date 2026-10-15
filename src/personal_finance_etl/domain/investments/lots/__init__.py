"""Tax lot tracking, FIFO disposal, and lot ordering.

Owns
----
- State-preserving FIFOPortfolio class and active lot queue.
- TaxLot models and chronological ordering rules.
- Lot disposal, realized gain/loss computation, and lot-level cost basis.

Does not own
-------------
- Statutory tax head classification (owned by domain.tax).
- Warehouse persistence (owned by infrastructure.warehouse).
"""

