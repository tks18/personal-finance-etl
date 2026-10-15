"""Packaged documentation browser presentation.

Owns
----
- In-app documentation manifest and document table of contents.
- Markdown and HTML rendering for reference documentation and diagrams.
- Guides browser window lifecycle.

Does not own
-------------
- Financial domain semantics (documentation UI is strictly presentation).
"""

from personal_finance_etl.presentation.docs.guides_window import show_guides_window
from personal_finance_etl.presentation.docs.manifest import DocEntry, DocsCatalog
from personal_finance_etl.presentation.docs.renderer import DocsRenderer

__all__ = ["DocEntry", "DocsCatalog", "DocsRenderer", "show_guides_window"]
