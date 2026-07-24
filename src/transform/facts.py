import polars as pl


def get_base_transactions(df_lazy: pl.LazyFrame, column_mapping: dict[str, str]) -> pl.LazyFrame:
    """
    Acts as the TRANSACTIONS helper query.
    Reads INOUTCOME once, renames columns, and filters deleted rows.
    """
    df_base = (
        df_lazy.rename(column_mapping)
        # Power Query used IS_DEL <> "1" (String comparison).
        # We cast to string first to be safe, then filter.
        .with_columns(
            [
                pl.col("IS_DEL").cast(pl.String),
                pl.col("LOCAL_AMOUNT").cast(pl.Float64, strict=False).fill_null(0.0),
                pl.col("AMOUNT_ACCOUNT").cast(pl.Float64, strict=False).fill_null(0.0),
                pl.col("TRANSACTION_TYPE").cast(pl.Int64, strict=False),
            ]
        )
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
    )

    return df_base


def transform_f_income_transactions(base_transactions_lazy: pl.LazyFrame) -> pl.LazyFrame:
    """
    Branches off the base transactions for Income (TYPE = 0)
    and applies the DAX calculation.
    """
    df_transformed = (
        base_transactions_lazy.filter(pl.col("TRANSACTION_TYPE") == 0)
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "UID",
                "ASSET_ID",
                "CARDDIVIDMONTH",
                "CATEGORY_ID",
                "TO_ASSET_ID",
                "DESCRIPTION",
                "TIMESTAMP",
                "DATE",
                "TIME",
                "PAID",
                "TRANSACTION_TYPE",
                "BASE_AMOUNT",
                "TRANSFER_UID",
                "FEES_NOTES",
                "LOCAL_AMOUNT",
                "MARK",
                "TRANSFER_FEES",
                "UPDATED_TIME",
                "CURRENCY_ID",
                "AMOUNT_ACCOUNT",
            ]
        )
        # DAX: EXCH_RATE = DIVIDE(AMOUNT_ACCOUNT, LOCAL_AMOUNT, 0)
        .with_columns(
            pl.when(pl.col("LOCAL_AMOUNT") == 0)
            .then(0.0)
            .otherwise(pl.col("AMOUNT_ACCOUNT") / pl.col("LOCAL_AMOUNT"))
            .alias("EXCH_RATE")
        )
    )

    return df_transformed


def transform_f_expense_transactions(base_transactions_lazy: pl.LazyFrame) -> pl.LazyFrame:
    """
    Branches off the base transactions for Expenses (TYPE = 1)
    and applies the EXCH_RATE calculation.
    """
    df_transformed = (
        base_transactions_lazy.filter(pl.col("TRANSACTION_TYPE") == 1)
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "UID",
                "ASSET_ID",
                "CARDDIVIDMONTH",
                "CATEGORY_ID",
                "TO_ASSET_ID",
                "DESCRIPTION",
                "TIMESTAMP",
                "DATE",
                "TIME",
                "PAID",
                "TRANSACTION_TYPE",
                "BASE_AMOUNT",
                "TRANSFER_UID",
                "FEES_NOTES",
                "LOCAL_AMOUNT",
                "MARK",
                "TRANSFER_FEES",
                "UPDATED_TIME",
                "CURRENCY_ID",
                "AMOUNT_ACCOUNT",
            ]
        )
        # DAX: EXCH_RATE = DIVIDE(AMOUNT_ACCOUNT, LOCAL_AMOUNT, 0)
        .with_columns(
            pl.when(pl.col("LOCAL_AMOUNT") == 0)
            .then(0.0)
            .otherwise(pl.col("AMOUNT_ACCOUNT") / pl.col("LOCAL_AMOUNT"))
            .alias("EXCH_RATE")
        )
    )

    return df_transformed


