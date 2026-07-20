import glob
import os


def categorize_statement_files(folder_path: str) -> dict[str, list[str]]:
    """Does a single directory traversal to categorize all statement files."""
    all_files = glob.glob(os.path.join(folder_path, "**", "*.*"), recursive=True)
    all_files = [f for f in all_files if not os.path.basename(f).startswith("~")]

    return {
        "stock_pl": [f for f in all_files if f.endswith(".xlsx") and "Stock PL Statements" in f],
        "mf_holdings": [
            f for f in all_files if f.endswith(".xlsx") and "Mutual Funds - Holdings" in f
        ],
        "stock_orders": [f for f in all_files if f.endswith(".xlsx") and "Stock - Orders" in f],
        "mf_orders": [f for f in all_files if f.endswith(".xlsx") and "Mutual Funds - Orders" in f],
    }
