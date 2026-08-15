"""
Frontend Presentation Layer.

This package contains all user-facing interfaces and interaction logic.
It is strictly isolated from the backend business logic and infrastructure.
No module within this package should import from `personal_finance_etl.backend` except for
the `personal_finance_etl.backend.api` facade.
"""

from personal_finance_etl.frontend.cli.app import main_cli
from personal_finance_etl.frontend.desktop import DesktopApp
from personal_finance_etl.frontend.launcher import main as run_app

__all__ = ["DesktopApp", "main_cli", "run_app"]
