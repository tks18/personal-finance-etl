"""Infrastructure layer: persistence, external providers, filesystem, and observability.

Owns
----
- Concrete DuckDB warehouse management and table publication.
- Concrete SQLite Control Plane management, repositories, and file synchronization.
- External evidence acquisition providers (files and market data APIs).
- Database backup, snapshot archives, and recovery persistence.
- User preference storage and asynchronous forensic trace persistence.

Does not own
-------------
- Financial interpretation, formulas, or accounting rules (owned by domain).
- Use cases or orchestration workflows (owned by application).
- User interface presentation (owned by presentation).
"""

__all__: list[str] = []
