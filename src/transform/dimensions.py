import polars as pl

from src.config.financial_rules import FinancialRules


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
    df_lazy: pl.LazyFrame,
    column_mapping: dict[str, str],
    df_d_income_category_lazy: pl.LazyFrame,
    rules: FinancialRules | None = None,
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

    if rules:
        active_cats = rules.income.active.category_ids
        active_subcats = rules.income.active.sub_category_ids
        div_cats = rules.income.dividends.category_ids
        div_subcats = rules.income.dividends.sub_category_ids
        int_cats = rules.income.interest.category_ids
        int_subcats = rules.income.interest.sub_category_ids

        df_transformed = df_transformed.with_columns(
            pl.when(pl.col("CATEGORY_ID").is_in(active_cats) | pl.col("UID").is_in(active_subcats))
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("Is_Active_Income"),
            pl.when(pl.col("CATEGORY_ID").is_in(div_cats) | pl.col("UID").is_in(div_subcats))
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("Is_Dividend_Income"),
            pl.when(pl.col("CATEGORY_ID").is_in(int_cats) | pl.col("UID").is_in(int_subcats))
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("Is_Interest_Income"),
        ).with_columns(
            (pl.col("Is_Dividend_Income") | pl.col("Is_Interest_Income")).alias("Is_Passive_Income")
        )
    else:
        df_transformed = df_transformed.with_columns(
            pl.lit(False).alias("Is_Active_Income"),
            pl.lit(False).alias("Is_Dividend_Income"),
            pl.lit(False).alias("Is_Interest_Income"),
            pl.lit(False).alias("Is_Passive_Income"),
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
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str], rules: FinancialRules | None = None
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

    if rules:
        core_cats = rules.expense.core.category_ids
        core_subcats = rules.expense.core.sub_category_ids

        df_transformed = df_transformed.with_columns(
            pl.when(pl.col("CATEGORY_ID").is_in(core_cats) | pl.col("UID").is_in(core_subcats))
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("Is_Core_Expense")
        )
    else:
        df_transformed = df_transformed.with_columns(pl.lit(False).alias("Is_Core_Expense"))

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
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str], rules: FinancialRules | None = None
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

    if rules:
        illiquid_cats = rules.assets.illiquid.category_ids
        illiquid_subcats = rules.assets.illiquid.sub_category_ids

        df_transformed = df_transformed.with_columns(
            pl.when(
                pl.col("ASSET_GROUP_ID").is_in(illiquid_cats)
                | pl.col("UID").is_in(illiquid_subcats)
            )
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("Is_Illiquid")
        ).with_columns((~pl.col("Is_Illiquid")).alias("Is_Liquid"))
    else:
        df_transformed = df_transformed.with_columns(
            pl.lit(False).alias("Is_Illiquid"),
            pl.lit(True).alias("Is_Liquid"),
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


def transform_d_macro_parameters(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """Executes the PQ logic for the Macro Parameters table."""
    return raw_data.select(
        [
            "FY",
            "__file_name__",
            "__folder_path__",
            "FY_Start_Date",
            "FY_End_Date",
            "Debt_MF_Cutoff_Date",
            "Inflation_Rate",
            "Risk_Free_Rate",
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
            "Dividend_Income_Tax_Rate",
            "Equity_LTCG_Exemption",
            "Remarks",
        ]
    )
