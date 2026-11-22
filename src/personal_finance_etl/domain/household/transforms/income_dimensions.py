"""Household income dimension transformations.

Owns
----
- Transformation of income categories (transform_d_income_category).
- Transformation of income subcategories with tax rules mapping (transform_d_income_subcategory).

Does not own
-------------
- Expense or asset dimensions (owned by expense_dimensions.py and asset_dimensions.py).
- Physical table insertion into DuckDB (owned by infrastructure.warehouse).
"""

from __future__ import annotations

import polars as pl

from personal_finance_etl.config.financial_rules import FinancialRules, TaxHeadConfig

__all__ = [
    "transform_d_income_category",
    "transform_d_income_subcategory",
]


def _build_tax_map_row(
    uid: str,
    head: str,
    sub_head: str,
    taxability: str,
    tax_method: str,
) -> dict[str, str]:
    """Construct a row dictionary mapping a category UID to its tax attributes.

    Parameters
    ----------
    uid : str
        Unique identifier for the category or subcategory.
    head : str
        Display name of the tax income head.
    sub_head : str
        Display name of the tax sub-head.
    taxability : str
        Taxability classification (e.g. 'Taxable', 'Exempt').
    tax_method : str
        Applicable tax calculation method.

    Returns
    -------
    dict[str, str]
        A mapping record for dimension LazyFrame construction.
    """
    return {
        "UID": uid,
        "Tax_Income_Head": head,
        "Tax_Sub_Head": sub_head,
        "Taxability": taxability,
        "Tax_Method": tax_method,
    }


