"""Desktop Graphical User Interface (GUI) presentation.

Owns
----
- CustomTkinter window, application lifecycle, and views.
- Base tab abstraction, tabs, and interactive components.
- Theme management and UI styles.

Does not own
-------------
- Pipeline execution or multi-process queue consumers (delegates to application.facade).
- Warehouse persistence (owned by infrastructure.warehouse).
"""
