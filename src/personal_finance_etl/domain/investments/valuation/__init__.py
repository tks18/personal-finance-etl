"""Investment market valuation, benchmark, and FX valuation.

Owns
----
- Valuation models for instruments at historical snapshots.
- Benchmark counterfactual valuation and tracking.
- Local currency and INR FX valuation gates.

Does not own
-------------
- Raw market data extraction (owned by infrastructure.providers.market).
- Lot FIFO state (owned by domain.investments.lots).
"""

