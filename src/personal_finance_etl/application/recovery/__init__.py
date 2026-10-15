"""Recovery and snapshot application services.

Owns
----
- Orchestrating snapshot creation and validation workflows.
- Orchestrating database restore and convergence workflows.
- Coordinating recovery state transitions with Control Plane.

Does not own
-------------
- Concrete archive file extraction or tar/zip mechanics (owned by infrastructure.recovery).
- Control Plane schema (owned by infrastructure.warehouse.schema).
- UI buttons or dialogs (owned by presentation).
"""
