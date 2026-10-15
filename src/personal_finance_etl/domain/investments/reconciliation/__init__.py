"""Investment quantity and basis reconciliation.

Owns
----
- Reconstructed vs. broker observed holdings comparison.
- Quantity discrepancy detection and reconciliation event generation.
- Cost-basis reconciliation events preserving disagreement evidence.

Does not own
-------------
- Source extraction of statements (owned by infrastructure.providers).
- Physical Gold reconciliation table writing (owned by infrastructure.warehouse).
"""
