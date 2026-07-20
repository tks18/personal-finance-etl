import calendar
from datetime import date

import polars as pl
from dateutil.relativedelta import relativedelta


def get_column_mapping(df_map: pl.DataFrame, table_name: str = "CATEGORY") -> dict[str, str]:
    """Filters the pre-loaded COLUMN_MASTER DataFrame and returns a dictionary of {OLD_COLUMN: NEW_COLUMN}"""
    # Filter for the specific table and create a dict
    mapping = (
        df_map.filter(pl.col("TABLE_NAME") == table_name)
        .select(["OLD_COLUMN", "NEW_COLUMN"])
        .rows()
    )
    return {old: new for old, new in mapping}


def get_stg_mf_isin_mapping(csv_path: str) -> pl.LazyFrame:
    """
    Loads the ISIN mapping as a LazyFrame.
    This will NOT be written to SQLite. It will be passed to the
    Investment Master transformation to replicate the DAX calculated column.
    """
    schema_overrides = {"INSTRUMENT_NAME": pl.String, "ISIN": pl.String}

    # Return the LazyFrame directly
    return pl.scan_csv(csv_path, schema_overrides=schema_overrides)


def get_stg_benchmark_mapping(csv_path: str) -> pl.LazyFrame:
    """
    Loads the Benchmark mapping as a LazyFrame.
    Will be passed to the Investment Master transformation to replicate
    DAX calculated columns via joins.
    """
    schema_overrides = {
        "ISIN": pl.String,
        "Sector": pl.String,
        "Industry": pl.String,
        "Benchmark_ID": pl.String,
    }

    # Return the LazyFrame directly
    return pl.scan_csv(csv_path, schema_overrides=schema_overrides)


def get_purchase_reference(
    df_lazy: pl.LazyFrame, instrument_col: str, date_col: str, price_col: str, qty_col: str
) -> pl.LazyFrame:
    """
    Translates DAX SUMMARIZE + CALCULATE(SUM) for Purchases.
    Groups by Instrument, ISIN, Date, and Price, then sums the Quantity.
    Returns: ISIN, Date, Price, Quantity, Value
    """
    df_grouped = (
        df_lazy
        # SUMMARIZE equivalent
        .group_by(
            [
                "ISIN",
                pl.col(instrument_col).alias("Instrument name"),
                pl.col(date_col).alias("Date"),
                pl.col(price_col).alias("Price"),
            ]
        )
        # CALCULATE(SUM(Quantity)) equivalent
        .agg(pl.col(qty_col).sum().alias("Quantity"))
        # DAX: Value = Quantity * Price
        .with_columns((pl.col("Quantity") * pl.col("Price")).alias("Value"))
    )
    return df_grouped


