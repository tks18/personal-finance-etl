"""
Shan's Personal Finance Quant Engine.

An institutional-grade wealth management pipeline and quantitative analytics engine.
This application strictly adheres to Clean Architecture (Ports and Adapters) design patterns,
enforcing a rigid boundary between the Presentation Layer (Frontend) and the Domain/Infrastructure Layer (Backend).

Architecture Overview:
----------------------
1. `personal_finance_etl.backend`: Core execution logic. Implements a dual-plane architecture:
   - Control Plane (SQLite): The operational source of truth for run lifecycle, ACID telemetry, and explicit data lineage.
   - Analytical Engine (DuckDB): The presentation and calculation engine serving Bronze, Silver, and Gold analytical contracts.
   - Transformation (Polars): High-performance DAG operations and Numba JIT-compiled stochastic Monte Carlo simulations.
   - API Facade: Exposes the `PersonalFinanceEngine` as the strict boundary boundary.
2. `personal_finance_etl.frontend`: User interface and presentation layer (CLI, Desktop GUI, and Document Rendering).
   Completely decoupled from state management, driving the application purely by consuming the API facade.

Author: Sudharshan TK
"""

from personal_finance_etl.backend import PersonalFinanceEngine
from personal_finance_etl.frontend import DesktopApp, main_cli, run_app

__all__ = [
    "__version__",
    "PACKAGE_NAME",
    "DesktopApp",
    "PersonalFinanceEngine",
    "main_cli",
    "run_app",
]

__version__ = "6.5.2"
PACKAGE_NAME = "personal-finance-etl"
