import glob
import os

from personal_finance_etl.backend.utils.logger import logger


def categorize_statement_files(folder_path: str, strict: bool = True) -> dict[str, list[str]]:
    """Does a single directory traversal to categorize all statement files."""
    all_files = glob.glob(os.path.join(folder_path, "**", "*.*"), recursive=True)
    all_files = [f for f in all_files if not os.path.basename(f).startswith("~")]

    categories = {
        "stock_pl": [f for f in all_files if f.endswith(".xlsx") and "Stock PL Statements" in f],
        "mf_holdings": [
            f for f in all_files if f.endswith(".xlsx") and "Mutual Funds - Holdings" in f
        ],
        "stock_orders": [f for f in all_files if f.endswith(".xlsx") and "Stock - Orders" in f],
        "mf_orders": [f for f in all_files if f.endswith(".xlsx") and "Mutual Funds - Orders" in f],
    }

    for cat, files in categories.items():
        if not files:
            if strict:
                raise FileNotFoundError(
                    f"No files found for category: '{cat}'. Please ensure statements are present."
                )
            else:
                logger.info(f"  -> [{cat}] Discovered 0 files.")
        else:
            logger.info(f"  -> [{cat}] Discovered {len(files)} files.")

    logger.info(
        f"Successfully categorized {sum(len(f) for f in categories.values())} total raw statement files."
    )
    return categories
