"""Legacy CLI app shim delegating to presentation.cli.app."""

from personal_finance_etl.presentation.cli.app import (
    LOGO,
    EngineStatus,
    get_file_interactive,
    main_cli,
    print_bootloader,
)

__all__ = ["LOGO", "EngineStatus", "get_file_interactive", "main_cli", "print_bootloader"]
