import argparse
import multiprocessing

from personal_finance_etl.frontend.cli.app import main_cli
from personal_finance_etl.frontend.desktop.app import DesktopApp


def main() -> None:
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(description="Personal Finance Quant Engine")
    subparsers = parser.add_subparsers(dest="command", help="Frontend to launch")

    # CLI Subcommand
    cli_parser = subparsers.add_parser("cli", help="Launch the savage terminal CLI")
    cli_parser.add_argument("--config", type=str, help="Path to config.toml", default=None)
    cli_parser.add_argument("--rules", type=str, help="Path to rules.toml", default=None)
    cli_parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Snapshot the DuckDB database instead of running ETL",
    )

    # Tkinter Subcommand
    subparsers.add_parser("tkinter", help="Launch the Desktop GUI")

    args = parser.parse_args()

    if args.command == "cli":
        main_cli(args)
    else:
        # Default to tkinter if no command, or if command == "tkinter"
        app = DesktopApp()
        app.mainloop()  # type: ignore


if __name__ == "__main__":
    main()
