"""Legacy CLI package shim delegating to presentation.cli."""

from personal_finance_etl.presentation.cli import (
    LOGO,
    EngineStatus,
    get_file_interactive,
    main_cli,
    print_bootloader,
)

__all__ = ["LOGO", "EngineStatus", "get_file_interactive", "main_cli", "print_bootloader"]
