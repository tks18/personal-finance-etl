"""Command-line interface (CLI) presentation.

Owns
----
- Terminal commands, arguments, and options.
- CLI-formatted progress output and status reporting.

Does not own
-------------
- Orchestration use cases (owned by application.pipeline).
- Financial algorithms (owned by domain.*).
"""

from personal_finance_etl.presentation.cli.app import (
    LOGO,
    EngineStatus,
    get_file_interactive,
    main_cli,
    print_bootloader,
)

__all__ = ["LOGO", "EngineStatus", "get_file_interactive", "main_cli", "print_bootloader"]
