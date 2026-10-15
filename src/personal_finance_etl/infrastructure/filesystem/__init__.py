"""Filesystem path helpers and normalization.

Owns
----
- Safe filesystem path normalization and directory resolution.
- Temporary file management and cleanup.
- File lock wrappers.

Does not own
-------------
- Specific financial statements or file parsing (owned by infrastructure.providers.files).
- Application workspace settings (owned by config.settings).
"""

from personal_finance_etl.infrastructure.filesystem.paths import (
    get_cache_dir,
    get_temp_dir,
    resource_path,
)

__all__ = [
    "get_cache_dir",
    "get_temp_dir",
    "resource_path",
]
