"""Legacy manifest shim delegating to presentation.docs.manifest."""

from personal_finance_etl.presentation.docs.manifest import DocEntry, DocsCatalog

__all__ = ["DocEntry", "DocsCatalog"]
