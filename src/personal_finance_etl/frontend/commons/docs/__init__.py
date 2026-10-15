"""Legacy docs package shim delegating to presentation.docs."""

from personal_finance_etl.presentation.docs import (
    DocEntry,
    DocsCatalog,
    DocsRenderer,
    show_guides_window,
)

__all__ = ["DocEntry", "DocsCatalog", "DocsRenderer", "show_guides_window"]
