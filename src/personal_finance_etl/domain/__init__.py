"""Financial domain logic, entities, algorithms, and canonical semantic transforms.

Owns
----
- Pure financial meaning, formulas, and deterministic algorithms.
- FIFO lot accounting, valuation, and reconciliation.
- Tax event classification and statutory liability estimates.
- Household cashflow, ledger, and budget modelling.
- Wealth net worth, scoring, and FIRE simulation.

Does not own
-------------
- Workflow orchestration or execution timing (owned by application).
- Concrete storage, DuckDB, SQLite, or network I/O (owned by infrastructure).
- UI presentation, CLI commands, or plotting (owned by presentation).
"""
