"""Pipeline orchestration and execution lifecycle.

Owns
----
- Pipeline stage sequencing and worker execution.
- Transactional commit and recovery state transitions.
- Coordination of end-to-end ETL execution.

Does not own
-------------
- Concrete database queries or DDL (owned by infrastructure.warehouse).
- Domain transformations (owned by domain.*).
- UI progress display (owned by presentation).
"""

