"""Personal Finance ETL Engine.

My local-first financial data engineering and quantitative decision-support platform for
reconciled personal finance, investment analytics, tax evidence, FIRE simulation, and BI.
This application strictly adheres to Clean Architecture and Domain-Driven Design (DDD),
enforcing clean, unidirectional boundaries across layered subsystems:

Architecture Overview:
----------------------
1. `personal_finance_etl.contracts`: Canonical interfaces, protocols, and data contracts.
2. `personal_finance_etl.config`: Strongly-typed configuration settings and partitioned financial policy models.
3. `personal_finance_etl.domain`: Pure functional financial mathematics, transforms, and domain logic.
4. `personal_finance_etl.infrastructure`: Database persistence (DuckDB + SQLite), logging, and external providers.
5. `personal_finance_etl.application`: Application services, pipeline execution, and public façade.
6. `personal_finance_etl.bootstrap`: Dependency injection and composition root.
Owns
----
- Top-level public package facade and versioning.
- Public exports of PersonalFinanceEngine, DesktopApp, main_cli, and run_app.

Does not own
-------------
- Implementation of domain logic, infrastructure storage, or workflow orchestration.
- Direct execution loops or database connections.

Author: Sudharshan TK
"""

from personal_finance_etl.application.facade import PersonalFinanceEngine
from personal_finance_etl.presentation.cli.app import main_cli
from personal_finance_etl.presentation.desktop.app import DesktopApp
from personal_finance_etl.presentation.launcher import main as run_app

__all__ = [
    "PACKAGE_NAME",
    "DesktopApp",
    "PersonalFinanceEngine",
    "__author__",
    "__version__",
    "main_cli",
    "run_app",
]

__version__ = "9.3.1"
__author__ = "Sudharshan TK"
PACKAGE_NAME = "personal-finance-etl"