def _extract_head_tax_mappings(
    heads: list[TaxHeadConfig],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Extract category and subcategory tax mapping records from tax head configurations.

    Parameters
    ----------
    heads : list[TaxHeadConfig]
        List of configured tax heads containing sub-head definitions and UID lists.

    Returns
    -------
    tuple[list[dict[str, str]], list[dict[str, str]]]
        Tuple containing category mapping rows and subcategory mapping rows.
    """
    cat_rows: list[dict[str, str]] = []
    sub_cat_rows: list[dict[str, str]] = []

    for head_config in heads:
        for sub_config in head_config.sub_heads.values():
            head = sub_config.tax_head_display_name
            sub = sub_config.sub_head_display_name
            taxability = sub_config.taxability
            method = sub_config.tax_method

            for cid in sub_config.cat_ids:
                cat_rows.append(_build_tax_map_row(cid, head, sub, taxability, method))
            for scid in sub_config.sub_cat_ids:
                sub_cat_rows.append(_build_tax_map_row(scid, head, sub, taxability, method))
            for credit_scid in sub_config.tax_credit_sub_cat_ids:
                sub_cat_rows.append(_build_tax_map_row(credit_scid, head, sub, taxability, method))

    return cat_rows, sub_cat_rows


def _get_tax_maps(rules: FinancialRules | None) -> tuple[pl.LazyFrame, pl.LazyFrame]:
    """Generate category and subcategory tax mapping LazyFrames from financial rules.

    Parameters
    ----------
    rules : FinancialRules | None
        Optional financial rules model containing tax configuration assumptions.

    Returns
    -------
    tuple[pl.LazyFrame, pl.LazyFrame]
        Pair of LazyFrames representing category and subcategory tax mappings.
    """
    schema = {
        "UID": pl.Utf8,
        "Tax_Income_Head": pl.Utf8,
        "Tax_Sub_Head": pl.Utf8,
        "Taxability": pl.Utf8,
        "Tax_Method": pl.Utf8,
    }
    if not rules:
        return pl.DataFrame(schema=schema).lazy(), pl.DataFrame(schema=schema).lazy()

    all_heads: list[TaxHeadConfig] = [
        *rules.assumptions.tax.heads_of_income.values(),
        *rules.assumptions.tax.exempt_income.values(),
        *rules.assumptions.tax.residual_income.values(),
    ]

    cat_rows, sub_cat_rows = _extract_head_tax_mappings(all_heads)

    for uid in rules.assumptions.tax.investment_exclusions.stcg_sub_cat_ids:
        sub_cat_rows.append(
            _build_tax_map_row(uid, "Capital Gains", "Investment STCG", "taxable", "capital_gains")
        )
    for uid in rules.assumptions.tax.investment_exclusions.ltcg_sub_cat_ids:
        sub_cat_rows.append(
            _build_tax_map_row(uid, "Capital Gains", "Investment LTCG", "taxable", "capital_gains")
        )

    cat_df = (
        pl.DataFrame(cat_rows, schema=schema).lazy()
        if cat_rows
        else pl.DataFrame(schema=schema).lazy()
    )
    sub_cat_df = (
        pl.DataFrame(sub_cat_rows, schema=schema).lazy()
        if sub_cat_rows
        else pl.DataFrame(schema=schema).lazy()
    )

    return cat_df, sub_cat_df


def transform_d_income_category(
    df_lazy: pl.LazyFrame, column_mapping: dict[str, str], _rules: FinancialRules | None = None
) -> pl.LazyFrame:
    """Execute the PQ and DAX logic using Polars LazyFrames."""
    return (
        df_lazy.rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
        .filter(
            (pl.col("TYPE") == 0)
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
        .with_columns(
            pl.col("CATEGORY_NAME")
            .str.replace("Income from ", "", literal=True)
            .alias("CATEGORY_NAME_SHORT")
        )
    )


def _classify_income_rules(df_transformed: pl.LazyFrame, rules: FinancialRules) -> pl.LazyFrame:
    """Classify income streams into active, dividend, interest, non-cash, and tax credits."""
    active_cats = rules.income.active.category_ids
    active_subcats = rules.income.active.sub_category_ids
    div_cats = rules.income.dividends.category_ids
    div_subcats = rules.income.dividends.sub_category_ids
    int_cats = rules.income.interest.category_ids
    int_subcats = rules.income.interest.sub_category_ids
    non_cash_cats = rules.income.non_cash.category_ids
    non_cash_subcats = rules.income.non_cash.sub_category_ids

    inv_exclusions = (
        rules.assumptions.tax.investment_exclusions.stcg_sub_cat_ids
        + rules.assumptions.tax.investment_exclusions.ltcg_sub_cat_ids
    )

    tax_credit_subcats: list[str] = []
    all_tax_heads: list[tuple[str, TaxHeadConfig]] = []
    all_tax_heads.extend(rules.assumptions.tax.heads_of_income.items())
    all_tax_heads.extend(rules.assumptions.tax.exempt_income.items())
    all_tax_heads.extend(rules.assumptions.tax.residual_income.items())
    for _h, head in all_tax_heads:
        for _s, sub in head.sub_heads.items():
            tax_credit_subcats.extend(sub.tax_credit_sub_cat_ids)

    return df_transformed.with_columns(
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
        pl.when(pl.col("CATEGORY_ID").is_in(non_cash_cats) | pl.col("UID").is_in(non_cash_subcats))
        .then(pl.lit(True))
        .otherwise(pl.lit(False))
        .alias("Is_Non_Cash_Income"),
        pl.when(pl.col("UID").is_in(inv_exclusions))
        .then(pl.lit(True))
        .otherwise(pl.lit(False))
        .alias("Is_Investment_Exclusion"),
        pl.when(pl.col("UID").is_in(tax_credit_subcats))
        .then(pl.lit(True))
        .otherwise(pl.lit(False))
        .alias("Is_Tax_Credits"),
    ).with_columns(
        (pl.col("Is_Dividend_Income") | pl.col("Is_Interest_Income")).alias("Is_Passive_Income")
    )


def _join_income_tax_mappings(
    df_transformed: pl.LazyFrame, rules: FinancialRules | None
) -> pl.LazyFrame:
    """Enrich income subcategories with tax heads, taxability, and tax methods."""
    cat_df, sub_cat_df = _get_tax_maps(rules)
    cat_df = cat_df.rename({c: f"cat_{c}" for c in cat_df.collect_schema().names() if c != "UID"})

    df_transformed = df_transformed.join(sub_cat_df, on="UID", how="left")
    df_transformed = df_transformed.join(cat_df, left_on="CATEGORY_ID", right_on="UID", how="left")

    return df_transformed.with_columns(
        pl.coalesce(["Tax_Income_Head", "cat_Tax_Income_Head"])
        .fill_null("CHECK_REQUIRED")
        .alias("Tax_Income_Head"),
        pl.coalesce(["Tax_Sub_Head", "cat_Tax_Sub_Head"])
        .fill_null("CHECK_REQUIRED")
        .alias("Tax_Sub_Head"),
        pl.coalesce(["Taxability", "cat_Taxability"]).fill_null("review").alias("Taxability"),
        pl.coalesce(["Tax_Method", "cat_Tax_Method"]).fill_null("review").alias("Tax_Method"),
    ).drop(["cat_Tax_Income_Head", "cat_Tax_Sub_Head", "cat_Taxability", "cat_Tax_Method"])


def transform_d_income_subcategory(
    df_lazy: pl.LazyFrame,
    column_mapping: dict[str, str],
    df_d_income_category_lazy: pl.LazyFrame,
    rules: FinancialRules | None = None,
) -> pl.LazyFrame:
    """Execute the PQ and DAX logic for Income Subcategories."""
    df_pq = (
        df_lazy.rename(column_mapping)
        .with_columns(pl.col("IS_DEL").cast(pl.String))
        .filter(pl.col("IS_DEL").fill_null("0") == "0")
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

    df_joined = df_pq.join(
        df_d_income_category_lazy.select(["UID", "CATEGORY_NAME_SHORT"]),
        left_on="CATEGORY_ID",
        right_on="UID",
        how="left",
    )

    df_transformed = df_joined.with_columns(
        pl.when(
            (pl.col("CATEGORY_NAME_SHORT") == "Salary")
            & pl.col("CATEGORY_NAME").str.contains("(?i)allowance")
        )
        .then(pl.lit("Allowances"))
        .otherwise(pl.col("CATEGORY_NAME"))
        .alias("CATEGORY_GROUPS")
    ).drop("CATEGORY_NAME_SHORT")

    if rules:
        df_transformed = _classify_income_rules(df_transformed, rules)
    else:
        df_transformed = df_transformed.with_columns(
            pl.lit(False).alias("Is_Active_Income"),
            pl.lit(False).alias("Is_Dividend_Income"),
            pl.lit(False).alias("Is_Interest_Income"),
            pl.lit(False).alias("Is_Passive_Income"),
            pl.lit(False).alias("Is_Non_Cash_Income"),
            pl.lit(False).alias("Is_Investment_Exclusion"),
            pl.lit(False).alias("Is_Tax_Credits"),
        )

    return _join_income_tax_mappings(df_transformed, rules)
