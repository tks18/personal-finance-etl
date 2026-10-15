"""DuckDB warehouse persistence and schema registries.

Owns
----
- DuckDB connection management, extensions, and PRAGMA configurations.
- DataContract registries for Bronze, Silver, Gold, and Meta layers.
- Concrete persistence implementations for Bronze, Silver, Gold, and Meta tables.

Does not own
-------------
- Control Plane operational metadata (owned by infrastructure.control_plane).
- Business formulas or financial transformations (owned by domain.*).
"""

