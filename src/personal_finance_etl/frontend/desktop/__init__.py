"""
Desktop GUI Application.

This module houses the CustomTkinter implementation of the Personal Finance ETL.
It provides a rich, dark-mode desktop experience for pipeline orchestration,
relying entirely on the `PersonalFinanceEngine` facade for execution.
"""

from personal_finance_etl.frontend.desktop.app import DesktopApp

__all__ = ["DesktopApp"]
