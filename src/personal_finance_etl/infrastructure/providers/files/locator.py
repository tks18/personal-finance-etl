"""Filesystem statement discovery and locator adapter.

Owns
----
- Scanning statement source folders recursively for active spreadsheet files.
- Categorizing statement files into known asset classes (stock PL, orders, MF, US stocks).
- Normalizing file paths to POSIX slashes and filtering temporary/lock files.

Does not own
-------------
- Reading file contents or binary payloads (owned by csv/excel adapters or artifact store).
- Schema validation or semantic interpretation (owned by domain and contracts).
"""

from __future__ import annotations

import glob
import os

from personal_finance_etl.infrastructure.logging import logger

__all__ = ["categorize_statement_files"]


def categorize_statement_files(folder_path: str, strict: bool = True) -> dict[str, list[str]]:
    """Perform a single directory traversal to categorize all statement files.

    Parameters
    ----------
    folder_path : str
        Root directory containing financial statements.
    strict : bool, optional
        Whether to raise FileNotFoundError if any non-optional category has no files.
        Defaults to True.

    Returns
    -------
    dict[str, list[str]]
        Dictionary mapping category names to lists of normalized filepaths.
    """
    all_files = glob.glob(os.path.join(folder_path, "**", "*.*"), recursive=True)
    all_files = [f.replace("\\", "/") for f in all_files if not os.path.basename(f).startswith("~")]
    logger.debug(
        f"[DISCOV:TRACE] Scanning directory: {folder_path} - Found {len(all_files)} total blobs."
    )

    categories: dict[str, list[str]] = {
        "stock_pl": [f for f in all_files if f.endswith(".xlsx") and "Stock PL Statements" in f],
        "mf_holdings": [
            f for f in all_files if f.endswith(".xlsx") and "Mutual Funds - Holdings" in f
        ],
        "stock_orders": [f for f in all_files if f.endswith(".xlsx") and "Stock - Orders" in f],
        "mf_orders": [f for f in all_files if f.endswith(".xlsx") and "Mutual Funds - Orders" in f],
        "us_stock_transactions": [
            f
            for f in all_files
            if f.endswith(".xlsx") and "IND Money (US Stocks)" in f and "Transaction Reports" in f
        ],
    }

    total_files = sum(len(f) for f in categories.values())

    for cat, files in categories.items():
        if not files and strict and cat != "us_stock_transactions":
            raise FileNotFoundError(
                f"No files found for category: '{cat}'. Please ensure statements are present."
            )

    logger.info(f"[DISCOV] Scanned {total_files} active statement files from local disk.")
    return categories
