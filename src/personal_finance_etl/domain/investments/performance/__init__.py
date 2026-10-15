"""Investment performance, returns, and attribution calculations.

Owns
----
- Pure XIRR and CAGR mathematical solvers and statuses.
- Period returns, active returns, and alpha calculations.
- Asset vs Forex performance attribution.

Does not own
-------------
- Stateful lot iteration (owned by domain.investments.lots).
- Aggregation across multiprocessing batches (owned by application.investments).
"""