def get_sale_reference(
    df_sale_lazy: pl.LazyFrame,
    df_purchase_ref_lazy: pl.LazyFrame,
    instrument_col: str,
    date_col: str,
    price_col: str,
    qty_col: str,
) -> pl.LazyFrame:
    """
    Translates DAX SUMMARIZE + CALCULATE(SUM) for Sales.
    Also calculates the Rolling Average Buy Price based on historical purchases.
    """

    # Step 1: Base Sale Aggregation (SUMMARIZE + SUM(Quantity))
    df_sale_grouped = (
        df_sale_lazy.group_by(
            [
                "ISIN",
                pl.col(instrument_col).alias("Instrument name"),
                pl.col(date_col).alias("Date"),
                pl.col(price_col).alias("Sell Price"),
            ]
        )
        .agg(pl.col(qty_col).sum().alias("Quantity"))
        .with_columns((pl.col("Quantity") * pl.col("Sell Price")).alias("Sell Value"))
    )

    # Step 2: Cumulative Sum of Purchases (Rolling calculation for DAX VAR Qty & VAR Val)
    # We sort by ISIN and Date, then calculate rolling sums to get total historical buys up to each date
    df_purchase_rolling = (
        df_purchase_ref_lazy.select(["ISIN", "Date", "Quantity", "Value"])
        .sort(["ISIN", "Date"])
        .with_columns(
            [
                pl.col("Quantity").cum_sum().over("ISIN").alias("Cum_Buy_Qty"),
                pl.col("Value").cum_sum().over("ISIN").alias("Cum_Buy_Val"),
            ]
        )
    )

    # Step 3: ASOF Join (Replicating FILTER(Date <= Sale Date))
    # join_asof perfectly matches each sale to the most recent historical purchase state
    df_final = (
        df_sale_grouped.sort(["ISIN", "Date"])  # Both frames must be sorted by the join keys
        .with_columns(pl.col("Date"))
        .join_asof(
            df_purchase_rolling.sort(["ISIN", "Date"]),
            on="Date",
            by="ISIN",
            strategy="backward",  # Matches the closest date <= Sale Date
        )
        # Calculate final DAX columns
        .with_columns(
            # Buy Price = DIVIDE(Cum_Buy_Val, Cum_Buy_Qty, 0)
            pl.when(pl.col("Cum_Buy_Qty").is_null() | (pl.col("Cum_Buy_Qty") == 0))
            .then(0.0)
            .otherwise(pl.col("Cum_Buy_Val") / pl.col("Cum_Buy_Qty"))
            .alias("Buy Price")
        )
        .with_columns(
            [
                (pl.col("Quantity") * pl.col("Buy Price")).alias("Buy Value"),
                (pl.col("Sell Price") - pl.col("Buy Price")).alias("Unit P/L"),
            ]
        )
        .with_columns((pl.col("Unit P/L") * pl.col("Quantity")).alias("Total P/L"))
        # Keep only required columns
        .select(
            [
                "ISIN",
                "Instrument name",
                "Date",
                "Quantity",
                "Sell Price",
                "Sell Value",
                "Buy Price",
                "Buy Value",
                "Unit P/L",
                "Total P/L",
            ]
        )
    )

    return df_final


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
        .select(["S_NO", "MODIFY_DATE", "UID", "CATEGORY_NAME", "ORDER_SEQUENCE"])
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
        .select(["S_NO", "MODIFY_DATE", "UID", "CATEGORY_NAME", "ORDER_SEQUENCE", "CATEGORY_ID"])
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
        .select(["S_NO", "MODIFY_DATE", "UID", "CATEGORY_NAME", "ORDER_SEQUENCE"])
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
        .select(["S_NO", "MODIFY_DATE", "UID", "CATEGORY_NAME", "ORDER_SEQUENCE", "CATEGORY_ID"])
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
        .select(["DEVICE_ID", "UID", "USE_TIME", "ASSET_GROUP", "TYPE", "ORDER_SEQUENCE"])
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


def transform_d_investment_benchmark_master(csv_path: str) -> pl.LazyFrame:
    """Executes the PQ logic for the Benchmark Master table."""

    # Enforce strict string types as defined in your Power Query
    schema_overrides = {
        "ID": pl.String,
        "Benchmark_Name": pl.String,
        "yF_Ticker": pl.String,
        "Currency": pl.String,
    }

    df_lazy = pl.scan_csv(csv_path, schema_overrides=schema_overrides)

    return df_lazy


def transform_d_tax_rates(csv_path: str) -> pl.LazyFrame:
    """Executes the PQ logic for the Tax Rates table."""

    # We use schema overrides to strictly enforce the types from your PQ logic.
    # We map PQ Percentage.Type -> pl.Float64, and PQ type date -> pl.Date.
    schema_overrides = {
        "FY": pl.String,
        "FY_Start_Date": pl.Date,
        "FY_End_Date": pl.Date,
        "Debt_MF_Cutoff_Date": pl.Date,
        "Equity_Listed_LTCG": pl.Float64,
        "Equity_Listed_STCG": pl.Float64,
        "Equity_Unlisted_LTCG": pl.Float64,
        "Equity_Unlisted_STCG": pl.Float64,
        "Gold_LTCG": pl.Float64,
        "Gold_STCG": pl.Float64,
        "Debt_MF_Pre_Cutoff_LTCG": pl.Float64,
        "Debt_MF_Pre_Cutoff_STCG": pl.Float64,
        "Debt_MF_Post_Cutoff_LTCG": pl.Float64,
        "Debt_MF_Post_Cutoff_STCG": pl.Float64,
        "Other_Debt_LTCG": pl.Float64,
        "Other_Debt_STCG": pl.Float64,
        "Default_LTCG": pl.Float64,
        "Default_STCG": pl.Float64,
        "Equity_LTCG_Exemption": pl.Int64,
        "Remarks": pl.String,
    }

    # try_parse_dates=True tells Polars to automatically parse 'YYYY-MM-DD' strings
    # into native Date objects based on the schema overrides.
    df_lazy = pl.scan_csv(csv_path, schema_overrides=schema_overrides, try_parse_dates=True)

    return df_lazy


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
            .then(pl.col("LOCAL_AMOUNT") * -1)
            .otherwise(pl.col("LOCAL_AMOUNT"))
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


