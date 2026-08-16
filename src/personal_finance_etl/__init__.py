"""
Shan's Personal Finance Quant Engine.

An institutional-grade wealth management pipeline and quantitative analytics engine.
This application strictly adheres to Clean Architecture (Ports and Adapters) design patterns,
enforcing a rigid boundary between the Presentation Layer (Frontend) and the Domain/Infrastructure Layer (Backend).

Architecture Overview:
----------------------
1. `personal_finance_etl.backend`: Core execution logic. Contains the DuckDB lakehouse orchestration,
   Polars-based DAG transformations, Numba JIT-compiled stochastic Monte Carlo
   simulations, and the `PersonalFinanceEngine` API facade.
2. `personal_finance_etl.frontend`: User interface and presentation layer. Completely decoupled from
   state management, it drives the application purely by consuming the `personal_finance_etl.backend.api`.

Author: Sudharshan TK
"""

from personal_finance_etl.backend import PersonalFinanceEngine
from personal_finance_etl.frontend import DesktopApp, main_cli, run_app

__all__ = ["__version__", "PACKAGE_NAME", "DesktopApp", "PersonalFinanceEngine", "main_cli", "run_app"]

__version__ = "5.0.6"
PACKAGE_NAME = "personal-finance-etl"
