import polars as pl

from personal_finance_etl.backend.config.financial_rules import FinancialRules


def _get_tax_maps(rules: FinancialRules | None):
    schema = {"UID": pl.Utf8, "Tax_Income_Head": pl.Utf8, "Tax_Sub_Head": pl.Utf8, "Taxability": pl.Utf8, "Tax_Method": pl.Utf8}
    if not rules:
        return pl.DataFrame(schema=schema).lazy(), pl.DataFrame(schema=schema).lazy()
    
    cat_rows: list[dict[str, str]] = []
    sub_cat_rows: list[dict[str, str]] = []
    
    all_heads = list(rules.assumptions.tax.heads_of_income.items())
    all_heads.append(("Residual", rules.assumptions.tax.residual_income))
    all_heads.append(("Exempt_Income", rules.assumptions.tax.exempt_income))
    
    for head_name, head_config in all_heads:
        for sub_name, sub_config in head_config.sub_heads.items():
            for cat_id in sub_config.cat_ids:
                cat_rows.append({
                    "UID": cat_id,
                    "Tax_Income_Head": head_name,
                    "Tax_Sub_Head": sub_name,
                    "Taxability": sub_config.taxability,
                    "Tax_Method": sub_config.tax_method
                })
            for sub_cat_id in sub_config.sub_cat_ids:
                sub_cat_rows.append({
                    "UID": sub_cat_id,
                    "Tax_Income_Head": head_name,
                    "Tax_Sub_Head": sub_name,
                    "Taxability": sub_config.taxability,
                    "Tax_Method": sub_config.tax_method
                })
                
    cat_df = pl.DataFrame(cat_rows, schema=schema).lazy() if cat_rows else pl.DataFrame(schema=schema).lazy()
    sub_cat_df = pl.DataFrame(sub_cat_rows, schema=schema).lazy() if sub_cat_rows else pl.DataFrame(schema=schema).lazy()
    
    return cat_df, sub_cat_df

