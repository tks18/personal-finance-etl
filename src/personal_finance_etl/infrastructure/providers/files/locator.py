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


def _match_category(filepath: str) -> str | None:
    """Classify an Excel file path into its corresponding statement category.

    Parameters
    ----------
    filepath : str
        Normalized file path.

    Returns
    -------
    str | None
        Category identifier string, or None if file does not match any known pattern.
    """
    if not filepath.endswith(".xlsx"):
        return None
    if "Stock PL Statements" in filepath:
        return "stock_pl"
    if "Mutual Funds - Holdings" in filepath:
        return "mf_holdings"
    if "Stock - Orders" in filepath:
        return "stock_orders"
    if "Mutual Funds - Orders" in filepath:
        return "mf_orders"
    if "IND Money (US Stocks)" in filepath and "Transaction Reports" in filepath:
        return "us_stock_transactions"
    return None


def _validate_required_categories(categories: dict[str, list[str]], strict: bool) -> None:
    """Validate that non-optional statement categories contain at least one file.

    Parameters
    ----------
    categories : dict[str, list[str]]
        Classified files mapped by category.
    strict : bool
        Whether to enforce presence of all non-optional files.

    Raises
    ------
    FileNotFoundError
        If strict is True and any required category is empty.
    """
    if not strict:
        return
    for cat, files in categories.items():
        if not files and cat != "us_stock_transactions":
            raise FileNotFoundError(
                f"No files found for category: '{cat}'. Please ensure statements are present."
            )


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
    logger.debug(f"Scanning directory: {folder_path} - Found {len(all_files)} total blobs.")

    categories: dict[str, list[str]] = {
        "stock_pl": [],
        "mf_holdings": [],
        "stock_orders": [],
        "mf_orders": [],
        "us_stock_transactions": [],
    }

    for f in all_files:
        cat = _match_category(f)
        if cat is not None:
            categories[cat].append(f)

    total_files = sum(len(f) for f in categories.values())
    _validate_required_categories(categories, strict)

    logger.info(f"Scanned {total_files} active statement files from local disk.")
    return categories
