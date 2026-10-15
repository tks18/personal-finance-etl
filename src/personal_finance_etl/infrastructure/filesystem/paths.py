"""Filesystem path resolution, temporary directories, and cache folder management.

Owns
----
- Safe resource path resolution across PyInstaller frozen binaries, PyPI packages, and local workspaces.
- Temporary working directory creation and resolution.
- Cache directory tree initialization and path resolution.

Does not own
-------------
- User application-data preferences files (owned by infrastructure.preferences).
- Raw statement file discovery or format ingestion (owned by infrastructure.providers.files).
- Database warehouse path configuration (owned by config.settings).
"""

from __future__ import annotations

import importlib.resources
import os
import sys
import tempfile


def resource_path(relative_path: str) -> str:
    """Get absolute path to a resource, supporting PyInstaller, PyPI, and local development.

    Parameters
    ----------
    relative_path : str
        Relative path to the resource file or directory.

    Returns
    -------
    str
        Resolved absolute filesystem path.
    """
    # 1. PyInstaller frozen executable (_MEIPASS)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass is not None:
        return os.path.join(str(meipass), relative_path)

    # 2. Local workspace directory
    local_path = os.path.join(os.path.abspath("."), relative_path)
    if os.path.exists(local_path):
        return local_path

    # 3. Installed package resources (pip/wheel distribution)
    try:
        parts = relative_path.replace("\\", "/").split("/")
        pkg_path = importlib.resources.files("personal_finance_etl").joinpath(*parts)
        if pkg_path.is_file() or pkg_path.is_dir():
            return str(pkg_path)
    except (TypeError, ModuleNotFoundError, FileNotFoundError):
        pass

    return local_path


def get_temp_dir() -> str:
    """Return a consistent temporary directory path for the application.

    Ensures the directory exists before returning.

    Returns
    -------
    str
        Absolute path to the application's temporary directory.
    """
    path = os.path.join(tempfile.gettempdir(), "PersonalFinanceETL")
    os.makedirs(path, exist_ok=True)
    return path


def get_cache_dir(base_path: str, subfolder: str = "") -> str:
    """Return an absolute path to a cache directory inside the given base path.

    Ensures the directory and any requested subfolder exist before returning.

    Parameters
    ----------
    base_path : str
        Root base directory.
    subfolder : str, default=""
        Optional child folder name within the cache directory.

    Returns
    -------
    str
        Absolute path to the created cache directory.
    """
    path = os.path.join(base_path, "cache")
    if subfolder:
        path = os.path.join(path, subfolder)
    os.makedirs(path, exist_ok=True)
    return path

