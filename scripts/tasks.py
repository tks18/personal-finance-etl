import subprocess
import sys


def dev():
    """Run the app with hot-reloading."""
    print("Starting development server...")
    sys.exit(subprocess.call(["tkreload", "main.py"]))


def build():
    """Build the executable using PyInstaller."""
    print("Building executable with PyInstaller...")
    sys.exit(subprocess.call(["pyinstaller", "--clean", "-y", "main.spec"]))
