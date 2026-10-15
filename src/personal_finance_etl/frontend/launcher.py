"""Legacy launcher shim delegating to presentation.launcher.

Preserves backward compatibility for main and build_argument_parser.
"""

from personal_finance_etl.presentation.launcher import build_argument_parser, main

__all__ = ["build_argument_parser", "main"]

if __name__ == "__main__":
    main()
