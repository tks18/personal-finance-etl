"""Frontend presentation layer legacy shim delegating to presentation package.

Preserves backward compatibility for DesktopApp, main_cli, and run_app.
"""

from personal_finance_etl.presentation.cli.app import main_cli
from personal_finance_etl.presentation.desktop.app import DesktopApp
from personal_finance_etl.presentation.launcher import main as run_app

__all__ = ["DesktopApp", "main_cli", "run_app"]