def transform_d_income_category(
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str], rules: FinancialRules | None = None
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

    cat_df, _ = _get_tax_maps(rules)
    df_transformed = df_transformed.join(cat_df, on="UID", how="left")
    
    df_transformed = df_transformed.with_columns(
        pl.col("Tax_Income_Head").fill_null("CHECK_REQUIRED"),
        pl.col("Tax_Sub_Head").fill_null("CHECK_REQUIRED"),
        pl.col("Taxability").fill_null("review"),
        pl.col("Tax_Method").fill_null("review")
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
        non_cash_cats = rules.income.non_cash.category_ids
        non_cash_subcats = rules.income.non_cash.sub_category_ids

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
            pl.when(
                pl.col("CATEGORY_ID").is_in(non_cash_cats) | pl.col("UID").is_in(non_cash_subcats)
            )
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("Is_Non_Cash_Income"),
        ).with_columns(
            (pl.col("Is_Dividend_Income") | pl.col("Is_Interest_Income")).alias("Is_Passive_Income")
        )

    else:
        df_transformed = df_transformed.with_columns(
            pl.lit(False).alias("Is_Active_Income"),
            pl.lit(False).alias("Is_Dividend_Income"),
            pl.lit(False).alias("Is_Interest_Income"),
            pl.lit(False).alias("Is_Passive_Income"),
            pl.lit(False).alias("Is_Non_Cash_Income"),
        )

    cat_df, sub_cat_df = _get_tax_maps(rules)
    cat_df = cat_df.rename({c: f"cat_{c}" for c in cat_df.collect_schema().names() if c != "UID"})
    
    df_transformed = df_transformed.join(sub_cat_df, on="UID", how="left")
    df_transformed = df_transformed.join(cat_df, left_on="CATEGORY_ID", right_on="UID", how="left")
    
    df_transformed = df_transformed.with_columns(
        pl.coalesce(["Tax_Income_Head", "cat_Tax_Income_Head"]).fill_null("CHECK_REQUIRED").alias("Tax_Income_Head"),
        pl.coalesce(["Tax_Sub_Head", "cat_Tax_Sub_Head"]).fill_null("CHECK_REQUIRED").alias("Tax_Sub_Head"),
        pl.coalesce(["Taxability", "cat_Taxability"]).fill_null("review").alias("Taxability"),
        pl.coalesce(["Tax_Method", "cat_Tax_Method"]).fill_null("review").alias("Tax_Method")
    ).drop(["cat_Tax_Income_Head", "cat_Tax_Sub_Head", "cat_Taxability", "cat_Tax_Method"])

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
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str], rules: FinancialRules | None = None
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

    if rules:
        digital_cats = rules.assets.digital.category_ids
        cash_pools = rules.assets.cashflow.cash_pools
        non_cash_pnl = rules.assets.cashflow.non_cash_pnl_sources
        working_capital = rules.assets.cashflow.working_capital_conduits
        investing = rules.assets.cashflow.investing_activities
        financing = rules.assets.cashflow.financing_liabilities

        df_transformed = df_transformed.with_columns(
            pl.when(pl.col("UID").is_in(digital_cats))
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("Is_Digital_Asset"),
            pl.when(pl.col("UID").is_in(cash_pools))
            .then(pl.lit("CASH_POOL"))
            .when(pl.col("UID").is_in(non_cash_pnl))
            .then(pl.lit("NON_CASH_PNL"))
            .when(pl.col("UID").is_in(working_capital))
            .then(pl.lit("WORKING_CAPITAL_CONDUIT"))
            .when(pl.col("UID").is_in(investing))
            .then(pl.lit("INVESTING_ASSET"))
            .when(pl.col("UID").is_in(financing))
            .then(pl.lit("FINANCING_LIABILITY"))
            .otherwise(pl.lit("UNCLASSIFIED"))
            .alias("ledger_role"),
            pl.when(pl.col("UID").is_in(cash_pools))
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("is_cash_pool"),
            pl.when(pl.col("UID").is_in(non_cash_pnl))
            .then(pl.lit(True))
            .otherwise(pl.lit(False))
            .alias("is_non_cash_pnl"),
        ).with_columns(
            pl.when(pl.col("ledger_role") == "CASH_POOL")
            .then(pl.lit("INTERNAL_TRANSFER"))
            .when(pl.col("ledger_role").is_in(["NON_CASH_PNL", "WORKING_CAPITAL_CONDUIT"]))
            .then(pl.lit("OPERATING"))
            .when(pl.col("ledger_role") == "INVESTING_ASSET")
            .then(pl.lit("INVESTING"))
            .when(pl.col("ledger_role") == "FINANCING_LIABILITY")
            .then(pl.lit("FINANCING"))
            .otherwise(pl.lit(None).cast(pl.String))
            .alias("cashflow_activity_type"),
            pl.when(pl.col("ledger_role") == "CASH_POOL")
            .then(pl.lit("IMMEDIATE_CASH"))
            .when(
                pl.col("ledger_role").is_in(
                    [
                        "NON_CASH_PNL",
                        "WORKING_CAPITAL_CONDUIT",
                        "INVESTING_ASSET",
                        "FINANCING_LIABILITY",
                    ]
                )
            )
            .then(pl.lit("DEFERRED_ACCRUAL"))
            .otherwise(pl.lit(None).cast(pl.String))
            .alias("settlement_timing"),
        )
    else:
        df_transformed = df_transformed.with_columns(
            pl.lit(False).alias("Is_Digital_Asset"),
            pl.lit("UNCLASSIFIED").alias("ledger_role"),
            pl.lit(False).alias("is_cash_pool"),
            pl.lit(False).alias("is_non_cash_pnl"),
            pl.lit(None).cast(pl.String).alias("cashflow_activity_type"),
            pl.lit(None).cast(pl.String).alias("settlement_timing"),
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
        digital_cats = rules.assets.digital.category_ids
        cash_pools = rules.assets.cashflow.cash_pools
        non_cash_pnl = rules.assets.cashflow.non_cash_pnl_sources
        working_capital = rules.assets.cashflow.working_capital_conduits
        investing = rules.assets.cashflow.investing_activities
        financing = rules.assets.cashflow.financing_liabilities

        df_transformed = (
            df_transformed.with_columns(
                pl.when(
                    pl.col("ASSET_GROUP_ID").is_in(illiquid_cats)
                    | pl.col("UID").is_in(illiquid_subcats)
                )
                .then(pl.lit(True))
                .otherwise(pl.lit(False))
                .alias("Is_Illiquid"),
                pl.when(pl.col("ASSET_GROUP_ID").is_in(digital_cats))
                .then(pl.lit(True))
                .otherwise(pl.lit(False))
                .alias("Is_Digital_Asset"),
                pl.when(pl.col("ASSET_GROUP_ID").is_in(cash_pools))
                .then(pl.lit("CASH_POOL"))
                .when(pl.col("ASSET_GROUP_ID").is_in(non_cash_pnl))
                .then(pl.lit("NON_CASH_PNL"))
                .when(pl.col("ASSET_GROUP_ID").is_in(working_capital))
                .then(pl.lit("WORKING_CAPITAL_CONDUIT"))
                .when(pl.col("ASSET_GROUP_ID").is_in(investing))
                .then(pl.lit("INVESTING_ASSET"))
                .when(pl.col("ASSET_GROUP_ID").is_in(financing))
                .then(pl.lit("FINANCING_LIABILITY"))
                .otherwise(pl.lit("UNCLASSIFIED"))
                .alias("ledger_role"),
                pl.when(pl.col("ASSET_GROUP_ID").is_in(cash_pools))
                .then(pl.lit(True))
                .otherwise(pl.lit(False))
                .alias("is_cash_pool"),
                pl.when(pl.col("ASSET_GROUP_ID").is_in(non_cash_pnl))
                .then(pl.lit(True))
                .otherwise(pl.lit(False))
                .alias("is_non_cash_pnl"),
            )
            .with_columns((~pl.col("Is_Illiquid")).alias("Is_Liquid"))
            .with_columns(
                pl.when(pl.col("ledger_role") == "CASH_POOL")
                .then(pl.lit("INTERNAL_TRANSFER"))
                .when(pl.col("ledger_role").is_in(["NON_CASH_PNL", "WORKING_CAPITAL_CONDUIT"]))
                .then(pl.lit("OPERATING"))
                .when(pl.col("ledger_role") == "INVESTING_ASSET")
                .then(pl.lit("INVESTING"))
                .when(pl.col("ledger_role") == "FINANCING_LIABILITY")
                .then(pl.lit("FINANCING"))
                .otherwise(pl.lit(None).cast(pl.String))
                .alias("cashflow_activity_type"),
                pl.when(pl.col("ledger_role") == "CASH_POOL")
                .then(pl.lit("IMMEDIATE_CASH"))
                .when(
                    pl.col("ledger_role").is_in(
                        [
                            "NON_CASH_PNL",
                            "WORKING_CAPITAL_CONDUIT",
                            "INVESTING_ASSET",
                            "FINANCING_LIABILITY",
                        ]
                    )
                )
                .then(pl.lit("DEFERRED_ACCRUAL"))
                .otherwise(pl.lit(None).cast(pl.String))
                .alias("settlement_timing"),
            )
        )
    else:
        df_transformed = df_transformed.with_columns(
            pl.lit(False).alias("Is_Illiquid"),
            pl.lit(True).alias("Is_Liquid"),
            pl.lit(False).alias("Is_Digital_Asset"),
            pl.lit("UNCLASSIFIED").alias("ledger_role"),
            pl.lit(False).alias("is_cash_pool"),
            pl.lit(False).alias("is_non_cash_pnl"),
            pl.lit(None).cast(pl.String).alias("cashflow_activity_type"),
            pl.lit(None).cast(pl.String).alias("settlement_timing"),
        )

    return df_transformed


def transform_d_currency(
    df_lazy: pl.LazyFrame,
    column_mapping: dict[str, str],
    mapping_lazy: pl.LazyFrame | None = None,
) -> pl.LazyFrame:
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

    if mapping_lazy is not None:
        mapping_lazy = mapping_lazy.select(
            ["UID", "Target_Currency_Code", "yF_Ticker", "Is_Active"]
        )
        if "Is_Active" in mapping_lazy.collect_schema().names():
            mapping_lazy = mapping_lazy.with_columns(
                pl.col("Is_Active").cast(pl.Boolean).fill_null(False)
            )
        df_transformed = df_transformed.join(mapping_lazy, on="UID", how="left")
    else:
        df_transformed = df_transformed.with_columns(
            pl.lit(None).cast(pl.String).alias("Target_Currency_Code"),
            pl.lit(None).cast(pl.String).alias("yF_Ticker"),
            pl.lit(False).alias("Is_Active"),
        )

    return df_transformed


def transform_d_investment_benchmark_master(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """Executes the PQ logic for the Benchmark Master table."""
    return raw_data.rename({"Currency": "CURRENCY_ID"}).select(
        [
            "__file_name__",
            "__folder_path__",
            "ID",
            "Benchmark_Name",
            "yF_Ticker",
            "CURRENCY_ID",
        ]
    )


def transform_d_macro_parameters(raw_data: pl.LazyFrame) -> pl.LazyFrame:
    """Executes the PQ logic for the Macro Parameters table."""
    return raw_data.with_columns(
        (
            pl.col("FY").str.extract(r"(20\d{2})", 1).cast(pl.Int64).cast(pl.String)
            + "-"
            + (pl.col("FY").str.extract(r"(20\d{2})", 1).cast(pl.Int64) + 1).cast(pl.String).str.slice(2, 2)
        ).alias("FY")
    ).select(
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
            "Estimated_Ordinary_Income_Tax_Rate",
            "Equity_LTCG_Exemption",
            "Remarks",
        ]
    )
