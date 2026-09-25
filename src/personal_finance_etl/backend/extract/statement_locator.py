import glob
import os

from personal_finance_etl.backend.utils.logger import logger


def categorize_statement_files(folder_path: str, strict: bool = True) -> dict[str, list[str]]:
    """Does a single directory traversal to categorize all statement files."""
    all_files = glob.glob(os.path.join(folder_path, "**", "*.*"), recursive=True)
    all_files = [f.replace("\\", "/") for f in all_files if not os.path.basename(f).startswith("~")]
    logger.debug(f"[DISCOV:TRACE] Scanning directory: {folder_path} - Found {len(all_files)} total blobs.")

    categories = {
        "stock_pl": [f for f in all_files if f.endswith(".xlsx") and "Stock PL Statements" in f],
        "mf_holdings": [
            f for f in all_files if f.endswith(".xlsx") and "Mutual Funds - Holdings" in f
        ],
        "stock_orders": [f for f in all_files if f.endswith(".xlsx") and "Stock - Orders" in f],
        "mf_orders": [f for f in all_files if f.endswith(".xlsx") and "Mutual Funds - Orders" in f],
    }

    total_files = sum(len(f) for f in categories.values())

    for cat, files in categories.items():
        if not files and strict:
            raise FileNotFoundError(
                f"No files found for category: '{cat}'. Please ensure statements are present."
            )

    logger.info(f"[DISCOV] Scanned {total_files} active statement files from local disk.")
    return categories
