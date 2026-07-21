import polars as pl


def transform_d_income_category(
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str]
) -> pl.LazyFrame:
    """Executes the PQ and DAX logic using Polars LazyFrames."""

    df_transformed = (
        df_lazy
        # PQ: #"Renamed Columns"
        .rename(column_mapping)
        # PQ: CATEGORY_MASTER -> #"Filtered Rows" (IS_DEL <> 1)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        # PQ: d_Income_Category -> #"Filtered Rows"
        # (TYPE = 0) and ((Length(CATEGORY_ID) < 1) or CATEGORY_ID is null)
        .filter(
            (pl.col("TYPE") == 0)
            & (pl.col("CATEGORY_ID").is_null() | (pl.col("CATEGORY_ID").str.len_chars() < 1))
        )
        # PQ: #"Removed Other Columns"
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "MODIFY_DATE",
                "UID",
                "CATEGORY_NAME",
                "ORDER_SEQUENCE",
            ]
        )
        # DAX: CATEGORY_NAME_SHORT
        # Using string replacement to remove "Income from " if it exists
        .with_columns(
            pl.col("CATEGORY_NAME")
            .str.replace("Income from ", "", literal=True)
            .alias("CATEGORY_NAME_SHORT")
        )
    )

    return df_transformed


def transform_d_income_subcategory(
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str], df_d_income_category_lazy: pl.LazyFrame
) -> pl.LazyFrame:
    """
    Executes the PQ and DAX logic for Income Subcategories.
    Requires the lazy frame of d_Income_Category to replicate DAX's RELATED().
    """
    # 1. Power Query Steps
    df_pq = (
        df_lazy.rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        # TYPE = 0 AND CATEGORY_ID length > 0
        .filter(
            (pl.col("TYPE") == 0)
            & pl.col("CATEGORY_ID").is_not_null()
            & (pl.col("CATEGORY_ID").str.len_chars() > 0)
        )
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "MODIFY_DATE",
                "UID",
                "CATEGORY_NAME",
                "ORDER_SEQUENCE",
                "CATEGORY_ID",
            ]
        )
    )

    # 2. DAX Steps (RELATED and IF/SEARCH)
    # Replicate RELATED(d_IncomeCategory[CATEGORY_NAME_SHORT])
    df_joined = df_pq.join(
        df_d_income_category_lazy.select(["UID", "CATEGORY_NAME_SHORT"]),
        left_on="CATEGORY_ID",
        right_on="UID",
        how="left",
    )

    df_transformed = (
        df_joined.with_columns(
            # DAX: SEARCH is case-insensitive. We use "(?i)" in Polars regex to mimic this.
            # ISERROR(SEARCH) means "If it does NOT contain 'Allowance', then [CATEGORY_NAME], else 'Allowances'"
            pl.when(
                (pl.col("CATEGORY_NAME_SHORT") == "Salary")
                & pl.col("CATEGORY_NAME").str.contains("(?i)allowance")
            )
            .then(pl.lit("Allowances"))
            .otherwise(pl.col("CATEGORY_NAME"))
            .alias("CATEGORY_GROUPS")
        )
        # Drop the joined column to keep the table matching the exact output needed
        .drop("CATEGORY_NAME_SHORT")
    )

    return df_transformed


def transform_d_expense_category(
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str]
) -> pl.LazyFrame:
    """Executes the PQ logic for Expense Categories (TYPE = 1)."""

    df_transformed = (
        df_lazy.rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        # TYPE = 1 (Expense) and parent category check (null or empty)
        .filter(
            (pl.col("TYPE") == 1)
            & (pl.col("CATEGORY_ID").is_null() | (pl.col("CATEGORY_ID").str.len_chars() < 1))
        )
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "MODIFY_DATE",
                "UID",
                "CATEGORY_NAME",
                "ORDER_SEQUENCE",
            ]
        )
    )

    return df_transformed


