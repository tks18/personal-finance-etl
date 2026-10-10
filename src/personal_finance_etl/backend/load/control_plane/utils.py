from __future__ import annotations

import hashlib
import posixpath

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


def normalize_path(filepath: str) -> str:
    """Canonicalize separators and dot segments while preserving path identity.

    Virtual artifacts deliberately retain their URI scheme's double slash.
    """
    if not filepath or not filepath:
        raise ValueError("Artifact path must be a non-empty string.")
    normalized = filepath.replace("\\", "/")
    if normalized.startswith("virtual://"):
        scheme, rest = normalized.split("://", 1)
        return f"{scheme}://{posixpath.normpath('/' + rest).lstrip('/')}"
    return posixpath.normpath(normalized)


def compute_file_hash(filepath: str) -> str:
    """Return a SHA-256 digest, or an empty string if the file vanished."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, "rb") as file_handle:
            for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        return ""


def hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def generate_file_id(filepath: str) -> str:
    """Generate a stable ID from a canonical path, independent of slash style."""
    return hashlib.sha256(normalize_path(filepath).encode("utf-8")).hexdigest()
