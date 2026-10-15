"""Household transformation shared helpers.

Owns
----
- Mapping table lookup utilities for column translation (Power Query equivalent).
- Pure tabular transformation utilities for household streams.

Does not own
-------------
- Validation logic (owned by domain.common.validation).
- Date calculation logic (owned by domain.common.dates).
"""

import polars as pl


def get_column_mapping(df_map: pl.DataFrame, table_name: str = "CATEGORY") -> dict[str, str]:
    """Filters the pre-loaded COLUMN_MASTER DataFrame and returns a dictionary of {OLD_COLUMN: NEW_COLUMN}.

    Parameters
    ----------
    df_map : pl.DataFrame
        Column mapping table containing `TABLE_NAME`, `OLD_COLUMN`, and `NEW_COLUMN`.
    table_name : str, default "CATEGORY"
        Specific table key to filter mappings for.

    Returns
    -------
    dict[str, str]
        Dictionary mapping legacy/source column names to canonical warehouse names.
    """
    mapping = (
        df_map.filter(pl.col("TABLE_NAME") == table_name)
        .select(["OLD_COLUMN", "NEW_COLUMN"])
        .rows()
    )
    return {old: new for old, new in mapping}

