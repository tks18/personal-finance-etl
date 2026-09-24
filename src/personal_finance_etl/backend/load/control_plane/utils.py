import hashlib

FILE_TYPE_MAP: dict[str, str] = {
    "mf_holdings": "excel",
    "mf_orders": "excel",
    "stock_pl": "excel",
    "stock_orders": "excel",
    "sqlite_source": "sqlite",
    "benchmark_master": "csv",
    "macro_parameters": "csv",
    "opening_balances": "csv",
    "mf_isin": "csv",
    "benchmark_mapping": "csv",
    "column_master": "csv",
    "benchmark_history": "parquet",
}


def compute_file_hash(filepath: str) -> str:
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        return ""


def generate_file_id(filepath: str) -> str:
    unique_path = filepath.replace("\\", "/")
    return hashlib.sha256(unique_path.encode("utf-8")).hexdigest()