def transform_f_transfer_transactions(
    base_transactions_lazy: pl.LazyFrame,
    df_d_asset_subcategory_lazy: pl.LazyFrame,
    df_d_asset_category_lazy: pl.LazyFrame,
) -> pl.LazyFrame:
    """
    Branches off base transactions for Transfers (TYPE = 3 or 4)
    and applies RELATED() logic via joins, plus temporal shifts for EDATE().
    """

    # 1. Replicate DAX RELATED() by joining up the Asset hierarchy
    # Join Transactions (ASSET_ID) -> SubCategory (UID)
    df_joined_sub = base_transactions_lazy.join(
        df_d_asset_subcategory_lazy.select([pl.col("UID").alias("SUB_UID"), "ASSET_GROUP_ID"]),
        left_on="ASSET_ID",
        right_on="SUB_UID",
        how="left",
    )

    # Join SubCategory (ASSET_GROUP_ID) -> Category (UID) to get ASSET_GROUP
    df_joined_cat = df_joined_sub.join(
        df_d_asset_category_lazy.select([pl.col("UID").alias("CAT_UID"), "ASSET_GROUP"]),
        left_on="ASSET_GROUP_ID",
        right_on="CAT_UID",
        how="left",
    )

    df_transformed = (
        df_joined_cat
        # Filter for Types 3 or 4
        .filter((pl.col("TRANSACTION_TYPE") == 3) | (pl.col("TRANSACTION_TYPE") == 4))
        # Select base columns
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "UID",
                "ASSET_ID",
                "CARDDIVIDMONTH",
                "CATEGORY_ID",
                "TO_ASSET_ID",
                "DESCRIPTION",
                "TIMESTAMP",
                "DATE",
                "TIME",
                "PAID",
                "TRANSACTION_TYPE",
                "BASE_AMOUNT",
                "TRANSFER_UID",
                "FEES_NOTES",
                "LOCAL_AMOUNT",
                "MARK",
                "TRANSFER_FEES",
                "UPDATED_TIME",
                "CURRENCY_ID",
                "AMOUNT_ACCOUNT",
                "ASSET_GROUP",  # Kept temporarily for the calculation
            ]
        )
        # Add Independent Calculated Columns
        .with_columns(
            # TRANSFER_TYPE
            pl.when(pl.col("TRANSACTION_TYPE") == 3)
            .then(pl.lit("Out"))
            .otherwise(pl.lit("In"))
            .alias("TRANSFER_TYPE"),
            # EXCH_RATE
            pl.when(pl.col("LOCAL_AMOUNT") == 0)
            .then(0.0)
            .otherwise(pl.col("AMOUNT_ACCOUNT") / pl.col("LOCAL_AMOUNT"))
            .alias("EXCH_RATE"),
        )
        # Add Dependent Calculated Columns (These rely on the previous step's outputs)
        .with_columns(
            # AMOUNT_PROPER
            pl.when(pl.col("TRANSFER_TYPE") == "Out")
            .then(pl.col("AMOUNT_ACCOUNT") * -1)
            .otherwise(pl.col("AMOUNT_ACCOUNT"))
            .alias("AMOUNT_PROPER"),
            # ADJUSTED_DATE_FOR_ANALYSIS (EDATE equivalent)
            pl.when(pl.col("ASSET_GROUP") == "Investments")
            .then(
                pl.col("DATE")
                .cast(pl.String)
                .str.to_date("%Y-%m-%d", strict=False)
                .dt.offset_by("-1mo")
            )
            .otherwise(pl.col("DATE").cast(pl.String).str.to_date("%Y-%m-%d", strict=False))
            .alias("ADJUSTED_DATE_FOR_ANALYSIS"),
        )
        # Clean up: Drop the temporary ASSET_GROUP column so it matches the exact schema
        .drop("ASSET_GROUP")
    )

    return df_transformed


def transform_f_opening_balances(
    raw_data: pl.LazyFrame, column_mapping: dict[str, str]
) -> pl.LazyFrame:
    """Executes the PQ logic for Opening Balances."""

    df_transformed = (
        raw_data
        # Apply the dynamic column mapping first
        .rename(column_mapping)
        # Select the columns immediately to minimize memory footprint
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "Z_PK",
                "ZUTIME",
                "ZDATE",
                "ZAMOUNT",
                "ZAMOUNTACCOUNT",
                "ZAMOUNTSUB",
                "ZCONTENT",
                "ZDO_TYPE",
                "ZASSETUID",
                "ZCATEGORYUID",
                "ZCURRENCYUID",
                "ZTOASSETUID",
                "ZTXDATESTR",
                "ZTXUIDFEE",
                "ZTXUIDTRANS",
                "ZUID",
            ]
        )
        # Enforce the strict types defined in your Power Query step.
        # Note: If ZTXDATESTR is a non-standard datetime string, replace .cast(pl.Datetime)
        # with .str.to_datetime(format="%Y-%m-%d %H:%M:%S") matching your CSV's exact format.
        .with_columns(
            pl.col("Z_PK").cast(pl.Int64),
            pl.col("ZUTIME").cast(pl.Int64),
            # PQ 'type number' handles decimals
            pl.col("ZDATE").cast(pl.Float64),
            pl.col("ZAMOUNT").cast(pl.Float64),
            pl.col("ZAMOUNTACCOUNT").cast(pl.Float64),
            pl.col("ZAMOUNTSUB").cast(pl.Float64),
            pl.col("ZDO_TYPE").cast(pl.Int64),
            pl.col("ZTXDATESTR").cast(pl.Datetime, strict=False).cast(pl.Date, strict=False),
        )
    )

    return df_transformed
