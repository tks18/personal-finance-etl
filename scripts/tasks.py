import subprocess
import sys

from scripts.create_releases import run_release_cli


def dev():
    """Run the app with hot-reloading."""
    print("Starting development server...")
    sys.exit(subprocess.call(["tkreload", "main.py"]))


def build():
    """Build the executable using PyInstaller."""
    print("Building executable with PyInstaller...")
    sys.exit(subprocess.call(["pyinstaller", "--clean", "-y", "main.spec"]))


def release():
    """Entrypoint called by uv run release"""
    # sys.argv[1:] passes all command line flags (like --preview, --single, --run)
    sys.exit(run_release_cli(sys.argv[1:]))
