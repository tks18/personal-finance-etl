"""Declarative database pragmas and performance tuning commands.

Owns
----
- SQLite Control Plane WAL pragmas and cache tuning definitions.

Does not own
-------------
- Connection lifecycle execution (owned by infrastructure.control_plane.connection).
- Table DDL schemas (owned by peer schema modules).
"""

SQLITE_PRAGMAS = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -20000;
PRAGMA mmap_size = 2147483648;
"""

