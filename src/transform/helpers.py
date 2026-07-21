import polars as pl

def get_column_mapping(df_map: pl.DataFrame, table_name: str = "CATEGORY") -> dict[str, str]:
    """Filters the pre-loaded COLUMN_MASTER DataFrame and returns a dictionary of {OLD_COLUMN: NEW_COLUMN}"""
    # Filter for the specific table and create a dict
    mapping = (
        df_map.filter(pl.col("TABLE_NAME") == table_name)
        .select(["OLD_COLUMN", "NEW_COLUMN"])
        .rows()
    )
    return {old: new for old, new in mapping}


