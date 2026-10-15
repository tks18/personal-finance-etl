"""Legacy desktop app shim delegating to presentation.desktop.app."""

from personal_finance_etl.presentation.desktop.app import DesktopApp, UnifiedETLTab, main

__all__ = ["DesktopApp", "UnifiedETLTab", "main"]

if __name__ == "__main__":
    main()
