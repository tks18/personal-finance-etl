"""Evidence ingestion and synchronization coordination.

Owns
----
- Orchestrating evidence acquisition from providers.
- Checking extraction completeness and recording provenance.
- Coordinating Bronze storage persistence and synchronization.

Does not own
-------------
- Concrete file parsers or API client requests (owned by infrastructure.providers).
- Control Plane database transactions (owned by infrastructure.control_plane).
- Semantic canonical transformations (owned by domain.*).
"""

