"""User preferences filesystem repository.

Owns
----
- Reading and writing user UI preferences (recent paths, theme, window state) to disk.
- Atomic file writes for preference persistence.

Does not own
-------------
- Execution settings or financial rules (owned by config).
- Presentation GUI widgets (owned by presentation.desktop).
"""

from personal_finance_etl.infrastructure.preferences.repository import PreferencesManager

__all__ = ["PreferencesManager"]
