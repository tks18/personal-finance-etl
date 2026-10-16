"""External evidence acquisition providers.

Owns
----
- Provider adapters for reading evidence from external systems and files.
- Transforming external payloads into typed extraction batch results.

Does not own
-------------
- Ingestion coordination policy or scheduling (owned by application.ingestion).
- Semantic canonical transformations (owned by domain.*).
"""

__all__: list[str] = []