def transform_d_expense_subcategory(
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str]
) -> pl.LazyFrame:
    """Executes the PQ logic for Expense Subcategories."""

    df_transformed = (
        df_lazy.rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        # TYPE = 1 (Expense) and child category check (has parent ID)
        .filter(
            (pl.col("TYPE") == 1)
            & pl.col("CATEGORY_ID").is_not_null()
            & (pl.col("CATEGORY_ID").str.len_chars() > 0)
        )
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "MODIFY_DATE",
                "UID",
                "CATEGORY_NAME",
                "ORDER_SEQUENCE",
                "CATEGORY_ID",
            ]
        )
    )

    return df_transformed


def transform_d_asset_category(
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str]
) -> pl.LazyFrame:
    """Executes the PQ logic for Asset Categories (ASSETGROUP)."""

    df_transformed = (
        df_lazy.rename(column_mapping)
        # IS_DEL <> 1
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "DEVICE_ID",
                "UID",
                "USE_TIME",
                "ASSET_GROUP",
                "TYPE",
                "ORDER_SEQUENCE",
            ]
        )
    )

    return df_transformed


def transform_d_asset_subcategory(
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str]
) -> pl.LazyFrame:
    """Executes the PQ logic for Asset Subcategories (ASSETS)."""

    df_transformed = (
        df_lazy.rename(column_mapping)
        # IS_DEL = 0
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "CARD_STATEMENT_DATE",
                "CARD_PAYMENT_DATE",
                "ASSET_NAME",
                "ORDER_SEQUENCE",
                "ASSET_DESCRIPTION",
                "NOTES",
                "TRANSFER_EXPENSE",
                "CARD_AUTOPAY",
                "ADDED_TIME",
                "UID",
                "CURRENCY_ID",
                "AUTOPAY_ASSET_ID",
                "ASSET_GROUP_ID",
            ]
        )
    )

    return df_transformed


def transform_d_currency(df_lazy: pl.LazyFrame, column_mapping: dict[str, str]) -> pl.LazyFrame:
    """Executes the PQ logic for the Currency Master table."""

    df_transformed = (
        df_lazy.rename(column_mapping)
        # IS_DEL <> 1
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .select(
            [
                "__file_name__",
                "__folder_path__",
                "S_NO",
                "UID",
                "CURRENCY_NAME",
                "ISO",
                "MAIN_ISO",
                "ORDER_SEQUENCE",
                "RATE",
                "SYMBOL",
                "INSERT_TYPE",
                "SYMBOL_POSITION",
                "IS_MAIN_CURRENCY",
                "IS_SHOW",
                "MODIFY_DATE",
                "DECIMAL_POINT",
            ]
        )
    )

    return df_transformed


def transform_d_investment_benchmark_master(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """Executes the PQ logic for the Benchmark Master table."""
    return raw_data.select(
        [
            "__file_name__",
            "__folder_path__",
            "ID",
            "Benchmark_Name",
            "yF_Ticker",
            "Currency",
        ]
    )


def transform_d_tax_rates(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """Executes the PQ logic for the Tax Rates table."""
    return raw_data.select(
        [
            "__file_name__",
            "__folder_path__",
            "FY",
            "FY_Start_Date",
            "FY_End_Date",
            "Debt_MF_Cutoff_Date",
            "Equity_Listed_LTCG",
            "Equity_Listed_STCG",
            "Equity_Unlisted_LTCG",
            "Equity_Unlisted_STCG",
            "Gold_LTCG",
            "Gold_STCG",
            "Debt_MF_Pre_Cutoff_LTCG",
            "Debt_MF_Pre_Cutoff_STCG",
            "Debt_MF_Post_Cutoff_LTCG",
            "Debt_MF_Post_Cutoff_STCG",
            "Other_Debt_LTCG",
            "Other_Debt_STCG",
            "Default_LTCG",
            "Default_STCG",
            "Equity_LTCG_Exemption",
            "Remarks",
        ]
    )
