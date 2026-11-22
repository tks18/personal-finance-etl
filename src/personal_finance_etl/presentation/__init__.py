"""Human-facing presentation surfaces: CLI and Desktop GUI.

Owns
----
- CLI commands and argument parsing.
- Desktop GUI (CustomTkinter) application, views, base tabs, and theme configuration.
- Human-facing application launcher.

Does not own
-------------
- Financial calculations, rules, or domain models (owned by domain.*).
- Execution orchestration (owned by application.*).
- Storage or persistence mechanisms (owned by infrastructure.*).
"""

from personal_finance_etl.presentation.launcher import build_argument_parser, main

__all__ = ["build_argument_parser", "main"]