def transform_f_opening_balances(csv_path: str, column_mapping: dict[str, str]) -> pl.LazyFrame:
    """Executes the PQ logic for Opening Balances."""

    # We use try_parse_dates so Polars automatically attempts to parse ZTXDATESTR
    df_lazy = pl.scan_csv(csv_path, try_parse_dates=True)

    df_transformed = (
        df_lazy
        # Apply the dynamic column mapping first
        .rename(column_mapping)
        # Select the columns immediately to minimize memory footprint
        .select(
            [
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


def get_stg_calendar_ref(
    f_inc_lazy: pl.LazyFrame,
    f_exp_lazy: pl.LazyFrame,
    f_trans_lazy: pl.LazyFrame,
    f_opbal_lazy: pl.LazyFrame,
    stg_mkt_lazy: pl.LazyFrame,
    f_pur_lazy: pl.LazyFrame,
    f_sale_lazy: pl.LazyFrame,
) -> tuple[date, date]:
    """
    Translates stg_CalendarRef.
    Unions the DATE columns from all 7 fact tables to find the min and max dates.
    """

    def safe_date_cast(col_name: str) -> pl.Expr:
        return pl.coalesce(
            [
                # 1. If it's already a Date or Datetime, this cast succeeds
                pl.col(col_name).cast(pl.Date, strict=False),
                # 2. If it's a standard string Date ("YYYY-MM-DD")
                pl.col(col_name).cast(pl.String).str.to_date("%Y-%m-%d", strict=False),
                # 3. If it's a standard string Date ("DD-MM-YYYY")
                pl.col(col_name).cast(pl.String).str.to_date("%d-%m-%Y", strict=False),
                # 4. If it's a string Datetime ("YYYY-MM-DD HH:MM:SS")
                pl.col(col_name)
                .cast(pl.String)
                .str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False)
                .dt.date(),
            ]
        ).alias("DATE")

    df_union = pl.concat(
        [
            f_inc_lazy.select(safe_date_cast("DATE")),
            f_exp_lazy.select(safe_date_cast("DATE")),
            f_trans_lazy.select(safe_date_cast("DATE")),
            f_opbal_lazy.select(safe_date_cast("ZTXDATESTR")),
            stg_mkt_lazy.select(safe_date_cast("Date")),
            f_pur_lazy.select(safe_date_cast("Date")),
            f_sale_lazy.select(safe_date_cast("Date")),
        ]
    ).unique()

    # We collect this immediately because we need the scalar min/max values to generate the calendar range
    df_collected = df_union.drop_nulls().collect()

    min_date = df_collected["DATE"].min()
    max_date = df_collected["DATE"].max()

    from typing import cast

    return cast(date, min_date), cast(date, max_date)


def transform_d_calendar(min_date: date, max_date: date) -> pl.LazyFrame:
    """
    Generates all 40 requested time-intelligence columns for the Calendar Master.
    Assumes an April 1st - March 31st Financial Year.
    """
    start_date = min_date.replace(day=1) - relativedelta(months=1)
    last_day_of_max_month = calendar.monthrange(max_date.year, max_date.month)[1]
    end_date = max_date.replace(day=last_day_of_max_month)

    df_cal = pl.DataFrame({"Date": pl.date_range(start_date, end_date, "1d", eager=True)}).lazy()

    df_transformed = (
        df_cal
        # Block 1: Base Numeric and String Extractions
        .with_columns(
            [
                pl.col("Date").dt.day().alias("Day"),
                pl.col("Date").dt.strftime("%A").alias("Day Name"),
                pl.col("Date").dt.strftime("%a").alias("Day Name Short"),
                pl.col("Date").dt.ordinal_day().alias("Day Ordinal"),
                pl.col("Date").dt.weekday().alias("Weekday"),
                pl.col("Date").dt.week().alias("Week"),
                pl.col("Date").dt.month().alias("Month"),
                pl.col("Date").dt.strftime("%B").alias("Month Name"),
                pl.col("Date").dt.strftime("%b").alias("Month Name Short"),
                pl.col("Date").dt.quarter().alias("Quarter"),
                pl.col("Date").dt.year().alias("Year"),
                pl.col("Date").dt.offset_by("-3mo").alias("FY_Shift"),
                pl.col("Date").dt.truncate("1mo").alias("Start of Month"),
                pl.col("Date").dt.month_end().alias("End of Month"),
                pl.col("Date").dt.truncate("1w").alias("Start of Week"),
            ]
        )
        # Block 2: Dependent Dates (Quarters and Weeks)
        .with_columns(
            [
                pl.col("Start of Week").dt.offset_by("6d").alias("End of Week"),
                (
                    pl.col("Year").cast(pl.String)
                    + "-"
                    + ((pl.col("Quarter") - 1) * 3 + 1).cast(pl.String).str.pad_start(2, "0")
                    + "-01"
                )
                .str.to_date("%Y-%m-%d", strict=False)
                .alias("Start of Quarter"),
            ]
        )
        # Block 3a: Dependent End of Quarter and FY Extracts
        .with_columns(
            [
                pl.col("Start of Quarter")
                .dt.offset_by("3mo")
                .dt.offset_by("-1d")
                .alias("End of Quarter"),
                pl.col("FY_Shift").dt.year().alias("FY Year"),
                pl.col("FY_Shift").dt.month().alias("FY Month"),
                pl.col("FY_Shift").dt.quarter().alias("FY Quarter"),
                pl.col("Week").alias("Week Ordinal"),
            ]
        )
        # Block 3b: SPLIT HERE - Safe to reference End of Quarter now
        .with_columns(
            [
                pl.col("Start of Month").alias("FY Start of Month"),
                pl.col("End of Month").alias("FY End of Month"),
                pl.col("Start of Quarter").alias("FY Start of Quarter"),
                pl.col("End of Quarter").alias("FY End of Quarter"),
            ]
        )
        # Block 4: String Concat and Labels
        .with_columns(
            [
                (pl.lit("Day ") + pl.col("Day Ordinal").cast(pl.String)).alias("Day Ordinal Name"),
                (pl.lit("Wk ") + pl.col("Week Ordinal").cast(pl.String)).alias("Week Ordinal Name"),
                (pl.lit("Q") + pl.col("Quarter").cast(pl.String)).alias("Quarter Name"),
                (pl.lit("Q") + pl.col("FY Quarter").cast(pl.String)).alias("FY Quarter Name"),
                (
                    pl.lit("FY")
                    + pl.col("FY Year").cast(pl.String).str.slice(2, 2)
                    + "-"
                    + (pl.col("FY Year") + 1).cast(pl.String).str.slice(2, 2)
                ).alias("Financial Year"),
                pl.col("Date").dt.strftime("%B %Y").alias("Month - Year"),
                pl.col("Date").dt.strftime("%b-%y").alias("Short Month - Year"),
                pl.col("Date").dt.strftime("%b '%y").alias("V Short Month - Year"),
                (pl.lit("Week ") + pl.col("Week").cast(pl.String)).alias("Week Name"),
                pl.when(pl.col("Weekday").is_in([6, 7])).then(1).otherwise(0).alias("IS_WEEKEND"),
            ]
        )
        # Block 5: Final Cross-Concatenations
        .with_columns(
            [
                (pl.col("Quarter Name") + "-" + pl.col("Year").cast(pl.String)).alias(
                    "Quarter - Year"
                ),
                (pl.col("FY Quarter Name") + "-" + pl.col("Financial Year")).alias(
                    "FY Quarter - Year"
                ),
                (
                    pl.lit("W")
                    + pl.col("Week").cast(pl.String)
                    + "-"
                    + pl.col("Year").cast(pl.String)
                ).alias("Week - Year"),
                (pl.col("Week Name") + " - " + pl.col("Year").cast(pl.String)).alias(
                    "Week Name - Year"
                ),
            ]
        )
        # Clean up
        .drop("FY_Shift")
        .select(
            [
                "Date",
                "Day",
                "Day Name",
                "Day Name Short",
                "Day Ordinal",
                "Day Ordinal Name",
                "Weekday",
                "Week",
                "Week Ordinal",
                "Week Ordinal Name",
                "Month",
                "Month Name",
                "Month Name Short",
                "Quarter",
                "Quarter Name",
                "Year",
                "FY Month",
                "FY Year",
                "Start of Month",
                "FY Start of Month",
                "FY Quarter",
                "FY Quarter Name",
                "Month - Year",
                "Short Month - Year",
                "Quarter - Year",
                "FY Quarter - Year",
                "Financial Year",
                "Start of Quarter",
                "FY Start of Quarter",
                "End of Month",
                "FY End of Month",
                "End of Quarter",
                "FY End of Quarter",
                "V Short Month - Year",
                "Week - Year",
                "Week Name",
                "Start of Week",
                "End of Week",
                "Week Name - Year",
                "IS_WEEKEND",
            ]
        )
    )

    return df_transformed


def transform_stg_investment_market_data(refs: list[pl.LazyFrame]) -> pl.LazyFrame:
    """
    Translates DAX UNION + SUMMARIZE.
    Concatenates the aggregated tables and selects the final columns.
    """

    # Ensure both frames have the exact same columns in the exact same order for UNION
    select_cols = [
        "Date",
        "ISIN",
        "Quantity",
        "Closing Price",
        "Buy Price",
        "Closing Value",
        "Buy Value",
        "Unit P/L",
        "Total P/L",
    ]

    df_union = pl.concat([ref.select(select_cols) for ref in refs], how="vertical")

    # The outer SUMMARIZE in DAX acts as a distinct/group by on the unioned result.
    df_final = (
        df_union.group_by(select_cols)
        .agg([])
        .sort(["ISIN", "Date", "Quantity", "Buy Price", "Closing Price"])
    )

    return df_final


def get_f_tf_investment_purchase_data(refs: list[pl.LazyFrame]) -> pl.LazyFrame:
    """Translates DAX UNION + SUMMARIZE for Purchases."""
    select_cols = ["ISIN", "Date", "Price", "Quantity", "Value"]

    df_union = pl.concat([ref.select(select_cols) for ref in refs], how="vertical")

    df_final = (
        df_union.group_by(select_cols)
        .agg([])  # SUMMARIZE (distinct)
        .sort(["ISIN", "Date", "Quantity", "Price"])
        # DAX calculated col
        .with_columns(pl.lit("INR_INR").alias("CURRENCY_ID"))
    )
    return df_final


def get_f_tf_investment_sale_data(refs: list[pl.LazyFrame]) -> pl.LazyFrame:
    """Translates DAX UNION + SUMMARIZE for Sales."""
    select_cols = [
        "ISIN",
        "Date",
        "Quantity",
        "Sell Price",
        "Sell Value",
        "Buy Price",
        "Buy Value",
        "Unit P/L",
        "Total P/L",
    ]

    df_union = pl.concat([ref.select(select_cols) for ref in refs], how="vertical")

    df_final = (
        df_union.group_by(select_cols)
        .agg([])  # SUMMARIZE (distinct)
        .sort(["ISIN", "Date", "Quantity", "Sell Price"])
        .with_columns(pl.lit("INR_INR").alias("CURRENCY_ID"))
    )
    return df_final


def get_d_tf_investment_master(
    master_refs: list[pl.LazyFrame], stg_benchmark_mapping_lazy: pl.LazyFrame
) -> pl.LazyFrame:
    """
    Translates d_tf_InvestmentMaster.
    Unions the References into a single distinct dimension table,
    then joins the Benchmark Mapping to pull in Sector, Industry, Tax flags, etc.
    """

    # Define common schema to ensure clean union
    select_cols = [
        "ISIN",
        "INSTRUMENT_NAME",
        "INSTRUMENT_HOUSE",
        "INSTRUMENT_CLASS",
        "INSTRUMENT_TYPE",
        "INSTRUMENT_SUBTYPE",
        "CATEGORY_ID",
    ]

    # Union the References
    df_master_union = pl.concat([ref.select(select_cols) for ref in master_refs]).unique(
        subset=["ISIN"]
    )  # Ensure one row per ISIN

    # Replicate DAX LOOKUPVALUE by joining the Benchmark Mapping
    df_final = df_master_union.join(stg_benchmark_mapping_lazy, on="ISIN", how="left").select(
        [
            "ISIN",
            "INSTRUMENT_NAME",
            "INSTRUMENT_HOUSE",
            "INSTRUMENT_CLASS",
            "INSTRUMENT_TYPE",
            "INSTRUMENT_SUBTYPE",
            "CATEGORY_ID",
            # Rename columns to match DAX output if needed
            pl.col("Sector").alias("SECTOR"),
            pl.col("Industry").alias("INDUSTRY"),
            pl.col("Benchmark_ID").alias("BENCHMARK_ID"),
            # Ensure these match the actual headers in BENCHMARK_MAPPING.csv
            pl.col("Tax_Instrument_Type").alias("TAX_TYPE"),
            pl.col("Tax_Instrument_Subtype").alias("TAX_SUBTYPE"),
        ]
    )

    return df_final
